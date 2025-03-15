from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import httpx
import json
import time
import random
import re
import asyncio
from urllib.parse import urlparse

app = FastAPI()

class Message(BaseModel):
    role: str
    content: str
    
class CompletionRequest(BaseModel):
    model: Optional[str] = "deepseek-chat"
    messages: List[Dict[str, str]] = []
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    api_key: Optional[str] = None

def generate_random_id():
    """生成随机ID，类似于原始代码中的函数"""
    return ''.join(random.choice('0123456789abcdef') for _ in range(32))

def create_reasoning_chunk(content, original_data, model_name):
    """创建推理数据块"""
    return {
        "id": original_data.get("id", generate_random_id()),
        "created": original_data.get("created", int(time.time())),
        "model": model_name,
        "object": "chat.completion.chunk",
        "choices": [{
            "delta": {
                "content": "",
                "reasoning_content": content,
                "role": "assistant"
            },
            "index": 0
        }],
        "usage": None
    }

def create_content_chunk(content, original_data):
    """创建内容数据块"""
    return {
        "id": original_data.get("id", generate_random_id()),
        "created": original_data.get("created", int(time.time())),
        "model": original_data.get("model"),
        "object": "chat.completion.chunk",
        "choices": [{
            "delta": {
                "content": content,
                "role": "assistant"
            },
            "index": 0
        }],
        "usage": None
    }

def process_non_stream_response(response_data):
    """处理非流式响应中的<think>标签"""
    if (response_data.get("choices") and response_data["choices"][0] 
            and response_data["choices"][0].get("message")):
        content = response_data["choices"][0]["message"].get("content", "")
        
        # 检查是否包含<think>标签
        think_match = re.search(r'<think>([\s\S]*?)</think>', content)
        
        if think_match:
            # 提取思考内容
            think_content = think_match.group(1)
            
            # 更新消息内容，移除<think>标签
            response_data["choices"][0]["message"]["content"] = re.sub(
                r'<think>[\s\S]*?</think>', '', content
            ).strip()
            
            # 添加reasoning_content字段
            response_data["choices"][0]["message"]["reasoning_content"] = think_content
    
    return response_data

async def process_stream_response(response, model_name="deepseek-r1"):
    """处理流式响应"""
    buffer = ''
    inside_think = False
    think_content = ''
    has_started_regular_content = False
    
    async for chunk in response.aiter_bytes():
        if not chunk:
            continue
            
        decoded = chunk.decode('utf-8')
        buffer += decoded
        
        # 处理完整行
        lines = buffer.split('\n')
        buffer = lines.pop() if lines else ''
        
        for line in lines:
            if not line.strip():
                yield b'\n'
                continue
                
            if line == 'data: [DONE]':
                yield b'data: [DONE]\n\n'
                continue
                
            if line.startswith('data: '):
                try:
                    # 解析JSON数据
                    json_data = json.loads(line[6:])
                    
                    # 更新模型名称（如果可用）
                    if json_data.get('model') and "reasoning" not in json_data.get('model', ""):
                        model_name = json_data['model']
                    
                    # 检查delta中是否有内容
                    if (json_data.get('choices') and json_data['choices'][0] 
                            and json_data['choices'][0].get('delta')):
                        delta = json_data['choices'][0]['delta']
                        content = delta.get('content', '')
                        
                        # 处理<think>标签和内容
                        if '<think>' in content and not inside_think:
                            inside_think = True
                            
                            # 如果<think>标签不在开头，处理之前的文本
                            parts = content.split('<think>')
                            if parts[0]:
                                # 发送<think>标签前的内容
                                content_chunk = create_content_chunk(parts[0], json_data)
                                yield f"data: {json.dumps(content_chunk)}\n\n".encode('utf-8')
                            
                            # 提取<think>标签中的内容（如果在同一块中关闭）
                            if '</think>' in content:
                                think_match = re.search(r'<think>([\s\S]*?)</think>', content)
                                if think_match and think_match.group(1):
                                    # 发送思考内容
                                    chunks = re.findall(r'.{1,5}|.+', think_match.group(1))
                                    for chunk in chunks:
                                        reasoning_chunk = create_reasoning_chunk(chunk, json_data, model_name)
                                        yield f"data: {json.dumps(reasoning_chunk)}\n\n".encode('utf-8')
                                    
                                    # 处理</think>后的内容
                                    after_think = content.split('</think>')[1] if '</think>' in content else ''
                                    if after_think:
                                        has_started_regular_content = True
                                        content_chunk = create_content_chunk(after_think, json_data)
                                        yield f"data: {json.dumps(content_chunk)}\n\n".encode('utf-8')
                                    
                                    inside_think = False
                                    
                                else:
                                    # 只有<think>标签的开头，存储<think>后的内容
                                    think_content = parts[1] if len(parts) > 1 else ''
                            
                        elif '</think>' in content and inside_think:
                            # 处理思考结束
                            parts = content.split('</think>')
                            think_content += parts[0]
                            
                            # 发送完整的思考内容
                            if think_content.strip():
                                chunks = re.findall(r'.{1,5}|.+', think_content)
                                for chunk in chunks:
                                    reasoning_chunk = create_reasoning_chunk(chunk, json_data, model_name)
                                    yield f"data: {json.dumps(reasoning_chunk)}\n\n".encode('utf-8')
                            
                            # 重置思考状态
                            inside_think = False
                            think_content = ''
                            
                            # 处理</think>后的内容
                            if parts[1]:
                                has_started_regular_content = True
                                content_chunk = create_content_chunk(parts[1], json_data)
                                yield f"data: {json.dumps(content_chunk)}\n\n".encode('utf-8')
                        
                        elif inside_think:
                            # 在思考内部，累积内容
                            think_content += content
                            
                            # 发送思考内容块以获得更好的流式体验
                            if len(think_content) > 10:
                                chunks = re.findall(r'.{1,5}|.+', think_content)
                                for chunk in chunks:
                                    reasoning_chunk = create_reasoning_chunk(chunk, json_data, model_name)
                                    yield f"data: {json.dumps(reasoning_chunk)}\n\n".encode('utf-8')
                                think_content = ''
                        
                        else:
                            # 思考之外的常规内容
                            has_started_regular_content = True
                            content_chunk = create_content_chunk(content, json_data)
                            yield f"data: {json.dumps(content_chunk)}\n\n".encode('utf-8')
                    
                    else:
                        # 没有delta内容或其他消息结构，原样传递
                        yield f"{line}\n\n".encode('utf-8')
                
                except Exception as e:
                    # JSON解析错误，只转发该行
                    print(f"Error parsing JSON: {e}")
                    yield f"{line}\n\n".encode('utf-8')
            
            else:
                # 不是数据行，按原样转发
                yield f"{line}\n".encode('utf-8')
    
    # 处理任何剩余缓冲区
    if buffer.strip():
        yield f"{buffer}\n\n".encode('utf-8')
    
    # 如果我们有任何剩余的思考内容，发送它
    if inside_think and think_content.strip():
        timestamp = int(time.time())
        id = generate_random_id()
        reasoning_chunk = create_reasoning_chunk(
            think_content, {"created": timestamp, "id": id}, model_name
        )
        yield f"data: {json.dumps(reasoning_chunk)}\n\n".encode('utf-8')

@app.post("/v1/chat/completions")
async def handle_request(request: Request, completion_req: CompletionRequest):
    try:
        # 从Authorization头中提取密钥和端点
        auth_header = request.headers.get('Authorization', '')
        bearer_match = re.match(r'^Bearer\s+(.+)$', auth_header, re.I)
        key_field = bearer_match.group(1) if bearer_match else completion_req.api_key or ''
        
        # 找到第一个冒号的位置，正确分割API密钥和端点URL
        colon_index = key_field.find(':')
        if colon_index == -1:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": 'Invalid API key format. Expected format: "key:https://endpoint.com"'}}
            )
        
        api_key = key_field[:colon_index]
        endpoint = key_field[colon_index + 1:]
        
        # 验证URL格式
        try:
            urlparse(endpoint)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": f"Invalid endpoint URL: {endpoint}"}}
            )
        
        # 准备发送到DeepSeek的请求
        is_streaming = completion_req.stream == True
        deepseek_request = {
            "model": completion_req.model,
            "messages": completion_req.messages,
            "temperature": completion_req.temperature,
            "top_p": completion_req.top_p,
            "max_tokens": completion_req.max_tokens,
            "stream": is_streaming
        }
        
        # 过滤掉None值
        deepseek_request = {k: v for k, v in deepseek_request.items() if v is not None}
        
        async with httpx.AsyncClient() as client:
            # 发送请求到DeepSeek API
            deepseek_response = await client.post(
                endpoint,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                },
                json=deepseek_request,
                timeout=60.0
            )
            
            # 检查响应是否成功
            if deepseek_response.status_code != 200:
                content_type = deepseek_response.headers.get('Content-Type', '')
                
                # 尝试读取错误信息
                if 'application/json' in content_type:
                    error_data = deepseek_response.json()
                    return JSONResponse(
                        status_code=deepseek_response.status_code,
                        content={"error": {"message": f"DeepSeek API error: {json.dumps(error_data)}"}}
                    )
                else:
                    # 非JSON错误响应
                    error_text = deepseek_response.text
                    return JSONResponse(
                        status_code=500,
                        content={"error": {"message": f"DeepSeek API returned non-JSON error: {error_text[:100]}..."}}
                    )
            
            # 处理流式或非流式响应
            if is_streaming:
                return StreamingResponse(
                    process_stream_response(deepseek_response, completion_req.model),
                    media_type="text/event-stream",
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive'
                    }
                )
            else:
                # 处理非流式响应
                response_data = deepseek_response.json()
                processed_data = process_non_stream_response(response_data)
                return JSONResponse(content=processed_data)
                
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": f"Error: {str(error)}"}}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)