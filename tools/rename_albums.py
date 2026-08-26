#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rename_albums.py — 把现有 manifest 里的专辑名改成「皇战+分类名」(≤8字且不重名)。
只改 name，不重新扫描文件，保留 compress.py 生成的 compressed/ 指针。
"""
import json
from collections import OrderedDict
from classify import make_album_name

with open("manifest.json", encoding="utf-8") as fp:
    manifest = json.load(fp)

counters = OrderedDict()
for a in manifest["albums"]:
    c = a["character"]
    counters[c] = counters.get(c, 0) + 1
    new_name = make_album_name(c, counters[c])
    print(f"[{a['index']:>2}] {a['name']!r:<22} -> {new_name!r}")
    a["name"] = new_name

with open("manifest.json", "w", encoding="utf-8") as fp:
    json.dump(manifest, fp, ensure_ascii=False, indent=2)

# 校验
names = [a["name"] for a in manifest["albums"]]
from collections import Counter
dups = [k for k, v in Counter(names).items() if v > 1]
over = [n for n in names if len(n) > 8]
print("---")
print("专辑数:", len(names))
print("重名:", dups if dups else "无")
print("超过8字:", over if over else "无")
