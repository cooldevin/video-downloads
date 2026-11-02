import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"


def get_system_downloads_dir() -> Path:
    """Get the standard OS Downloads folder (with Windows registry support)."""
    if os.name == 'nt':
        try:
            import winreg
            sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                val, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
                p = Path(os.path.expandvars(val))
                if p.exists():
                    return p
        except Exception:
            pass
    fallback = Path.home() / "Downloads"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DEFAULT_DOWNLOAD_DIR = get_system_downloads_dir()


class AppConfig(BaseModel):
    download_dir: str = str(DEFAULT_DOWNLOAD_DIR)
    max_concurrent: int = 3
    default_quality: str = "best"  # "best", "1080p", "720p", "480p", "audio"
    default_format: str = "mp4"    # "mp4", "mkv", "mp3", "m4a"
    download_subtitles: bool = False
    embed_thumbnail: bool = True
    cookies_file: str = ""
    cookies_from_browser: str = ""  # "chrome", "edge", "firefox", "brave", etc.

    @property
    def ffmpeg_location(self) -> str:
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if os.path.exists(exe):
                return exe
        except Exception:
            pass
        return "ffmpeg"


def load_config() -> AppConfig:
    legacy_project_downloads = BASE_DIR / "downloads"
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # If currently pointing to old in-project downloads, migrate to system Downloads
                if data.get("download_dir") == str(legacy_project_downloads):
                    data["download_dir"] = str(DEFAULT_DOWNLOAD_DIR)
                cfg = AppConfig(**data)
                save_config(cfg)
                return cfg
        except Exception as e:
            print(f"[Config] Error loading config.json, using defaults: {e}")
    cfg = AppConfig()
    save_config(cfg)
    return cfg


def save_config(cfg: AppConfig):
    # Ensure download directory exists
    Path(cfg.download_dir).mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, indent=2, ensure_ascii=False)


# Initialize global config
config = load_config()
Path(config.download_dir).mkdir(parents=True, exist_ok=True)
