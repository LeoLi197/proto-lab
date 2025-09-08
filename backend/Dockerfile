# Use the full python:3.11 base image. It contains necessary build tools.
FROM python:3.11

# Set the working directory
WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# [最佳实践] 优化 Docker 层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有剩余的源代码和配置文件
COPY . .

# Command to run the application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}