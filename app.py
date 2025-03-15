from flask import Flask, request, jsonify
import requests
import json
import re
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 获取转发地址，如果环境变量未设置则使用默认值
FORWARD_URL = os.getenv('FORWARD_URL', 'https://api.deepseek.com/v1/chat/completions')

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    user_data = request.json
    
    if 'messages' in user_data:
        cleaned_messages = []
        for msg in user_data['messages']:
            content = msg.get('content', '')
            cleaned_content = re.sub(r'<think>.*?</think>\s*\n*', '', content, flags=re.DOTALL)
            cleaned_msg = msg.copy()
            cleaned_msg['content'] = cleaned_content.strip()
            cleaned_messages.append(cleaned_msg)
        user_data['messages'] = cleaned_messages
    
    headers = {
        "Authorization": request.headers.get('Authorization'),
        "Content-Type": "application/json"
    }
    
    # 移除 stream 参数，确保不使用流式传输
    if 'stream' in user_data:
        del user_data['stream']
    
    # 发送请求并获取响应
    response = requests.post(
        FORWARD_URL,
        json=user_data,
        headers=headers
    )
    
    # 返回响应结果
    return response.json(), response.status_code

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9006) 