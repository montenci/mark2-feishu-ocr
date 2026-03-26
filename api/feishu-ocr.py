import os
import json
import base64
import hashlib
import hmac
import time
import requests
from flask import Flask, request, jsonify
from typing import Dict, Any, Optional

app = Flask(__name__)

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "cli_a94e114082b95cbd")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "lHVLsgvpriiYGDOyRoscH62PWmW4AMx7")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "4A6hbamr2MmwTR2ReFLTixSDZr8UIrWv")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "openclaw125800")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")

class FeishuOCRService:
    def __init__(self):
        self.access_token = None
        self._refresh_access_token()
    
    def _refresh_access_token(self):
        if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
            return False
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            result = response.json()
            if result.get("code") == 0:
                self.access_token = result["tenant_access_token"]
                return True
        except:
            pass
        return False
    
    def verify_signature(self, timestamp: str, nonce: str, signature: str, body: str) -> bool:
        if not FEISHU_ENCRYPT_KEY:
            return True
        content = f"{timestamp}\n{nonce}\n{body}\n"
        key = FEISHU_ENCRYPT_KEY.encode('utf-8')
        message = content.encode('utf-8')
        hmac_obj = hmac.new(key, message, digestmod=hashlib.sha256)
        calculated_signature = hmac_obj.hexdigest()
        return hmac.compare_digest(calculated_signature, signature)
    
    def download_image(self, image_key: str) -> Optional[bytes]:
        if not self.access_token and not self._refresh_access_token():
            return None
        url = f"https://open.feishu.cn/open-apis/im/v1/images/{image_key}"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=30)
            return response.content
        except:
            return None
    
    def analyze_image(self, image_data: bytes) -> Optional[str]:
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "qwen/qwen-vl-max",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "提取图片中的所有文字，特别是日期时间科目名称表格数据。简洁回复。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }],
            "max_tokens": 1000
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            result = response.json()
            return result['choices'][0]['message']['content']
        except:
            return None
    
    def reply_message(self, chat_id: str, content: str) -> bool:
        if not self.access_token and not self._refresh_access_token():
            return False
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        data = {"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": content})}
        try:
            requests.post(url, headers=headers, json=data, timeout=10)
            return True
        except:
            return False

ocr_service = FeishuOCRService()

@app.route('/feishu-ocr-webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "无效请求"}), 400
        timestamp = request.headers.get('X-Lark-Request-Timestamp', '')
        nonce = request.headers.get('X-Lark-Request-Nonce', '')
        signature = request.headers.get('X-Lark-Signature', '')
        body = request.get_data(as_text=True)
        if not ocr_service.verify_signature(timestamp, nonce, signature, body):
            return jsonify({"error": "签名验证失败"}), 403
        if data.get("type") == "url_verification":
            return jsonify({"challenge": data.get("challenge", "")})
        if data.get("type") == "event_callback":
            event = data.get("event", {})
            if event.get("type") == "im.message.receive_v1":
                return handle_message(event)
        return jsonify({"code": 0, "msg": "success"})
    except:
        return jsonify({"error": "内部错误"}), 500

def handle_message(event: Dict[str, Any]):
    try:
        message = event.get("message", {})
        if message.get("message_type") != "image":
            return jsonify({"code": 0, "msg": "忽略非图片"})
        chat_id = message.get("chat_id", "")
        content = json.loads(message.get("content", "{}"))
        image_key = content.get("image_key", "")
        if not image_key:
            return jsonify({"code": 0, "msg": "无图片key"})
        image_data = ocr_service.download_image(image_key)
        if not image_data:
            return jsonify({"code": 0, "msg": "下载失败"})
        ocr_result = ocr_service.analyze_image(image_data)
        if not ocr_result:
            ocr_result = "图片分析失败"
        reply_content = f"📸 图片文字提取：\n\n{ocr_result}\n\n---\n🤖 Mark2 OCR助手"
        ocr_service.reply_message(chat_id, reply_content)
        return jsonify({"code": 0, "msg": "处理成功"})
    except:
        return jsonify({"code": 0, "msg": "处理异常"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "feishu-ocr", "timestamp": time.time()})

@app.route('/', methods=['GET'])
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Mark2飞书OCR助手</title></head>
    <body>
        <h1>🤖 Mark2飞书OCR助手</h1>
        <p>状态：运行正常</p>
        <p>Webhook地址：<code>/feishu-ocr-webhook</code></p>
        <p>健康检查：<a href="/health">/health</a></p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=False)
