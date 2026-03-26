#!/usr/bin/env python3
"""
最简单的飞书OCR服务 - 只处理验证和健康检查
"""

import os
import json
import hashlib
import hmac
from flask import Flask, request, jsonify

app = Flask(__name__)

# 配置
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "AlQaJumGn0JaupuJPy1w8cevAWIZMebJ")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "openclaw125800")

def verify_signature(timestamp: str, nonce: str, signature: str, body: str) -> bool:
    """验证飞书签名"""
    if not FEISHU_ENCRYPT_KEY:
        return True
    content = f"{timestamp}\n{nonce}\n{body}\n"
    key = FEISHU_ENCRYPT_KEY.encode('utf-8')
    message = content.encode('utf-8')
    hmac_obj = hmac.new(key, message, digestmod=hashlib.sha256)
    calculated_signature = hmac_obj.hexdigest()
    return hmac.compare_digest(calculated_signature, signature)

@app.route('/feishu-ocr-webhook', methods=['POST'])
def webhook():
    """处理飞书webhook"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "无效请求"}), 400
        
        # 验证签名
        timestamp = request.headers.get('X-Lark-Request-Timestamp', '')
        nonce = request.headers.get('X-Lark-Request-Nonce', '')
        signature = request.headers.get('X-Lark-Signature', '')
        body = request.get_data(as_text=True)
        
        if not verify_signature(timestamp, nonce, signature, body):
            return jsonify({"error": "签名验证失败"}), 403
        
        # 处理挑战请求（飞书验证）
        if data.get("type") == "url_verification":
            challenge = data.get("challenge", "")
            print(f"✅ 飞书验证请求，返回challenge: {challenge}")
            return jsonify({"challenge": challenge})
        
        # 处理消息事件（简化版）
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            if event.get("type") == "im.message.receive_v1":
                print(f"📨 收到消息事件")
                return jsonify({"code": 0, "msg": "收到消息，OCR功能待实现"})
        
        return jsonify({"code": 0, "msg": "success"})
        
    except Exception as e:
        print(f"❌ Webhook处理异常: {e}")
        return jsonify({"error": "内部服务器错误"}), 500

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "feishu-ocr-simple",
        "timestamp": 1234567890
    })

@app.route('/', methods=['GET'])
def index():
    """首页"""
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Mark2飞书OCR助手</title></head>
    <body>
        <h1>🤖 Mark2飞书OCR助手（简化版）</h1>
        <p>状态：运行正常</p>
        <p>Webhook地址：<code>/feishu-ocr-webhook</code></p>
        <p>健康检查：<a href="/health">/health</a></p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    print("🚀 启动简化版飞书OCR服务...")
    app.run(host='0.0.0.0', port=3000, debug=False)