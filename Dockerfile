FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
# 确保安装特定版本的依赖
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# 设置环境变量，可在运行容器时覆盖
ENV API_FORWARD_URL="https://api.openai.com/v1/chat/completions"

# 暴露9006端口
EXPOSE 9006

# 运行应用
CMD ["python", "app.py"] 