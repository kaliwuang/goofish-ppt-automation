# 闲管家开放平台 Python SDK

闲管家 (Goofish Pro) 闲鱼商家管理工具的开源 Python SDK，支持自动发货、订单管理、Webhook 回调处理。

## 目录结构

```
xian-guanjia-sdk/
├── xian_guanjia/          # SDK 核心包
│   ├── __init__.py
│   ├── client.py          # HTTP 客户端 (订单/商品接口)
│   ├── signature.py       # MD5 签名工具
│   └── models.py          # 数据模型与常量
├── webhook_server.py      # FastAPI Webhook 接收服务
├── example.py             # 使用示例
├── requirements.txt       # 依赖
└── .env.example           # 环境变量模板
```

## 快速开始

### 1. 安装依赖

```bash
cd xian-guanjia-sdk
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 AppKey 和 AppSecret
```

### 3. 使用 SDK

```python
from xian_guanjia import XianGuanjiaClient

client = XianGuanjiaClient(
    app_key="your_app_key",
    app_secret="your_app_secret",
)

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
```

### 4. 启动 Webhook 服务

```bash
# 方式1: 直接启动
uvicorn webhook_server:app --host 0.0.0.0 --port 8000

# 方式2: 后台运行
nohup uvicorn webhook_server:app --host 0.0.0.0 --port 8000 > webhook.log 2>&1 &
```

Webhook 地址: `POST http://your-domain:8000/webhook/xian-guanjia`

将此地址配置到闲管家开放平台后台的推送地址中。

## 签名规则

闲管家采用 MD5 签名鉴权:

```
body_md5  = md5(json_body_string)
sign_str  = "appKey,body_md5,timestamp,appSecret"
sign      = md5(sign_str)
```

- `timestamp` 为秒级 Unix 时间戳，5分钟内有效
- 无 Body 时: `body_md5 = md5("")`
- 商务对接(传 seller_id): `sign_str = "appKey,body_md5,timestamp,seller_id,appSecret"`

## 核心接口

### 订单接口

| 方法 | 说明 | 接口路径 |
|------|------|----------|
| `get_order_list()` | 查询订单列表 | `POST /api/open/order/list` |
| `get_order_detail()` | 查询订单详情 | `POST /api/open/order/detail` |
| `ship_order()` | 订单物流发货 | `POST /api/open/order/ship` |
| `cancel_order()` | 取消交易 | `POST /api/open/order/cancel` |

### 商品接口

| 方法 | 说明 | 接口路径 |
|------|------|----------|
| `publish_product()` | 上架商品 (异步) | `POST /api/open/product/publish` |
| `down_shelf_product()` | 下架商品 | `POST /api/open/product/downShelf` |
| `delete_product()` | 删除商品 | `POST /api/open/product/delete` |
| `get_product_list()` | 查询商品列表 | `POST /api/open/product/list` |
| `get_product_detail()` | 查询商品详情 | `POST /api/open/product/detail` |

## 订单状态码

| 状态码 | 含义 |
|--------|------|
| 11 | 待付款 |
| 12 | 待发货 |
| 21 | 已发货 |
| 22 | 交易成功 |
| 23 | 已退款 |
| 24 | 交易关闭 |

## Webhook 订单推送

当订单状态变更时，闲管家会向配置的推送地址发送 POST 请求:

**Query 参数:** `appid`, `timestamp`, `sign`

**Body 参数:**
```json
{
    "seller_id": 123456,
    "user_name": "买家会员名",
    "order_no": "1234567890123456789",
    "order_type": 1,
    "order_status": 12,
    "refund_status": 0,
    "modify_time": 1700000000
}
```

**响应要求 (3秒内):**
```json
{"result": "success", "msg": "成功"}
```

## 对接流程

```
1. 注册闲管家账号 → https://goofish.pro/register
2. 订购 ERP专业版 / 铂金版
3. 创建应用 (我的应用 → 添加应用 → 我有自研系统)
4. 获取 AppKey / AppSecret
5. 配置 Webhook 推送地址
6. 部署本服务并测试
```

## 与 PPT 生成系统集成

修改 `webhook_server.py` 中的 `handle_order()` 函数:

```python
async def handle_order(order: OrderPushData):
    if not order.is_wait_ship:
        return

    # 1. 生成兑换码
    redeem_code = generate_redeem_code(order.order_no)

    # 2. 调用你的 PPT 系统创建任务
    # await your_ppt_system.create_task(
    #     order_no=order.order_no,
    #     buyer=order.user_name,
    #     redeem_code=redeem_code,
    # )

    # 3. 发货 (发送兑换码)
    client.ship_order(
        order_no=order.order_no,
        waybill_no=redeem_code,
        express_code="other",
    )
```

## 参考文档

- [闲管家开放平台文档](https://apifox.com/apidoc/shared-3ac13d69-5a38-4536-ae9b-a54001854ef8)
- [虚拟货源标准接口](https://apifox.com/apidoc/shared-cf4d53fd-8bb2-41c5-8da3-371ba9a38956/doc-4985015)
- [开源 Python SDK](https://github.com/thefreelight/xian-guanjia)
