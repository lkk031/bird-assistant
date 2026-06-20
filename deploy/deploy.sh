#!/usr/bin/env bash
#
# 鸟助手 (Assistant-Bird) — 服务器部署脚本
# 适用于 Ubuntu 22.04/24.04
#
# 用法:
#   1. 将项目上传到服务器的 /opt/assistant-bird/
#   2. 以 root 运行:  bash /opt/assistant-bird/deploy/deploy.sh
#
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_USER="assistant-bird"
APP_DIR="/opt/assistant-bird"
LOG_DIR="/var/log/assistant-bird"
PORT=19900
PYTHON_VERSION="3.12"

# ── 检查是否为 root ───────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}请以 root 运行此脚本: sudo bash $0${NC}"
    exit 1
fi

echo -e "${GREEN}=== 鸟助手 (Assistant-Bird) 服务器部署 ===${NC}"
echo ""

# ── Step 1: 安装系统依赖 ─────────────────────────────────────────────
echo -e "${YELLOW}[1/7] 安装系统依赖...${NC}"
apt-get update -qq
apt-get install -y -qq \
    "python${PYTHON_VERSION}" \
    "python${PYTHON_VERSION}-venv" \
    python3-pip \
    git \
    curl \
    > /dev/null 2>&1

# 安装 Poetry
if ! command -v poetry &> /dev/null; then
    echo "  安装 Poetry..."
    curl -sSL https://install.python-poetry.org | python3 - > /dev/null 2>&1
    export PATH="/root/.local/bin:$PATH"
fi

# ── Step 2: 创建专用用户 ─────────────────────────────────────────────
echo -e "${YELLOW}[2/7] 创建专用用户...${NC}"
if ! id "$APP_USER" &> /dev/null; then
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
    echo "  用户 $APP_USER 已创建"
else
    echo "  用户 $APP_USER 已存在"
fi

# ── Step 3: 创建目录 ─────────────────────────────────────────────────
echo -e "${YELLOW}[3/7] 创建目录...${NC}"
mkdir -p "$APP_DIR" "$LOG_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$LOG_DIR"
chmod 755 "$APP_DIR" "$LOG_DIR"

# ── Step 4: 安装 Python 依赖 ─────────────────────────────────────────
echo -e "${YELLOW}[4/7] 安装 Python 依赖...${NC}"
cd "$APP_DIR"

export PATH="/root/.local/bin:$PATH"
poetry config virtualenvs.in-project true --local
poetry install --no-dev 2>&1 | tail -5
chown -R "$APP_USER:$APP_USER" "$APP_DIR/.venv"
echo "  依赖安装完成"

# ── Step 5: 检查 .env 文件 ───────────────────────────────────────────
echo -e "${YELLOW}[5/7] 检查配置文件...${NC}"
if [[ ! -f "$APP_DIR/.env" ]]; then
    if [[ -f "$APP_DIR/.env.example" ]]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        echo -e "${RED}  ⚠ 请编辑 $APP_DIR/.env，填入你的 DEEPSEEK_API_KEY${NC}"
    else
        echo -e "${RED}  ⚠ .env.example 不存在，请手动创建 $APP_DIR/.env${NC}"
    fi
else
    echo "  .env 已存在"
fi

# ── Step 6: 安装 systemd 服务 ────────────────────────────────────────
echo -e "${YELLOW}[6/7] 安装 systemd 服务...${NC}"
cp "$APP_DIR/deploy/assistant-bird.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable assistant-bird

# ── Step 7: 配置防火墙 ───────────────────────────────────────────────
echo -e "${YELLOW}[7/7] 配置防火墙...${NC}"
if command -v ufw &> /dev/null && ufw status | grep -q "active"; then
    ufw allow "$PORT"/tcp comment "assistant-bird" 2>/dev/null || true
    echo "  已放行端口 $PORT"
else
    echo "  ufw 未启用，跳过防火墙配置"
    echo -e "${YELLOW}  ⚠ 请确保云服务商安全组已放行 TCP $PORT${NC}"
fi

# ── 完成 ──────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  后续步骤:"
echo ""
echo -e "  1. ${YELLOW}编辑配置文件${NC}:"
echo "     vim $APP_DIR/.env"
echo "     → 填写 DEEPSEEK_API_KEY（必填）"
echo "     → 填写 MEM0_API_KEY（可选，不填则禁用记忆功能）"
echo ""
echo "  2. ${YELLOW}启动服务${NC}:"
echo "     sudo systemctl start assistant-bird"
echo ""
echo "  3. ${YELLOW}检查状态${NC}:"
echo "     sudo systemctl status assistant-bird"
echo "     curl http://localhost:$PORT/health"
echo ""
echo "  4. ${YELLOW}手机连接${NC}:"
echo "     手机浏览器打开: http://<服务器公网IP>:$PORT"
echo "     (确保云服务商安全组/防火墙已放行 $PORT 端口)"
echo ""
echo "  查看日志:"
echo "     sudo journalctl -u assistant-bird -f"
echo "     tail -f $LOG_DIR/access.log"
echo ""
