# RPA 配置指南

## 前提条件

1. **Kimi Allegro 会员账号** (¥559-699/月)
2. **服务器/电脑能运行 Chrome** (建议 Linux 服务器)

## 安装

```bash
cd auto_deploy
pip install -r requirements.txt
playwright install chromium
```

## 第一步：录制操作获取选择器

RPA 代码中的界面元素选择器需要根据 Kimi 网页版实际界面来配置。用 Playwright 的 codegen 工具录制一遍操作：

```bash
# 启动录制工具
playwright codegen https://kimi.moonshot.cn/
```

这会打开一个浏览器窗口和一个录制面板。你手动操作一遍：
1. 登录 Kimi Allegro
2. 找到并点击 PPT 助手入口
3. 输入提示词
4. 选择风格
5. 点击生成
6. 等待完成
7. 点击下载

录制完成后，复制 codegen 生成的代码，提取其中的选择器，填入 `rpa/config.py` 的 `PPTUIConfig` 中。

## 第二步：导出登录 Cookie（推荐）

手动登录一次 Kimi，导出 Cookie 供 RPA 复用：

```bash
python -c "
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto('https://kimi.moonshot.cn/')
    print('请手动登录，登录完成后按回车...')
    input()
    cookies = context.cookies()
    with open('kimi_cookies.json', 'w') as f:
        json.dump(cookies, f)
    print('Cookie 已保存到 kimi_cookies.json')
    browser.close()
"
```

## 第三步：配置环境变量

```bash
export XIANGUANJIA_APP_KEY="xxx"
export XIANGUANJIA_APP_SECRET="yyy"
export KIMI_COOKIE_FILE="./kimi_cookies.json"
# 或账号密码
export KIMI_USERNAME="你的手机号"
export KIMI_PASSWORD="你的密码"
export SMTP_HOST="smtp.qq.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your@qq.com"
export SMTP_PASSWORD="授权码"
export SENDER_NAME="PPT生成服务"
export ADMIN_TOKEN="admin123"
```

## 第四步：启动服务

```bash
# 开发模式（有界面，方便调试）
export RPA_HEADLESS=false
uvicorn webhook_server:app --reload

# 生产模式
export RPA_HEADLESS=true
uvicorn webhook_server:app --host 0.0.0.0 --port 8000
```

## 注意事项

1. **并发限制**：Allegro 账号可能限制同时进行的任务数，建议 `max_concurrent=1`
2. **网页改版**：Kimi 网页版改版后，选择器可能失效，需要重新录制
3. **Cookie 过期**：Cookie 通常有有效期，过期后需要重新导出
4. **验证码**：如果触发了验证码，RPA 会失败，需要人工处理

## 成本核算

| 方案 | 月成本 | 说明 |
|------|--------|------|
| 买 7元码 | 卖多少花多少 | 无需开发维护 |
| Allegro RPA | ¥699/月 + 服务器 | 需要维护，月销>100单才划算 |

如果你月销 < 100 单，建议用 7元码方案（之前写好的 k.ai-synth.com 中转版）。
