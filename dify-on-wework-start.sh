#!/bin/bash

set -a
if [ -f "$PWD/.env" ]; then
	source "$PWD/.env"
fi
set +a

# 激活虚拟环境（使用动态路径）
source "$PWD/venv/bin/activate"

# 启动 Uvicorn
nohup uvicorn main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-80}" >> "${UVICORN_LOG_FILE:-/var/log/dify_on_wework_main.log}" 2>> "${UVICORN_ERROR_LOG_FILE:-/var/log/dify_on_wework_main_error.log}" &

# 启动 Celery
nohup celery -A tasks worker --loglevel=info >> "${CELERY_LOG_FILE:-/var/log/dify_on_wework_celery.log}" 2>> "${CELERY_ERROR_LOG_FILE:-/var/log/dify_on_wework_celery_error.log}" &
