# -*- coding: utf-8 -*-
import re
from datetime import datetime

from patchright.async_api import Playwright, async_playwright
import os
import asyncio

from conf import LOCAL_CHROME_PATH, LOCAL_CHROME_HEADLESS
try:
    from conf import YT_PROXY
except Exception:
    YT_PROXY = None
from uploader.tk_uploader.tk_config import Tk_Locator
from utils.base_social_media import set_init_script
from utils.files_times import get_absolute_path
from utils.log import tiktok_logger


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        launch_kwargs = {
            "headless": False,
            "channel": "chrome",
            "proxy": {"server": YT_PROXY} if YT_PROXY else None,
            "args": ["--no-sandbox"],
        }
        if LOCAL_CHROME_PATH:
            launch_kwargs.pop("channel", None)
            launch_kwargs["executable_path"] = LOCAL_CHROME_PATH
        browser = await playwright.chromium.launch(**launch_kwargs)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://www.tiktok.com/tiktokstudio/upload?lang=en")
        await page.wait_for_load_state('networkidle')
        try:
            # 选择所有的 select 元素
            select_elements = await page.query_selector_all('select')
            for element in select_elements:
                class_name = await element.get_attribute('class')
                # 使用正则表达式匹配特定模式的 class 名称
                if re.match(r'tiktok-.*-SelectFormContainer.*', class_name):
                    tiktok_logger.error("[+] cookie expired")
                    return False
            tiktok_logger.success("[+] cookie valid")
            return True
        except:
            tiktok_logger.success("[+] cookie valid")
            return True


async def tiktok_setup(account_file, handle=False):
    account_file = get_absolute_path(account_file, "tk_uploader")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            return False
        tiktok_logger.info('[+] cookie file is not existed or expired. Now open the browser auto. Please login with your way(gmail phone, whatever, the cookie file will generated after login')
        await get_tiktok_cookie(account_file)
    return True


async def get_tiktok_cookie(account_file):
    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB',
            ],
            'headless': LOCAL_CHROME_HEADLESS,  # Set headless option here
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login?lang=en")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


class TiktokVideo(object):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None):
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.thumbnail_path = thumbnail_path
        self.account_file = account_file
        self.local_executable_path = LOCAL_CHROME_PATH
        self.headless = False
        self.locator_base = None

    async def set_schedule_time(self, page, publish_date):
        schedule_input_element = self.locator_base.get_by_label('Schedule')
        await schedule_input_element.wait_for(state='visible')  # 确保按钮可见

        await schedule_input_element.click(force=True)
        if await self.locator_base.locator('div.TUXButton-content >> text=Allow').count():
            await self.locator_base.locator('div.TUXButton-content >> text=Allow').click()

        scheduled_picker = self.locator_base.locator('div.scheduled-picker')
        await scheduled_picker.locator('div.TUXInputBox').nth(1).click()

        calendar_month = await self.locator_base.locator(
            'div.calendar-wrapper span.month-title').inner_text()

        n_calendar_month = datetime.strptime(calendar_month, '%B').month

        schedule_month = publish_date.month

        if n_calendar_month != schedule_month:
            if n_calendar_month < schedule_month:
                arrow = self.locator_base.locator('div.calendar-wrapper span.arrow').nth(-1)
            else:
                arrow = self.locator_base.locator('div.calendar-wrapper span.arrow').nth(0)
            await arrow.click()

        # day set
        valid_days_locator = self.locator_base.locator(
            'div.calendar-wrapper span.day.valid')
        valid_days = await valid_days_locator.count()
        for i in range(valid_days):
            day_element = valid_days_locator.nth(i)
            text = await day_element.inner_text()
            if text.strip() == str(publish_date.day):
                await day_element.click()
                break
        # time set
        await scheduled_picker.locator('div.TUXInputBox').nth(0).click()

        hour_str = publish_date.strftime("%H")
        correct_minute = int(publish_date.minute / 5)
        minute_str = f"{correct_minute:02d}"

        hour_selector = f"span.tiktok-timepicker-left:has-text('{hour_str}')"
        minute_selector = f"span.tiktok-timepicker-right:has-text('{minute_str}')"

        # pick hour first
        await page.wait_for_timeout(1000)  # 等待500毫秒
        await self.locator_base.locator(hour_selector).click()
        # click time button again
        await page.wait_for_timeout(1000)  # 等待500毫秒
        # pick minutes after
        await self.locator_base.locator(minute_selector).click()

        # click title to remove the focus.
        # await self.locator_base.locator("h1:has-text('Upload video')").click()

    async def handle_upload_error(self, page):
        tiktok_logger.info("video upload error retrying.")
        select_file_button = self.locator_base.locator('button[aria-label="Select file"]')
        async with page.expect_file_chooser() as fc_info:
            await select_file_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        launch_kwargs = {
            "headless": self.headless,
            "proxy": {"server": YT_PROXY} if YT_PROXY else None,
            "args": ["--no-sandbox"],
        }
        if self.local_executable_path:
            launch_kwargs["executable_path"] = self.local_executable_path
        else:
            launch_kwargs["channel"] = "chrome"
        browser = await playwright.chromium.launch(**launch_kwargs)
        context = await browser.new_context(storage_state=f"{self.account_file}")
        # context = await set_init_script(context)
        page = await context.new_page()

        # change language to eng first
        await self.change_language(page)
        await page.goto("https://www.tiktok.com/tiktokstudio/upload", wait_until="domcontentloaded", timeout=60000)
        tiktok_logger.info(f'[+]Uploading-------{self.title}.mp4')

        await page.wait_for_timeout(3000)

        try:
            await page.wait_for_selector('iframe[data-tt="Upload_index_iframe"], div.upload-container', timeout=10000)
            tiktok_logger.info("Either iframe or div appeared.")
        except Exception as e:
            tiktok_logger.error("Neither iframe nor div appeared within the timeout.")

        await self.choose_base_locator(page)

        upload_button = self.locator_base.locator(
            'button:has-text("Select video"):visible')
        await upload_button.wait_for(state='visible')  # 确保按钮可见

        async with page.expect_file_chooser() as fc_info:
            await upload_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)

        await self.dismiss_blocking_modals(page)
        await self.add_title_tags(page)
        # detect upload status
        await self.detect_upload_status(page)
        if self.thumbnail_path:
            tiktok_logger.info(f'[+] Uploading thumbnail file {self.title}.png')
            await self.upload_thumbnails(page)

        if self.publish_date != 0:
            await self.set_schedule_time(page, self.publish_date)

        if os.environ.get("SAU_PAUSE_BEFORE_PUBLISH", "").lower() in ("1", "true", "yes"):
            from pathlib import Path
            import json
            review_dir = Path(__file__).resolve().parents[2] / ".runtime-tmp"
            review_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = review_dir / f"tiktok-review-{stamp}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            try:
                body_text = await page.locator("body").first.inner_text()
            except Exception:
                body_text = ""
            review_text = review_dir / f"tiktok-review-{stamp}.txt"
            review_text.write_text("BODY:\n" + body_text, encoding="utf-8")
            tiktok_logger.info(f"发布前已暂停，截图: {screenshot_path}，页面文本: {review_text}")
            flag_path = review_dir / "tiktok-publish-go.flag"
            if flag_path.exists():
                flag_path.unlink()
            for _ in range(1800):
                if flag_path.exists():
                    decision = flag_path.read_text(encoding="utf-8").strip().lower()
                    flag_path.unlink()
                    if decision in {"go", "yes", "publish"}:
                        tiktok_logger.info("收到发布确认，继续点击发布")
                        break
                    raise RuntimeError(f"发布前被取消: {decision or 'empty'}")
                await asyncio.sleep(1)
            else:
                raise RuntimeError("等待发布确认超时，尚未点击发布")

        await self.click_publish(page)
        tiktok_logger.success(f"video_id: {await self.get_last_video_id(page)}")

        await context.storage_state(path=f"{self.account_file}")  # save cookie
        tiktok_logger.info('  [-] update cookie！')
        await asyncio.sleep(2)  # close delay for look the video status
        # close all
        await context.close()
        await browser.close()

    async def dismiss_blocking_modals(self, page):
        """关闭 TikTok 上传后弹出的“开启自动内容检查”等遮罩。"""
        try:
            await page.evaluate("""() => {
                document.querySelectorAll('.react-joyride__overlay, #react-joyride-portal').forEach(e => e.remove());
            }""")
            await page.wait_for_timeout(500)
        except Exception:
            pass
        for label in ("Skip", "Skip tour", "跳过", "跳过引导", "Got it", "知道了", "OK"):
            try:
                btn = page.get_by_role("button", name=label, exact=True).first
                if await btn.count() and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(500)
            except Exception:
                pass
        for text in ("Got it", "知道了"):
            try:
                loc = page.get_by_text(text, exact=True).first
                if await loc.count() and await loc.is_visible():
                    await loc.click()
                    await page.wait_for_timeout(1000)
            except Exception:
                pass
        try:
            await page.evaluate("""() => {
                document.querySelectorAll('.react-joyride__overlay, #react-joyride-portal').forEach(e => e.remove());
            }""")
            await page.wait_for_timeout(500)
        except Exception:
            pass
        try:
            text = page.get_by_text("Turn on automatic content checks?", exact=False).first
            if await text.count():
                cancel = page.get_by_role("button", name="Cancel", exact=True).first
                if await cancel.count():
                    await cancel.click()
                else:
                    await page.keyboard.press("Escape")
                tiktok_logger.info("已关闭 TikTok 自动内容检查弹窗")
                await page.wait_for_timeout(800)
        except Exception as exc:
            tiktok_logger.warning(f"关闭自动内容检查弹窗失败（继续尝试）: {exc}")

    async def add_title_tags(self, page):

        await self.dismiss_blocking_modals(page)
        try:
            await page.evaluate("""() => {
                const el = document.querySelector('div.public-DraftEditor-content');
                if (el) { el.focus(); el.click(); }
            }""")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        await page.keyboard.press("End")

        await page.keyboard.press("Control+A")

        await page.keyboard.press("Delete")

        await page.keyboard.press("End")

        await page.wait_for_timeout(1000)  # 等待1秒

        await page.keyboard.insert_text(self.title)
        await page.wait_for_timeout(1000)  # 等待1秒
        await page.keyboard.press("End")

        await page.keyboard.press("Enter")

        # tag part
        for index, tag in enumerate(self.tags, start=1):
            tiktok_logger.info("Setting the %s tag" % index)
            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)  # 等待1秒
            await page.keyboard.insert_text("#" + tag + " ")
            await page.keyboard.press("Space")
            await page.wait_for_timeout(1000)  # 等待1秒

            await page.keyboard.press("Backspace")
            await page.keyboard.press("End")

    async def upload_thumbnails(self, page):
        await self.locator_base.locator(".cover-container").click()
        await self.locator_base.locator(".cover-edit-container >> text=Upload cover").click()
        async with page.expect_file_chooser() as fc_info:
            await self.locator_base.locator(".upload-image-upload-area").click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(self.thumbnail_path)
        await self.locator_base.locator('div.cover-edit-panel:not(.hide-panel)').get_by_role(
            "button", name="Confirm").click()
        await page.wait_for_timeout(3000)  # wait 3s, fix it later

    async def change_language(self, page):
        # set the language to english (best-effort; TikTok 首页加载慢时直接跳过)
        try:
            await page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await page.wait_for_selector('[data-e2e="nav-more-menu"]', timeout=15000)
            if await page.locator('[data-e2e="nav-more-menu"]').text_content() == "More":
                return
            await page.locator('[data-e2e="nav-more-menu"]').click()
            await page.locator('[data-e2e="language-select"]').click()
            await page.locator('#creator-tools-selection-menu-header >> text=English (US)').click()
        except Exception as exc:
            tiktok_logger.warning(f"语言切换跳过（不影响上传）: {exc}")

    async def click_publish(self, page):
        deadline = loop_time = __import__("time").monotonic() + 180
        attempt = 0
        while __import__("time").monotonic() < deadline:
            attempt += 1
            try:
                publish_button = self.locator_base.locator('div.button-group button').nth(0)
                if await publish_button.count():
                    await publish_button.click()

                await page.wait_for_url("https://www.tiktok.com/tiktokstudio/content", timeout=5000)
                tiktok_logger.success("  [-] video published success")
                return
            except Exception as e:
                tiktok_logger.info(f"  [-] video publishing (attempt {attempt}): {e}")
                await asyncio.sleep(1)
        raise RuntimeError("TikTok 发布未在 180 秒内完成")

    async def get_last_video_id(self, page):
        await page.wait_for_selector('div[data-tt="components_PostTable_Container"]')
        video_list_locator = self.locator_base.locator('div[data-tt="components_PostTable_Container"] div[data-tt="components_PostInfoCell_Container"] a')
        if await video_list_locator.count():
            first_video_obj = await video_list_locator.nth(0).get_attribute('href')
            video_id = re.search(r'video/(\d+)', first_video_obj).group(1) if first_video_obj else None
            return video_id


    async def detect_upload_status(self, page):
        while True:
            try:
                # if await self.locator_base.locator('div.btn-post > button').get_attribute("disabled") is None:
                if await self.locator_base.locator(
                        'div.button-group > button >> text=Post').get_attribute("disabled") is None:
                    tiktok_logger.info("  [-]video uploaded.")
                    break
                else:
                    tiktok_logger.info("  [-] video uploading...")
                    await asyncio.sleep(2)
                    if await self.locator_base.locator(
                            'button[aria-label="Select file"]').count():
                        tiktok_logger.info("  [-] found some error while uploading now retry...")
                        await self.handle_upload_error(page)
            except:
                tiktok_logger.info("  [-] video uploading...")
                await asyncio.sleep(2)

    async def choose_base_locator(self, page):
        # await page.wait_for_selector('div.upload-container')
        if await page.locator('iframe[data-tt="Upload_index_iframe"]').count():
            self.locator_base = page.frame_locator(Tk_Locator.tk_iframe)
        else:
            self.locator_base = page.locator(Tk_Locator.default) 

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)
