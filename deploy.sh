#!/usr/bin/env bash
#
# 一键部署脚本 - 闲鱼 PPT 全自动发货系统
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# 支持系统: Ubuntu/Debian/CentOS/macOS

set -euo pipefail

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
REPO_URL="https://github.com/kaliwuang/goofish-ppt-automation.git"
PROJECT_DIR="goofish-ppt-automation"
APP_DIR="auto_deploy"
VENV_DIR="venv"
PYTHON_CMD=""

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ===================================================================
# 1. 检测系统
# ===================================================================
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &>/dev/null; then
            OS="ubuntu"
        elif command -v yum &>/dev/null; then
            OS="centos"
        elif command -v apk &>/dev/null; then
            OS="alpine"
        else
            OS="linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi
    log_info "检测到系统: $OS"
}

# ===================================================================
# 2. 安装系统依赖
# ===================================================================
install_system_deps() {
    log_info "安装系统依赖..."

    case $OS in
        ubuntu|debian)
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                python3 python3-venv python3-pip \
                git curl wget \
                libnss3 libatk-bridge2.0-0 libxss1 libgtk-3-0 \
                libgbm1 libasound2 libx11-xcb1 libxcomposite1 \
                libxdamage1 libxfixes3 libpango-1.0-0 libcairo2
            ;;
        centos|rhel|fedora)
            sudo yum install -y -q \
                python3 python3-pip git curl wget \
                nss atk at-spi2-atk cups-libs libxcomposite \
                libxrandr libXdamage pango libXcursor \
                libgbm libxss alsa-lib
            ;;
        alpine)
            sudo apk add --no-cache \
                python3 py3-pip git curl bash
            ;;
        macos)
            if ! command -v brew &>/dev/null; then
                log_error "macOS 需要 Homebrew，请先安装: https://brew.sh"
                exit 1
            fi
            brew install python3 git 2>/dev/null || true
            ;;
        *)
            log_warn "未知系统，请手动安装 Python 3.11+ 和 git"
            ;;
    esac

    log_ok "系统依赖安装完成"
}

# ===================================================================
# 3. 检测 Python 版本
# ===================================================================
find_python() {
    log_info "检测 Python 版本..."

    for cmd in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            version=$($cmd --version 2>&1 | awk '{print $2}')
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)

            if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
                PYTHON_CMD="$cmd"
                log_ok "使用 Python $version ($PYTHON_CMD)"
                return 0
            fi
        fi
    done

    log_error "需要 Python 3.10+，但未找到"
    exit 1
}

# ===================================================================
# 4. 克隆代码
# ===================================================================
clone_repo() {
    if [[ -d "$PROJECT_DIR" ]]; then
        log_warn "目录 $PROJECT_DIR 已存在"
        read -rp "是否删除重新克隆? [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            rm -rf "$PROJECT_DIR"
        else
            log_info "使用现有代码"
            return 0
        fi
    fi

    log_info "克隆代码..."
    git clone --depth 1 "$REPO_URL" "$PROJECT_DIR"
    log_ok "代码克隆完成"
}

# ===================================================================
# 5. 创建虚拟环境
# ===================================================================
setup_venv() {
    cd "$PROJECT_DIR/$APP_DIR"

    if [[ -d "$VENV_DIR" ]]; then
        log_warn "虚拟环境已存在"
        read -rp "是否重新创建? [y/N] " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
            "$PYTHON_CMD" -m venv "$VENV_DIR"
        fi
    else
        log_info "创建虚拟环境..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    fi

    source "$VENV_DIR/bin/activate"
    log_ok "虚拟环境已激活"
}

# ===================================================================
# 6. 安装 Python 依赖
# ===================================================================
install_python_deps() {
    log_info "安装 Python 依赖..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    log_ok "Python 依赖安装完成"
}

# ===================================================================
# 7. 安装 Playwright 浏览器（可选）
# ===================================================================
install_playwright() {
    log_info ""
    echo "====================================="
    echo "  选择部署方案"
    echo "====================================="
    echo ""
    echo "1) 中转方案 (推荐) - 用 k.ai-synth.com 7元码"
    echo "   成本低，无需 Allegro 账号"
    echo ""
    echo "2) RPA 方案 - 用 Kimi Allegro 自动生成"
    echo "   需要 Allegro 会员 (¥699/月)"
    echo ""
    read -rp "选择方案 [1/2, 默认1]: " scheme
    scheme=${scheme:-1}

    if [[ "$scheme" == "2" ]]; then
        log_info "安装 Playwright Chromium..."
        playwright install chromium
        log_ok "Playwright 安装完成"
        SCHEME="rpa"
    else
        log_info "使用中转方案，跳过 Playwright"
        SCHEME="proxy"
    fi
}

# ===================================================================
# 8. 配置环境变量
# ===================================================================
configure_env() {
    log_info ""
    echo "====================================="
    echo "  配置环境变量"
    echo "====================================="
    echo ""

    if [[ -f ".env" ]]; then
        log_warn ".env 文件已存在"
        read -rp "是否覆盖? [y/N] " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            return 0
        fi
    fi

    read -rp "闲管家 AppKey: " app_key
    read -rp "闲管家 AppSecret: " app_secret
    read -rp "管理后台密码 [默认: admin]: " admin_token
    admin_token=${admin_token:-admin}
    read -rp "服务域名 (如 https://ppt.yourdomain.com): " base_url

    cat > .env <<EOF
XIANGUANJIA_APP_KEY=$app_key
XIANGUANJIA_APP_SECRET=$app_secret
ADMIN_TOKEN=$admin_token
BASE_URL=$base_url

# SMTP 配置（用于邮件通知，可选）
# SMTP_HOST=smtp.qq.com
# SMTP_PORT=587
# SMTP_USERNAME=your@qq.com
# SMTP_PASSWORD=授权码
# SENDER_NAME=PPT生成服务

# RPA 配置（仅方案2需要）
# KIMI_USERNAME=手机号
# KIMI_PASSWORD=密码
# KIMI_COOKIE_FILE=./kimi_cookies.json
EOF

    log_ok ".env 配置完成"
}

# ===================================================================
# 9. 初始化数据库
# ===================================================================
init_database() {
    log_info "初始化数据库..."
    python3 -c "from database import init_db; init_db()"
    log_ok "数据库初始化完成"
}

# ===================================================================
# 10. 导入测试兑换码（可选）
# ===================================================================
import_codes() {
    log_info ""
    read -rp "是否有兑换码 CSV 文件需要导入? [y/N] " has_csv
    if [[ "$has_csv" =~ ^[Yy]$ ]]; then
        read -rp "CSV 文件路径: " csv_path
        if [[ -f "$csv_path" ]]; then
            cp "$csv_path" ./codes.csv
            python3 import_codes.py codes.csv
        else
            log_error "文件不存在: $csv_path"
        fi
    fi
}

# ===================================================================
# 11. 启动服务
# ===================================================================
start_service() {
    log_info ""
    echo "====================================="
    echo "  启动服务"
    echo "====================================="
    echo ""

    read -rp "是否现在启动服务? [Y/n] " start_now
    start_now=${start_now:-Y}

    if [[ "$start_now" =~ ^[Yy]$ ]]; then
        log_info "启动服务..."
        log_info "访问地址:"
        echo "  管理后台: ${base_url}/admin/dashboard?token=${admin_token}"
        echo "  Webhook:  ${base_url}/webhook/xian-guanjia"
        echo "  健康检查: ${base_url}/health"
        echo ""
        echo "按 Ctrl+C 停止服务"
        echo ""

        uvicorn webhook_server:app --host 0.0.0.0 --port 8000
    else
        log_info ""
        log_info "稍后手动启动:"
        echo "  cd $PROJECT_DIR/$APP_DIR"
        echo "  source venv/bin/activate"
        echo "  uvicorn webhook_server:app --host 0.0.0.0 --port 8000"
    fi
}

# ===================================================================
# 主流程
# ===================================================================
main() {
    echo ""
    echo "====================================="
    echo "  闲鱼 PPT 全自动发货系统"
    echo "  一键部署脚本"
    echo "====================================="
    echo ""

    detect_os
    install_system_deps
    find_python
    clone_repo
    setup_venv
    install_python_deps
    install_playwright
    configure_env
    init_database
    import_codes
    start_service
}

main "$@"
