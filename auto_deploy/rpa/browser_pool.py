"""浏览器池管理.

管理 Playwright 浏览器实例的生命周期.
Allegro 账号可能有并发限制, 建议 max_concurrent=1.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .config import RPAConfig

logger = logging.getLogger(__name__)


class BrowserPool:
    """浏览器实例池.

    Usage:
        pool = BrowserPool(config)
        await pool.start()

        async with pool.acquire() as page:
            await page.goto("https://kimi.moonshot.cn")
            ...

        await pool.stop()
    """

    def __init__(self, config: RPAConfig):
        self.config = config
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._in_use = 0

    async def start(self):
        """启动浏览器."""
        logger.info("启动浏览器 (headless=%s)", self.config.headless)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("浏览器启动完成")

    async def stop(self):
        """关闭浏览器."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("浏览器已关闭")

    @asynccontextmanager
    async def acquire(self):
        """获取一个浏览器页面上下文."""
        async with self._semaphore:
            if not self._browser:
                raise RuntimeError("浏览器未启动, 先调用 start()")

            self._in_use += 1
            logger.debug("获取浏览器实例, 当前使用: %d", self._in_use)

            context = await self._browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                accept_downloads=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            )

            # 注入反反爬脚本
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()

            try:
                yield page
            finally:
                await context.close()
                self._in_use -= 1
                logger.debug("释放浏览器实例, 当前使用: %d", self._in_use)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
