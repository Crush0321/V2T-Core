#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
单视频字幕提取脚本（CPU 优化版）
基于 faster-whisper，适用于抖音等短视频的本地离线字幕生成。
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import timedelta


def format_timestamp(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳 HH:MM:SS,mmm"""
    milliseconds = int((seconds % 1) * 1000)
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def write_srt(segments, output_path: Path):
    """将识别结果写入 SRT 文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            start = format_timestamp(seg.start)
            end = format_timestamp(seg.end)
            text = seg.text.strip()
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")


def write_txt(segments, output_path: Path):
    """将识别结果写入纯文本 TXT 文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(seg.text.strip() + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="本地视频字幕提取（faster-whisper CPU 版）"
    )
    parser.add_argument(
        "-i", "--input", required=True, help="输入视频文件路径"
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        help="输出目录（默认当前目录）"
    )
    parser.add_argument(
        "-m", "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper 模型大小（默认 medium，抖音短视频可用 small）"
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        default=8,
        help="CPU 线程数（默认 8，Apple M4 建议 8，Intel i7-14700 建议 16~20）"
    )
    parser.add_argument(
        "--no-vad",
        action="store_true",
        help="关闭语音活动检测（VAD），不建议关闭"
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"❌ 错误：输入文件不存在：{input_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    srt_path = output_dir / f"{stem}.srt"
    txt_path = output_dir / f"{stem}.txt"

    print(f"📹 输入视频：{input_path}")
    print(f"🧠 模型：{args.model}")
    print(f"💻 设备：CPU (int8, threads={args.threads})")
    print(f"🔇 VAD 过滤：{'关闭' if args.no_vad else '开启'}")
    print("-" * 40)

    # 延迟导入，方便先检查参数
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("❌ 未安装 faster-whisper，请先运行：pip install -r requirements.txt")
        sys.exit(1)

    # 加载模型（首次会自动下载到本地缓存）
    print("⏳ 正在加载模型，首次使用需要下载...")
    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8",
        cpu_threads=args.threads,
    )

    # 转写
    print("⏳ 正在提取字幕，请稍候...")
    segments, info = model.transcribe(
        str(input_path),
        vad_filter=not args.no_vad,
        word_timestamps=False,
    )

    # 由于 segments 是生成器，需要转成列表才能多次使用
    segments = list(segments)

    detected_lang = info.language
    lang_prob = info.language_probability
    print(f"🌍 检测到语言：{detected_lang} (置信度: {lang_prob:.2%})")

    # 写入文件
    write_srt(segments, srt_path)
    write_txt(segments, txt_path)

    print("-" * 40)
    print(f"✅ SRT 字幕：{srt_path}")
    print(f"✅ 纯文本 TXT：{txt_path}")
    print(f"📝 共 {len(segments)} 段字幕")


if __name__ == "__main__":
    main()
