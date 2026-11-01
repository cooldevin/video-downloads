import os
import re
import sys
import subprocess
import urllib.request
from pathlib import Path
from typing import Tuple, Optional

def format_bytes(size: Optional[float]) -> str:
    if size is None or size <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"

def format_seconds(seconds: Optional[int]) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def open_in_explorer(target_path: str):
    """Open Windows Explorer and highlight the file or open directory"""
    path = Path(target_path)
    if not path.exists():
        if path.parent.exists():
            path = path.parent
        else:
            return False
            
    if sys.platform == "win32":
        if path.is_file():
            subprocess.Popen(f'explorer /select,"{str(path)}"')
        else:
            subprocess.Popen(f'explorer "{str(path)}"')
        return True
    else:
        # Cross platform fallback
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            return True
        except Exception:
            return False

def test_proxy_connection(proxy_url: str) -> Tuple[bool, str]:
    """Test whether the proxy can reach YouTube or Google"""
    if not proxy_url:
        target = "https://www.youtube.com"
        try:
            req = urllib.request.Request(target, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status < 400:
                    return True, "直连连接成功"
        except Exception as e:
            return False, f"直连失败: {str(e)}"
    else:
        try:
            proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request("https://www.youtube.com", headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=8) as resp:
                if resp.status < 400:
                    return True, "代理连接 YouTube 成功"
        except Exception as e:
            return False, f"代理测试失败: {str(e)}"
    return False, "连接超时或无响应"

def clean_youtube_url(url: str) -> str:
    return url.strip()
