"""
Authentication manager for YouTube Downloader.
Provides an isolated, dedicated browser window for one-click YouTube login,
and extracts cookies to root cookies.txt without interfering with existing browsers.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Supported browser executable candidates
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

ROOT_DIR = Path(__file__).resolve().parent.parent
COOKIES_TXT_PATH = ROOT_DIR / "cookies.txt"
LOGIN_PROFILE_DIR = ROOT_DIR / "data" / "login_profile"


def find_browser() -> Tuple[str, Optional[str]]:
    """Return ('edge' | 'chrome', exe_path) or ('', None) if not found."""
    for p in EDGE_PATHS:
        if os.path.exists(p):
            return "edge", p
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return "chrome", p
    return "", None


def open_login_window() -> Dict[str, Any]:
    """Launch an isolated mini-app browser window for YouTube login."""
    b_name, exe_path = find_browser()
    if not exe_path:
        return {
            "success": False,
            "message": "未在系统中找到 Microsoft Edge 或 Google Chrome 浏览器"
        }

    LOGIN_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    target_url = "https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com"

    cmd = [
        exe_path,
        f"--user-data-dir={LOGIN_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--app={target_url}"
    ]

    try:
        subprocess.Popen(cmd)
        return {
            "success": True,
            "browser": b_name,
            "message": "已打开独立登录窗口，请在弹出的窗口中登录您的 Google / YouTube 账号。登录完成后请关闭该窗口并点击【完成并保存】。"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"启动登录窗口失败: {str(e)}"
        }


def extract_and_save_cookies() -> Dict[str, Any]:
    """Extract cookies from the isolated login profile and save to root cookies.txt."""
    b_name, _ = find_browser()
    if not b_name:
        b_name = "edge"

    default_profile = LOGIN_PROFILE_DIR / "Default"
    profile_target = default_profile if default_profile.exists() else LOGIN_PROFILE_DIR

    from yt_dlp.cookies import extract_cookies_from_browser

    try:
        # Extract cookies from custom isolated profile
        jar = extract_cookies_from_browser(b_name, str(profile_target))
        if not jar or len(jar) == 0:
            # Fallback try root profile
            if profile_target != LOGIN_PROFILE_DIR:
                jar = extract_cookies_from_browser(b_name, str(LOGIN_PROFILE_DIR))

        cookie_count = len(jar) if jar else 0
        if cookie_count == 0:
            return {
                "success": False,
                "message": "未在独立登录配置中检测到已登录的 Cookie，请确保您在弹出的窗口中已完成登录并已关闭窗口。"
            }

        # Save to cookies.txt
        jar.filename = str(COOKIES_TXT_PATH)
        jar.save(ignore_discard=True, ignore_expires=True)

        return {
            "success": True,
            "count": cookie_count,
            "path": str(COOKIES_TXT_PATH),
            "message": f"成功提取并保存 {cookie_count} 个安全凭据！专属凭证已生效，后续所有下载将自动免除人机验证。"
        }
    except Exception as e:
        err_msg = str(e)
        if "Could not copy" in err_msg or "Permission denied" in err_msg:
            return {
                "success": False,
                "message": "独立登录窗口似乎尚未完全关闭，请先关闭刚才弹出的登录小窗口，然后再次点击保存。"
            }
        return {
            "success": False,
            "message": f"提取凭据失败: {err_msg}"
        }


def get_auth_status() -> Dict[str, Any]:
    """Check whether valid cookies.txt exists."""
    has_cookies = COOKIES_TXT_PATH.exists() and COOKIES_TXT_PATH.stat().st_size > 50
    mtime_str = ""
    file_size_str = ""
    if has_cookies:
        try:
            stat = COOKIES_TXT_PATH.stat()
            file_size_str = f"{round(stat.st_size / 1024, 1)} KB"
            mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        except Exception:
            pass

    return {
        "authenticated": has_cookies,
        "path": str(COOKIES_TXT_PATH) if has_cookies else "",
        "size": file_size_str,
        "updated_at": mtime_str
    }


def clear_auth() -> Dict[str, Any]:
    """Remove root cookies.txt."""
    if COOKIES_TXT_PATH.exists():
        try:
            COOKIES_TXT_PATH.unlink()
            return {"success": True, "message": "已清除保存的登录凭据"}
        except Exception as e:
            return {"success": False, "message": f"清除失败: {str(e)}"}
    return {"success": True, "message": "暂无需要清除的凭据"}
