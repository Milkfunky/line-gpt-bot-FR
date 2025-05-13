from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os

app = Flask(__name__)

# ดึง token และ secret จาก environment variables
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/")
def home():
    return "LINE-GPT Bot is running."

# ✅ Route นี้ต้องมี methods=['POST'] เพื่อให้ Webhook ของ LINE ทำงานได้
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK', 200

# ✅ จัดการข้อความที่เข้ามา
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text

    # เรียก ChatGPT มาตอบ
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # หรือ "gpt-4" ถ้ามีสิทธิ์
        messages=[
            {"role": "system", "content": "คุณคือฝ่ายขายรถจักรยานยนต์"},
            {"role": "user", "content": user_msg}
        ]
    )

    reply_text = response.choices[0].message.content
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()
