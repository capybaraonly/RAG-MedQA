#!/usr/bin/env bash
# 开发模式后端启动脚本
# 在项目根目录执行：bash docker/launch_backend_service.sh
# 前提：已激活 uv 虚拟环境，并运行了 docker compose -f docker/docker-compose-base.yml up -d

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$PROJECT_ROOT"

# 加载 docker/.env（若存在）
ENV_FILE="$SCRIPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
fi

cd "$PROJECT_ROOT"

# 等待 MySQL 就绪（最多 60 秒）
echo "Waiting for MySQL..."
for i in $(seq 1 30); do
    if python3 - <<'EOF' 2>/dev/null
import socket, sys
try:
    s = socket.create_connection(('127.0.0.1', 3306), timeout=2)
    s.close()
    sys.exit(0)
except: sys.exit(1)
EOF
    then
        echo "MySQL is ready."
        break
    fi
    echo "  MySQL not ready yet ($i/30)..."
    sleep 2
done

# 等待 Elasticsearch 就绪（最多 60 秒）
echo "Waiting for Elasticsearch..."
for i in $(seq 1 30); do
    if curl -sf -u "elastic:infini_rag_flow" "http://localhost:1200/_cluster/health" \
        2>/dev/null | grep -qE '"status":"(green|yellow)"'; then
        echo "Elasticsearch is ready."
        break
    fi
    echo "  ES not ready yet ($i/30)..."
    sleep 2
done

echo "Starting RAG-MedQA backend..."
exec python api/ragflow_server.py "$@"
