import asyncio
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import config, save_config, AppConfig, BASE_DIR
from backend.downloader import download_manager, scan_downloaded_files
from backend.utils import open_in_explorer, test_proxy_connection, format_bytes

app = FastAPI(title="Bklit YouTube Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = BASE_DIR / "frontend"


class DownloadRequest(BaseModel):
    urls: List[str]
    items: Optional[List[Dict[str, Any]]] = None  # Pre-parsed items with indices
    quality: Optional[str] = "best"
    format: Optional[str] = "mp4"
    custom_dir: Optional[str] = None
    expand_playlists: Optional[bool] = True
    start_index: Optional[int] = None


class ParseRequest(BaseModel):
    urls: List[str]
    start_index: Optional[int] = None


class ConfigUpdateRequest(BaseModel):
    download_dir: Optional[str] = None
    proxy: Optional[str] = None
    max_concurrent: Optional[int] = None
    default_quality: Optional[str] = None
    default_format: Optional[str] = None
    download_subtitles: Optional[bool] = None
    cookies_file: Optional[str] = None


class TestProxyRequest(BaseModel):
    proxy: Optional[str] = ""


class OpenFileRequest(BaseModel):
    file_path: str


@app.get("/api/tasks")
def get_tasks():
    tasks = download_manager.get_all_tasks()
    stats = {
        "total": len(tasks),
        "queued": sum(1 for t in tasks if t["status"] == "queued"),
        "downloading": sum(1 for t in tasks if t["status"] in ["downloading", "extracting", "processing"]),
        "completed": sum(1 for t in tasks if t["status"] == "completed"),
        "failed": sum(1 for t in tasks if t["status"] in ["failed", "cancelled"]),
        "total_downloaded_bytes": sum(t["downloaded_bytes"] for t in tasks),
        "total_downloaded_str": format_bytes(sum(t["downloaded_bytes"] for t in tasks)),
    }
    return {"tasks": tasks, "stats": stats}


@app.get("/api/library")
def get_library():
    """Scan and list all downloaded videos on disk with their recorded sequence index"""
    files = scan_downloaded_files(config.download_dir)
    return {
        "files": files,
        "total": len(files),
        "download_dir": config.download_dir,
    }


@app.post("/api/library/renumber")
def renumber_library():
    """Renumber all existing downloaded files in the folder in chronological order with 001., 002. prefixes"""
    p = Path(config.download_dir)
    if not p.exists():
        raise HTTPException(status_code=404, detail="下载目录不存在")
    
    files = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in [".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".wav"]]
    # Sort files by creation time
    files.sort(key=lambda f: f.stat().st_mtime)
    
    renamed = 0
    for idx, f in enumerate(files, start=1):
        m = re.match(r"^(\d{1,4})[\.\-\_\s]+(.*)", f.name)
        clean_title = m.group(2) if m else f.name
        new_name = f"{idx:03d}. {clean_title}"
        if f.name != new_name:
            target = f.parent / new_name
            f.rename(target)
            renamed += 1
            
    return {"message": f"已成功为 {renamed} 个现有视频添加规范序号 (001, 002...)", "total": len(files)}


@app.post("/api/download")
async def start_downloads(req: DownloadRequest):
    created_tasks = []
    current_index = req.start_index if (req.start_index and req.start_index > 0) else download_manager.get_next_index(req.custom_dir)

    # 1. If explicit pre-parsed items are passed (from preview modal)
    if req.items and len(req.items) > 0:
        for item in req.items:
            item_url = item.get("url")
            if not item_url or item.get("error"):
                continue
            idx = item.get("index") or current_index
            t = download_manager.add_task(
                url=item_url,
                index=idx,
                quality=req.quality,
                container_format=req.format,
                custom_dir=req.custom_dir
            )
            t.title = item.get("title", t.title)
            t.thumbnail = item.get("thumbnail", "")
            t.duration = item.get("duration", 0)
            t.duration_str = item.get("duration_str", "--:--")
            t.uploader = item.get("uploader", "")
            created_tasks.append(t.to_dict())
            if not item.get("index"):
                current_index += 1
        return {"message": f"成功创建 {len(created_tasks)} 个下载任务", "tasks": created_tasks}

    # 2. Batch URLs from textarea
    cleaned_urls = [u.strip() for u in req.urls if u.strip()]
    if not cleaned_urls:
        raise HTTPException(status_code=400, detail="请至少提供一个有效的视频链接")

    for url in cleaned_urls:
        if req.expand_playlists and ("list=" in url or "/playlist" in url):
            try:
                # Async background expansion or fast flat parse
                parsed_items = await asyncio.to_thread(download_manager.parse_urls, [url], current_index)
                if parsed_items and len(parsed_items) > 1:
                    for item in parsed_items:
                        if not item.get("error"):
                            t = download_manager.add_task(
                                url=item["url"],
                                index=item.get("index") or current_index,
                                quality=req.quality,
                                container_format=req.format,
                                custom_dir=req.custom_dir
                            )
                            t.title = item.get("title", t.title)
                            t.thumbnail = item.get("thumbnail", "")
                            t.duration = item.get("duration", 0)
                            t.duration_str = item.get("duration_str", "--:--")
                            t.uploader = item.get("uploader", "")
                            created_tasks.append(t.to_dict())
                            current_index = max(current_index, (item.get("index") or current_index)) + 1
                    continue
            except Exception as e:
                print(f"[Download] Failed to expand playlist {url}: {e}")

        # Regular single video
        t = download_manager.add_task(
            url=url,
            index=current_index,
            quality=req.quality,
            container_format=req.format,
            custom_dir=req.custom_dir
        )
        created_tasks.append(t.to_dict())
        current_index += 1

    return {"message": f"成功创建 {len(created_tasks)} 个下载任务", "tasks": created_tasks}


@app.post("/api/parse")
async def parse_urls(req: ParseRequest):
    cleaned_urls = [u.strip() for u in req.urls if u.strip()]
    if not cleaned_urls:
        raise HTTPException(status_code=400, detail="链接列表为空")
    
    start_index = req.start_index if (req.start_index and req.start_index > 0) else download_manager.get_next_index()
    results = await asyncio.to_thread(download_manager.parse_urls, cleaned_urls, start_index)
    return {"items": results, "start_index": start_index}


@app.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    success = download_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或当前状态无法取消")
    return {"message": "任务已取消"}


@app.post("/api/tasks/{task_id}/retry")
def retry_task(task_id: str):
    success = download_manager.retry_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或无法重试")
    return {"message": "任务已重新加入队列"}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    success = download_manager.remove_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务已删除"}


@app.post("/api/tasks/clear-completed")
def clear_completed():
    download_manager.clear_completed()
    return {"message": "已清理所有已完成和已停止任务"}


@app.post("/api/tasks/{task_id}/open")
def open_task_file(task_id: str):
    task = download_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    target = task.file_path if (task.file_path and os.path.exists(task.file_path)) else task.download_dir
    ok = open_in_explorer(target)
    if not ok:
        raise HTTPException(status_code=500, detail="无法在系统资源管理器中打开目标")
    return {"message": "已在系统资源管理器中定位"}


@app.post("/api/open-folder")
def open_folder(request: Request):
    ok = open_in_explorer(config.download_dir)
    if not ok:
        raise HTTPException(status_code=500, detail="无法打开文件夹")
    return {"message": "已打开下载目录"}


@app.post("/api/open-file")
def open_specific_file(req: OpenFileRequest):
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    ok = open_in_explorer(req.file_path)
    if not ok:
        raise HTTPException(status_code=500, detail="无法打开文件")
    return {"message": "已在系统资源管理器中定位"}


@app.get("/api/config")
def get_config():
    return {
        "config": config.model_dump(),
        "system": {
            "ffmpeg_path": config.ffmpeg_location,
            "ffmpeg_ready": os.path.exists(config.ffmpeg_location),
            "download_dir_exists": os.path.exists(config.download_dir),
            "next_index": download_manager.get_next_index(),
        }
    }


@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    if req.download_dir is not None:
        config.download_dir = req.download_dir
    if req.proxy is not None:
        config.proxy = req.proxy.strip()
    if req.max_concurrent is not None:
        config.max_concurrent = max(1, min(10, req.max_concurrent))
    if req.default_quality is not None:
        config.default_quality = req.default_quality
    if req.default_format is not None:
        config.default_format = req.default_format
    if req.download_subtitles is not None:
        config.download_subtitles = req.download_subtitles
    if req.cookies_file is not None:
        config.cookies_file = req.cookies_file.strip()

    save_config(config)
    return {"message": "配置已保存", "config": config.model_dump()}


@app.post("/api/test-proxy")
async def test_proxy(req: TestProxyRequest):
    proxy_val = req.proxy if req.proxy is not None else config.proxy
    success, msg = await asyncio.to_thread(test_proxy_connection, proxy_val)
    return {"success": success, "message": msg}


@app.get("/api/events")
async def event_stream(request: Request):
    """Server-Sent Events endpoint to stream real-time task updates"""
    queue: asyncio.Queue = asyncio.Queue()

    def on_task_update(task_dict):
        try:
            queue.put_nowait(task_dict)
        except Exception:
            pass

    download_manager.add_listener(on_task_update)

    async def event_generator():
        try:
            yield f"event: ping\ndata: {json.dumps({'time': 'connected'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    task_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"event: task_update\ndata: {json.dumps(task_data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        finally:
            download_manager.remove_listener(on_task_update)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Mount static frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")
