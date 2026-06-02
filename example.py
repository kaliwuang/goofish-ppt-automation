"""使用示例."""

import os
import time

from xian_guanjia import XianGuanjiaClient, XianGuanjiaError

# 从环境变量读取配置 (实际项目中建议使用 pydantic-settings)
APP_KEY = os.getenv("XIANGUANJIA_APP_KEY", "your_app_key")
APP_SECRET = os.getenv("XIANGUANJIA_APP_SECRET", "your_app_secret")

client = XianGuanjiaClient(app_key=APP_KEY, app_secret=APP_SECRET)


def demo_query_orders():
    """查询订单列表示例."""
    try:
        # 查询待发货订单
        result = client.get_order_list(
            page=1,
            page_size=10,
            order_status=12,  # 待发货
        )
        print("订单列表:", result)

        # 获取订单数据
        orders = result.get("data", {}).get("list", [])
        for order in orders:
            print(f"订单号: {order.get('order_no')} 买家: {order.get('user_name')}")

    except XianGuanjiaError as e:
        print(f"API错误: {e} (code={e.code})")


def demo_order_detail():
    """查询订单详情示例."""
    try:
        result = client.get_order_detail(order_no="1234567890123456789")
        print("订单详情:", result)
    except XianGuanjiaError as e:
        print(f"API错误: {e} (code={e.code})")


def demo_ship_order():
    """订单发货示例."""
    try:
        result = client.ship_order(
            order_no="1234567890123456789",
            waybill_no="SF1234567890123",
            express_code="shunfeng",  # 顺丰
            ship_name="发货人姓名",
            ship_mobile="13800138000",
            ship_address="详细发货地址",
        )
        print("发货结果:", result)
    except XianGuanjiaError as e:
        print(f"发货失败: {e} (code={e.code})")


def demo_product_mgmt():
    """商品管理示例."""
    try:
        # 查询商品列表
        result = client.get_product_list(page=1, page_size=10)
        print("商品列表:", result)

        # 上架商品 (具体字段请参考官方文档)
        # result = client.publish_product({
        #     "title": "PPT定制服务",
        #     "price": 5000,  # 单位: 分
        #     "category_id": "...",
        #     # ... 其他字段
        # })
        # print("上架结果:", result)

        # 下架商品
        # result = client.down_shelf_product(product_id="xxx")
        # print("下架结果:", result)

    except XianGuanjiaError as e:
        print(f"API错误: {e} (code={e.code})")


def demo_signature():
    """签名生成示例."""
    from xian_guanjia import Signer

    signer = Signer(app_key=APP_KEY, app_secret=APP_SECRET)

    # 生成签名
    body = {"order_no": "1234567890123456789"}
    sign_data = signer.generate(body=body)
    print("签名参数:", sign_data)

    # 验证签名
    body_bytes = sign_data["body_str"].encode("utf-8")
    is_valid = signer.verify(
        appid=sign_data["appid"],
        timestamp=sign_data["timestamp"],
        sign=sign_data["sign"],
        body_bytes=body_bytes,
    )
    print("签名验证:", is_valid)


if __name__ == "__main__":
    print("=" * 50)
    print("闲管家 SDK 使用示例")
    print("=" * 50)

    # 选择要运行的示例
    # demo_query_orders()
    # demo_order_detail()
    # demo_ship_order()
    # demo_product_mgmt()
    demo_signature()
