#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify.py — 扫描 GIF 文件，自动识别角色，拆分为 ≤24 个/专辑的分组，导出 manifest.json

工作流程：
  1. 读取 D:\\夸克网盘\\cr_emotes 下所有 .gif
  2. 通过「角色关键词优先级表」识别每个文件属于哪个角色（分类）
  3. 通过「动作/情绪关键词表」为每个文件提取中文含义词（词义）
  4. 按角色分组；超过 24 个则拆成 角色2 / 角色3 ...
  5. 生成 manifest.json 供 upload.py 使用

用法:
    python classify.py
    python classify.py --src "D:\\夸克网盘\\cr_emotes" --out manifest.json
"""

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path

from meaning_map import MEANING_RULES  # 通用中英关键词→中文含义表

MAX_PER_ALBUM = 24  # 微信单个表情专辑上限

# ---------------------------------------------------------------------------
# 第 1 步：角色识别
# 关键词按「优先级」排序（越具体越靠前）。对文件名做小写化后做子串匹配，
# 命中顺序靠前的第一个角色即判定为该文件所属角色。
# 每个元素: (正则字符串, 中文分类名)
# ---------------------------------------------------------------------------
CHARACTER_RULES = [
    # 弓箭手系
    (r"magicarcher|emotesheistmagicarcher", "神箭游侠"),
    (r"archerqueen", "弓箭女皇"),
    (r"archer", "弓箭手"),
    # 龙系
    (r"babydragon|dragonegg|bewarethedragon|bewardthedragon|pantingbabydragon", "飞龙宝宝"),
    (r"electrodragon", "雷电飞龙"),
    (r"infernodragon", "地狱飞龙"),
    (r"skeletondragon", "骷髅飞龙"),
    (r"dragon", "飞龙宝宝"),
    # 气球
    (r"balloon|ballon", "气球兵"),
    # 刺客
    (r"bossbandit|emotesheistbandit", "首领刺客"),
    (r"bandit", "刺客"),
    # 疗愈天使
    (r"battlehealer", "疗愈天使"),
    # 蝙蝠
    (r"\bbat\b|bat[s]?halloween|bats01|batssleeping|batevospin|batkiss|batcrazy", "蝙蝠"),
    # 狂战士
    (r"berserker", "狂战士"),
    # 野蛮人（注意优先于其它含 barb 的词）
    (r"elitebarbarian|barbarian|barb", "野蛮人"),
    # 炸弹兵
    (r"bomberevo|bomber", "炸弹兵"),
    # 巨石投手
    (r"bowler", "巨石投手"),
    # 炮手 / 加农炮（cannoneer 必须排在 cannon 之前）
    (r"cannoneer", "炮手"),
    (r"cannon", "加农炮"),
    # 黑暗王子 / 王子 / 公主（公主必须排在王子前面，因为 princess 包含 prince）
    (r"princess", "公主"),
    (r"darkprince", "黑暗王子"),
    (r"prince", "王子"),
    # 吹箭哥布林
    (r"dartgoblin|dartgoblin", "吹箭哥布林"),
    # 匕首公爵
    (r"daggerduchess", "匕首公爵"),
    # 雷电系
    (r"electrowizard", "雷电法师"),
    (r"electrogiant|electrogiant", "雷电巨人"),
    (r"electrospirit", "雷电精灵"),
    (r"electro", "雷电巨人"),
    # 刽子手
    (r"executioner", "刽子手"),
    # 烟花炮手
    (r"firecracker", "烟花炮手"),
    # 火精灵
    (r"firespirit", "火精灵"),
    # 渔夫
    (r"fisherman", "渔夫"),
    # 熔炉
    (r"furnace", "熔炉"),
    # 皇家幽灵 / 幽灵王
    (r"ghostking|royalghost", "皇家幽灵"),
    # 国王（皇家国王）
    (r"king", "国王"),
    # 复仇滚木（只匹配具体词，避免误伤 LoginLove 等）
    (r"gloriouslog|sadlog|angrylog|logmas", "复仇滚木"),
    # 地狱之塔
    (r"inferno", "地狱之塔"),
    # 治疗精灵
    (r"healspirit", "治疗精灵"),
    # 猎人
    (r"hunter", "猎人"),
    # 树藤
    (r"vine", "树藤"),
    # 雪球
    (r"snowball", "雪球"),
    # 十字弩
    (r"xbow", "十字弩"),
    # 巨人系列（越具体越靠前）
    (r"elixirgolem", "圣水戈仑"),
    (r"icegolem", "冰人"),
    (r"goblingiant|gobliant|goblin", "哥布林"),          # 戈仑巨人/哥布林归入哥布林
    (r"royalgiant", "皇家巨人"),
    (r"runegiant", "符文巨人"),
    (r"skeletongiant", "骷髅巨人"),
    (r"golem", "戈仑石人"),
    (r"giant", "巨人"),
    # 哥布林（兜底，含 typo "gobin" 与合成词 "Gobarian"）
    (r"gob", "哥布林"),
    # 野猪系
    (r"royalhog", "皇家野猪"),
    (r"hog", "野猪骑士"),
    # 冰雪法师
    (r"icewizard|icewizard", "冰雪法师"),
    (r"icespirit", "冰雪精灵"),
    # 骑士 / 超级骑士
    (r"megaknight", "超级骑士"),
    (r"knight", "骑士"),
    # 熔岩猎犬
    (r"lavahound", "熔岩猎犬"),
    # 伐木工
    (r"lumberjack|lumberjack", "伐木工"),
    # 亡灵
    (r"megaminion", "亡灵"),
    (r"minionhorde|minion", "亡灵"),
    # 融合少女
    (r"mergemaiden", "融合少女"),
    # 矿工
    (r"mightyminer", "超级矿工"),
    (r"miner", "矿工"),
    # 皮卡
    (r"minipekka", "迷你皮卡"),
    (r"pekka", "皮卡超人"),
    # 武僧
    (r"monk", "武僧"),
    # 迫击炮
    (r"mortar", "迫击炮"),
    # 女巫系
    (r"motherwitch", "女巫"),
    (r"nightwitch", "夜巫"),
    (r"witch", "女巫"),
    # 火枪手
    (r"musketeer", "火枪手"),
    # 凤凰
    (r"phoenix", "凤凰"),
    # 狂暴攻城槌
    (r"ramrider|ram", "攻城槌骑士"),
    # 火枪姐妹
    (r"rascal", "火枪姐妹"),
    # 皇家新兵
    (r"royalrecruit|royalrecruitevo|royale", "皇家新兵"),
    # 骷髅
    (r"skeleton|skele", "骷髅"),
    # 电磁炮
    (r"sparky", "电磁炮"),
    # 特斯拉电磁塔
    (r"tesla", "特斯拉电塔"),
    # 女武神
    (r"valkyrie", "女武神"),
    # 城墙破坏者
    (r"wallbreaker", "城墙破坏者"),
    # 法师（放在最后，因为很多复合词在前已处理）
    (r"wizard", "法师"),
    # 通用/未识别
]

GENERIC_NAME = "通用表情"


def detect_character(filename: str) -> str:
    """返回文件名对应的角色中文名，未命中返回 GENERIC_NAME。"""
    name = filename.lower()
    for pattern, cn_name in CHARACTER_RULES:
        if re.search(pattern, name):
            return cn_name
    return GENERIC_NAME


# ---------------------------------------------------------------------------
# 第 2 步：含义词提取
# 同样按优先级顺序匹配（越具体越靠前）。命中第一个即作为含义词。
# 要求：简短中文、不带标点、≤4 字；同名冲突由分组逻辑追加数字。
# ---------------------------------------------------------------------------
ACTION_RULES = [
    # 攻击 / 命中系列
    (r"arrowfail|missfail|failarrow", "没射中"),
    (r"arrow|shoot|aim|dart", "射箭"),
    (r"attack|hits|punch|strike", "攻击"),
    (r"slash|slice|cleave", "斩击"),
    (r"smash|slam|crush|bash", "猛砸"),
    (r"explode|explosion|boom|popping|bomb|blow", "爆炸"),
    (r"burn|burning|fire|flame|scorch", "喷火"),
    (r"electrocut|shock|zap|spark|stun|freeze", "电击"),
    # 胜利 / 荣耀
    (r"3crown|threecrown", "三冠"),
    (r"crown", "皇冠"),
    (r"trophy", "奖杯"),
    (r"win|victory|champion|challenge|glorious", "胜利"),
    (r"\bgg\b|goodgame|greatgame", "好棒"),
    (r"confetti|celebrat", "庆祝"),
    # 失败 / 投降
    (r"fail|miss|lose|looser|lost|defeat", "失败"),
    (r"surrender|whiteflag|giveup", "投降"),
    (r"nope|no\b|quit|timeout", "说不"),
    # 生气
    (r"angry|rage|angr|mad|grrr|furious", "生气"),
    (r"frustrat|pout|annoy", "不爽"),
    (r"scream|screech|shout", "大喊"),
    # 悲伤
    (r"cry|crying|tears|boohoo|sob|sad|sadface", "哭泣"),
    (r"tired|sleepy|sleep|snore|yawn|dizzy|exhaust", "犯困"),
    (r"nervous|sweat|anxious|worry", "紧张"),
    (r"scared|scary|creepy|horror|terrify", "害怕"),
    # 开心
    (r"biglaugh|rofl|lmao|\blol\b|haha|laugh", "大笑"),
    (r"smile|smiling|grin|giggle|cheer", "微笑"),
    (r"happy|joy|delight|yay", "开心"),
    # 爱
    (r"kiss|kissy|kisses|smoch", "亲亲"),
    (r"love|heart|romance|valentine", "爱"),
    (r"hug|embrace|cuddle", "抱抱"),
    # 问候
    (r"\bhi\b|hello|hey|greeting|howdy", "你好"),
    (r"bye|goodbye|farewell|see ya|peaceout", "再见"),
    (r"thumbsup|thumbsup|\bok\b|yeah|yes|cool|approve", "点赞"),
    (r"thumbsdown|dislike|\bno\b|disapprove", "踩"),
    (r"welcome|thanks|thank", "感谢"),
    # 舞蹈
    (r"disco|robotdance|tiktok|karoke|karaoke|party|dance|dancing|boogie", "跳舞"),
    (r"rock|roll|band|guitar|headbang", "摇滚"),
    (r"sing|song|mic|microphone|karaoke", "唱歌"),
    # 食物
    (r"eat|eating|chew|bite|devour|munch|noodle|cake|cookie|candy|popcorn|gingerbread|fruitcake|chocolate|sushi", "吃"),
    (r"drink|sipping|sip|tea|coffee|bottle|juice", "喝"),
    (r"cooking|chef|cook|bake|kitchen", "做饭"),
    (r"hungry|starv|greedy", "饿"),
    # 魔法
    (r"magic|spell|potion|cast|enchants|witchcraft", "施法"),
    (r"pray|bless|worship|meditat", "祈祷"),
    # 思考 / 疑问
    (r"think|thought|ponder|contemplate|wonder|chess", "思考"),
    (r"question|confus|huh|what|why|suspicious", "疑惑"),
    (r"wait|hold on|patience|eternal", "等待"),
    # 震惊
    (r"mindblow|mind blow|shock|surprise|jawdrop|wow|amaze|stun", "震惊"),
    (r"facepalm|face palm|headache|faceplam", "扶额"),
    (r"eye|blink|stare|glare|glance|watching", "注视"),
    # 寒冷 / 天气
    (r"snow|winter|ice|icey|freez|chill|frozen|cold", "好冷"),
    (r"rain|storm|thunder|lightning", "下雨"),
    (r"sun|sunset|summer|beach|hot", "开心"),
    # 节日
    (r"halloween|spooky|pumpkin|ghostly|frankenstein|scary", "万圣节"),
    (r"christmas|xmas|santa|reindeer|logmas|jingle|holiday|present", "圣诞节"),
    (r"birthday|birthday", "生日"),
    (r"lny|chinese new year|lantern|festival", "新年"),
    (r"easter|bunny|rabbit|egg", "复活节"),
    (r"valentine|lenny", "情人节"),
    # 音乐
    (r"music|melody|note|violin|piano", "音乐"),
    # 游戏 / 电子
    (r"game|console|arcade|atari|retro|nintendo|pixel|8bit|wii", "打游戏"),
    (r"phone|selfie|phot|stream|camera|video", "拍照"),
    (r"text|letter|envelope|mail|typing", "发消息"),
    # 耍酷 / 自夸
    (r"sunglass|shades|badass|handsome|gorgeous|boss|almighty|supervillain", "耍酷"),
    (r"flex|muscle|bicep|gym|strong|pe?cs|gorilla|buff", "秀肌肉"),
    (r"mew|kawaii|anime|pretty|cutie|innocent|sparkle", "卖萌"),
    (r"sexy|flirt|seduct|hearteyes|wink", "放电"),
    # 嘲讽
    (r"taunt|mock|tease|brag|showoff|troll", "嘲讽"),
    (r"derp|silly|goofy|dumb|awkw|clueless", "犯傻"),
    (r"embarrass|shy|awkward|blush|wrap", "害羞"),
    # 跑步 / 移动
    (r"run|sprint|dash|charge|gallop|ride|flying|fly|leap", "冲刺"),
    (r"walk|stroll|stride|march", "走路"),
    (r"spin|spiral|twirl|roll|somersau", "转圈"),
    # 睡觉状态
    (r"wak|wakeup|rise|alarm|awake", "醒来"),
    # 更多常见后缀（越具体越靠前，放在通用兜底之前）
    (r"8bit|pixel|retro|backintime", "像素风"),
    (r"banjo|trumpet|violin|piano|sax|horn|guitar", "演奏"),
    (r"\bbow\b|longbow", "射箭"),
    (r"braid|plait", "编发"),
    (r"hood|cloak|hat\b", "兜帽"),
    (r"slomo|slow.?motion|freeze.?frame", "慢镜头"),
    (r"supersight|super.?sight", "瞄准"),
    (r"polish|sharpening|sharpen|whet", "磨刀"),
    (r"moustache|mustache|beard", "胡子"),
    (r"robot|mech|android", "机器人"),
    (r"coin|gold|treasure|gem|rich", "金币"),
    (r"cake|cake", "蛋糕"),
    # 通用兜底
    (r"emote|starter|emoji|mood|feeling|sign|gesture", "表情"),
]

DEFAULT_MEANING = "表情"


def _fallback_meaning(filename: str) -> str:
    """翻不出中文时保留原英文名（去掉扩展名）。"""
    return filename


def detect_meaning(filename: str) -> str:
    """返回文件名对应的中文含义词（1~4 字）。翻译不到时保留原英文名。"""
    name = filename.lower()
    # 先查覆盖面更大的 MEANING_RULES（更具体），再查内置 ACTION_RULES
    for pattern, meaning in MEANING_RULES + ACTION_RULES:
        if re.search(pattern, name):
            return meaning
    return _fallback_meaning(filename)


# ---------------------------------------------------------------------------
# 分组逻辑
# ---------------------------------------------------------------------------
def make_album_name(character, chunk_idx):
    """微信专辑名最多 8 字。用「皇战」+分类名 (+序号)，保证 ≤8 字且不重名。"""
    base = "皇战" + character
    if chunk_idx > 1:
        s = str(chunk_idx)
        return base[: 8 - len(s)] + s
    return base[:8]


def group_albums(files):
    """按角色分组；每角色内再按 ≤MAX_PER_ALBUM 拆分，返回专辑列表。"""
    by_character = OrderedDict()
    for f in files:
        f = Path(f)
        name = f.stem
        character = detect_character(name)
        meaning = detect_meaning(name)
        by_character.setdefault(character, []).append({
            "file": str(f),
            "name": name,
            "meaning": meaning,
        })

    # 每个角色内部按文件名排序，保证稳定顺序
    for c in by_character:
        by_character[c].sort(key=lambda x: x["name"].lower())

    albums = []
    for character, emotes in by_character.items():
        # 分拆成多组
        chunks = [emotes[i:i + MAX_PER_ALBUM] for i in range(0, len(emotes), MAX_PER_ALBUM)]
        for idx, chunk in enumerate(chunks):
            album_name = make_album_name(character, idx + 1)
            # 同一专辑内保证含义词尽量不重复：重复则追加数字
            final_emotes = _dedupe_meanings(chunk)
            albums.append({
                "index": len(albums) + 1,
                "name": album_name,
                "character": character,
                "emote_count": len(final_emotes),
                "emotes": final_emotes,
            })
    return albums


def _dedupe_meanings(emotes):
    """保证同一专辑内含义词唯一；重复含义追加数字，如 攻击 -> 攻击1 -> 攻击2。"""
    seen = {}
    out = []
    for e in emotes:
        m = e["meaning"]
        if m in seen:
            seen[m] += 1
            e = dict(e)
            e["meaning"] = f"{m}{seen[m]}"
        else:
            seen[m] = 0
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="扫描 GIF 并按角色分组导出 manifest.json")
    parser.add_argument("--src", default=r"D:\夸克网盘\cr_emotes", help="GIF 所在目录")
    parser.add_argument("--out", default="manifest.json", help="输出的 manifest 文件")
    args = parser.parse_args()

    src = Path(args.src)
    if not src.is_dir():
        raise SystemExit(f"[错误] 目录不存在: {src}")

    gifs = sorted(src.glob("*.gif")) + sorted(src.glob("*.GIF"))
    # 去重（避免大小写不同重复）
    seen_files = set()
    gifs = [g for g in gifs if str(g).lower() not in seen_files and not seen_files.add(str(g).lower())]
    if not gifs:
        raise SystemExit("[错误] 未找到任何 GIF 文件")

    albums = group_albums(gifs)

    manifest = {
        "source_dir": str(src),
        "total_files": len(gifs),
        "album_count": len(albums),
        "albums": albums,
    }

    out_path = Path(args.out)
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=2)

    # 打印摘要
    print(f"总文件数 : {len(gifs)}")
    print(f"专辑数   : {len(albums)}")
    print("-" * 60)
    for a in albums:
        print(f"  [{a['index']:>2}] {a['name']:<16} x{a['emote_count']:>2}")
    print("-" * 60)
    print(f"已写出: {out_path.resolve()}")


if __name__ == "__main__":
    main()
