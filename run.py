import sys
import time
import socket
import webbrowser
import threading
from pathlib import Path

# Ensure root directory is in python path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from backend.config import config

def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def find_available_port(host: str, default_port: int = 8000) -> int:
    port = default_port
    while port < default_port + 20:
        if not is_port_in_use(host, port):
            return port
        port += 1
    return default_port

def open_browser_delayed(url: str, delay: float = 1.0):
    time.sleep(delay)
    print(f"\n[Bklit Downloader] 正在打开浏览器: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    host = "127.0.0.1"
    port = find_available_port(host, 8000)
    url = f"http://{host}:{port}"

    print("=" * 60)
    print("  YouTube 批量视频下载工具 - Bklit UI 版")
    print(f"  服务地址: {url}")
    print(f"  保存目录: {config.download_dir}")
    print(f"  FFmpeg 路径: {config.ffmpeg_location}")
    if config.proxy:
        print(f"  代理设置: {config.proxy}")
    else:
        print("  代理设置: 直连 (如需下载 YouTube 请在界面设置中配置代理)")
    print("=" * 60)

    # Launch browser automatically
    threading.Thread(target=open_browser_delayed, args=(url,), daemon=True).start()

    # Start FastAPI / Uvicorn Server
    uvicorn.run("backend.app:app", host=host, port=port, log_level="info")
