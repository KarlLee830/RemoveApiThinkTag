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

def clean_think_content(text):
    """清理文本中的思考内容"""
    return re.sub(r'<think>.*?</think>\s*\n*', '', text, flags=re.DOTALL).strip()

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    user_data = request.json
    
    # 清理输入消息中的思考内容
    if 'messages' in user_data:
        cleaned_messages = []
        for msg in user_data['messages']:
            content = msg.get('content', '')
            cleaned_msg = msg.copy()
            cleaned_msg['content'] = clean_think_content(content)
            cleaned_messages.append(cleaned_msg)
        user_data['messages'] = cleaned_messages
    
    # 确保不使用流式传输
    if 'stream' in user_data:
        del user_data['stream']
    
    headers = {
        "Authorization": request.headers.get('Authorization'),
        "Content-Type": "application/json"
    }
    
    # 发送请求并获取响应
    response = requests.post(
        FORWARD_URL,
        json=user_data,
        headers=headers
    )
    
    try:
        response_data = response.json()
        
        # 清理响应中的思考内容
        if 'choices' in response_data:
            for choice in response_data['choices']:
                if 'message' in choice:
                    content = choice['message'].get('content', '')
                    choice['message']['content'] = clean_think_content(content)
                if 'text' in choice:
                    choice['text'] = clean_think_content(choice['text'])
                if 'content' in choice:
                    choice['content'] = clean_think_content(choice['content'])
        
        return response_data, response.status_code
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response from API"}, 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9006) 