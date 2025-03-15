from flask import Flask, request, Response, stream_with_context
import requests
import json
import re
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 获取转发地址，如果环境变量未设置则使用默认值
FORWARD_URL = os.getenv('FORWARD_URL', 'https://api.deepseek.comv1/chat/completions')

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
    
    user_data['stream'] = True
    
    # 转发请求
    response = requests.post(
        FORWARD_URL,
        json=user_data,
        headers=headers,
        stream=True
    )
    
    def generate():
        # 用于跟踪我们是否在<think>标签内
        in_think_block = False
        buffer = ""
        
        for line in response.iter_lines():
            if line:
                json_str = line.decode('utf-8').replace('data: ', '')
                
                if json_str == '[DONE]':
                    yield 'data: [DONE]\n\n'
                    break
                
                try:
                    response_data = json.loads(json_str)
                    if 'choices' in response_data and response_data['choices']:
                        choice = response_data['choices'][0]
                        if 'delta' in choice:
                            delta = choice['delta']
                            
                            # 忽略reasoning_content，不处理
                            if 'reasoning_content' in delta:
                                continue
                            
                            # 处理普通content
                            content = delta.get('content', '')
                            if content:
                                # 将内容添加到缓冲区
                                buffer += content
                                
                                # 检查缓冲区是否包含<think>标签
                                think_start = buffer.find("<think>")
                                if think_start != -1 and not in_think_block:
                                    # 发送<think>之前的内容
                                    if think_start > 0:
                                        modified_data = {
                                            'choices': [{
                                                'delta': {
                                                    'content': buffer[:think_start]
                                                }
                                            }]
                                        }
                                        yield f"data: {json.dumps(modified_data)}\n\n"
                                    in_think_block = True
                                    buffer = buffer[think_start + 7:]  # 移除<think>
                                
                                # 检查缓冲区是否包含</think>标签
                                if in_think_block:
                                    think_end = buffer.find("</think>")
                                    if think_end != -1:
                                        in_think_block = False
                                        # 只保留</think>后面的内容
                                        buffer = buffer[think_end + 8:]
                                
                                # 如果不在思考块中且缓冲区有内容，发送内容
                                if not in_think_block and buffer and "<think>" not in buffer:
                                    modified_data = {
                                        'choices': [{
                                            'delta': {
                                                'content': buffer
                                            }
                                        }]
                                    }
                                    yield f"data: {json.dumps(modified_data)}\n\n"
                                    buffer = ""
                            
                            # 处理其他非content字段
                            if not content and not delta.get('reasoning_content', ''):
                                yield f"data: {json_str}\n\n"
                        else:
                            yield f"data: {json_str}\n\n"
                    else:
                        yield f"data: {json_str}\n\n"
                        
                except json.JSONDecodeError:
                    yield f"data: {json_str}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream'
    )

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=9006) 