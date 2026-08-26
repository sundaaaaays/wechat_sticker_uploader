#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild_manifest.py — 按新的 65 个文件夹 + folder_map.txt 的命名，重建 manifest.json。
每个专辑 = 一个文件夹；名字取自 folder_map；每个表情的含义词由 detect_meaning 生成（同专辑去重）。
"""
import json
from pathlib import Path
from classify import detect_meaning, _dedupe_meanings

BASE = Path("compressed")

# 读 folder_map.txt（保持用户手改的命名，不改它）
fm = {}
for line in (BASE / "folder_map.txt").read_text(encoding="utf-8").splitlines():
    parts = line.split("\t")
    if len(parts) >= 3:
        fm[int(parts[0])] = parts[1].strip()

albums = []
for idx in sorted(fm):
    folder = BASE / str(idx)
    gifs = [g for g in folder.glob("*.gif") if ".tmp." not in g.name]
    gifs.sort(key=lambda p: p.name.lower())
    name = fm[idx]
    # character = 名称去掉“皇战”前缀，用于介绍
    char = name[2:] if name.startswith("皇战") else name
    emotes = [{"file": str(g.resolve()), "name": g.stem, "meaning": detect_meaning(g.stem)} for g in gifs]
    emotes = _dedupe_meanings(emotes)
    albums.append({"index": idx, "name": name, "character": char,
                   "emote_count": len(emotes), "emotes": emotes})

total = sum(len(a["emotes"]) for a in albums)
manifest = {"source_dir": "compressed", "total_files": total, "album_count": len(albums), "albums": albums}
json.dump(manifest, open("manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"专辑数: {len(albums)}  表情总数: {total}")
over = [a["name"] for a in albums if len(a["name"]) > 8]
print("超过8字名称:", over if over else "无")
for a in albums[:8]:
    print(" ", a["index"], a["name"], a["emote_count"])
