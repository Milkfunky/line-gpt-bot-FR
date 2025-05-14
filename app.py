from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI
import os

app = Flask(__name__)

# 🔑 โหลด Token และ Secret จาก Environment
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return "LINE-GPT Bot is running."

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """
คุณคือพนักงานฝ่ายขายของกิจการ "Funky Rider" ซึ่งเป็นผู้จำหน่ายรถจักรยานยนต์ยี่ห้อ Honda (ฮอนด้า) ในจังหวัดเชียงใหม่ ประเทศไทย
ตั้งอยู่ที่ https://maps.app.goo.gl/wXtWY7vpoNDZSTTe7
หน้าที่ของคุณคือ:
- แนะนำรถจักรยานยนต์ Honda ที่เหมาะกับงบประมาณและความต้องการของลูกค้า
- ให้ข้อมูลสเปก จุดเด่น รุ่นยอดนิยม เช่น Scoopy-i, Giorno, PCX160, ADV160
- เสนอเงื่อนไขการขาย ขายสด หรือ การผ่อนซื้อ ไฟแนนซ์
- ตอบอย่างสุภาพ ชัดเจน และเป็นกันเอง เพศหญิง
- อ้างอิงข้อมูลเพิ่มเติมได้จากเว็บไซต์ทางการของ Honda: https://www.thaihonda.co.th/honda/
"""
                },
                {"role": "user", "content": user_msg}
            ]
        )
        reply_text = response.choices[0].message.content.strip()

    except Exception as e:
        print("❌ Error calling OpenAI:", e)
        if "insufficient_quota" in str(e):
            reply_text = "ขออภัยค่ะ ระบบพนักงานขายอัติโนมัติ ขัดข้อง กรุณาติดต่อเจ้าหน้าที่หรือรอสักครู่"
        else:
            reply_text = "ขออภัยค่ะ ระบบเกิดข้อผิดพลาดชั่วคราว: " + str(e)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()
