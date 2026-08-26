#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_covers.py — 为每个专辑生成「该专辑 GIF 拼图」封面，存到 covers/{index}.png。
每个封面由该专辑表情的首帧组成网格，做到“不同专辑不同封面”。
"""
import json
import math
import os
from pathlib import Path
from PIL import Image, ImageDraw

MANIFEST = Path("manifest.json")
OUT = Path("covers")
BG = (20, 32, 96)          # 深蓝背景
THUMB = 120                # 每格尺寸

with open(MANIFEST, encoding="utf-8") as fp:
    manifest = json.load(fp)

OUT.mkdir(exist_ok=True)


def thumb_frame(path, size):
    """取 GIF 的【第 12 帧】（0-based 11）；帧数不足则取最后一帧，缩放到 size 见方（留白）。"""
    im = Image.open(path)
    try:
        n_frames = getattr(im, "n_frames", 1)
    except Exception:
        n_frames = 1
    idx = min(11, max(0, n_frames - 1))   # 第 12 帧；不足则最后一帧
    try:
        im.seek(idx)
    except Exception:
        im.seek(0)
    frame = im.convert("RGB")
    frame.thumbnail((size, size))
    bg = Image.new("RGB", (size, size), (255, 255, 255))
    bg.paste(frame, ((size - frame.width) // 2, (size - frame.height) // 2))
    return bg


def make_cover(album):
    emotes = album["emotes"]
    n = len(emotes)
    cols = math.ceil(math.sqrt(n))
    cols = max(1, min(cols, 6))
    rows = math.ceil(n / cols)
    W = cols * THUMB
    H = rows * THUMB
    canvas = Image.new("RGB", (W, H), BG)
    for i in range(n):
        try:
            t = thumb_frame(emotes[i]["file"], THUMB - 8)
            r, c = divmod(i, cols)
            canvas.paste(t, (c * THUMB + 4, r * THUMB + 4))
        except Exception:
            pass
    # 若专辑名在，底部加一行深色
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, H - 36, W, H], fill=(10, 18, 50))
    return canvas


count = 0
for a in manifest["albums"]:
    out = OUT / f"{a['index']}.png"
    cover = make_cover(a)
    cover.save(out, "PNG")
    kb = round(out.stat().st_size / 1024, 1)
    count += 1
    if count <= 5 or count % 20 == 0:
        print(f"  [{a['index']:>2}] {a['name']:<10} {cover.size[0]}x{cover.size[1]} {kb}KB")

print(f"已生成 {count} 个封面 -> covers/")
