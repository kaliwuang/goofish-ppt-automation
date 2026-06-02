"""Allegro RPA 自动化模块."""

from .allegro_worker import AllegroWorker, RPAError
from .browser_pool import BrowserPool
from .config import RPAConfig

__all__ = ["AllegroWorker", "RPAError", "BrowserPool", "RPAConfig"]
