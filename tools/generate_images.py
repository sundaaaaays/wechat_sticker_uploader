#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_images.py — 生成专辑横幅/封面/图标占位图（均 <500KB）

输出到项目目录：banner.png / cover.png / icon.png
样式：深蓝→青渐变的封面 + 金色标题「皇室战争 · 表情专辑」。
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE = Path(__file__).resolve().parent
FONT = "C:/Windows/Fonts/msyhbd.ttc"  # 微软雅黑粗体

TOP = (20, 32, 96)      # 深蓝
BOTTOM = (0, 168, 150)  # 青绿


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vertical_gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        c = lerp(top, bottom, y / max(1, h - 1))
        for x in range(w):
            px[x, y] = c
    return img


def add_text(img, main, sub):
    d = ImageDraw.Draw(img)
    w, h = img.size
    # 主标题
    fs = int(h * 0.30)
    try:
        font = ImageFont.truetype(FONT, fs)
        sub_font = ImageFont.truetype(FONT, int(h * 0.16))
    except Exception:
        font = ImageFont.load_default()
        sub_font = font
    # 主标题居中
    bbox = d.textbbox((0, 0), main, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((w - tw) / 2, h * 0.28), main, font=font, fill=(255, 215, 0))
    # 副标题
    bbox2 = d.textbbox((0, 0), sub, font=sub_font)
    tw2 = bbox2[2] - bbox2[0]
    d.text(((w - tw2) / 2, h * 0.60), sub, font=sub_font, fill=(255, 255, 255))
    return img


def save(img, name):
    path = BASE / name
    img.save(path, "PNG")
    kb = path.stat().st_size / 1024
    print(f"  {name:<12} {img.size[0]}x{img.size[1]}  {round(kb,1)}KB")
    return path


def main():
    print("生成图片…")
    banner = vertical_gradient(900, 300, TOP, BOTTOM)
    save(add_text(banner, "皇室战争", "经典角色 · 高清动态表情"), "banner.png")

    cover = vertical_gradient(300, 300, TOP, BOTTOM)
    save(add_text(cover, "皇室战争", "表情专辑"), "cover.png")

    icon = vertical_gradient(120, 120, TOP, BOTTOM)
    save(add_text(icon, "皇", "室战"), "icon.png")


if __name__ == "__main__":
    main()
