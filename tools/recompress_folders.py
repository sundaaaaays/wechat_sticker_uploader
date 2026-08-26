#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
recompress_folders.py — 重新压缩 compressed/1..84 里的 GIF。
规则：保留原始宽高、保留全部帧、去残影；仅降低调色板颜色。
对每个文件：若 cr_emotes 里有同名原始文件 -> 用原始文件重压并覆盖；否则(本就小的原文件)保留。
"""
import json
from pathlib import Path
from compress import compress_gif

BASE = Path("compressed")
SRC = Path(r"D:\夸克网盘\cr_emotes")

report = []
over = 0
done = 0
kept = 0
missing = 0
for folder in sorted(BASE.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
    if not folder.is_dir():
        continue
    for f in folder.glob("*.gif"):
        if ".tmp." in f.name:
            continue
        orig = SRC / f.name
        if orig.exists():
            try:
                compress_gif(str(orig), str(f), 500)
                done += 1
            except Exception as e:
                missing += 1
                print(f"  [失败] {folder.name}/{f.name}: {e}")
        else:
            kept += 1   # 本就是压缩前的小文件（或原始），保留
        kb = round(f.stat().st_size / 1024, 1)
        dims = tuple(f and (Path(f).name,))
        if kb > 500:
            over += 1
        report.append((folder.name, f.name, kb))

# 写一份大小报告
with open(BASE / "size_report.txt", "w", encoding="utf-8") as fp:
    for folder, name, kb in report:
        fp.write(f"{folder}\t{name}\t{kb}KB\n")

print(f"重压完成: 重压 {done}，保留 {kept}，失败 {missing}")
print(f"其中超过 500KB 的: {over} 个")
print("大小报告 -> compressed/size_report.txt")
