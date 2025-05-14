from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI
import os

app = Flask(__name__)

# 🔑 โหลดค่า Token จาก Environment
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return "LINE-GPT Bot is running."

# ✅ ต้องรองรับ POST เท่านั้น
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    print(">> Webhook body:", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Signature verification failed.")
        abort(400)
    except Exception as e:
        print("❌ Unexpected Error:", e)
        abort(500)

    return 'OK', 200

# ✅ ดักข้อความจากผู้ใช้
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "คุณคือฝ่ายขายรถจักรยานยนต์ ช่วยแนะนำรถที่เหมาะสมกับลูกค้า และกระตุ้นให้จองรถอย่างสุภาพ"},
                {"role": "user", "content": user_msg}
            ]
        )
        reply_text = response.choices[0].message.content.strip()
    except Exception as e:
        reply_text = "ขออภัยค่ะ ระบบตอบกลับผิดพลาด: " + str(e)
        print("❌ Error calling OpenAI:", e)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()
