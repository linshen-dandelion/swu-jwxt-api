# 使用 Python 3.11 轻量镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（ddddocr 需要）
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY main.py .
COPY des.py .

# 暴露端口（Railway 会自动设置 PORT 环境变量）
EXPOSE ${PORT:-8000}

# 启动应用
CMD ["python", "main.py"]
