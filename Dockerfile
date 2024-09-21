# 基础镜像为 Python 3.8.10
FROM python:3.8.10-slim

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt 到容器中
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目的所有文件到容器中
COPY . .

# 运行程序 (假设入口文件是 bot.py)
CMD ["python", "bot.py"]
