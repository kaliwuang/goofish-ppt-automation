@echo off
chcp 65001 >nul 2>&1
title 闲鱼 PPT 全自动发货系统 - 一键部署
setlocal EnableDelayedExpansion

REM ============================================
REM 闲鱼 PPT 全自动发货系统 - Windows 一键部署
REM ============================================

echo.
echo  ============================================
echo   闲鱼 PPT 全自动发货系统
echo   Windows 一键部署脚本
echo  ============================================
echo.

set "REPO_URL=https://github.com/kaliwuang/goofish-ppt-automation.git"
set "PROJECT_DIR=goofish-ppt-automation"
set "APP_DIR=auto_deploy"
set "VENV_DIR=venv"

REM 检测 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%a in ('python --version 2^>^&1') do set "PY_VER=%%a"
echo [INFO] 检测到 Python: %PY_VER%

REM 检测 Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Git，请先安装 Git
    echo 下载地址: https://git-scm.com/download/win
    pause
    exit /b 1
)

REM 克隆代码
if exist "%PROJECT_DIR%" (
    echo [WARN] 目录 %PROJECT_DIR% 已存在
    set /p "CONFIRM=是否删除重新克隆? [y/N] "
    if /i "!CONFIRM!"=="y" (
        rmdir /s /q "%PROJECT_DIR%"
        git clone --depth 1 "%REPO_URL%" "%PROJECT_DIR%"
    ) else (
        echo [INFO] 使用现有代码
    )
) else (
    echo [INFO] 克隆代码...
    git clone --depth 1 "%REPO_URL%" "%PROJECT_DIR%"
)

cd "%PROJECT_DIR%\%APP_DIR%"

REM 创建虚拟环境
if exist "%VENV_DIR%" (
    echo [WARN] 虚拟环境已存在
    set /p "CONFIRM=是否重新创建? [y/N] "
    if /i "!CONFIRM!"=="y" (
        rmdir /s /q "%VENV_DIR%"
        python -m venv "%VENV_DIR%"
    )
) else (
    echo [INFO] 创建虚拟环境...
    python -m venv "%VENV_DIR%"
)

REM 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"

REM 安装依赖
echo [INFO] 安装 Python 依赖...
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo [OK] Python 依赖安装完成

REM 选择方案
echo.
echo  ============================================
echo   选择部署方案
echo  ============================================
echo.
echo  1) 中转方案 ^(推荐^) - 用 k.ai-synth.com 7元码
echo     成本低，无需 Allegro 账号
echo.
echo  2) RPA 方案 - 用 Kimi Allegro 自动生成
echo     需要 Allegro 会员 ^(¥699/月^)
echo.
set /p "SCHEME=选择方案 [1/2, 默认1]: "
if "%SCHEME%"=="" set "SCHEME=1"

if "%SCHEME%"=="2" (
    echo [INFO] 安装 Playwright Chromium...
    playwright install chromium
    echo [OK] Playwright 安装完成
)

REM 配置环境变量
echo.
echo  ============================================
echo   配置环境变量
echo  ============================================
echo.

if exist ".env" (
    echo [WARN] .env 文件已存在
    set /p "CONFIRM=是否覆盖? [y/N] "
    if /i "!CONFIRM!"=="y" (
        goto :configure
    )
    goto :skip_config
)

:configure
set /p "APP_KEY=闲管家 AppKey: "
set /p "APP_SECRET=闲管家 AppSecret: "
set /p "ADMIN_TOKEN=管理后台密码 [默认: admin]: "
if "!ADMIN_TOKEN!"=="" set "ADMIN_TOKEN=admin"
set /p "BASE_URL=服务域名 (如 https://ppt.yourdomain.com): "

(
    echo XIANGUANJIA_APP_KEY=!APP_KEY!
    echo XIANGUANJIA_APP_SECRET=!APP_SECRET!
    echo ADMIN_TOKEN=!ADMIN_TOKEN!
    echo BASE_URL=!BASE_URL!
    echo.
    echo # SMTP 配置（可选）
    echo # SMTP_HOST=smtp.qq.com
    echo # SMTP_PORT=587
    echo # SMTP_USERNAME=your@qq.com
    echo # SMTP_PASSWORD=授权码
    echo # SENDER_NAME=PPT生成服务
    echo.
    echo # RPA 配置（仅方案2需要）
    echo # KIMI_COOKIE_FILE=./kimi_cookies.json
) > .env

echo [OK] .env 配置完成

:skip_config

REM 初始化数据库
echo [INFO] 初始化数据库...
python -c "from database import init_db; init_db()"
echo [OK] 数据库初始化完成

REM 导入兑换码
echo.
set /p "HAS_CSV=是否有兑换码 CSV 文件需要导入? [y/N] "
if /i "!HAS_CSV!"=="y" (
    set /p "CSV_PATH=CSV 文件路径: "
    if exist "!CSV_PATH!" (
        copy "!CSV_PATH!" .\codes.csv >nul
        python import_codes.py codes.csv
    ) else (
        echo [ERROR] 文件不存在: !CSV_PATH!
    )
)

REM 启动服务
echo.
echo  ============================================
echo   启动服务
echo  ============================================
echo.

set /p "START_NOW=是否现在启动服务? [Y/n] "
if "!START_NOW!"=="" set "START_NOW=Y"

if /i "!START_NOW!"=="Y" (
    echo [INFO] 启动服务...
    echo.
    echo 访问地址:
    echo   管理后台: !BASE_URL!/admin/dashboard?token=!ADMIN_TOKEN!
    echo   Webhook:  !BASE_URL!/webhook/xian-guanjia
    echo   健康检查: !BASE_URL!/health
    echo.
    echo 按 Ctrl+C 停止服务
    echo.
    uvicorn webhook_server:app --host 0.0.0.0 --port 8000
) else (
    echo.
    echo 稍后手动启动:
    echo   cd %PROJECT_DIR%\%APP_DIR%
    echo   call venv\Scripts\activate.bat
    echo   uvicorn webhook_server:app --host 0.0.0.0 --port 8000
    echo.
    pause
)

endlocal
