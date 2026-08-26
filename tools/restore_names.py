#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore_names.py — 把补位后的文件夹映射回【原始专辑名】（来自 manifest 的 皇战X）。
新文件夹N = 删除空文件夹后按旧序号重排的第N个；其名称 = 旧序号对应的 manifest 专辑名。
"""
import json
from pathlib import Path

BASE = Path("compressed")
REMOVED = [3, 30, 34, 38, 50, 55, 56, 57, 58, 60, 63, 64, 70, 72, 75, 76, 78, 83, 84]

m = json.load(open("manifest.json", encoding="utf-8"))
idx2name = {a["index"]: a["name"] for a in m["albums"]}

non_empty_old = [i for i in range(1, 85) if i not in REMOVED]
assert len(non_empty_old) == 65, f"非空旧序号数={len(non_empty_old)}"

lines = []
for new_idx, old_idx in enumerate(non_empty_old, start=1):
    folder = BASE / str(new_idx)
    cnt = len([f for f in folder.glob("*.gif") if ".tmp." not in f.name])
    name = idx2name.get(old_idx, "皇战?")
    lines.append((new_idx, old_idx, name, cnt))

(BASE / "folder_map.txt").write_text(
    "\n".join(f"{i}\t{n}\t{c}" for i, o, n, c in lines), encoding="utf-8")
# 另写一份带旧序号对照的
(BASE / "folder_map_old.txt").write_text(
    "\n".join(f"{i}\t{o}\t{n}\t{c}" for i, o, n, c in lines), encoding="utf-8")

print("新序号\t旧序号\t名称\t数量")
for i, o, n, c in lines:
    print(f"  {i}\t{o}\t{n}\t{c}")
