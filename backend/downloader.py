import asyncio
import os
import threading
import time
import uuid
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import yt_dlp
from yt_dlp.utils import DownloadCancelled

from backend.config import config, AppConfig
from backend.utils import format_bytes, format_seconds

def get_max_folder_index(download_dir: str) -> int:
    """Scan directory to find the highest existing index prefix (e.g. 001, 002)"""
    max_idx = 0
    p = Path(download_dir)
    if not p.exists():
        return 0
    for f in p.iterdir():
        if f.is_file():
            m = re.match(r"^(\d{1,4})[\.\-\_\s]", f.name)
            if m:
                try:
                    num = int(m.group(1))
                    if num > max_idx:
                        max_idx = num
                except ValueError:
                    pass
    return max_idx

def scan_downloaded_files(download_dir: str) -> List[Dict[str, Any]]:
    """Scan and parse all video/audio files in the folder with their recorded sequence index"""
    files = []
    p = Path(download_dir)
    if not p.exists():
        return []
    for f in p.iterdir():
        if f.is_file() and f.suffix.lower() in [".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".wav"]:
            m = re.match(r"^(\d{1,4})[\.\-\_\s]+(.*)", f.name)
            index = int(m.group(1)) if m else None
            stat = f.stat()
            files.append({
                "index": index,
                "index_str": f"{index:03d}" if index is not None else "--",
                "filename": f.name,
                "file_path": str(f.resolve()),
                "size": stat.st_size,
                "size_str": format_bytes(stat.st_size),
                "created_at": stat.st_mtime,
                "ext": f.suffix.lower().replace(".", "")
            })
    # Sort by index (ascending), unindexed at the end
    files.sort(key=lambda x: (0 if x["index"] is not None else 1, x["index"] if x["index"] is not None else 0, -x["created_at"]))
    return files


class DownloadTask:
    def __init__(self, url: str, index: int = 1, quality: str = "best", container_format: str = "mp4", custom_dir: Optional[str] = None):
        self.id = str(uuid.uuid4())[:8]
        self.url = url
        self.index = index
        self.quality = quality
        self.format = container_format
        self.download_dir = custom_dir or config.download_dir
        
        self.title = "正在解析视频信息..."
        self.uploader = ""
        self.thumbnail = ""
        self.duration = 0
        self.duration_str = "--:--"
        self.status = "queued"  # queued, extracting, downloading, processing, completed, failed, cancelled
        self.percent = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed = 0.0
        self.speed_str = "0 KB/s"
        self.eta = 0
        self.eta_str = "--:--"
        self.file_path = ""
        self.error_message = ""
        self.created_at = time.time()
        self.updated_at = time.time()
        
        self._cancel_requested = False
        self._ydl_instance: Optional[yt_dlp.YoutubeDL] = None

    def cancel(self):
        self._cancel_requested = True
        self.status = "cancelled"
        self.error_message = "下载已取消"
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "index": self.index,
            "index_str": f"{self.index:03d}",
            "quality": self.quality,
            "format": self.format,
            "title": self.title,
            "uploader": self.uploader,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "duration_str": self.duration_str,
            "status": self.status,
            "percent": round(self.percent, 1),
            "downloaded_bytes": self.downloaded_bytes,
            "downloaded_str": format_bytes(self.downloaded_bytes),
            "total_bytes": self.total_bytes,
            "total_str": format_bytes(self.total_bytes),
            "speed": self.speed,
            "speed_str": self.speed_str,
            "eta": self.eta,
            "eta_str": self.eta_str,
            "file_path": self.file_path,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "download_dir": self.download_dir,
        }


class DownloadManager:
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = True
        self._start_worker()

    def _start_worker(self):
        self._worker_thread = threading.Thread(target=self._queue_loop, daemon=True)
        self._worker_thread.start()

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]):
        self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], None]):
        if callback in self.listeners:
            self.listeners.remove(callback)

    def broadcast_update(self, task: DownloadTask):
        task.updated_at = time.time()
        data = task.to_dict()
        for cb in list(self.listeners):
            try:
                cb(data)
            except Exception:
                pass

    def get_next_index(self, target_dir: Optional[str] = None) -> int:
        target_dir = target_dir or config.download_dir
        with self._lock:
            existing_task_indices = [t.index for t in self.tasks.values()]
        folder_max = get_max_folder_index(target_dir)
        all_indices = existing_task_indices + [folder_max] + [0]
        return max(all_indices) + 1

    def add_task(self, url: str, index: Optional[int] = None, quality: Optional[str] = None, container_format: Optional[str] = None, custom_dir: Optional[str] = None) -> DownloadTask:
        quality = quality or config.default_quality
        container_format = container_format or config.default_format
        actual_dir = custom_dir or config.download_dir
        
        if index is None or index <= 0:
            index = self.get_next_index(actual_dir)

        task = DownloadTask(url=url, index=index, quality=quality, container_format=container_format, custom_dir=actual_dir)
        with self._lock:
            self.tasks[task.id] = task
        self.broadcast_update(task)
        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            # Sort by sequence index (or created_at)
            return [t.to_dict() for t in sorted(self.tasks.values(), key=lambda x: (x.index, x.created_at))]

    def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task and task.status in ["queued", "extracting", "downloading", "processing"]:
            task.cancel()
            self.broadcast_update(task)
            return True
        return False

    def retry_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task and task.status in ["failed", "cancelled"]:
            task.status = "queued"
            task.percent = 0.0
            task.downloaded_bytes = 0
            task.total_bytes = 0
            task.error_message = ""
            task._cancel_requested = False
            self.broadcast_update(task)
            return True
        return False

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status in ["downloading", "extracting"]:
                    task.cancel()
                del self.tasks[task_id]
                return True
        return False

    def clear_completed(self):
        with self._lock:
            to_remove = [tid for tid, t in self.tasks.items() if t.status in ["completed", "failed", "cancelled"]]
            for tid in to_remove:
                del self.tasks[tid]

    def _queue_loop(self):
        active_threads: Dict[str, threading.Thread] = {}
        
        while self._running:
            # Clean up finished threads
            finished = [tid for tid, th in active_threads.items() if not th.is_alive()]
            for tid in finished:
                del active_threads[tid]

            # Check how many slots available
            slots_available = config.max_concurrent - len(active_threads)
            if slots_available > 0:
                with self._lock:
                    queued_tasks = [t for t in self.tasks.values() if t.status == "queued"]
                
                # Sort by index to download sequentially in order
                queued_tasks.sort(key=lambda t: (t.index, t.created_at))

                for task in queued_tasks[:slots_available]:
                    th = threading.Thread(target=self._run_download, args=(task,), daemon=True)
                    active_threads[task.id] = th
                    th.start()

            time.sleep(0.5)

    def _run_download(self, task: DownloadTask):
        try:
            task.status = "extracting"
            self.broadcast_update(task)

            # Build format selector
            is_audio_only = task.format in ["mp3", "m4a", "wav"] or task.quality == "audio"
            
            if is_audio_only:
                format_expr = "bestaudio/best"
            elif task.quality == "4k" or task.quality == "2160p":
                format_expr = "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
            elif task.quality == "1080p":
                format_expr = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            elif task.quality == "720p":
                format_expr = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif task.quality == "480p":
                format_expr = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            else:
                format_expr = "bestvideo+bestaudio/best"

            output_dir = Path(task.download_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Format filename with sequence number prefix: e.g. 001. VideoTitle [id].ext
            prefix = f"{task.index:03d}. "
            outtmpl = str(output_dir / f"{prefix}%(title).150B [%(id)s].%(ext)s")

            def progress_hook(d):
                if task._cancel_requested:
                    raise DownloadCancelled("User cancelled")
                
                status = d.get("status")
                if status == "downloading":
                    task.status = "downloading"
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes") or 0
                    speed = d.get("speed") or 0
                    eta = d.get("eta") or 0
                    
                    task.total_bytes = total
                    task.downloaded_bytes = downloaded
                    task.speed = speed
                    task.speed_str = f"{format_bytes(speed)}/s" if speed else "0 KB/s"
                    task.eta = eta
                    task.eta_str = format_seconds(eta)
                    
                    if total > 0:
                        task.percent = min(100.0, (downloaded / total) * 100.0)
                    elif d.get("_percent_str"):
                        try:
                            # clean ansi color codes
                            clean_p = re.sub(r'\x1b\[[0-9;]*m', '', d["_percent_str"]).replace("%", "").strip()
                            task.percent = float(clean_p)
                        except Exception:
                            pass
                    
                    self.broadcast_update(task)
                    
                elif status == "finished":
                    task.status = "processing"
                    task.percent = 100.0
                    task.speed_str = "转码混流中..."
                    self.broadcast_update(task)

            postprocessors = []
            if is_audio_only:
                postprocessors.append({
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3' if task.format == 'mp3' else 'm4a',
                    'preferredquality': '320',
                })
            else:
                postprocessors.append({
                    'key': 'FFmpegVideoRemuxer',
                    'preferedformat': task.format if task.format in ['mp4', 'mkv'] else 'mp4'
                })

            ydl_opts: Dict[str, Any] = {
                'format': format_expr,
                'outtmpl': outtmpl,
                'progress_hooks': [progress_hook],
                'ffmpeg_location': config.ffmpeg_location,
                'noplaylist': True,  # Individual task mode; playlist is expanded beforehand
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'retries': 5,
                'socket_timeout': 30,
            }

            if config.proxy:
                ydl_opts['proxy'] = config.proxy

            if config.cookies_file and os.path.exists(config.cookies_file):
                ydl_opts['cookiefile'] = config.cookies_file

            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                task._ydl_instance = ydl
                # First extract info
                info = ydl.extract_info(task.url, download=False)
                if not info:
                    raise Exception("无法解析视频信息")
                
                task.title = info.get("title", task.url)
                task.uploader = info.get("uploader", info.get("channel", "YouTube"))
                task.thumbnail = info.get("thumbnail", "")
                task.duration = info.get("duration", 0)
                task.duration_str = format_seconds(task.duration)
                task.status = "downloading"
                self.broadcast_update(task)

                # Now download
                ydl.download([task.url])

                # Locate finished file
                expected_filename = ydl.prepare_filename(info)
                if is_audio_only:
                    target_ext = 'mp3' if task.format == 'mp3' else 'm4a'
                    expected_filename = str(Path(expected_filename).with_suffix(f".{target_ext}"))
                
                # Verify file existence or fallback search in download dir
                if os.path.exists(expected_filename):
                    task.file_path = expected_filename
                else:
                    # Look for file matching video id or sequence prefix
                    vid_id = info.get("id")
                    if vid_id:
                        for p in output_dir.glob(f"*{vid_id}*"):
                            if p.is_file():
                                task.file_path = str(p)
                                break
                    if not task.file_path:
                        for p in output_dir.glob(f"{prefix}*"):
                            if p.is_file():
                                task.file_path = str(p)
                                break

                task.status = "completed"
                task.percent = 100.0
                task.speed_str = "已完成"
                task.eta_str = "00:00"
                self.broadcast_update(task)

        except DownloadCancelled:
            task.status = "cancelled"
            task.error_message = "下载已取消"
            self.broadcast_update(task)
        except Exception as e:
            if task._cancel_requested:
                task.status = "cancelled"
                task.error_message = "下载已取消"
            else:
                task.status = "failed"
                task.error_message = str(e)
            self.broadcast_update(task)

    def parse_urls(self, urls: List[str], start_index: Optional[int] = None) -> List[Dict[str, Any]]:
        """Extract quick metadata from URLs, recording sequential index"""
        results = []
        ydl_opts: Dict[str, Any] = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': config.ffmpeg_location,
            'socket_timeout': 15,
        }
        if config.proxy:
            ydl_opts['proxy'] = config.proxy
        if config.cookies_file and os.path.exists(config.cookies_file):
            ydl_opts['cookiefile'] = config.cookies_file

        current_idx = start_index if (start_index and start_index > 0) else self.get_next_index()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                url = url.strip()
                if not url:
                    continue
                try:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue
                    
                    # If it's a playlist or multiple entries
                    if "entries" in info and info["entries"]:
                        entries = list(info["entries"])
                        for entry in entries:
                            if not entry:
                                continue
                            v_url = entry.get("url")
                            if v_url and not v_url.startswith("http"):
                                v_url = f"https://www.youtube.com/watch?v={v_url}"
                            
                            seq_num = current_idx
                            current_idx += 1

                            results.append({
                                "index": seq_num,
                                "index_str": f"{seq_num:03d}",
                                "url": v_url or url,
                                "title": entry.get("title", "YouTube Video"),
                                "uploader": entry.get("uploader", info.get("title", "Playlist")),
                                "duration": entry.get("duration", 0),
                                "duration_str": format_seconds(entry.get("duration", 0)),
                                "thumbnail": entry.get("thumbnail", ""),
                                "is_playlist": True,
                                "playlist_title": info.get("title", ""),
                            })
                    else:
                        seq_num = current_idx
                        current_idx += 1

                        results.append({
                            "index": seq_num,
                            "index_str": f"{seq_num:03d}",
                            "url": url,
                            "title": info.get("title", "YouTube Video"),
                            "uploader": info.get("uploader", info.get("channel", "YouTube")),
                            "duration": info.get("duration", 0),
                            "duration_str": format_seconds(info.get("duration", 0)),
                            "thumbnail": info.get("thumbnail", ""),
                            "is_playlist": False,
                        })
                except Exception as e:
                    seq_num = current_idx
                    current_idx += 1
                    results.append({
                        "index": seq_num,
                        "index_str": f"{seq_num:03d}",
                        "url": url,
                        "title": f"解析失败: {url}",
                        "error": str(e),
                        "duration_str": "--:--",
                        "thumbnail": "",
                        "is_playlist": False,
                    })
        return results


# Global singleton manager
download_manager = DownloadManager()
