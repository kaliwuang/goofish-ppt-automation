"""闲管家 OpenAPI 客户端."""

import json
import logging
from typing import Any

import requests

from .signature import Signer

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://open.goofish.pro"
DEFAULT_TIMEOUT = 30


class XianGuanjiaError(Exception):
    """闲管家 API 错误."""

    def __init__(self, message: str, code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response or {}


class XianGuanjiaClient:
    """闲管家开放平台 HTTP 客户端.

    Usage:
        client = XianGuanjiaClient(app_key="xxx", app_secret="yyy")

        # 查询订单列表
        orders = client.get_order_list(page=1, page_size=20)

        # 查询订单详情
        order = client.get_order_detail(order_no="1234567890123456789")

        # 订单发货
        client.ship_order(
            order_no="1234567890123456789",
            waybill_no="SF1234567890",
            express_code="shunfeng",
        )
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.signer = Signer(app_key, app_secret)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """发送签名请求."""
        sign_data = self.signer.generate(body=body)
        query = {
            "appid": sign_data["appid"],
            "timestamp": sign_data["timestamp"],
            "sign": sign_data["sign"],
        }
        if params:
            query.update(params)

        url = f"{self.base_url}{path}"
        data = sign_data["body_str"].encode("utf-8") if sign_data["body_str"] else b"{}"

        logger.debug("[%s] %s body=%s", method, url, sign_data["body_str"])

        resp = self.session.request(
            method=method,
            url=url,
            params=query,
            data=data,
            timeout=self.timeout,
        )
        resp.raise_for_status()

        result = resp.json()
        logger.debug("Response: %s", result)

        # 闲管家只有 code=0 表示成功
        if result.get("code") != 0 and result.get("code") is not None:
            raise XianGuanjiaError(
                message=result.get("msg", "API error"),
                code=result.get("code"),
                response=result,
            )

        return result

    # ------------------------------------------------------------------
    # 订单相关接口
    # ------------------------------------------------------------------

    def get_order_list(
        self,
        page: int = 1,
        page_size: int = 20,
        order_status: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> dict[str, Any]:
        """查询订单列表.

        Args:
            page: 页码, 从1开始
            page_size: 每页数量
            order_status: 订单状态筛选
            start_time: 开始时间戳(秒)
            end_time: 结束时间戳(秒)
        """
        body: dict[str, Any] = {"page": page, "page_size": page_size}
        if order_status is not None:
            body["order_status"] = order_status
        if start_time is not None:
            body["start_time"] = start_time
        if end_time is not None:
            body["end_time"] = end_time
        return self._request("POST", "/api/open/order/list", body=body)

    def get_order_detail(self, order_no: str) -> dict[str, Any]:
        """查询订单详情."""
        return self._request("POST", "/api/open/order/detail", body={"order_no": order_no})

    def ship_order(
        self,
        order_no: str,
        waybill_no: str,
        express_code: str,
        ship_name: str | None = None,
        ship_mobile: str | None = None,
        ship_district_id: int | None = None,
        ship_address: str | None = None,
        ship_prov_name: str | None = None,
        ship_city_name: str | None = None,
        ship_area_name: str | None = None,
    ) -> dict[str, Any]:
        """订单物流发货.

        Args:
            order_no: 闲鱼订单号 (19位以上数字)
            waybill_no: 快递单号
            express_code: 快递公司代码
                shunfeng=顺丰, shentong=申通, yunda=韵达,
                zhongtong=中通, ems=EMS, other=其他
            ship_name: 寄件人姓名
            ship_mobile: 寄件人手机号
            ship_district_id: 寄件地区ID
            ship_address: 详细地址
            ship_prov_name / ship_city_name / ship_area_name: 省市区名称
        """
        body: dict[str, Any] = {
            "order_no": order_no,
            "waybill_no": waybill_no,
            "express_code": express_code,
        }
        if ship_name:
            body["ship_name"] = ship_name
        if ship_mobile:
            body["ship_mobile"] = ship_mobile
        if ship_district_id is not None:
            body["ship_district_id"] = ship_district_id
        if ship_address:
            body["ship_address"] = ship_address
        if ship_prov_name:
            body["ship_prov_name"] = ship_prov_name
        if ship_city_name:
            body["ship_city_name"] = ship_city_name
        if ship_area_name:
            body["ship_area_name"] = ship_area_name

        return self._request("POST", "/api/open/order/ship", body=body)

    # ------------------------------------------------------------------
    # 商品相关接口
    # ------------------------------------------------------------------

    def publish_product(self, product_data: dict[str, Any]) -> dict[str, Any]:
        """上架商品 (异步接口, 结果通过回调通知).

        product_data 必须严格按文档字段类型传参.
        参考文档获取完整字段列表.
        """
        return self._request("POST", "/api/open/product/publish", body=product_data)

    def down_shelf_product(self, product_id: str) -> dict[str, Any]:
        """下架商品."""
        return self._request("POST", "/api/open/product/downShelf", body={"product_id": product_id})

    def delete_product(self, product_id: str) -> dict[str, Any]:
        """删除商品 (仅删除草稿/待发布状态)."""
        return self._request("POST", "/api/open/product/delete", body={"product_id": product_id})

    def get_product_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: int | None = None,
    ) -> dict[str, Any]:
        """查询商品列表."""
        body: dict[str, Any] = {"page": page, "page_size": page_size}
        if status is not None:
            body["status"] = status
        return self._request("POST", "/api/open/product/list", body=body)

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        """查询商品详情."""
        return self._request("POST", "/api/open/product/detail", body={"product_id": product_id})

    # ------------------------------------------------------------------
    # 取消交易
    # ------------------------------------------------------------------

    def cancel_order(self, order_no: str, reason: str | None = None) -> dict[str, Any]:
        """取消交易."""
        body: dict[str, Any] = {"order_no": order_no}
        if reason:
            body["reason"] = reason
        return self._request("POST", "/api/open/order/cancel", body=body)
