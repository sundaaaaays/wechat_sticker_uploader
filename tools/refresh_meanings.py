#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_meanings.py — 用改进后的 detect_meaning 重算每个表情的含义词。
不重新扫描文件，只改 manifest 里每个表情的 meaning（保留 compressed/ 指针）。
"""
import json
from classify import detect_meaning, _dedupe_meanings

with open("manifest.json", encoding="utf-8") as fp:
    manifest = json.load(fp)

total = 0
english_fallback = 0
for a in manifest["albums"]:
    for e in a["emotes"]:
        m = detect_meaning(e["name"])
        e["meaning"] = m
        total += 1
        # 判断是否为英文兜底（含字母且无常见汉字）
        if not m.startswith(("表情",)) and any("\u4e00" <= ch <= "\u9fff" for ch in m) is False:
            english_fallback += 1
    # 同专辑内去重（重复含义追加数字）
    a["emotes"] = _dedupe_meanings(a["emotes"])

with open("manifest.json", "w", encoding="utf-8") as fp:
    json.dump(manifest, fp, ensure_ascii=False, indent=2)

print("重算含义词完成。表情总数:", total)

# 统计兜底
from collections import Counter
c = Counter()
for a in manifest["albums"]:
    for e in a["emotes"]:
        c[e["meaning"]] += 1
print("唯一含义词种类:", len(c))
print("含义词最常见 Top5:", c.most_common(5))
