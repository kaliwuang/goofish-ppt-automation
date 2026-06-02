"""RPA 配置定义.

Kimi Allegro 网页版界面元素选择器配置.
需要根据实际界面调整.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LoginConfig:
    """登录配置."""

    # 方式1: Cookie 登录（推荐，更稳定）
    cookie_file: Optional[str] = None  # Cookie JSON 文件路径

    # 方式2: 账号密码登录
    username: Optional[str] = None     # 手机号/邮箱
    password: Optional[str] = None     # 密码

    # 登录页面
    login_url: str = "https://kimi.moonshot.cn/"


@dataclass
class PPTUIConfig:
    """PPT 生成界面元素选择器配置.

    ⚠️ 重要: 以下选择器需要根据 Kimi 网页版实际界面调整.
    首次部署前，需要用 Playwright 的 codegen 工具录制一遍操作,
    然后更新这里的选择器.
    """

    # PPT 助手入口
    # 可能的值: "text=PPT助手", "[data-testid='ppt-assistant']", 等
    ppt_entry_selector: str = "text=PPT"

    # 输入框
    prompt_input_selector: str = "textarea[placeholder*='PPT']"

    # 风格选择
    style_button_selector: str = "button:has-text('{style_name}')"

    # 页数选择
    page_count_selector: str = "button:has-text('{page_count}')"

    # 生成按钮
    generate_button_selector: str = "button:has-text('生成')"

    # 上传文件按钮
    upload_button_selector: str = "input[type='file']"

    # 生成进度/状态指示器
    progress_indicator_selector: str = ".generating-indicator"

    # 完成标志
    complete_indicator_selector: str = ".ppt-complete, button:has-text('下载')"

    # 下载按钮
    download_button_selector: str = "button:has-text('下载')"

    # PPT 预览/结果容器
    result_container_selector: str = ".ppt-result"


@dataclass
class RPAConfig:
    """RPA 全局配置."""

    # 登录
    login: LoginConfig = field(default_factory=LoginConfig)

    # 界面选择器
    ui: PPTUIConfig = field(default_factory=PPTUIConfig)

    # 浏览器
    headless: bool = True              # 是否无头模式（生产环境建议True）
    slow_mo: int = 500                 # 操作间隔毫秒（防反爬）
    timeout: int = 60000               # 默认超时（毫秒）
    viewport_width: int = 1920
    viewport_height: int = 1080

    # 生成等待
    generation_timeout: int = 600      # PPT生成最长等待时间（秒）
    poll_interval: int = 10            # 轮询间隔（秒）

    # 并发
    max_concurrent: int = 1            # 同时运行数（Allegro可能限制并发）

    # 下载
    download_dir: str = "./downloads"  # PPT下载目录

    @classmethod
    def from_env(cls) -> "RPAConfig":
        """从环境变量加载配置."""
        cfg = cls()
        cfg.login.username = os.getenv("KIMI_USERNAME")
        cfg.login.password = os.getenv("KIMI_PASSWORD")
        cfg.login.cookie_file = os.getenv("KIMI_COOKIE_FILE")
        cfg.headless = os.getenv("RPA_HEADLESS", "true").lower() == "true"
        return cfg
