"""全自动部署服务 - RPA 版.

整合功能:
    1. 接收闲管家 Webhook (订单推送)
    2. 自动分配兑换码 + 调用闲管家发货 (发送提交链接)
    3. 买家提交需求后触发 RPA 生成 PPT
    4. RPA 生成完成后自动发送邮件
    5. 管理后台

Usage:
    cd auto_deploy
    uvicorn webhook_server:app --host 0.0.0.0 --port 8000

环境变量:
    XIANGUANJIA_APP_KEY      闲管家 AppKey
    XIANGUANJIA_APP_SECRET   闲管家 AppSecret
    ADMIN_TOKEN              管理后台访问令牌
    KIMI_USERNAME            Kimi 登录账号
    KIMI_PASSWORD            Kimi 登录密码
    KIMI_COOKIE_FILE         Cookie 文件路径 (优先使用)
    SMTP_HOST                SMTP 服务器
    SMTP_PORT                SMTP 端口
    SMTP_USERNAME            SMTP 用户名
    SMTP_PASSWORD            SMTP 密码
    SENDER_NAME              发件人名称
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Query, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

# 导入 SDK
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from xian_guanjia import (
    XianGuanjiaClient, Signer, OrderPushData,
    OrderStatus, WebhookResponse, XianGuanjiaError,
)

from database import init_db, get_db, RedeemCode, CodeStatus, XianyuOrder, RPATask, RPATaskStatus
from redeem_manager import RedeemManager
from email_sender import EmailSender

# RPA (条件导入, 未安装 playwright 时跳过)
try:
    from rpa import AllegroWorker, RPAConfig, RPAError
    RPA_AVAILABLE = True
except ImportError:
    RPA_AVAILABLE = False
    logging.warning("Playwright 未安装, RPA 功能不可用. 运行: pip install playwright && playwright install chromium")

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
APP_KEY = os.getenv("XIANGUANJIA_APP_KEY", "")
APP_SECRET = os.getenv("XIANGUANJIA_APP_SECRET", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin")

# 初始化数据库
init_db()

# 闲管家客户端
xgj_client = None
xgj_signer = None
if APP_KEY and APP_SECRET:
    xgj_client = XianGuanjiaClient(app_key=APP_KEY, app_secret=APP_SECRET)
    xgj_signer = Signer(app_key=APP_KEY, app_secret=APP_SECRET)

redeem_mgr = RedeemManager()
email_sender = EmailSender()

# RPA Worker (懒加载)
rpa_worker = None

async def get_rpa_worker():
    global rpa_worker
    if not RPA_AVAILABLE:
        return None
    if rpa_worker is None:
        cfg = RPAConfig.from_env()
        rpa_worker = AllegroWorker(cfg)
        await rpa_worker.start()
    return rpa_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 队列
# ------------------------------------------------------------------
order_queue: asyncio.Queue[OrderPushData] = asyncio.Queue()
rpa_task_queue: asyncio.Queue[int] = asyncio.Queue()  # RPATask.id

# ------------------------------------------------------------------
# 订单处理 Worker
# ------------------------------------------------------------------

async def process_order_worker():
    while True:
        order = await order_queue.get()
        try:
            await handle_order(order)
        except Exception:
            logger.exception("处理订单 %s 失败", order.order_no)
        finally:
            order_queue.task_done()


async def handle_order(order: OrderPushData):
    """处理订单: 分配兑换码 -> 发货."""
    logger.info("处理订单 %s 状态=%s 买家=%s", order.order_no, order.order_status, order.user_name)

    if not order.is_wait_ship:
        return
    if order.has_refund:
        logger.warning("订单 %s 有退款申请, 暂不发货", order.order_no)
        return

    existing = redeem_mgr.get_by_xianyu_order(order.order_no)
    if existing:
        logger.info("订单 %s 已有兑换码, 跳过", order.order_no)
        return

    code = redeem_mgr.assign_code(order.order_no, order.user_name)
    if not code:
        logger.error("订单 %s 兑换码库存不足!", order.order_no)
        return

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    submit_url = f"{base_url}/s/{code.code}"
    logger.info("订单 %s 分配链接: %s", order.order_no, submit_url)

    if not xgj_client:
        logger.error("闲管家客户端未配置")
        return

    try:
        result = xgj_client.ship_order(
            order_no=order.order_no,
            waybill_no=submit_url,
            express_code="other",
        )
        logger.info("订单 %s 发货成功", order.order_no)
        with get_db() as db:
            xo = db.query(XianyuOrder).filter(XianyuOrder.order_no == order.order_no).first()
            if xo:
                xo.shipped = True
                xo.shipped_at = datetime.utcnow()
                xo.ship_result = json.dumps(result, ensure_ascii=False)
                db.commit()
    except XianGuanjiaError as e:
        logger.error("订单 %s 发货失败: %s", order.order_no, e)


# ------------------------------------------------------------------
# RPA Worker
# ------------------------------------------------------------------

async def rpa_worker_loop():
    """后台 RPA 任务处理循环."""
    if not RPA_AVAILABLE:
        logger.warning("RPA 不可用, 跳过 RPA Worker")
        return

    worker = await get_rpa_worker()
    if not worker:
        logger.error("RPA Worker 初始化失败")
        return

    logger.info("RPA Worker 启动, 等待任务...")

    while True:
        task_id = await rpa_task_queue.get()
        try:
            await process_rpa_task(worker, task_id)
        except Exception:
            logger.exception("RPA 任务 %d 处理失败", task_id)
        finally:
            rpa_task_queue.task_done()


async def process_rpa_task(worker: AllegroWorker, task_id: int):
    """处理单个 RPA 任务."""
    with get_db() as db:
        task = db.query(RPATask).filter(RPATask.id == task_id).first()
        if not task:
            return
        task.status = RPATaskStatus.LOGGING_IN
        task.started_at = datetime.utcnow()
        db.commit()

    logger.info("RPA 任务 %d 开始: order=%s email=%s", task_id, task.xianyu_order_no, task.customer_email)

    try:
        # 执行 RPA
        task.status = RPATaskStatus.GENERATING
        db.commit()

        result = await worker.run_task(
            prompt=task.prompt,
            email=task.customer_email,
            style=task.style or "自由风格",
            page_mode=task.page_mode or "auto",
        )

        if not result["success"]:
            raise RPAError(result.get("error", "未知错误"))

        # 更新状态
        task.status = RPATaskStatus.SENDING
        task.file_path = result["file_path"]
        task.duration = result["duration"]
        db.commit()

        # 发送邮件
        if email_sender.is_configured() and result["file_path"]:
            sent = await email_sender.send_ppt(
                to_email=task.customer_email,
                subject="您的 PPT 已生成",
                body=f"您好，您提交的 PPT 需求已生成完成，请查收附件。\n\n原始需求：{task.prompt[:200]}",
                ppt_path=result["file_path"],
            )
            if sent:
                logger.info("任务 %d 邮件已发送至 %s", task_id, task.customer_email)
            else:
                logger.warning("任务 %d 邮件发送失败", task_id)

        task.status = RPATaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        db.commit()
        logger.info("RPA 任务 %d 完成, 耗时 %.1f 秒", task_id, result["duration"])

    except Exception as e:
        task.status = RPATaskStatus.FAILED
        task.error_message = str(e)
        task.completed_at = datetime.utcnow()
        db.commit()
        logger.error("RPA 任务 %d 失败: %s", task_id, e)


# ------------------------------------------------------------------
# FastAPI 应用
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(process_order_worker()),
        asyncio.create_task(rpa_worker_loop()),
    ]
    logger.info("全自动部署服务启动 (RPA 模式)")
    yield
    for t in tasks:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    if rpa_worker:
        await rpa_worker.stop()
    logger.info("服务关闭")


app = FastAPI(title="PPT 全自动发货系统 (RPA)", lifespan=lifespan)


def verify_admin(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="管理员令牌错误")


# ==================================================================
# 1. 闲管家 Webhook
# ==================================================================

@app.post("/webhook/xian-guanjia")
async def receive_webhook(request: Request, appid: str = Query(...), timestamp: str = Query(...), sign: str = Query(...)):
    if not xgj_signer:
        raise HTTPException(status_code=500, detail="签名工具未配置")

    body_bytes = await request.body()
    if not xgj_signer.verify(appid=appid, timestamp=timestamp, sign=sign, body_bytes=body_bytes):
        raise HTTPException(status_code=403, detail="签名验证失败")

    try:
        data = json.loads(body_bytes)
        order = OrderPushData.from_dict(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail="无效的订单数据")

    await order_queue.put(order)
    return JSONResponse(content=WebhookResponse.success().to_dict())


# ==================================================================
# 2. 买家提交页面
# ==================================================================

@app.get("/s/{code}")
async def submit_page(code: str):
    rc = redeem_mgr.get_by_code(code)
    if not rc:
        return HTMLResponse(content="<h1>兑换码不存在</h1>", status_code=404)
    if rc.status == CodeStatus.USED:
        return HTMLResponse(content="<h1>兑换码已被使用</h1><p>如需查看结果，请检查您的邮箱。</p>")
    if rc.status != CodeStatus.ASSIGNED:
        return HTMLResponse(content="<h1>兑换码无效</h1>", status_code=400)

    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>PPT 自助生成</title>
        <style>
            body {{ margin: 0; padding: 24px; font-family: -apple-system, "PingFang SC", sans-serif; background: linear-gradient(180deg, #faf7f2 0%, #fff 48%, #f8fafc 100%); min-height: 100vh; }}
            .wrap {{ max-width: 680px; margin: 0 auto; }}
            h1 {{ font-size: 32px; margin: 0 0 8px; }}
            .subtitle {{ color: #64748b; margin-bottom: 24px; }}
            .card {{ background: white; border-radius: 20px; padding: 24px; box-shadow: 0 4px 20px rgba(0,0,0,.06); margin-bottom: 16px; }}
            label {{ display: block; margin-bottom: 16px; }}
            label span {{ display: block; font-size: 14px; font-weight: 700; margin-bottom: 6px; color: #27272a; }}
            input, textarea, select {{ width: 100%; padding: 12px 14px; border: 1px solid #e4e4e7; border-radius: 14px; font-size: 15px; outline: none; box-sizing: border-box; }}
            textarea {{ min-height: 120px; resize: vertical; }}
            .hint {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
            button {{ width: 100%; padding: 16px; border: 0; border-radius: 16px; background: #f97316; color: white; font-size: 17px; font-weight: 800; cursor: pointer; }}
            button:disabled {{ opacity: .5; }}
            .error {{ color: #b91c1c; background: #fef2f2; padding: 12px; border-radius: 12px; margin-bottom: 16px; display: none; }}
            .success {{ color: #047857; background: #ecfdf5; padding: 12px; border-radius: 12px; margin-bottom: 16px; display: none; }}
            .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        </style>
    </head>
    <body>
        <div class="wrap">
            <h1>KIMI PPT 生成</h1>
            <p class="subtitle">填写需求后，AI 自动为您生成 PPT 并发送到邮箱</p>
            <div class="card">
                <div class="error" id="error"></div>
                <div class="success" id="success"></div>
                <form id="form">
                    <input type="hidden" name="code" value="{code}">
                    <label>
                        <span>收件邮箱</span>
                        <input type="email" name="email" placeholder="yourname@qq.com" required>
                        <p class="hint">生成完成后 PPT 会发送到此邮箱</p>
                    </label>
                    <label>
                        <span>PPT 需求描述</span>
                        <textarea name="prompt" placeholder="例如：帮我生成一份关于跨境电商春季选品复盘的PPT..." required></textarea>
                    </label>
                    <div class="row">
                        <label>
                            <span>页数</span>
                            <select name="page_mode">
                                <option value="auto">自动页数</option>
                                <option value="range_1_5">1-5 页</option>
                                <option value="range_6_10">6-10 页</option>
                                <option value="range_11_15">11-15 页</option>
                                <option value="range_16_20">16-20 页</option>
                            </select>
                        </label>
                        <label>
                            <span>风格</span>
                            <select name="style">
                                <option value="自由风格">自由风格</option>
                                <option value="学术">学术</option>
                                <option value="极简">极简</option>
                                <option value="专业">专业</option>
                                <option value="植境">植境</option>
                                <option value="侘寂">侘寂</option>
                                <option value="孟菲斯">孟菲斯</option>
                                <option value="8-bit">8-bit</option>
                            </select>
                        </label>
                    </div>
                    <button type="submit" id="submitBtn">提交生成任务</button>
                </form>
            </div>
        </div>
        <script>
            document.getElementById('form').addEventListener('submit', async (e) => {{
                e.preventDefault();
                const btn = document.getElementById('submitBtn');
                const err = document.getElementById('error');
                const suc = document.getElementById('success');
                btn.disabled = true;
                err.style.display = 'none';
                suc.style.display = 'none';

                const body = new URLSearchParams(new FormData(e.target));
                try {{
                    const res = await fetch('/api/submit', {{ method: 'POST', body }});
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || '提交失败');
                    suc.textContent = '任务已提交！PPT 生成需要 10-60 分钟，完成后会发送到您的邮箱。请勿重复提交。';
                    suc.style.display = 'block';
                    btn.textContent = '已提交';
                }} catch (e) {{
                    err.textContent = e.message;
                    err.style.display = 'block';
                    btn.disabled = false;
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.post("/api/submit")
async def api_submit(
    code: str = Form(...),
    email: str = Form(...),
    prompt: str = Form(...),
    page_mode: str = Form("auto"),
    style: str = Form("自由风格"),
):
    """接收买家提交，创建 RPA 任务."""
    rc = redeem_mgr.get_by_code(code)
    if not rc or rc.status != CodeStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="兑换码无效或已被使用")

    with get_db() as db:
        task = RPATask(
            xianyu_order_no=rc.xianyu_order_no or "",
            customer_email=email,
            prompt=prompt,
            style=style,
            page_mode=page_mode,
            status=RPATaskStatus.QUEUED,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 标记兑换码为已使用
        rc.status = CodeStatus.USED
        rc.used_at = datetime.utcnow()
        rc.customer_email = email
        rc.prompt = prompt
        db.commit()

    # 放入 RPA 队列
    await rpa_task_queue.put(task.id)
    logger.info("RPA 任务 %d 已入队", task.id)

    return {"success": True, "task_id": task.id, "message": "任务已提交，生成完成后会发送到您的邮箱"}


# ==================================================================
# 3. 管理后台
# ==================================================================

@app.get("/admin/dashboard")
async def admin_dashboard(token: str = Query(...)):
    verify_admin(token)
    stats = redeem_mgr.get_stats()

    with get_db() as db:
        rpa_stats = {s.value: db.query(RPATask).filter(RPATask.status == s).count() for s in RPATaskStatus}
        recent_tasks = db.query(RPATask).order_by(RPATask.created_at.desc()).limit(20).all()

    html = f"""
    <!DOCTYPE html><html><head><meta charset="utf-8"><title>管理后台</title>
    <style>
        body {{ margin: 0; padding: 24px; font-family: -apple-system, "PingFang SC", sans-serif; background: #f8fafc; }}
        .wrap {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ margin: 0 0 24px; font-size: 28px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-bottom: 24px; }}
        .stat {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.05); }}
        .stat-value {{ font-size: 28px; font-weight: 800; color: #2563eb; }}
        .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        .section {{ margin-bottom: 32px; }}
        .section h2 {{ font-size: 18px; margin: 0 0 12px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.05); font-size: 13px; }}
        th, td {{ padding: 10px 12px; text-align: left; }}
        th {{ background: #f1f5f9; font-weight: 700; color: #475569; }}
        td {{ border-top: 1px solid #f1f5f9; }}
        .status-queued {{ color: #6b7280; }}
        .status-generating {{ color: #2563eb; }}
        .status-completed {{ color: #16a34a; }}
        .status-failed {{ color: #dc2626; }}
        .low {{ color: #dc2626; font-weight: 700; }}
    </style></head><body>
    <div class="wrap">
        <h1>PPT 全自动发货系统 (RPA)</h1>

        <div class="section">
            <h2>兑换码库存</h2>
            <div class="stats">
                <div class="stat"><div class="stat-value {'low' if stats['unused'] < 5 else ''}">{stats['unused']}</div><div class="stat-label">未使用</div></div>
                <div class="stat"><div class="stat-value">{stats['assigned']}</div><div class="stat-label">已分配</div></div>
                <div class="stat"><div class="stat-value">{stats['used']}</div><div class="stat-label">已使用</div></div>
                <div class="stat"><div class="stat-value">{stats['total']}</div><div class="stat-label">总计</div></div>
            </div>
        </div>

        <div class="section">
            <h2>RPA 任务状态</h2>
            <div class="stats">
                {''.join(f'<div class="stat"><div class="stat-value">{v}</div><div class="stat-label">{k}</div></div>' for k, v in rpa_stats.items())}
            </div>
        </div>

        <div class="section">
            <h2>最近任务</h2>
            <table>
                <tr><th>ID</th><th>订单</th><th>邮箱</th><th>状态</th><th>耗时</th><th>时间</th></tr>
    """
    for t in recent_tasks:
        status_class = f"status-{t.status.value}"
        duration_str = f"{t.duration:.0f}s" if t.duration else "-"
        html += f"<tr><td>{t.id}</td><td>{t.xianyu_order_no}</td><td>{t.customer_email}</td><td class='{status_class}'>{t.status.value}</td><td>{duration_str}</td><td>{t.created_at.strftime('%m-%d %H:%M')}</td></tr>"

    html += "</table></div></div></body></html>"
    return HTMLResponse(content=html)


@app.get("/admin/api/stats")
async def admin_stats(token: str = Query(...)):
    verify_admin(token)
    return {"redeem_codes": redeem_mgr.get_stats()}


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "rpa_available": RPA_AVAILABLE,
        "queue_size": order_queue.qsize(),
        "rpa_queue_size": rpa_task_queue.qsize(),
    }


@app.get("/")
async def root():
    return {"message": "PPT 全自动发货系统 (RPA)", "rpa": RPA_AVAILABLE}
