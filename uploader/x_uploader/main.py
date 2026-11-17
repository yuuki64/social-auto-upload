# -*- coding: utf-8 -*-
"""X (Twitter) 视频上传器（浏览器自动化，非官方 API）。

X 没有在 social-auto-upload 的 CLI 中；此模块作为本地扩展使用。
登录：x_login(account_file, headless=False) 由用户本人完成登录，保存 storage_state。
发布：XVideo(...).main() 打开 x.com/compose/post，上传视频、填文本、点 Post。
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path

from patchright.async_api import Page, Playwright, async_playwright

from conf import BASE_DIR, LOCAL_CHROME_PATH
try:
    from conf import YT_PROXY
except Exception:
    YT_PROXY = None
from utils.log import create_logger

x_logger = create_logger("x", "logs/x.log")

COMPOSE_URL = "https://x.com/compose/post"
LOGIN_URL = "https://x.com/i/flow/login"


def _launch_kwargs(headless: bool) -> dict:
    kwargs = {
        "headless": headless,
        "proxy": {"server": YT_PROXY} if YT_PROXY else None,
        "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    }
    if LOCAL_CHROME_PATH:
        kwargs["executable_path"] = LOCAL_CHROME_PATH
    else:
        kwargs["channel"] = "chrome"
    return kwargs


async def x_cookie_auth(account_file: str | Path, headless: bool = False) -> bool:
    account_path = Path(account_file)
    if not account_path.is_file():
        return False
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_launch_kwargs(headless))
        context = await browser.new_context(storage_state=str(account_path))
        page = await context.new_page()
        try:
            selector = 'a[data-testid="AppTabBar_Home_Link"], div[data-testid="SideNav_AccountSwitcher_Button"]'
            for attempt in range(2):
                await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=90000)
                if "login" in page.url or "i/flow/login" in page.url:
                    return False
                try:
                    await page.locator(selector).first.wait_for(state="visible", timeout=20000)
                    return True
                except Exception:
                    if attempt == 1:
                        return False
                    await page.wait_for_timeout(2000)
            return False
        finally:
            await browser.close()


async def x_login(account_file: str, headless: bool = False) -> bool:
    account_path = Path(account_file)
    account_path.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**_launch_kwargs(headless))
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
        x_logger.info("请在打开的 X 页面登录；登录完成后会自动保存 cookie")
        ok = False
        for _ in range(600):
            try:
                if "x.com" in page.url and "/i/flow/login" not in page.url and "/login" not in page.url:
                    try:
                        await page.locator('a[data-testid="AppTabBar_Home_Link"], div[data-testid="SideNav_AccountSwitcher_Button"]').first.wait_for(state="visible", timeout=5000)
                    except Exception:
                        await asyncio.sleep(1)
                        continue
                    await page.wait_for_timeout(2000)
                    await context.storage_state(path=str(account_path))
                    x_logger.success(f"X 登录态已保存: {account_path}")
                    ok = True
                    break
            except Exception:
                pass
            await asyncio.sleep(1)
        if not ok:
            x_logger.error(f"X 登录超时，当前 URL: {page.url}")
        await browser.close()
        return ok


class XVideo:
    def __init__(self, title: str, file_path: str, tags: list[str], account_file: str,
                 description: str = "", headless: bool = False):
        self.title = title
        self.file_path = str(file_path)
        self.tags = tags or []
        self.account_file = str(account_file)
        self.description = description or ""
        self.headless = headless

    def _text(self) -> str:
        tags = " ".join("#" + tag for tag in self.tags)
        parts = [self.title.strip(), self.description.strip(), tags.strip()]
        return "\n\n".join(part for part in parts if part).strip()

    async def upload(self, playwright: Playwright) -> str | None:
        browser = await playwright.chromium.launch(**_launch_kwargs(self.headless))
        context = await browser.new_context(storage_state=self.account_file)
        page = await context.new_page()
        page.set_default_timeout(60000)
        video_url = None
        try:
            await page.goto(COMPOSE_URL, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(4000)
            if "login" in page.url or "i/flow/login" in page.url:
                raise RuntimeError("X 登录态失效，请重新执行 x_login")

            # 等编辑器出现
            editor = page.locator('div[data-testid="tweetTextarea_0"], div[role="textbox"][contenteditable="true"]').first
            await editor.wait_for(state="visible", timeout=60000)

            # 上传视频
            file_input = page.locator('input[data-testid="fileInput"], input[type="file"][accept*="video"]').first
            await file_input.wait_for(state="attached", timeout=30000)
            await file_input.set_input_files(self.file_path)
            x_logger.info(f"已选择视频: {Path(self.file_path).name}")

            # 等媒体附件出现，且进度条消失
            try:
                await page.locator('div[data-testid="attachments"]').first.wait_for(state="visible", timeout=120000)
            except Exception:
                pass
            for _ in range(180):
                progress = page.locator('div[role="progressbar"]')
                if await progress.count() == 0:
                    break
                await asyncio.sleep(1)
            await page.wait_for_timeout(2000)

            # 填文本
            await editor.click()
            await page.keyboard.insert_text(self._text())
            await page.wait_for_timeout(1000)
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

            if os.environ.get("SAU_PAUSE_BEFORE_PUBLISH", "").lower() in ("1", "true", "yes"):
                review_dir = Path(BASE_DIR) / ".runtime-tmp"
                review_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = review_dir / f"x-review-{stamp}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)
                try:
                    body_text = await page.locator("body").first.inner_text()
                except Exception:
                    body_text = ""
                (review_dir / f"x-review-{stamp}.txt").write_text("BODY:\n" + body_text, encoding="utf-8")
                x_logger.info(f"发布前已暂停，截图: {screenshot_path}")
                flag_path = review_dir / "x-publish-go.flag"
                if flag_path.exists():
                    flag_path.unlink()
                for _ in range(1800):
                    if flag_path.exists():
                        decision = flag_path.read_text(encoding="utf-8").strip().lower()
                        flag_path.unlink()
                        if decision in {"go", "yes", "publish"}:
                            x_logger.info("收到发布确认，继续点击 Post")
                            break
                        raise RuntimeError(f"发布前被取消: {decision or 'empty'}")
                    await asyncio.sleep(1)
                else:
                    raise RuntimeError("等待发布确认超时，尚未点击 Post")

            post_button = page.locator('button[data-testid="tweetButton"]').first
            try:
                await page.wait_for_function(
                    """() => { const b = document.querySelector('button[data-testid="tweetButton"]'); return b && !b.disabled; }""",
                    timeout=120000,
                )
            except Exception:
                pass
            try:
                await post_button.click(timeout=15000)
            except Exception:
                await post_button.evaluate("el => el.click()")
            x_logger.info("已点击 Post，等待提交结果")

            sent = False
            for _ in range(60):
                await asyncio.sleep(1)
                try:
                    toast = page.locator('div[data-testid="toast"]')
                    if await toast.count():
                        text = await toast.first.inner_text()
                        if "sent" in text.lower() or "已发送" in text or "posted" in text.lower():
                            x_logger.success(f"X 发布成功: {text.strip()[:80]}")
                            link = toast.first.locator('a[href*="/status/"]').first
                            if await link.count():
                                href = await link.get_attribute("href")
                                if href:
                                    video_url = "https://x.com" + href if href.startswith("/") else href
                            sent = True
                            break
                    if await page.locator('div[data-testid="tweetTextarea_0"]').count() == 0:
                        x_logger.success("X 发布成功（编辑器已关闭）")
                        sent = True
                        break
                except Exception:
                    pass
            if not sent:
                x_logger.warning("点 Post 后未捕获到成功提示，需人工核验")

            try:
                await context.storage_state(path=self.account_file)
            except Exception:
                pass
        finally:
            await context.close()
            await browser.close()
        return video_url

    async def main(self) -> str | None:
        async with async_playwright() as playwright:
            return await self.upload(playwright)
