#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upload.py — 微信表情开放平台「表情专辑」批量上传自动化（Selenium）

流程（对应三张截图）：
  我的表情 -> 提交作品 -> 表情专辑 -> 填写表单 -> 保存/提交

核心约束：
  - 只在本地 Chrome 复用已登录的 profile（首次用 --login 扫码登录一次，之后复用 session）
  - 每个专辑最多 24 张（classify.py 已拆分）
  - 自动填写专辑名/介绍/版权方、含义词、风格/主题/地区等
  - 默认点击「保存」存为草稿；加 --final-submit 才会真正「提交」送审（不可逆）
  - 加入随机延时，模拟人工操作，降低风控概率

用法：
  python upload.py --login               # 打开浏览器，扫码登录（一次即可）
  python upload.py --probe               # 进入提交页，打印页面上的输入控件/按钮，帮助校准选择器
  python upload.py                       # 按 manifest 逐个上传专辑（存为草稿）
  python upload.py --start 5 --limit 3   # 从第 5 个专辑开始，最多处理 3 个
  python upload.py --final-submit        # 草稿阶段结束后，真正提交送审
"""

import argparse
import json
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException, StaleElementReferenceException

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
MANIFEST_PATH = BASE_DIR / "manifest.json"


# --------------------------------------------------------------------------
# 配置加载
# --------------------------------------------------------------------------
def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as fp:
        return json.load(fp)


def load_manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as fp:
        return json.load(fp)


# --------------------------------------------------------------------------
# 选择器（全部集中在此，方便按实际页面微调）
# 每个条目是一组候选「定位策略」，按顺序尝试；命中第一个即可。
# 策略格式：(By, selector, 可选文本) 或 (By, selector)
# --------------------------------------------------------------------------
class Sel:
    # 顶部导航“我的表情”
    NAV_MY_EMOTION = [
        (By.XPATH, "//*[contains(@class,'nav') or contains(@class,'tab')]//*[contains(text(),'我的表情')]"),
        (By.XPATH, "//a[contains(text(),'我的表情')]"),
        (By.XPATH, "//*[contains(text(),'我的表情')]"),
    ]
    # 直接用专辑提交页 URL，绕开“提交作品”下拉
    SUBMIT_ALBUM_URL = "/cgi-bin/mmemoticonwebnode-bin/pages/stickerPage/detail"
    # 类型：动态表情（上传表情卡片的单选；文本在子 span，需按类匹配）
    TYPE_DYNAMIC = [
        (By.XPATH, "//span[contains(@class,'weui-desktop-form__check-c') and contains(text(),'动态表情')]"),
        (By.XPATH, "//*[contains(@class,'check-content') and contains(text(),'动态表情')]"),
        (By.XPATH, "//*[contains(text(),'动态表情')]"),
    ]
    # 表情文件上传：第一个含 gif 的隐藏 input[type=file]（webuploader）
    EMOTE_FILE_INPUT = [
        (By.XPATH, "//input[@type='file'][contains(@accept,'gif')]"),
    ]
    # 含义词输入框（每个上传的表情一个，占位符=输入含义词）
    MEANING_INPUT = [
        (By.XPATH, "//input[@placeholder='输入含义词']"),
        (By.XPATH, "//*[contains(text(),'含义词')]/following::input[1]"),
    ]
    # 专辑名称 / 介绍 / 版权方
    ALBUM_NAME = [(By.XPATH, "//input[@placeholder='填写表情专辑名称']"),
                  (By.XPATH, "//input[@placeholder and contains(@placeholder,'名称')]")]
    ALBUM_INTRO = [(By.XPATH, "//textarea[@placeholder='描述表情的特点和故事']")]
    COPYRIGHT = [(By.XPATH, "//input[@placeholder='填写版权信息']"),
                 (By.XPATH, "//input[@placeholder and contains(@placeholder,'版权')]")]
    # 横幅 / 封面 / 图标：按 accept 精确定位（index 0=横幅, 1=封面, 2=图标）
    BANNER_INPUT = [(By.XPATH, "//input[@type='file'][@accept='image/png,image/jpeg,image/jpg']")]
    COVER_INPUT = [(By.XPATH, "//input[@type='file'][@accept='image/png']")]
    ICON_INPUT = [(By.XPATH, "//input[@type='file'][@accept='image/png']")]
    # 类型：卡通表情/其他（附加信息卡片）
    TYPE_CARTOON = [
        (By.XPATH, "//label[contains(text(),'卡通表情')]"),
        (By.XPATH, "//*[contains(text(),'卡通表情')]"),
    ]
    # 角色/内容 级联下拉触发器（weui-desktop-form__dropdowncascade，显示“未选择”）
    ROLE_DROPDOWN = [
        (By.XPATH, "//*[contains(@class,'weui-desktop-form__dropdowncascade__dt')][contains(@class,'placeholder')]"),
        (By.XPATH, "//*[contains(@class,'dropdowncascade') and contains(text(),'未选择')]"),
    ]
    # 下拉展开后的候选项（级联菜单 li）
    ROLE_OPTION = [
        (By.XPATH, "//li[contains(@class,'weui-desktop-dropdown__list-ele')]"),
    ]
    # 勾选项（风格/主题/地区）——用文本点击
    LABEL_TEXT = [
        (By.XPATH, "//*[contains(@class,'weui-desktop-form__check-content') and contains(text(),'{t}')]"),
        (By.XPATH, "//label[contains(text(),'{t}')]"),
        (By.XPATH, "//*[contains(text(),'{t}')]"),
    ]
    # 尺寸：横幅(JPG/PNG)、封面(PNG)、图标(PNG) 的统一上传（accepted by specific selector separately）
    # 保存（草稿）
    SAVE_BUTTON = [
        (By.XPATH, "//button[contains(text(),'保存')]"),
        (By.XPATH, "//*[contains(@class,'btn') and contains(text(),'保存')]"),
    ]
    # 提交（送审）
    SUBMIT_BUTTON = [
        (By.XPATH, "//button[contains(text(),'提交')]"),
        (By.XPATH, "//*[contains(@class,'btn') and contains(text(),'提交')]"),
    ]


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------
def human_delay(config, factor=1.0):
    lo = config.get("min_sleep", 0.6) * factor
    hi = config.get("max_sleep", 1.8) * factor
    time.sleep(random.uniform(lo, hi))


def find_one(driver, strategies, timeout=10):
    """按一组候选策略查找「可见」元素，找到即返回；找不到返回 None。"""
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in strategies:
            try:
                for el in driver.find_elements(by, sel):
                    if el.is_displayed():
                        return el
            except (NoSuchElementException, WebDriverException):
                continue
        time.sleep(0.2)
    return None


def find_many(driver, strategies, timeout=6):
    """收集所有命中的元素（用于含义词输入框、风格勾选）。"""
    end = time.time() + timeout
    last = []
    while time.time() < end:
        for by, sel in strategies:
            try:
                els = driver.find_elements(by, sel)
                vis = [e for e in els if e.is_displayed()]
                if vis:
                    last = vis
                    if len(vis) >= 2:
                        return vis
            except (NoSuchElementException, WebDriverException):
                continue
        time.sleep(0.2)
    return last


def find_any(driver, strategies, timeout=8):
    """查找元素且【不要求可见】——用于隐藏的 file input。命中第一个即返回。"""
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in strategies:
            try:
                els = driver.find_elements(by, sel)
                if els:
                    return els[0]
            except (NoSuchElementException, WebDriverException):
                continue
        time.sleep(0.2)
    return None


def find_nth(driver, strategies, n, timeout=8):
    """查找第 n 个（0-based）隐藏元素——用于区分封面/图标这类相同 accept 的上传框。"""
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in strategies:
            try:
                els = driver.find_elements(by, sel)
                if len(els) > n:
                    return els[n]
            except (NoSuchElementException, WebDriverException):
                continue
        time.sleep(0.2)
    return None


def click(driver, strategies, timeout=10, scroll=True):
    el = find_one(driver, strategies, timeout)
    if not el:
        raise RuntimeError(f"未找到可点击元素: {strategies}")
    if scroll:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    el.click()
    return el


def set_text(driver, strategies, value, timeout=10, clear=True):
    end = time.time() + timeout
    while time.time() < end:
        el = find_one(driver, strategies, timeout=3)
        if el:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                if clear:
                    el.send_keys(Keys.CONTROL, "a")
                    el.send_keys(Keys.DELETE)
                el.send_keys(value)
                return el
            except (StaleElementReferenceException, WebDriverException):
                time.sleep(0.5)
                continue
        time.sleep(0.3)
    raise RuntimeError(f"未找到可输入元素: {strategies}")


def upload(driver, file_input_strategies, abs_path, timeout=15):
    """对某个隐藏的 file input 上传本地文件（忽略可见性）；元素失效时重试。"""
    end = time.time() + timeout
    while time.time() < end:
        el = find_any(driver, file_input_strategies, timeout=3)
        if el:
            try:
                el.send_keys(abs_path)
                return abs_path
            except (StaleElementReferenceException, WebDriverException):
                time.sleep(1)
                continue
        time.sleep(0.3)
    raise RuntimeError(f"未找到上传控件: {file_input_strategies}")


def find_btn(driver, text, timeout=8):
    """按渲染文本 .text 精确查找按钮（微信把按钮文字放在子节点，contains(text()) 匹配不到）。"""
    xp = "//button | //a[contains(@class,'btn')] | //*[@role='button']"
    end = time.time() + timeout
    while time.time() < end:
        for el in driver.find_elements(By.XPATH, xp):
            try:
                if el.is_displayed() and (el.text or '').strip() == text:
                    return el
            except (StaleElementReferenceException, WebDriverException):
                continue
        time.sleep(0.3)
    return None


def upload_icon(driver, icon_path):
    """图标与封面的 accept 相同（都是 png），因此取【第 2 个】png 输入框上传。"""
    if not (icon_path and Path(icon_path).exists()):
        return
    el = find_nth(driver, Sel.COVER_INPUT, 1, timeout=8)
    if not el:
        print("  [提示] 未找到图标上传框")
        return
    for _ in range(3):
        try:
            el.send_keys(str(Path(icon_path).resolve()))
            return
        except WebDriverException:
            time.sleep(1)
    print("  [提示] 图标上传失败")


def click_option(driver, text, timeout=8):
    """按选项文本（rendered text）点击其 radio/checkbox input。

    微信表单把文本放在子 span 里，且选项文字不一定是一个直接文本节点，
    因此用 normalize-space() 精确匹配 check-content，再点击其所属 label 内的 input。
    会点击所有匹配项（例如上架/下载地区同为「中国大陆」，应都选中）。
    """
    xp = ("//label[(.//*[contains(@class,'check-content') and normalize-space()="
          + repr(text) + "])]//input")
    end = time.time() + timeout
    while time.time() < end:
        els = driver.find_elements(By.XPATH, xp)
        if els:
            for el in els:
                try:
                    driver.execute_script("arguments[0].click();", el)
                except WebDriverException:
                    pass
            return True
        time.sleep(0.3)
    return False


def click_li(driver, text, timeout=6):
    """在级联下拉里点击文本为 text 的 li 选项（用 JS 点击）。"""
    xp = ("//li[contains(@class,'weui-desktop-dropdown__list-ele') and normalize-space()="
          + repr(text) + "]")
    end = time.time() + timeout
    while time.time() < end:
        for el in driver.find_elements(By.XPATH, xp):
            try:
                driver.execute_script("arguments[0].click();", el)
                return True
            except WebDriverException:
                continue
        time.sleep(0.3)
    return False


def retry(fn, config, tries=3, wait=10):
    """重试封装：失败后等待 wait 秒再试，最多 tries 次。"""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            print(f"  [重试 {i+1}/{tries-1}] 出错: {e}，等待 {wait}s")
            time.sleep(wait)


# --------------------------------------------------------------------------
# 主控制器
# --------------------------------------------------------------------------
class StickerUploader:
    def __init__(self, config):
        self.config = config
        self.driver = self._build_driver()

    def _build_driver(self):
        browser = self.config.get("browser", "chrome").lower()
        opts = webdriver.ChromeOptions() if browser == "chrome" else webdriver.EdgeOptions()

        # 复用已登录会话：附着到已开启远程调试端口的浏览器，不新开窗口
        if self.config.get("attach_to_running", False):
            addr = self.config.get("debugger_address", "127.0.0.1:9222")
            opts.add_experimental_option("debuggerAddress", addr)
            opts.add_argument("--lang=zh-CN")
            if browser == "chrome":
                return webdriver.Chrome(options=opts)
            return webdriver.Edge(options=opts)

        # 否则：用一个独立 profile 新开浏览器（首次 --login 用）
        profile = str((BASE_DIR / self.config.get("profile_dir", "browser_profile")).resolve())
        opts.add_argument("--user-data-dir=" + profile)
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--lang=zh-CN")
        if self.config.get("headless", False):
            opts.add_argument("--headless=new")
        if browser == "chrome":
            return webdriver.Chrome(options=opts)
        return webdriver.Edge(options=opts)

    def open_home(self):
        base = self.config.get("base_url", "https://sticker.weixin.qq.com/")
        self.driver.get(base)
        time.sleep(3)

    def goto_my_emotion(self):
        click(self.driver, Sel.NAV_MY_EMOTION, timeout=12)
        time.sleep(2)

    def open_submit_album(self):
        """直接访问「提交表情专辑」页，绕开“提交作品”下拉（该下拉是 JS 懒加载）。"""
        base = self.config.get("base_url", "https://sticker.weixin.qq.com/").rstrip("/")
        self.driver.get(base + Sel.SUBMIT_ALBUM_URL)
        time.sleep(3)

    def set_type(self):
        if not click_option(self.driver, "动态表情"):
            raise RuntimeError("未找到「动态表情」类型选项")
        time.sleep(0.8)

    def upload_emotes(self, files):
        """批量一次多选上传所有 GIF（file input 支持 multiple，投喂换行分隔路径）。"""
        if not files:
            return
        paths = "\n".join(str(Path(f).resolve()) for f in files)
        upload(self.driver, Sel.EMOTE_FILE_INPUT, paths)
        print(f"  已批量提交 {len(files)} 张，等待服务端生成缩略图…")

    def fill_meanings(self, meanings):
        """等待含义词框全部出现且数量稳定后，再逐个填入（避免边填边重渲染导致 stale）。"""
        want = len(meanings)
        end = time.time() + 90
        inputs = []
        last = -1
        stable = 0
        while time.time() < end:
            inputs = [e for e in self.driver.find_elements(By.XPATH, "//input[@placeholder='输入含义词']") if e.is_displayed()]
            cur = len(inputs)
            if cur >= want:
                time.sleep(4)
                break
            if cur == last:
                stable += 1
                if stable >= 8:   # 连续 ~8s 无新增 → 视为稳定
                    break
            else:
                stable = 0
                last = cur
            time.sleep(1)
        if not inputs:
            print("  [提示] 未找到含义词输入框，跳过含义填写")
            return
        for i, meaning in enumerate(meanings):
            if i >= len(inputs):
                break
            val = meaning or self.config.get("default_meaning", "表情")
            if self._fill_one_meaning(i, val):
                print(f"  含义词[{i+1}] = {val}")
                human_delay(self.config, factor=0.4)
            else:
                print(f"  [提示] 含义词[{i+1}] 未能填入")

    def _fill_one_meaning(self, idx, val):
        """第 idx 个含义词框，独立重查并填入（重试防 stale）。"""
        for _ in range(6):
            els = [e for e in self.driver.find_elements(By.XPATH, "//input[@placeholder='输入含义词']") if e.is_displayed()]
            if idx < len(els):
                el = els[idx]
                try:
                    el.send_keys(Keys.CONTROL, "a")
                    el.send_keys(Keys.DELETE)
                    el.send_keys(val)
                    return True
                except (StaleElementReferenceException, WebDriverException):
                    time.sleep(0.6)
                    continue
            time.sleep(0.3)
        return False

    def fill_basic(self, album):
        # 名称
        set_text(self.driver, Sel.ALBUM_NAME, album["name"])
        human_delay(self.config)
        # 介绍：角色专辑写对应人物，通用表情用通用文案
        set_text(self.driver, Sel.ALBUM_INTRO, self._intro_for(album))
        human_delay(self.config)
        # 版权（SY工作室）
        set_text(self.driver, Sel.COPYRIGHT, self.config.get("copyright_holder", ""))
        human_delay(self.config)
        # 横幅 / 封面 / 图标
        banner = self._resolve_path(self.config.get("banner"))
        cover_path = BASE_DIR / "covers" / f"{album['index']}.png"
        if not cover_path.exists():
            cover_path = self._resolve_path(self.config.get("cover"))
        icon_path = BASE_DIR / "icons" / f"{album['index']}.png"
        if not icon_path.exists():
            icon_path = self._resolve_path(self.config.get("icon"))
        if banner and banner.exists():
            upload(self.driver, Sel.BANNER_INPUT, str(banner.resolve()))
            human_delay(self.config)
        if cover_path and cover_path.exists():
            upload(self.driver, [Sel.COVER_INPUT[0]], str(cover_path.resolve()))
            human_delay(self.config)
            # 图标是“第 2 个 png”，重新查询后跳过一个
            upload_icon(self.driver, icon_path)

    def _resolve_path(self, p):
        """把相对路径解析到本项目根目录，便于仓库内直接运行。"""
        if not p:
            return None
        pp = Path(p)
        return pp if pp.is_absolute() else BASE_DIR / pp

    def _intro_for(self, album):
        """角色专辑：介绍对应人物；通用表情专辑：用通用文案。"""
        char = album.get("character", "")
        if char and char != "通用表情":
            return f"《皇室战争》{char}的经典高清动态表情，还原角色标志性动作与情绪，为聊天增添趣味。"
        return self.config.get("album_intro", "")

    def check(self, text):
        """按文本点击某个风格/主题/地区选项。"""
        return click_option(self.driver, text)

    def select_role(self, character):
        """打开角色/内容级联下拉并选择：一级「人物角色」→ 二级「游戏角色」（皇室战争都是游戏角色）。"""
        trig = find_one(self.driver, Sel.ROLE_DROPDOWN, timeout=8)
        if not trig:
            print("  [提示] 未找到角色/内容下拉触发器")
            return False
        try:
            self.driver.execute_script("arguments[0].click();", trig)
        except WebDriverException:
            trig.click()
        time.sleep(0.8)
        # 一级
        if not click_li(self.driver, "人物角色"):
            print("  [提示] 未找到一级选项「人物角色」")
            # 兜底：直接尝试匹配角色名
            if click_li(self.driver, character):
                return True
            return False
        time.sleep(0.8)
        # 二级：优先匹配具体角色名，找不到则选「游戏角色」
        if click_li(self.driver, character):
            return True
        if click_li(self.driver, "游戏角色"):
            return True
        print(f"  [提示] 二级下拉中未找到『{character}』或「游戏角色」，需人工选择")
        return False

    def fill_extra(self, album):
        if not click_option(self.driver, "卡通表情/其他"):
            print("  [提示] 未找到「卡通表情/其他」类型选项")
        time.sleep(0.6)
        self.select_role(album.get("character", ""))
        # 风格 + 主题
        for s in self.config.get("style", ["搞笑", "日常"]) + self.config.get("theme", ["游戏"]):
            self.check(s)
            human_delay(self.config, factor=0.4)
        # 地区
        self.check(self.config.get("up_region", "中国大陆"))
        self.check(self.config.get("download_region", "中国大陆"))

    def save_draft(self):
        btn = find_btn(self.driver, "保存", timeout=10)
        if not btn:
            raise RuntimeError("未找到「保存」按钮")
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            self.driver.execute_script("arguments[0].click();", btn)
        except WebDriverException:
            btn.click()
        time.sleep(3)

    def submit(self):
        btn = find_btn(self.driver, "提交", timeout=10)
        if not btn:
            raise RuntimeError("未找到「提交」按钮")
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            self.driver.execute_script("arguments[0].click();", btn)
        except WebDriverException:
            btn.click()
        time.sleep(3)

    def probe(self):
        """进入「提交表情专辑」页并打印控件，用于校准选择器。"""
        self.open_submit_album()
        time.sleep(3)
        print("=== 当前 URL ===")
        print(self.driver.current_url)
        print("--- input / textarea ---")
        for e in self.driver.find_elements(By.XPATH, "//input | //textarea"):
            try:
                if e.is_displayed():
                    print("  <%s> type=%r ph=%r" % (e.tag_name, e.get_attribute('type') or '', e.get_attribute('placeholder') or ''))
            except WebDriverException:
                pass
        print("--- 可见 button ---")
        for e in self.driver.find_elements(By.XPATH, "//button"):
            try:
                if e.is_displayed() and (e.text or '').strip():
                    print("  ", (e.text or '').strip()[:20])
            except WebDriverException:
                pass
        print("--- 可见 label 选项 ---")
        seen = set()
        for e in self.driver.find_elements(By.XPATH, "//label | //*[contains(@class,'check-content')] | //*[contains(@class,'tag')]"):
            try:
                t = (e.text or '').strip()
                if t and e.is_displayed() and t not in seen:
                    seen.add(t); print("  ", t[:24])
            except WebDriverException:
                pass
        print("--- 文件上传框 accept ---")
        for i, e in enumerate(self.driver.find_elements(By.XPATH, "//input[@type='file']")):
            print("  [%d] accept=%r" % (i, e.get_attribute('accept') or ''))

    def check_login(self):
        """验证是否已附着到 Edge 并已登录。"""
        self.open_home()
        nav = find_many(self.driver, Sel.NAV_MY_EMOTION, timeout=6)
        logged_in = bool(nav)
        print(f"当前 URL   : {self.driver.current_url}")
        print(f"已登录状态 : {'是（找到「我的表情」）' if logged_in else '否 / 待确认'}")
        if not logged_in:
            print("提示：若看到的是登录/扫码按钮，说明 session 未带上，请检查 start-edge.bat 用的 profile 是否为已登录的那个。")
        return logged_in

    def close(self):
        """结束后收尾。附着模式（attach_to_running）下不会关闭用户打开的 Edge 窗口。"""
        if not self.config.get("attach_to_running", False):
            try:
                self.driver.quit()
            except WebDriverException:
                pass

    def run(self, start=1, limit=None, final_submit=False, dry_run=False):
        manifest = load_manifest()
        albums = manifest["albums"]
        if limit:
            albums = albums[start - 1:start - 1 + limit]
        else:
            albums = albums[start - 1:]

        for idx, album in enumerate(albums, start=start):
            print(f"\n===== 处理专辑 {idx}/{len(manifest['albums'])}: {album['name']} =====")
            try:
                self.open_submit_album()
                time.sleep(2)
                self.set_type()
                files = [e["file"] for e in album["emotes"]]
                self.upload_emotes(files)
                self.fill_meanings([e["meaning"] for e in album["emotes"]])
                self.fill_basic(album)
                self.fill_extra(album)
                human_delay(self.config, factor=1.5)
                if dry_run:
                    print("  [DRY] 已填完但【未保存】，离开页面（不产生草稿）。")
                    self.driver.get(self.config.get("base_url", "https://sticker.weixin.qq.com/"))
                elif final_submit:
                    self.submit()
                else:
                    self.save_draft()
                human_delay(self.config, factor=2)
            except Exception as e:  # noqa: BLE001
                print(f"  [跳过] 专辑 {album['name']} 处理出错: {e}")
                try:
                    self.driver.get(self.config.get("base_url", "https://sticker.weixin.qq.com/"))
                except Exception:
                    pass
        self.close()
        print("\n全部处理完成。")


def main():
    ap = argparse.ArgumentParser(description="微信表情专辑批量上传")
    ap.add_argument("--login", action="store_true", help="打开浏览器扫码登录（独立 profile 时一次即可）")
    ap.add_argument("--check", action="store_true", help="检查是否已附着 Edge 且已登录")
    ap.add_argument("--probe", action="store_true", help="提交页控件探测，用于校准选择器")
    ap.add_argument("--start", type=int, default=1, help="起始专辑序号（从 1 开始）")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 个专辑")
    ap.add_argument("--final-submit", action="store_true", help="点击「提交」送审（不可逆），否则只点「保存」存草稿")
    ap.add_argument("--dry-run", action="store_true", help="只填写不保存/提交（不产生草稿），用于验证流程")
    args = ap.parse_args()

    config = load_config()
    up = StickerUploader(config)

    try:
        if args.check:
            up.check_login()
        elif args.login:
            print("【第一步】正在附着到 9222 端口运行的那个 Edge 窗口。")
            up.open_home()
            note = ("请在弹出的 Edge 窗口中点击登录，用微信扫码。"
                    "登录成功、看到「我的表情」后，回到本窗口按回车继续…")
            input(">> " + note + "\n")
            up.check_login()
            print("\n>> 已登录。请【保持这个 Edge 窗口一直开着】——微信登录是会话级 cookie，")
            print(">> 关掉就掉线。后续 --probe / --run 都会附着它复用登录。")
        elif args.probe:
            up.probe()
        else:
            up.run(start=args.start, limit=args.limit, final_submit=args.final_submit, dry_run=args.dry_run)
    finally:
        up.close()


if __name__ == "__main__":
    main()
