#!/usr/bin/env python3
"""
语料合并脚本 — 将目录下所有 .txt 字幕文件合并为一个语料文件
用法：python merge_corpus.py <输入目录> [输出文件]
"""

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Optional


def clean_filename(filename: str) -> str:
    """从文件名提取可读标题，去掉 task_id 前缀和分辨率后缀"""
    stem = Path(filename).stem
    # 去掉 8 位 hex task_id 前缀和下划线
    if len(stem) > 9 and stem[8] == "_":
        stem = stem[9:]
    # 去掉末尾的分辨率标记
    for suffix in [" 4K", " 2K", " 1080P", " 720P"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem.strip()


def merge_corpus(input_dir: str, output_file: Optional[str] = None) -> Path:
    """合并目录下所有 .txt 文件，去重后输出为一个语料文件"""
    input_path = Path(input_dir)
    if not input_path.is_dir():
        print(f"❌ 目录不存在：{input_path}")
        sys.exit(1)

    txt_files = sorted(input_path.glob("*.txt"))
    if not txt_files:
        print(f"❌ 目录下没有 .txt 文件：{input_path}")
        sys.exit(1)

    seen_hashes: set[str] = set()
    entries: list[dict] = []
    duplicates = 0

    for f in txt_files:
        content = f.read_text(encoding="utf-8").strip()
        if not content:
            continue

        content_hash = hashlib.md5(content.encode()).hexdigest()
        if content_hash in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(content_hash)

        title = clean_filename(f.name)
        entries.append({"title": title, "content": content, "file": f.name})

    # 输出路径
    if output_file:
        out_path = Path(output_file)
    else:
        out_path = input_path.parent / "corpus.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入合并文件
    with open(out_path, "w", encoding="utf-8") as f:
        for i, entry in enumerate(entries, 1):
            f.write(f"{'=' * 60}\n")
            f.write(f"[{i}] {entry['title']}\n")
            f.write(f"{'=' * 60}\n\n")
            f.write(entry["content"] + "\n\n")

    # 统计
    total_chars = sum(len(e["content"]) for e in entries)
    print(f"✅ 合并完成：{out_path}")
    print(f"   篇数：{len(entries)}（去重 {duplicates} 篇）")
    print(f"   总字数：{total_chars:,}")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="语料合并脚本")
    parser.add_argument("input_dir", help="包含 .txt 文件的目录")
    parser.add_argument("-o", "--output", default=None, help="输出文件路径（默认为输入目录的上级 corpus.txt）")
    args = parser.parse_args()

    merge_corpus(args.input_dir, args.output)


if __name__ == "__main__":
    main()
