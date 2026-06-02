"""k.ai-synth.com API 客户端."""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://k.ai-synth.com"


class AISynthError(Exception):
    """AI Synth 平台错误."""

    def __init__(self, message: str, status_code: int = 0, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class AISynthClient:
    """k.ai-synth.com API 客户端.

    用于代买家提交 PPT 生成任务.

    Usage:
        client = AISynthClient()

        # 直接提交任务 (代填表单)
        result = client.submit_job(
            order_no="3306169489513009982",
            redeem_code="LCJBCKMRLXHW",
            prompt="帮我生成一份关于跨境电商的PPT",
            customer_email="buyer@qq.com",
            style="自由风格",
            page_mode="auto",
        )

        # 获取任务状态
        status = client.get_task_status(task_id="uuid")
    """

    def __init__(self, base_url: str = BASE_URL, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def submit_job(
        self,
        order_no: str,
        redeem_code: str,
        prompt: str,
        customer_email: str = "",
        style: str = "自由风格",
        page_mode: str = "auto",
        style_catalog_version: str = "legacy_html",
        files: Optional[list] = None,
    ) -> dict:
        """提交 PPT 生成任务.

        Args:
            order_no: k.ai-synth.com 订单号
            redeem_code: 兑换码
            prompt: PPT 提示词 (必填)
            customer_email: 收件邮箱 (可选)
            style: 风格 (自由风格/学术/极简/专业/植境/侘寂/孟菲斯/构成主义/新粗野主义/8-bit/流行电子)
            page_mode: 分页策略 (auto/range_1_5/range_6_10/...)
            style_catalog_version: 风格版本 (legacy_html/pptd)
            files: 附件列表 [(filename, file_bytes), ...]

        Returns:
            {"accepted": true, "task": {...}, "orderNo": ..., "redeemCode": ...}
        """
        url = f"{self.base_url}/p-api/jobs"

        data = {
            "orderNo": order_no,
            "redeemCode": redeem_code,
            "jobMode": "ppt",
            "prompt": prompt,
            "template": "模板暂不开放，如需指定模板请联系小铺",
            "layoutMode": "smart",
            "pageMode": page_mode,
            "style": style,
            "styleCatalogVersion": style_catalog_version,
        }

        if customer_email:
            data["customerEmail"] = customer_email

        # 准备文件
        file_payload = []
        if files:
            for filename, file_bytes in files:
                file_payload.append(
                    ("source-files", (filename, file_bytes, "application/octet-stream"))
                )

        logger.info(
            "提交任务 order_no=%s prompt=%s style=%s",
            order_no, prompt[:50], style,
        )

        resp = self.session.post(
            url,
            data=data,
            files=file_payload or None,
            timeout=self.timeout,
        )

        if resp.status_code != 200:
            raise AISynthError(
                f"提交失败: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )

        result = resp.json()

        if not result.get("accepted"):
            raise AISynthError(
                f"提交被拒绝: {result}",
                status_code=resp.status_code,
                response=result,
            )

        logger.info(
            "任务提交成功 task_id=%s status=%s",
            result.get("task", {}).get("id"),
            result.get("task", {}).get("status"),
        )
        return result

    def get_task_status(self, task_id: str) -> dict:
        """查询任务状态."""
        # 状态查询端点需要从 statusUrl 推断
        # /p-api/jobs/{task_id}/status 或类似
        # 目前先占位，实际端点需要进一步抓包确认
        url = f"{self.base_url}/p-api/jobs/{task_id}"
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_status_page_url(self, order_id: str, redeem_code: str) -> str:
        """获取状态查询页面链接."""
        return f"{self.base_url}/submit/status?o={order_id}&c={redeem_code}"
