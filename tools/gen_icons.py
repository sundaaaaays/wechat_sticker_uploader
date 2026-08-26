#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_icons.py — 为每个专辑生成图标 icons/{index}.png。
- 角色专辑：取该专辑【首个表情】的第 12 帧（帧数不足则最后一帧）。
- 通用表情专辑：取该专辑封面拼图（covers/{index}.png）缩小，保证与封面样式一致。
"""
import json
from pathlib import Path
from PIL import Image

MANIFEST = Path("manifest.json")
COVERS = Path("covers")
OUT = Path("icons")
ICON = 120

with open(MANIFEST, encoding="utf-8") as fp:
    manifest = json.load(fp)
OUT.mkdir(exist_ok=True)


def frame12(path, size):
    im = Image.open(path)
    n = getattr(im, "n_frames", 1)
    idx = min(11, max(0, n - 1))
    try:
        im.seek(idx)
    except Exception:
        im.seek(0)
    frame = im.convert("RGB")
    frame.thumbnail((size, size))
    bg = Image.new("RGB", (size, size), (255, 255, 255))
    bg.paste(frame, ((size - frame.width) // 2, (size - frame.height) // 2))
    return bg


def cover_icon(a):
    """通用表情用封面拼图缩成图标，样式与封面一致。"""
    cov = COVERS / f"{a['index']}.png"
    im = Image.open(cov).convert("RGB")
    im.thumbnail((ICON, ICON))
    bg = Image.new("RGB", (ICON, ICON), (255, 255, 255))
    bg.paste(im, ((ICON - im.width) // 2, (ICON - im.height) // 2))
    return bg


count = 0
for a in manifest["albums"]:
    out = OUT / f"{a['index']}.png"
    if a.get("character") == "通用表情":
        img = cover_icon(a)
    else:
        first = a["emotes"][0]["file"]
        img = frame12(first, ICON)
    img.save(out, "PNG")
    count += 1
    if count <= 5 or count % 20 == 0:
        print(f"  [{a['index']:>2}] {a['name']:<10} {out.stat().st_size//1024}KB")

print(f"已生成 {count} 个图标 -> icons/")
