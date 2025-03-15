# 使用 Python 3.12 作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .

# 暴露端口
EXPOSE 9006

# 设置默认环境变量
ENV FORWARD_URL=https://api.deepseek.com/v1/chat/completions

# 启动应用
CMD ["python", "app.py"] 