"""Allegro RPA Worker.

使用 Playwright 自动化 Kimi Allegro 网页版生成 PPT.

⚠️ 重要说明:
    1. 需要 Kimi Allegro 会员账号 (¥559-699/月)
    2. 首次使用前, 需要用 Playwright codegen 录制操作来完善选择器
    3. 网页版可能随时改版, RPA 需要定期维护

Usage:
    worker = AllegroWorker(config)
    await worker.run_task(
        prompt="帮我生成一份关于跨境电商的PPT",
        email="buyer@qq.com",
        style="自由风格",
        page_mode="auto",
    )
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .browser_pool import BrowserPool
from .config import RPAConfig

logger = logging.getLogger(__name__)


class RPAError(Exception):
    """RPA 执行错误."""
    pass


class AllegroWorker:
    """Allegro PPT 生成自动化 Worker."""

    def __init__(self, config: RPAConfig):
        self.config = config
        self.pool = BrowserPool(config)
        # 确保下载目录存在
        os.makedirs(config.download_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    async def _login(self, page: Page) -> bool:
        """登录 Kimi Allegro.

        支持两种方式:
        1. Cookie 登录 (推荐): 先手动登录一次, 导出 cookie 到文件
        2. 账号密码登录: 自动填写表单
        """
        cfg = self.config.login

        # 方式1: Cookie 登录
        if cfg.cookie_file and os.path.exists(cfg.cookie_file):
            logger.info("使用 Cookie 登录")
            with open(cfg.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await page.context.add_cookies(cookies)
            await page.goto("https://kimi.moonshot.cn/")
            await page.wait_for_load_state("networkidle")

            # 验证是否登录成功
            if await self._is_logged_in(page):
                logger.info("Cookie 登录成功")
                return True
            else:
                logger.warning("Cookie 已过期, 尝试账号密码登录")

        # 方式2: 账号密码登录
        if cfg.username and cfg.password:
            logger.info("使用账号密码登录: %s", cfg.username)
            await page.goto(cfg.login_url)
            await page.wait_for_load_state("networkidle")

            # TODO: 根据实际登录页面填写选择器
            # 这里需要根据 Kimi 网页版的实际登录表单来完善
            try:
                # 示例选择器, 需要根据实际界面调整
                await page.fill("input[type='tel'], input[type='email']", cfg.username)
                await page.fill("input[type='password']", cfg.password)
                await page.click("button[type='submit']")

                # 等待登录完成
                await page.wait_for_url("**/kimi.moonshot.cn/**", timeout=30000)

                # 保存 cookie 供下次使用
                cookies = await page.context.cookies()
                if cfg.cookie_file:
                    with open(cfg.cookie_file, "w", encoding="utf-8") as f:
                        json.dump(cookies, f)

                logger.info("账号密码登录成功")
                return True

            except PlaywrightTimeout:
                raise RPAError("登录超时, 请检查账号密码或界面是否改版")

        raise RPAError("未配置登录方式, 请设置 KIMI_USERNAME/KIMI_PASSWORD 或 KIMI_COOKIE_FILE")

    async def _is_logged_in(self, page: Page) -> bool:
        """检查是否已登录."""
        # TODO: 根据实际界面调整判断逻辑
        # 示例: 检查页面是否有用户头像或用户名
        try:
            avatar = await page.query_selector(".user-avatar, .avatar, [class*='user']")
            return avatar is not None
        except Exception:
            return False

    # ------------------------------------------------------------------
    # PPT 生成
    # ------------------------------------------------------------------

    async def _navigate_to_ppt(self, page: Page):
        """导航到 PPT 生成页面."""
        logger.info("导航到 PPT 生成页面")

        # 方式1: 直接访问 PPT 助手 URL (如果有)
        # await page.goto("https://kimi.moonshot.cn/ppt")

        # 方式2: 从首页点击 PPT 助手入口
        try:
            await page.click(self.config.ui.ppt_entry_selector)
            await page.wait_for_load_state("networkidle")
        except Exception as e:
            logger.warning("点击 PPT 入口失败: %s, 尝试直接访问", e)
            # 尝试直接访问已知的 PPT 页面 URL
            # 需要用户根据实际情况提供
            raise RPAError(f"无法导航到 PPT 页面: {e}")

    async def _fill_form(
        self,
        page: Page,
        prompt: str,
        style: str = "自由风格",
        page_mode: str = "auto",
        files: Optional[list] = None,
    ):
        """填写 PPT 生成表单."""
        ui = self.config.ui

        logger.info("填写表单: style=%s page_mode=%s", style, page_mode)

        # 1. 输入提示词
        try:
            await page.fill(ui.prompt_input_selector, prompt)
            logger.debug("提示词已填写")
        except Exception as e:
            raise RPAError(f"填写提示词失败: {e}")

        # 2. 选择风格 (如果界面支持)
        if style and style != "自由风格":
            try:
                style_selector = ui.style_button_selector.format(style_name=style)
                await page.click(style_selector)
                logger.debug("风格已选择: %s", style)
                await asyncio.sleep(0.5)
            except Exception:
                logger.warning("选择风格失败, 使用默认风格")

        # 3. 选择页数 (如果界面支持)
        if page_mode and page_mode != "auto":
            try:
                page_selector = ui.page_count_selector.format(page_count=page_mode)
                await page.click(page_selector)
                logger.debug("页数已选择: %s", page_mode)
            except Exception:
                logger.warning("选择页数失败, 使用自动")

        # 4. 上传附件 (如果有)
        if files:
            for filepath in files:
                if os.path.exists(filepath):
                    try:
                        await page.set_input_files(ui.upload_button_selector, filepath)
                        logger.debug("文件已上传: %s", filepath)
                        await asyncio.sleep(1)
                    except Exception as e:
                        logger.warning("上传文件失败 %s: %s", filepath, e)

    async def _click_generate(self, page: Page) -> str:
        """点击生成按钮, 返回任务ID或None."""
        logger.info("点击生成按钮")

        try:
            await page.click(self.config.ui.generate_button_selector)
            logger.info("生成按钮已点击, 等待生成...")
            return ""
        except Exception as e:
            raise RPAError(f"点击生成按钮失败: {e}")

    async def _wait_for_completion(self, page: Page, timeout: Optional[int] = None) -> bool:
        """等待 PPT 生成完成.

        Returns:
            True: 生成成功
            False: 超时
        """
        timeout = timeout or self.config.generation_timeout
        ui = self.config.ui
        poll_interval = self.config.poll_interval

        logger.info("等待生成完成, 最长 %d 秒", timeout)
        start_time = datetime.utcnow()

        while True:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                logger.error("生成超时 (%d 秒)", timeout)
                return False

            # 检查是否完成
            try:
                complete = await page.query_selector(ui.complete_indicator_selector)
                if complete and await complete.is_visible():
                    logger.info("PPT 生成完成! 耗时 %.0f 秒", elapsed)
                    return True
            except Exception:
                pass

            # 检查是否出错
            try:
                error_el = await page.query_selector(".error-message, .error, [class*='error']")
                if error_el and await error_el.is_visible():
                    error_text = await error_el.text_content()
                    raise RPAError(f"生成出错: {error_text}")
            except RPAError:
                raise
            except Exception:
                pass

            await asyncio.sleep(poll_interval)

    async def _download_ppt(self, page: Page, download_dir: str) -> Optional[str]:
        """下载生成的 PPT 文件.

        Returns:
            下载的文件路径, 或 None
        """
        ui = self.config.ui

        try:
            # 等待下载事件
            async with page.expect_download(timeout=30000) as download_info:
                await page.click(ui.download_button_selector)

            download = await download_info.value
            file_path = os.path.join(download_dir, download.suggested_filename)
            await download.save_as(file_path)

            logger.info("PPT 已下载: %s", file_path)
            return file_path

        except PlaywrightTimeout:
            logger.error("下载超时")
            return None
        except Exception as e:
            logger.error("下载失败: %s", e)
            return None

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    async def run_task(
        self,
        prompt: str,
        email: str,
        style: str = "自由风格",
        page_mode: str = "auto",
        files: Optional[list] = None,
    ) -> dict:
        """执行完整的 PPT 生成任务.

        Returns:
            {
                "success": bool,
                "file_path": str | None,
                "error": str | None,
                "duration": float,
            }
        """
        start_time = datetime.utcnow()
        result = {
            "success": False,
            "file_path": None,
            "error": None,
            "duration": 0,
        }

        try:
            async with self.pool.acquire() as page:
                # 1. 登录
                await self._login(page)

                # 2. 导航到 PPT 页面
                await self._navigate_to_ppt(page)

                # 3. 填写表单
                await self._fill_form(
                    page=page,
                    prompt=prompt,
                    style=style,
                    page_mode=page_mode,
                    files=files,
                )

                # 4. 点击生成
                await self._click_generate(page)

                # 5. 等待完成
                completed = await self._wait_for_completion(page)
                if not completed:
                    raise RPAError("PPT 生成超时")

                # 6. 下载
                file_path = await self._download_ppt(page, self.config.download_dir)
                if not file_path:
                    raise RPAError("PPT 下载失败")

                result["success"] = True
                result["file_path"] = file_path

        except RPAError as e:
            logger.error("RPA 任务失败: %s", e)
            result["error"] = str(e)
        except Exception as e:
            logger.exception("RPA 任务异常")
            result["error"] = f"未知错误: {e}"
        finally:
            result["duration"] = (datetime.utcnow() - start_time).total_seconds()

        return result

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self):
        """启动 Worker."""
        await self.pool.start()

    async def stop(self):
        """停止 Worker."""
        await self.pool.stop()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
