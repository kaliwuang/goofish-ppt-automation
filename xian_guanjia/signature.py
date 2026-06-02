"""闲管家 MD5 签名工具."""

import hashlib
import json
import time
from typing import Any


class Signer:
    """MD5 签名生成器.

    签名规则:
        1. body_md5 = md5(json_body_string)
        2. sign_str = "appKey,body_md5,timestamp,appSecret"
        3. sign = md5(sign_str)

    商务对接(传 seller_id):
        sign_str = "appKey,body_md5,timestamp,seller_id,appSecret"
    """

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret

    def _md5(self, s: str) -> str:
        return hashlib.md5(s.encode("utf-8")).hexdigest()

    def _body_md5(self, body: dict[str, Any] | None) -> str:
        if not body:
            return self._md5("")
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        return self._md5(body_str)

    def generate(
        self,
        body: dict[str, Any] | None = None,
        timestamp: int | None = None,
        seller_id: str | None = None,
    ) -> dict[str, str]:
        """生成签名参数.

        Returns:
            {"appid": ..., "timestamp": ..., "sign": ..., "body_str": ...}
        """
        if timestamp is None:
            timestamp = int(time.time())

        body_md5 = self._body_md5(body)

        if seller_id:
            sign_str = f"{self.app_key},{body_md5},{timestamp},{seller_id},{self.app_secret}"
        else:
            sign_str = f"{self.app_key},{body_md5},{timestamp},{self.app_secret}"

        sign = self._md5(sign_str)

        return {
            "appid": self.app_key,
            "timestamp": str(timestamp),
            "sign": sign,
            "body_str": json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body else "",
        }

    def verify(
        self,
        appid: str,
        timestamp: str,
        sign: str,
        body_bytes: bytes,
        seller_id: str | None = None,
    ) -> bool:
        """验证 Webhook 签名."""
        body_md5 = hashlib.md5(body_bytes).hexdigest()

        if seller_id:
            sign_str = f"{appid},{body_md5},{timestamp},{seller_id},{self.app_secret}"
        else:
            sign_str = f"{appid},{body_md5},{timestamp},{self.app_secret}"

        expected = self._md5(sign_str)
        return expected == sign
