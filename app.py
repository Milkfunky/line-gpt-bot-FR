from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials
import os
import json

app = Flask(__name__)

# ✅ LINE credentials
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ✅ OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Google Sheet credentials from ENV (NOT FILE)
try:
    cred_json = os.getenv("GOOGLE_CREDENTIAL_JSON")
    cred_dict = json.loads(cred_json)
    creds = Credentials.from_service_account_info(
        cred_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gs_client = gspread.authorize(creds)
    sheet = gs_client.open("honda_prices").worksheet("prices")
except Exception as e:
    print("❌ Error loading Google Sheet credentials:", e)
    sheet = None  # fallback if sheet can't be loaded

# ✅ ดึงราคาจาก Google Sheet
def get_price_from_sheet(model_name):
    if not sheet:
        return "❌ ไม่สามารถโหลดข้อมูลราคาจากระบบได้ในขณะนี้"
    
    try:
        data = sheet.get_all_records()
        for row in data:
            if row['รุ่น'].lower() == model_name.lower():
                return (
                    f"📍 ราคา {row['รุ่น']}:\n"
                    f"💰 เงินสด: {row['ราคาเงินสด']:,} บาท\n"
                    f"📆 ผ่อน 12 เดือน: {row['ผ่อน 12 เดือน']:,} บาท/เดือน\n"
                    f"📆 ผ่อน 24 เดือน: {row['ผ่อน 24 เดือน']:,} บาท/เดือน"
                )
        return f"❗ ไม่พบข้อมูลของรุ่น '{model_name}' กรุณาตรวจสอบชื่อรุ่น"
    except Exception as e:
        print("❌ Error reading sheet:", e)
        return "❌ ระบบไม่สามารถดึงข้อมูลได้ในขณะนี้"

@app.route("/")
def home():
    return "Funky Rider LINE Bot is running."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ Signature verification failed")
        abort(400)
    except Exception as e:
        print("❌ Unexpected error:", e)
        abort(500)

    return 'OK', 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()

    # ✅ ตรวจสอบคำว่า "ราคา" เพื่อตอบจาก Google Sheet
    if "ราคา" in user_msg:
        model = user_msg.replace("ราคา", "").strip()
        reply_text = get_price_from_sheet(model)
    else:
        # ✅ ตอบผ่าน OpenAI Chat
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
               "role": "system",
  "content": """
คุณคือพนักงานฝ่ายขายของกิจการ "Funky Rider" ซึ่งเป็นผู้จำหน่ายรถจักรยานยนต์ยี่ห้อ Honda (ฮอนด้า) ในจังหวัดเชียงใหม่ ประเทศไทย

- คุณคือพนักงานหญิง อายุ 36 ปี ชื่อเล่นว่า "เอมี่ (Ami)"
- Funky Rider ตั้งอยู่ที่ 199/7-8 ถนนห้วยแก้ว ตำบลสุเทพ อำเภอเมืองเชียงใหม่ จังหวัดเชียงใหม่ 50200
- เบอร์ติดต่อ: 099-556-6998 หรือ 099-556-6695
- ลิงก์แผนที่ร้าน: https://maps.app.goo.gl/wXtWY7vpoNDZSTTe7

หน้าที่ของคุณ:
- ให้คำแนะนำรุ่นรถจักรยานยนต์ Honda ที่เหมาะกับความต้องการของลูกค้า
- ช่วยลูกค้าเลือกจากงบประมาณ, การใช้งาน เช่น ใช้ในเมือง, ส่งของ, หรือเดินทางไกล
- ตอบกลับอย่างมืออาชีพ สุภาพ เป็นกันเอง และเข้าใจง่าย
- ให้ข้อมูลเรื่องราคา/โปรโมชั่น/ช่องทางจอง ทดลองขับ หรือให้เบอร์ติดต่อ
- ใช้ภาษาที่ลูกค้าใช้ถาม (เช่น ถ้าลูกค้าพิมพ์ภาษาจีน ให้ตอบเป็นภาษาจีน)
- จดจำภาษาที่ลูกค้าใช้ เพื่อใช้ในการตอบในครั้งถัดไปเสมอ

เว็บไซต์อ้างอิงข้อมูลสินค้า: https://www.thaihonda.co.th/honda/
"""
                    },
                    {"role": "user", "content": user_msg}
                ]
            )
            reply_text = response.choices[0].message.content.strip()

        except Exception as e:
            print("❌ Error calling OpenAI:", e)
            if "insufficient_quota" in str(e):
                reply_text = "ขออภัยค่ะ ระบบเกินโควต้าการใช้งาน GPT กรุณารอสักครู่หรือติดต่อเจ้าหน้าที่"
            else:
                reply_text = "เกิดข้อผิดพลาดในการตอบกลับ กรุณาลองใหม่อีกครั้ง"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    app.run()
