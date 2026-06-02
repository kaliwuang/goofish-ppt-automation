"""FastAPI Webhook 接收服务.

接收闲管家订单推送, 自动处理发货.

Usage:
    uvicorn webhook_server:app --host 0.0.0.0 --port 8000

环境变量:
    XIANGUANJIA_APP_KEY      应用 AppKey
    XIANGUANJIA_APP_SECRET   应用 AppSecret
    XIANGUANJIA_NOTIFY_URL   本服务公网地址 (用于配置在开放平台后台)
"""

import asyncio
import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from xian_guanjia import (
    XianGuanjiaClient,
    Signer,
    OrderPushData,
    OrderStatus,
    WebhookResponse,
    XianGuanjiaError,
)

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
APP_KEY = os.getenv("XIANGUANJIA_APP_KEY", "")
APP_SECRET = os.getenv("XIANGUANJIA_APP_SECRET", "")

if not APP_KEY or not APP_SECRET:
    raise RuntimeError(
        "环境变量 XIANGUANJIA_APP_KEY 和 XIANGUANJIA_APP_SECRET 必须设置"
    )

client = XianGuanjiaClient(app_key=APP_KEY, app_secret=APP_SECRET)
signer = Signer(app_key=APP_KEY, app_secret=APP_SECRET)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 订单处理队列 (简单内存队列, 生产环境建议用 Redis/RabbitMQ)
# ------------------------------------------------------------------
order_queue: asyncio.Queue[OrderPushData] = asyncio.Queue()


async def process_order_worker():
    """后台订单处理协程."""
    while True:
        order = await order_queue.get()
        try:
            await handle_order(order)
        except Exception as e:
            logger.exception("处理订单 %s 失败: %s", order.order_no, e)
        finally:
            order_queue.task_done()


async def handle_order(order: OrderPushData):
    """处理单个订单."""
    logger.info(
        "处理订单 %s 状态=%s 退款状态=%s 买家=%s",
        order.order_no,
        order.order_status,
        order.refund_status,
        order.user_name,
    )

    # 只处理待发货状态
    if not order.is_wait_ship:
        logger.info("订单 %s 不是待发货状态, 跳过", order.order_no)
        return

    # 如果有退款申请, 不发货
    if order.has_refund:
        logger.warning("订单 %s 有退款申请, 暂不发货", order.order_no)
        return

    # TODO: 在这里实现你的业务逻辑
    # 例如:
    # 1. 生成兑换码 / 卡密
    # 2. 调用你的 PPT 生成系统创建任务
    # 3. 调用闲管家发货接口发送卡密

    # 示例: 生成一个兑换码 (实际业务中应该从你的系统获取)
    redeem_code = generate_redeem_code(order.order_no)
    logger.info("订单 %s 生成兑换码: %s", order.order_no, redeem_code)

    # 调用发货接口
    # 注意: 闲管家的 ship_order 是物流发货接口
    # 如果是虚拟商品/卡密, 可能需要使用虚拟货源标准接口
    # 这里示例用 "other" 快递代码发送卡密作为运单号
    # 实际对接时请以官方文档为准
    try:
        result = client.ship_order(
            order_no=order.order_no,
            waybill_no=redeem_code,  # 卡密作为运单号
            express_code="other",    # 其他快递
        )
        logger.info("订单 %s 发货成功: %s", order.order_no, result)
    except XianGuanjiaError as e:
        logger.error("订单 %s 发货失败: %s (code=%s)", order.order_no, e, e.code)
        # 生产环境: 发送告警、记录到数据库重试


def generate_redeem_code(order_no: str) -> str:
    """生成兑换码 (示例实现, 生产环境应使用更安全的方案)."""
    import uuid
    # 基于订单号生成唯一兑换码
    return f"PPT-{order_no[-8:]}-{uuid.uuid4().hex[:6].upper()}"


# ------------------------------------------------------------------
# FastAPI 应用
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动后台处理任务
    worker_task = asyncio.create_task(process_order_worker())
    logger.info("Webhook 服务启动, 监听地址 /webhook/xian-guanjia")
    yield
    # 关闭时取消后台任务
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Webhook 服务关闭")


app = FastAPI(title="闲管家 Webhook 服务", lifespan=lifespan)


@app.post("/webhook/xian-guanjia")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    appid: str = Query(..., description="应用ID"),
    timestamp: str = Query(..., description="时间戳(秒)"),
    sign: str = Query(..., description="签名"),
):
    """接收闲管家订单推送 Webhook.

    平台会在订单状态变更时推送通知.
    收到通知后:
        1. 验证签名
        2. 立即返回 success (3秒内必须响应)
        3. 后台异步处理订单
    """
    body_bytes = await request.body()

    # 1. 验证签名
    if not signer.verify(appid=appid, timestamp=timestamp, sign=sign, body_bytes=body_bytes):
        logger.warning("签名验证失败 appid=%s timestamp=%s", appid, timestamp)
        raise HTTPException(status_code=403, detail="签名验证失败")

    # 2. 解析订单数据
    try:
        data = json.loads(body_bytes)
        order = OrderPushData.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error("解析订单数据失败: %s", e)
        raise HTTPException(status_code=400, detail="无效的订单数据")

    logger.info(
        "收到订单推送: order_no=%s status=%s buyer=%s",
        order.order_no,
        order.order_status,
        order.user_name,
    )

    # 3. 放入队列异步处理, 立即返回 success
    await order_queue.put(order)

    return JSONResponse(content=WebhookResponse.success().to_dict())


@app.get("/health")
async def health_check():
    """健康检查接口."""
    return {"status": "ok", "queue_size": order_queue.qsize()}


@app.get("/")
async def root():
    return {"message": "闲管家 Webhook 服务运行中"}
