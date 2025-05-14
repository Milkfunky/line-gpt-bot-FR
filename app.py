from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials
import os

app = Flask(__name__)

# 🔑 LINE Credentials
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 🔑 OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🔑 Google Sheets Credentials
gs_creds = Credentials.from_service_account_file(
    "gen-lang-client-0125688965-ed755cff90db.json",  # << แก้ชื่อไฟล์ให้ตรงกับของคุณ
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gs_client = gspread.authorize(gs_creds)
sheet = gs_client.open("honda_prices").worksheet("prices")  # << ชื่อตารางใน Google Sheet

def get_price_from_sheet(model_name):
    data = sheet.get_all_records()
    for row in data:
        if row['รุ่น'].lower() == model_name.lower():
            return (
                f"📍 ราคา {row['รุ่น']}:\n"
                f"💰 เงินสด: {row['ราคาเงินสด']:,} บาท\n"
                f"📆 ผ่อน 12 เดือน: {row['ผ่อน 12 เดือน']:,} บาท/เดือน\n"
                f"📆 ผ่อน 24 เดือน: {row['ผ่อน 24 เดือน']:,} บาท/เดือน\n"
                f"📆 ผ่อน 36 เดือน: {row['ผ่อน 36 เดือน']:,} บาท/เดือน"
            )
    return None

@app.route("/")
def home():
    return "LINE-GPT Bot is running."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print("❌ Callback Error:", e)
        abort(500)

    return 'OK', 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()

    # ✅ กรณีถามราคารถ
    if "ราคา" in user_msg:
        model_name = user_msg.replace("ราคา", "").strip()
        price_reply = get_price_from_sheet(model_name)
        if price_reply:
            reply_text = price_reply
        else:
            reply_text = f"ขออภัยค่ะ ไม่พบข้อมูลของรุ่น '{model_name}' กรุณาพิมพ์ชื่อรุ่นให้ชัดเจน เช่น: Click125i"
    else:
        # ✅ ใช้ GPT ช่วยตอบ
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """
คุณคือพนักงานฝ่ายขายของกิจการ "Funky Rider" ซึ่งเป็นผู้จำหน่ายรถจักรยานยนต์ยี่ห้อ Honda (ฮอนด้า) ในจังหวัดเชียงใหม่ ประเทศไทย
- คุณคือพนักงานฝ่ายขาย เพศ หญิง อายุ 36 ปี ชื่อเล่นว่า เอมี่ ( Ami )
- Funky Rider ตั้งอยู่ที่ 199/7-8 Huay Kaew Rd, Suthep, Mueang Chiang Mai District, Chiang Mai 50200
- เบอร์โทรศัพท์ 0995566998 หรือ 0995566695
- Link ที่อยู่ร้านค้า https://maps.app.goo.gl/wXtWY7vpoNDZSTTe7
- ตอบกลับลูกค้าอย่างมืออาชีพ สุภาพ เข้าใจง่าย
- ตอบกลับเป็นภาษาเดียวกับที่ลูกค้าใช้ (ไทย, อังกฤษ, จีน) โดยอัตโนมัติ และ จดจำภาษาที่ผู้ใช้ใช้ถาม เพื่อตอบในครั้งถัดไป
- ช่วยแนะนำรุ่นรถที่เหมาะกับงบประมาณและลักษณะการใช้งาน
- ช่วยปิดการขาย เช่น เสนอจอง ทดลองขับ หรือให้เบอร์ติดต่อ
เว็บไซต์อ้างอิง: https://www.thaihonda.co.th/honda/
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
