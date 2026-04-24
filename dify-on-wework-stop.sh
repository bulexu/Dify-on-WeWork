#!/bin/bash

set -a
if [ -f "$PWD/.env" ]; then
	source "$PWD/.env"
fi
set +a

# 停止 Uvicorn
pkill -f "uvicorn main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-80}"

# 停止 Celery
pkill -f "celery -A tasks worker"
