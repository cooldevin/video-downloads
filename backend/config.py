import json
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "downloads"

class AppConfig(BaseModel):
    download_dir: str = str(DEFAULT_DOWNLOAD_DIR)
    proxy: str = ""  # e.g., "http://127.0.0.1:7890" or empty
    max_concurrent: int = 3
    default_quality: str = "best"  # "best", "1080p", "720p", "480p", "audio"
    default_format: str = "mp4"    # "mp4", "mkv", "mp3", "m4a"
    download_subtitles: bool = False
    embed_thumbnail: bool = True
    cookies_file: str = ""

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
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AppConfig(**data)
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
