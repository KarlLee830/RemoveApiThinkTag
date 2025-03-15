# RemoveApiThinkTag

这是一个Flask应用，用于过滤API请求中的`<think></think>`标签内容，并将请求转发到指定的API端点。

## 功能

- 过滤掉消息中的`<think></think>`标签及其内容
- 将处理后的请求转发到配置的API端点
- 支持流式响应处理

## 环境变量

- `API_FORWARD_URL`: API转发地址，默认为OpenAI的API地址 `https://api.openai.com/v1/chat/completions`

## 依赖说明

应用使用以下依赖版本：
- Flask 2.0.1
- Werkzeug 2.0.3（特定版本以解决兼容性问题）
- Requests 2.26.0

## 使用Docker运行

### 使用预构建镜像

```bash
docker pull ghcr.io/用户名/RemoveApiThinkTag:latest
docker run -p 9006:9006 -e API_FORWARD_URL="你的API地址" ghcr.io/用户名/RemoveApiThinkTag:latest
```

### 本地构建

```bash
# 克隆仓库
git clone https://github.com/用户名/RemoveApiThinkTag.git
cd RemoveApiThinkTag

# 构建Docker镜像
docker build -t remove-api-think-tag .

# 运行容器
docker run -p 9006:9006 -e API_FORWARD_URL="你的API地址" remove-api-think-tag
```

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export API_FORWARD_URL="你的API地址"

# 运行应用
python app.py
```

## API使用

应用监听在`/v1/chat/completions`端点，与OpenAI API兼容。发送请求时，应用会自动过滤掉消息中的`<think></think>`标签内容。

```bash
curl -X POST http://localhost:9006/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {
        "role": "user",
        "content": "计算1+1等于几？<think>我需要计算1+1，这等于2</think>所以答案是2"
      }
    ]
  }'
```

## 故障排除

如果遇到依赖相关的错误，请确保使用requirements.txt中指定的版本。特别是Werkzeug必须使用2.0.3版本，以避免与Flask 2.0.1的兼容性问题。

## GitHub Actions

本仓库配置了GitHub Actions工作流，当推送到main或master分支时，会自动构建Docker镜像并发布到GitHub Packages。 