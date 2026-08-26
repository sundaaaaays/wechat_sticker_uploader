#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
organize_folders.py — 把 580 个 GIF 按 manifest 的分组移动到 compressed/{1..84}/。
同时生成 compressed/folder_map.txt：每个文件夹对应的专辑名与表情数。
"""
import json
import shutil
from pathlib import Path

with open("manifest.json", encoding="utf-8") as fp:
    manifest = json.load(fp)

base = Path("compressed")
base.mkdir(exist_ok=True)

lines = []
moved = 0
missing = 0
skipped = 0
for a in manifest["albums"]:
    idx = a["index"]
    folder = base / str(idx)
    folder.mkdir(parents=True, exist_ok=True)
    for e in a["emotes"]:
        src = Path(e["file"])
        if not src.exists():
            print(f"  [缺失] {src}")
            missing += 1
            continue
        dst = folder / src.name
        if dst.exists():
            skipped += 1
            continue
        shutil.move(str(src), str(dst))
        moved += 1
    lines.append(f"{idx}\t{a['name']}\t{len(a['emotes'])}")

map_file = base / "folder_map.txt"
map_file.write_text("\n".join(lines), encoding="utf-8")
print(f"已移动 {moved} 个文件，缺失 {missing}，跳过 {skipped}")
print(f"共创建 {len(manifest['albums'])} 个文件夹 -> compressed/1..84")
print("对照表 -> compressed/folder_map.txt")
print("--- 对照表预览(前12) ---")
for l in lines[:12]:
    print("  ", l)
