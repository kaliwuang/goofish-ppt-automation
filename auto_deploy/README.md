# PPT 全自动发货系统

闲鱼订单 -> 自动分配兑换码 -> 调用闲管家发货 -> 买家自助生成 PPT

## 工作原理

```
买家在闲鱼下单并付款
        |
        v
闲管家检测订单状态变更
        |
        v
Webhook POST 推送到本服务
        |
        v
服务从兑换码池取出一个未使用的码
        |
        v
调用闲管家发货接口，发送 k.ai-synth.com 链接
        |
        v
买家点击链接，输入邮箱+需求，KIMI 自动生成 PPT
        |
        v
生成完成后邮件发送结果给买家
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `webhook_server.py` | FastAPI 主服务：Webhook接收 + 管理后台 + 买家提交页 |
| `database.py` | SQLite 数据库模型 (兑换码池、订单记录) |
| `redeem_manager.py` | 兑换码管理：导入、分配、查询、统计 |
| `ai_synth_client.py` | k.ai-synth.com API 客户端 |
| `import_codes.py` | 兑换码批量导入工具 |

## 快速部署

### 1. 安装依赖

```bash
cd auto_deploy
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export XIANGUANJIA_APP_KEY="你的闲管家AppKey"
export XIANGUANJIA_APP_SECRET="你的闲管家AppSecret"
export ADMIN_TOKEN="自定义管理后台密码"
```

### 3. 导入兑换码

先批量购买 k.ai-synth.com 的兑换码，整理成 CSV：

```csv
code,order_id
LCJBCKMRLXHW,3306169489513009982
ABC123DEF456,3306169489513009983
```

然后导入：

```bash
python import_codes.py codes.csv
```

查看库存：

```bash
python import_codes.py --stats
```

### 4. 启动服务

```bash
uvicorn webhook_server:app --host 0.0.0.0 --port 8000
```

### 5. 配置闲管家 Webhook

在闲管家开放平台后台，将推送地址设为：

```
https://你的域名/webhook/xian-guanjia
```

## 管理后台

访问 `/admin/dashboard?token=你的ADMIN_TOKEN` 查看：
- 兑换码库存统计
- 最近分配的兑换码
- 订单发货状态

## 买家流程

### 方式A：直接转发链接（推荐，最简单）

买家收到消息后，直接点击 k.ai-synth.com 的原链接自助提交。无需任何额外开发。

### 方式B：中转提交页

访问 `/s/{兑换码}` 进入简化版提交页面，填写需求后由后端代提交到 k.ai-synth.com。

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/webhook/xian-guanjia` | POST | 接收闲管家订单推送 |
| `/s/{code}` | GET | 买家提交页面 |
| `/api/submit` | POST | 代提交到 k.ai-synth.com |
| `/admin/dashboard` | GET | 管理后台 |
| `/admin/api/stats` | GET | 库存统计 API |
| `/admin/api/codes` | GET | 兑换码列表 API |
| `/health` | GET | 健康检查 |

## 注意事项

1. **兑换码是一次性的**：每个 k.ai-synth.com 兑换码只能生成一次 PPT，需要预先批量购买
2. **库存预警**：当未使用兑换码少于5个时，管理后台会标红提醒补货
3. **发货方式**：通过闲管家 `ship_order` 接口，使用 `express_code="other"`，将链接作为运单号发送
