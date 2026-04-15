# V2T-Core

本地离线视频字幕提取工具。基于 [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)，支持**单视频/批量视频**上传、实时进度查看、SRT/TXT 单独或批量下载。

> 完全本地运行，无需联网（除首次下载模型外），不上传任何数据到第三方服务器。

---

## 特性

- **批量上传**：支持一次拖拽/选择多个视频，自动排队处理
- **实时进度**：每个任务显示独立进度条，页面顶部汇总整体进度
- **双模式输出**：每个视频生成 `.srt`（带时间轴）和 `.txt`（纯文本）
- **批量下载**：支持勾选多个已完成任务，打包成 ZIP 一键下载
- **CPU 深度优化**：针对 Intel 高性能 CPU 优化，支持调节线程数，严格单队列执行保证最快速度
- **纯离线**：基于 OpenAI Whisper 的 Faster-Whisper 实现，模型下载后永久本地缓存

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows / macOS / Linux |
| Python | 3.8 - 3.11（推荐 3.10） |
| FFmpeg | **必须安装**，并加入系统 PATH |
| 内存 | 8GB 可用内存即可，推荐 16GB+ |
| GPU | 非必须，纯 CPU 即可运行 |

---

## 快速开始

### 1. 安装 FFmpeg

**Windows（推荐）**：
1. 下载 [FFmpeg Essentials](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip)
2. 解压后，将 `bin` 文件夹路径添加到系统环境变量 `PATH`
3. 打开新的 PowerShell / CMD，验证安装：
   ```powershell
   ffmpeg -version
   ```

**macOS**：
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian)**：
```bash
sudo apt update && sudo apt install ffmpeg -y
```

### 2. 克隆仓库并安装依赖

```bash
git clone https://github.com/Crush0321/V2T-Core.git
cd V2T-Core

python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

> 首次运行时会自动从 HuggingFace 下载 Whisper 模型（`small` 约 244MB，`medium` 约 769MB），下载后永久缓存到本地。

### 3. 启动 Web 服务

```bash
python web_app.py
```

打开浏览器访问：
```
http://localhost:8000
```

---

## 使用说明

### Web 界面（推荐）

1. **上传视频**：点击上传区或拖拽多个视频文件到页面
2. **选择模型**：
   - `small` — 速度更快，适合短视频/抖音（推荐）
   - `medium` — 精度更高，适合对字幕准确率要求高的场景
3. **调节线程**：默认 16 线程，可根据 CPU 核心数微调
4. **开始提取**：点击「开始提取」，任务自动进入队列处理
5. **下载结果**：
   - 单个下载：任务完成后点击右侧 **SRT** 或 **TXT**
   - 批量下载：勾选多个已完成任务，点击顶部「批量下载 SRT / TXT / 全部」

### 命令行（单视频快速处理）

如果你不想开 Web 服务，也可以直接用命令行处理单个视频：

```bash
# small 模型，适合短视频
python extract_subtitle.py -i "你的视频.mp4" -o "./字幕输出" -m small

# medium 模型，精度更高
python extract_subtitle.py -i "你的视频.mp4" -o "./字幕输出" -m medium
```

输出结果：
- `你的视频.srt` — 带时间轴字幕
- `你的视频.txt` — 纯文本稿

---

## 项目结构

```
V2T-Core/
├── extract_subtitle.py      # 命令行单视频提取脚本
├── web_app.py               # FastAPI Web 后端（批量上传 + 队列调度）
├── templates/
│   └── index.html           # Web 前端页面
├── requirements.txt         # Python 依赖
├── .gitignore               # Git 忽略规则
├── uploads/                 # 上传的视频缓存（运行后生成）
├── outputs/                 # 生成的字幕文件（运行后生成）
└── README.md                # 本文件
```

---

## 常见问题

### Q: 首次启动提示下载模型很慢？
A: Faster-Whisper 默认从 HuggingFace 下载模型。如果网络较慢，可以设置镜像源后再启动：
```bash
# Windows PowerShell
$env:HF_ENDPOINT = "https://hf-mirror.com"
python web_app.py
```

### Q: 处理视频时 CPU 占用很高？
A: 这是正常的，Whisper 语音识别是 CPU 密集型任务。建议保持默认队列机制，**不要并发处理多个视频**，这样整体耗时最短。

### Q: 可以支持 GPU 加速吗？
A: 如果你有 NVIDIA 显卡并安装了 CUDA，可以将 `web_app.py` 和 `extract_subtitle.py` 中的 `device="cpu"` 改为 `device="cuda"`，`compute_type="int8"` 改为 `compute_type="float16"`，即可获得显著加速。

### Q: 上传大视频后页面卡住？
A: 大文件上传需要时间，请耐心等待上传进度完成。上传完成后才会进入提取阶段。

---

## 模型对比

| 模型 | 大小 | 1 小时视频（CPU 预估） | 推荐场景 |
|------|------|----------------------|---------|
| `small` | ~244MB | 5~10 分钟 | 抖音/短视频，快速出稿 |
| `medium` | ~769MB | 15~25 分钟 | 网课/录播，追求准确率 |
| `large-v3` | ~1.5GB | 40~70 分钟 | 电影/高精度需求 |

> 修改 `web_app.py` 中 `choices` 列表或命令行参数即可使用 `large-v3`。

---

## License

MIT
