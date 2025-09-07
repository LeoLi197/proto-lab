#!/bin/bash

echo "Setting local environment variables for the backend..."

# 在这里定义所有本地开发需要的源（origin），用逗号隔开
export ALLOWED_ORIGINS="http://localhost:8787,http://127.0.0.1:8787"

echo "Starting FastAPI backend server on port 8080..."
echo "Allowed Origins: $ALLOWED_ORIGINS"
echo "--------------------------------------------------------"

# 进入后端目录并启动服务
cd backend
uvicorn main:app --reload --port 8080