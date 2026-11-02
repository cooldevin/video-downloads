import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Optional

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

def clean_youtube_url(url: str) -> str:
    return url.strip()
