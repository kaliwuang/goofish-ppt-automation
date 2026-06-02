"""数据模型与常量定义."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class OrderStatus(IntEnum):
    """订单状态码."""

    WAIT_PAY = 11          # 待付款
    WAIT_SHIP = 12         # 待发货
    SHIPPED = 21           # 已发货
    SUCCESS = 22           # 交易成功
    REFUNDED = 23          # 已退款
    CLOSED = 24            # 交易关闭


class RefundStatus(IntEnum):
    """退款状态码."""

    NONE = 0               # 未申请
    WAIT_MERCHANT = 1      # 待商家处理
    WAIT_BUYER_RETURN = 2  # 待买家退货
    WAIT_MERCHANT_RECV = 3 # 待商家收货
    REFUND_CLOSED = 4      # 退款关闭
    REFUND_SUCCESS = 5     # 退款成功
    REJECTED = 6           # 已拒绝
    WAIT_CONFIRM_ADDR = 8  # 待确认退货地址


@dataclass
class OrderPushData:
    """订单推送数据结构 (Webhook Body)."""

    seller_id: int
    user_name: str
    order_no: str
    order_type: int
    order_status: int
    refund_status: int
    modify_time: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderPushData":
        return cls(
            seller_id=int(data.get("seller_id", 0)),
            user_name=str(data.get("user_name", "")),
            order_no=str(data.get("order_no", "")),
            order_type=int(data.get("order_type", 0)),
            order_status=int(data.get("order_status", 0)),
            refund_status=int(data.get("refund_status", 0)),
            modify_time=int(data.get("modify_time", 0)),
        )

    @property
    def is_wait_ship(self) -> bool:
        return self.order_status == OrderStatus.WAIT_SHIP

    @property
    def is_success(self) -> bool:
        return self.order_status == OrderStatus.SUCCESS

    @property
    def is_paid(self) -> bool:
        return self.order_status in (OrderStatus.WAIT_SHIP, OrderStatus.SHIPPED, OrderStatus.SUCCESS)

    @property
    def has_refund(self) -> bool:
        return self.refund_status in (
            RefundStatus.WAIT_MERCHANT,
            RefundStatus.WAIT_BUYER_RETURN,
            RefundStatus.WAIT_MERCHANT_RECV,
            RefundStatus.REFUND_SUCCESS,
        )


@dataclass
class ShipRequest:
    """订单发货请求参数."""

    order_no: str
    waybill_no: str
    express_code: str
    ship_name: str | None = None
    ship_mobile: str | None = None
    ship_district_id: int | None = None
    ship_prov_name: str | None = None
    ship_city_name: str | None = None
    ship_area_name: str | None = None
    ship_address: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "order_no": self.order_no,
            "waybill_no": self.waybill_no,
            "express_code": self.express_code,
        }
        if self.ship_name:
            d["ship_name"] = self.ship_name
        if self.ship_mobile:
            d["ship_mobile"] = self.ship_mobile
        if self.ship_district_id is not None:
            d["ship_district_id"] = self.ship_district_id
        if self.ship_prov_name:
            d["ship_prov_name"] = self.ship_prov_name
        if self.ship_city_name:
            d["ship_city_name"] = self.ship_city_name
        if self.ship_area_name:
            d["ship_area_name"] = self.ship_area_name
        if self.ship_address:
            d["ship_address"] = self.ship_address
        return d


@dataclass
class WebhookResponse:
    """Webhook 响应结构."""

    result: str
    msg: str

    @classmethod
    def success(cls, msg: str = "成功") -> "WebhookResponse":
        return cls(result="success", msg=msg)

    @classmethod
    def fail(cls, msg: str = "失败") -> "WebhookResponse":
        return cls(result="fail", msg=msg)

    def to_dict(self) -> dict[str, str]:
        return {"result": self.result, "msg": self.msg}
