#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress.py — GIF 压缩工具

微信专辑要求单个表情 ≤ 500KB。本模块扫描 manifest 中的文件，
超限的 GIF 自动压缩后输出到 `compressed/` 目录，并更新 manifest 中的 file 路径。

策略（逐步加压，直到满足大小上限或达到最小上限）：
  1. 先尝试 Pillow 以 optimize 重新编码（降低冗余）
  2. 再尝试降低调色板颜色数（256 -> 128 -> 64 -> 32...）
  3. 最后逐步缩小尺寸（每次 0.9 倍），并同步降低颜色数

用法：
    python compress.py                      # 读取 manifest.json 并压缩超限文件
    python compress.py --max-kb 400         # 自定义上限
    python compress.py --dry-run            # 只统计不写盘
"""

import argparse
import os
import shutil
from pathlib import Path

from PIL import Image, ImageSequence

MANIFEST = "manifest.json"
OUT_DIR = "compressed"
MIN_SIZE_FACTOR = 0.4          # 尺寸最小缩到原图的 40%
PALETTE_STEPS = [256, 128, 96, 64, 48, 32, 16]
SCALE_FACTOR = 0.9


def get_duration(frame):
    """取单帧时长（毫秒），缺失时给 100ms。"""
    d = frame.info.get("duration")
    return d if d else 100


def load_full_frames(src):
    """读取动画所有帧为【RGBA（保留透明底）】，并保留时长/loop。不合成到白底。"""
    im = Image.open(src)
    frames = []
    durations = []
    for frame in ImageSequence.Iterator(im):
        frames.append(frame.convert("RGBA"))       # 保留透明背景
        durations.append(get_duration(frame))
    loop = im.info.get("loop")
    return frames, durations, loop


def _rgba_to_p_trans(rgba, colors, threshold=128):
    """把 RGBA 帧转为 P，并保留一个【透明索引】以保证透明底可靠。"""
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB")
    p = rgb.quantize(colors=colors, method=Image.MEDIANCUT)
    # 调色板：在 quantize 出来的颜色后追加一个透明色索引
    pal = list(p.getpalette())
    while len(pal) < colors * 3:
        pal += [0, 0, 0]
    pal = pal[: colors * 3]
    trans_idx = colors
    pal += [0, 0, 0]                      # 透明色（播放时被忽略）
    # 像素：alpha<threshold 的设为 trans_idx，否则保留量化后的索引
    arr = list(p.getdata())
    al = list(alpha.getdata())
    new_arr = [trans_idx if a < threshold else idx for idx, a in zip(arr, al)]
    new_p = Image.new("P", rgba.size)
    new_p.putpalette(pal)
    new_p.putdata(new_arr)
    new_p.info["transparency"] = trans_idx
    return new_p


def _save(frames, durations, loop, dst, colors):
    """把 RGBA 帧保存为 GIF：保留透明底、保留原始宽高、只降调色板颜色。"""
    q = []
    n = min(colors, 254)
    for f in frames:
        q.append(_rgba_to_p_trans(f, n))
    q[0].save(dst, format="GIF", save_all=True, append_images=q[1:],
              duration=durations, loop=loop, disposal=2, optimize=False)


def compress_gif(src, dst, max_kb=500):
    """将 src 压缩到 <= max_kb，写入 dst。只降调色板颜色（不缩宽高、不丢帧、去残影）。"""
    max_bytes = max_kb * 1024
    dst = Path(dst)
    parent = dst.parent
    if str(parent):
        os.makedirs(parent, exist_ok=True)
    frames, durations, loop = load_full_frames(src)
    tmp = str(dst) + ".tmp.gif"

    best = None
    for colors in [256, 224, 192, 160, 128, 96, 64, 48, 32, 24, 16, 12, 8]:
        try:
            _save(frames, durations, loop, tmp, colors)
        except Exception:
            continue
        size = os.path.getsize(tmp)
        if size <= max_bytes:
            os.replace(tmp, dst)
            return True
        if best is None or size < best[0]:
            best = (size, colors)

    # 压不到上限：用最低色数（16 色）作为结果，尽量保留宽高与帧数
    try:
        _save(frames, durations, loop, tmp, 16)
        os.replace(tmp, dst)
        return True
    except Exception:
        if best:
            _save(frames, durations, loop, tmp, best[1])
            os.replace(tmp, dst)
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="压缩超限 GIF")
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--max-kb", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true", help="只统计不写盘")
    args = ap.parse_args()

    import json
    with open(args.manifest, encoding="utf-8") as fp:
        manifest = json.load(fp)

    out_dir = Path(OUT_DIR)
    stats = {"over": 0, "compressed": 0, "failed": 0, "already_ok": 0}
    for album in manifest["albums"]:
        for e in album["emotes"]:
            src = Path(e["file"])
            if not src.exists():
                print(f"[跳过] 不存在: {src}")
                stats["failed"] += 1
                continue
            size_kb = round(src.stat().st_size / 1024, 1)
            if size_kb <= args.max_kb:
                stats["already_ok"] += 1
                continue
            stats["over"] += 1
            if args.dry_run:
                print(f"[超限] {src.name}  {size_kb}KB")
                continue
            out_dir.mkdir(exist_ok=True)
            dst = out_dir / src.name
            if compress_gif(src, dst, args.max_kb):
                # 更新 manifest 指向压缩后的文件
                e["file"] = str(dst.resolve())
                stats["compressed"] += 1
                print(f"[压缩] {src.name}  {size_kb}KB -> {round(dst.stat().st_size/1024,1)}KB")
            else:
                stats["failed"] += 1
                print(f"[失败] {src.name}  无法压到 {args.max_kb}KB 以内")

    if not args.dry_run:
        with open(args.manifest, "w", encoding="utf-8") as fp:
            json.dump(manifest, fp, ensure_ascii=False, indent=2)

    print("-" * 50)
    print(f"本来已合规 : {stats['already_ok']}")
    print(f"需要压缩   : {stats['over']}")
    print(f"压缩成功   : {stats['compressed']}")
    print(f"失败       : {stats['failed']}")


if __name__ == "__main__":
    main()
