# YouTube 批量视频下载工具 (Bklit UI 版)

一款专为 YouTube 批量视频下载与音频提取打造的高颜值、高性能下载工具，前端界面深度融合 [Bklit UI](https://bklit.com/) 现代设计规范。

---

## ✨ 核心特性

- 🎨 **Bklit UI 优雅现代设计**：
  - 遵循 [bklit.com](https://bklit.com/docs/installation) 的网格版式、极简毛玻璃顶栏、圆角设计与微交互质感。
  - 原生暗色 / 亮色双主题支持，状态持久化保存。
  - 侧边栏式多维筛选：按任务状态（下载中、等待中、已完成、失败）与媒体类型（视频 / 纯音频）快速分类。

- ⚡ **批量并发与高画质支持**：
  - 支持多行 YouTube 链接一次性批量投递，一键开始批量下载。
  - 支持 **4K (2160p) / 1080p FHD / 720p HD** 自动画质选择。
  - 支持 **纯音频提取**：无损封装为 MP3 (320kbps) 或 M4A。
  - 支持 YouTube 播放列表（Playlist）自动展开为独立子任务。
  - 队列并发控制：可自定义 1~10 线程并发下载。

- 🔢 **智能序号编排与媒体库索引**：
  - 下载文件自动添加规范序号前缀（如 `001. 视频标题 [id].mp4`）。
  - 内置已下载媒体库扫描与智能续编，新下载任务无缝衔接序号，支持一键标准化规整已有文件。

- 🔌 **开箱即用，免手动配置 FFmpeg**：
  - 自动集成独立 FFmpeg 二进制，全自动进行音视频流合并（Muxing）与转码封装。

- 🌐 **代理支持与一键连通性测试**：
  - 支持 HTTP / SOCKS5 代理（如 Clash 7890、v2rayN 10808 等），提供一键预设与实时连通性探测。

- 📂 **深度系统集成**：
  - 支持一键在 Windows 资源管理器中打开下载目录或高亮定位已下载完成的音视频文件。
  - 基于 Server-Sent Events (SSE) 的实时双向进度推送，百分比、实时下载速度与剩余预估时间一目了然。

---

## 🚀 快速启动

### 1. 运行工具
在项目根目录下执行以下命令：
```powershell
python run.py
```
服务启动后将自动在默认浏览器中打开：`http://127.0.0.1:8000`

---

## 🛠️ 技术栈

- **后端**：Python + FastAPI + Uvicorn + yt-dlp + imageio-ffmpeg (FFmpeg v7.1)
- **前端**：原生 Vanilla JS + 本地化 Tailwind CSS + Lucide Icons + Bklit UI Design System (零外网依赖，极速秒开)
- **通讯**：REST API + Server-Sent Events (SSE 实时推流)
