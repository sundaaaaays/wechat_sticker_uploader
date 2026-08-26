# wechat-sticker-uploader

微信表情开放平台「表情专辑」批量上传自动化工具（基于 Selenium + Pillow）。

扫描本地 GIF → 自动识别角色/含义词 → 分组 → 压缩到 500KB 内 → 自动登录复用会话 →
逐个上传并填写专辑信息（名称/介绍/版权/横幅/封面/图标/角色/风格/主题/地区）→ 保存草稿/提交送审。

> ⚠️ **版权提示**：微信对取材于游戏/他人作品的表情要求提交版权授权证明。
> 请确保素材由你原创或已获得授权，否则会被平台驳回。本工具只做自动化，不代你解决授权。
> 本项目完全是 CLI 工具，**不上传任何素材文件**。

---

## 目录结构

```
wechat_sticker_uploader/
├── classify.py         # 扫描 GIF → 识别角色 + 含义词 → 分组(≤24/专辑) → manifest.json
├── compress.py         # 把超限 GIF 压缩到 ≤500KB（去残影、保宽高、保帧率）
├── upload.py           # Selenium 按 manifest 逐个上传专辑（附着已登录 Edge）
├── meaning_map.py      # 英文关键词 → 中文含义词 映射表（可编辑）
├── start-edge.bat      # 开启带调试端口的专用 Edge（复用登录）
├── config.json         # 所有参数（版权方、文案、图片、地区、延时……）
├── requirements.txt
└── tools/              # 辅助脚本（生成图、重建清单、整理分组等）
```

---

## 安装

```powershell
pip install -r requirements.txt
pip install pillow
```

- 需已安装 **Microsoft Edge**；Selenium 4.6+ 自动管理对应的 `msedgedriver`，无需手动配置。

---

## 数据准备

素材 GIF 已放在本仓库的 [`emotes/`](emotes/) 目录下。
也可把你自己的 GIF 放到任意目录，然后用 `--src` 指定：

```powershell
python classify.py --src "emotes" --out manifest.json
```

- 自动识别每个 GIF 的角色（`弓箭手`、`飞龙宝宝`…）与含义词（`射箭`、`哭泣`…）。
- 同一角色超过 24 个自动拆分为 `皇战弓箭手`、`皇战弓箭手2`…（微信专辑名 ≤8 字）。
- 结果写入 `manifest.json`。

可选：压缩超限 GIF（微信限制单图 ≤500KB）：

```powershell
python compress.py --max-kb 500
```

压缩策略：**保留原始宽高、保留全部帧、去除残影、只降调色板颜色**。

---

## 登录（复用你已登录的 Edge）

微信登录是会话级 cookie，需**保持窗口开启**。本项目附着到你已登录的 Edge：

1. **完全退出 Edge**，运行 `start-edge.bat`（用专用 profile `edge_attach/` + 端口 9222 开启）。
2. 在打开的 Edge 里用微信扫码登录。
3. 验证与附着：

```powershell
python upload.py --check     # 已登录状态：是
```

> 请**保持该 Edge 窗口开启**，后续上传都附着它。

---

## 上传专辑

```powershell
python upload.py --start 1 --limit 10     # 从第 1 张开始，最多 10 张
python upload.py                          # 全部
python upload.py --dry-run                # 只填写不保存（验证流程）
python upload.py --final-submit           # 真正提交送审（不可逆）
```

每个专辑会自动填写：动态表情类型 → 批量上传 GIF → 填含义词 → 名称/介绍/版权 →
横幅/封面/图标 → 类型(卡通表情/其他) → 角色(人物角色→游戏角色) → 风格/主题 → 地区 → 保存。

主要参数在 `config.json`（`copyright_holder`、`album_intro`、`banner`、`cover`、`icon`、
`style`、`theme`、`up_region`、`max_file_kb` 等）。

---

## tools/ 辅助脚本

| 脚本 | 作用 |
| --- | --- |
| `generate_images.py` | 生成横幅/封面/图标占位图 |
| `gen_covers.py` | 每个专辑生成「该专辑 GIF 拼图」封面（第 12 帧） |
| `gen_icons.py` | 每个专辑生成图标（首表情第 12 帧 / 通用用封面同款） |
| `rename_albums.py` / `rebuild_manifest.py` | 重命名 / 重建 manifest |
| `refresh_meanings.py` | 刷新含义词 |
| `compact_folders.py` / `restore_names.py` | 整理/恢复分组文件夹 |

---

## 免责声明

- 本工具仅供学习与自动化你**合法拥有**的素材；请勿用于侵权内容。
- 上传前请确认你的表情素材不侵犯第三方版权，或已取得游戏/作品版权方授权。
- 平台规则可能变化，选择器（`upload.py` 内 `class Sel`）可能需按实际页面微调。
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
[DSH Codex Desktop](https://github.com/MichengAI/dsh-codex-desktop)
[Apache License 2.0](LICENSE)
[Semidia/dsh-session-manager](https://github.com/Semidia/dsh-session-manager)
