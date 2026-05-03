#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web 版本地视频字幕提取
FastAPI + SSE + 单任务队列调度 + 批量下载
"""

import asyncio
import io
import json
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import ffmpeg
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from faster_whisper import WhisperModel

# ---------- 配置 ----------
UPLOAD_DIR = Path("./uploads")
OUTPUT_DIR = Path("./outputs")
TXT_OUTPUT_DIR = Path("./outputs/txt")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
TXT_OUTPUT_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory="templates")

# ---------- 全局状态 ----------
tasks: dict[str, dict] = {}
task_queue: asyncio.Queue[str] = asyncio.Queue()

_current_model_key: Optional[str] = None
_current_model: Optional[WhisperModel] = None


# ---------- 工具函数 ----------
def format_timestamp(seconds: float) -> str:
    milliseconds = int((seconds % 1) * 1000)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(segments, output_path: Path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp(seg.start)} --> {format_timestamp(seg.end)}\n")
            f.write(f"{seg.text.strip()}\n\n")


def write_txt(segments, output_path: Path):
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(seg.text.strip() + "\n")


def get_video_duration(path: Path) -> Optional[float]:
    try:
        probe = ffmpeg.probe(str(path))
        return float(probe["format"]["duration"])
    except Exception:
        return None


def get_model(model_name: str, threads: int) -> WhisperModel:
    global _current_model_key, _current_model
    key = f"{model_name}_{threads}"
    if _current_model_key != key:
        _current_model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=threads,
        )
        _current_model_key = key
    return _current_model


def create_task(file: UploadFile, model: str, threads: int) -> str:
    task_id = str(uuid.uuid4())[:8]
    stem = Path(file.filename).stem
    safe_stem = "".join(c for c in stem if c.isalnum() or c in " _-").strip() or "video"

    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    out_dir = OUTPUT_DIR / task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    upload_path = task_dir / f"{safe_stem}{Path(file.filename).suffix}"

    task = {
        "id": task_id,
        "filename": file.filename,
        "stem": safe_stem,
        "model": model,
        "threads": threads,
        "status": "pending",
        "progress": 0.0,
        "message": "等待处理...",
        "created_at": datetime.now().isoformat(),
        "upload_path": str(upload_path),
        "output_dir": str(out_dir),
        "duration": None,
        "language": None,
        "srt_path": None,
        "txt_path": None,
        "segment_count": 0,
    }
    tasks[task_id] = task
    return task_id, upload_path


# ---------- 后台工作线程 ----------
async def worker():
    while True:
        task_id = await task_queue.get()
        task = tasks[task_id]
        task["status"] = "processing"
        task["message"] = "正在初始化..."

        try:
            upload_path = Path(task["upload_path"])
            out_dir = Path(task["output_dir"])
            out_dir.mkdir(parents=True, exist_ok=True)

            duration = get_video_duration(upload_path)
            task["duration"] = duration

            task["message"] = "正在加载模型..."
            model = get_model(task["model"], task["threads"])

            task["message"] = "正在提取字幕..."
            segments_generator, info = model.transcribe(
                str(upload_path),
                vad_filter=True,
                word_timestamps=False,
            )

            detected_lang = info.language
            task["language"] = detected_lang

            segments = []
            progress = 0.0
            for seg in segments_generator:
                segments.append(seg)
                if duration and duration > 0:
                    progress = min((seg.end / duration) * 100, 99.0)
                else:
                    progress = min(progress + 5.0, 99.0)
                task["progress"] = round(progress, 1)

            task["progress"] = 100.0
            task["message"] = "正在生成文件..."

            # SRT 保留在 per-task 目录，TXT 扁平存储到 outputs/txt/ 方便直接查阅
            srt_path = out_dir / f"{task['stem']}.srt"
            flat_txt_path = TXT_OUTPUT_DIR / f"{task_id}_{task['stem']}.txt"
            write_srt(segments, srt_path)
            write_txt(segments, flat_txt_path)

            task["status"] = "completed"
            task["message"] = f"完成，检测到语言：{detected_lang}"
            task["srt_path"] = str(srt_path)
            task["txt_path"] = str(flat_txt_path)
            task["segment_count"] = len(segments)

        except Exception as e:
            task["status"] = "failed"
            task["message"] = f"处理失败：{e}"
            task["progress"] = 0.0
        finally:
            task_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(worker())
    yield


app = FastAPI(title="本地视频字幕提取", lifespan=lifespan)


# ---------- 路由 ----------
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/upload")
async def upload(
    files: list[UploadFile] = File(...),
    model: str = Form("small"),
    threads: int = Form(8),
):
    result = []
    for file in files:
        task_id, upload_path = create_task(file, model, threads)
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)
        await task_queue.put(task_id)
        result.append({"task_id": task_id, "filename": file.filename, "status": "pending"})

    return {"tasks": result}


@app.get("/api/tasks")
async def get_tasks():
    sorted_tasks = sorted(tasks.values(), key=lambda x: x["created_at"], reverse=True)
    return sorted_tasks


@app.get("/api/progress/{task_id}")
async def progress(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        while True:
            task = tasks.get(task_id)
            if not task:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break

            payload = {
                "status": task["status"],
                "progress": task["progress"],
                "message": task["message"],
                "language": task.get("language"),
                "segment_count": task.get("segment_count"),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if task["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/download/{task_id}/{format}")
async def download(task_id: str, format: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    path = Path(task["srt_path"]) if format == "srt" else Path(task["txt_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=f"{task['stem']}.{format}",
    )


@app.post("/api/bulk_download")
async def bulk_download(
    task_ids: str = Form(...),
    format: str = Form("both"),
):
    ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="No task ids provided")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for tid in ids:
            if tid not in tasks:
                continue
            task = tasks[tid]
            if task["status"] != "completed":
                continue

            stem = task["stem"]
            if format in ("srt", "both"):
                srt_path = Path(task["srt_path"])
                if srt_path.exists():
                    zf.write(srt_path, arcname=f"{stem}.srt")
            if format in ("txt", "both"):
                txt_path = Path(task["txt_path"])
                if txt_path.exists():
                    zf.write(txt_path, arcname=f"{stem}.txt")

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="subtitles.zip"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=False)
