#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compact_folders.py — 删除 compressed 下的空文件夹，并按旧序号补位重编号为 1..N。
每个文件夹按其内容的主导角色重新生成专辑名（皇战X），并更新 folder_map.txt。
"""
import shutil
from pathlib import Path
from collections import Counter, OrderedDict
from classify import detect_character, make_album_name

BASE = Path("compressed")


def main():
    # 1) 收集所有数字文件夹（按旧序号排）
    folders = []
    for d in BASE.iterdir():
        if d.is_dir() and d.name.isdigit():
            folders.append((int(d.name), d))
    folders.sort()

    # 2) 删除空文件夹
    removed = []
    non_empty = []  # (old_idx, dir, count)
    for idx, d in folders:
        gifs = list(d.glob("*.gif"))
        gifs = [g for g in gifs if ".tmp." not in g.name]
        if not gifs:
            shutil.rmtree(d, ignore_errors=True)
            removed.append(idx)
        else:
            non_empty.append((idx, d, len(gifs)))

    # 3) 每个文件夹：按主导角色生成名称 + 计数（按旧序，处理同名角色多组）
    results = []  # (old_idx, new_idx, name, count)
    char_counters = OrderedDict()
    for new_idx, (old_idx, d, cnt) in enumerate(non_empty, start=1):
        c = Counter()
        for g in d.glob("*.gif"):
            if ".tmp." in g.name:
                continue
            c[detect_character(g.stem)] += 1
        char = c.most_common(1)[0][0]
        char_counters[char] = char_counters.get(char, 0) + 1
        name = make_album_name(char, char_counters[char])
        results.append((old_idx, new_idx, name, cnt))

    # 4) 重命名文件夹（先临时名，避免冲突）
    for old_idx, new_idx, name, cnt in results:
        if old_idx != new_idx:
            d = BASE / str(old_idx)
            if d.exists():
                d.rename(BASE / f"__x_{old_idx}")
    for old_idx, new_idx, name, cnt in results:
        if old_idx != new_idx:
            tmp = BASE / f"__x_{old_idx}"
            if tmp.exists():
                tmp.rename(BASE / str(new_idx))

    # 5) 更新 folder_map.txt
    lines = [f"{new_idx}\t{name}\t{cnt}" for old_idx, new_idx, name, cnt in results]
    (BASE / "folder_map.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"删除空文件夹: {removed}")
    print(f"剩余文件夹数: {len(results)}")
    print("--- 新 folder_map.txt ---")
    for line in lines:
        print("  ", line)


if __name__ == "__main__":
    main()
