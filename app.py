from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import gspread
from google.oauth2.service_account import Credentials
from langdetect import detect
import os
import json
import traceback

app = Flask(__name__)

# ✅ LINE credentials
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ✅ OpenAI client
print("✅ OpenAI library version:", openai.__version__)
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Google Sheet credentials
cred_json = os.getenv("GOOGLE_CREDENTIAL_JSON")
try:
    cred_dict = json.loads(cred_json)
    print("✅ JSON loaded successfully")
except Exception as e:
    print("❌ Error loading JSON:", e)

try:
    creds = Credentials.from_service_account_info(
        cred_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    print("✅ Loaded Google Sheet scopes:", creds.scopes)

    gs_client = gspread.authorize(creds)
    spreadsheet = gs_client.open_by_key("191yAMF0HIGfcg3Lr-V_gKGU0I4Lj1dIixtlbrSqhpos")
    print("✅ Connected to Google Sheet.")
except Exception as e:
    print("❌ Error loading Google Sheet credentials:", e)
    spreadsheet = None

# ✅ จำภาษาผู้ใช้
user_language_memory = {}

def detect_user_language(user_id, message):
    if user_id not in user_language_memory:
        try:
            lang = detect(message)
            user_language_memory[user_id] = lang
            print(f"🔤 Detected language for {user_id}: {lang}")
        except:
            user_language_memory[user_id] = "th"
    return user_language_memory[user_id]

def get_lang_instruction(lang_code):
    if lang_code == "th":
        return "โปรดตอบกลับเป็นภาษาไทย"
    elif lang_code.startswith("zh"):
        return "请用中文回复客户。"
    elif lang_code == "en":
        return "Please reply in English."
    else:
        return "Please respond in the language the customer used."

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
    user_id = event.source.user_id
    user_msg = event.message.text.strip()

    lang_code = detect_user_language(user_id, user_msg)
    lang_instruction = get_lang_instruction(lang_code)

    # ✅ ดึงข้อมูลจากทุก worksheet
    if not spreadsheet:
        reply_text = "❌ ระบบไม่สามารถเชื่อมต่อข้อมูลได้ กรุณาลองใหม่ภายหลัง"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return

    try:
        all_worksheets = spreadsheet.worksheets()
        all_data = {}
        for ws in all_worksheets:
            records = ws.get_all_records()
            if records:
                all_data[ws.title] = records

        sheet_text = json.dumps(all_data, ensure_ascii=False, indent=2)

    except Exception as e:
        print("❌ Error reading worksheets:", e)
        reply_text = "❌ ระบบไม่สามารถโหลดข้อมูลจาก Google Sheet ได้ในขณะนี้"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return

    # ✅ ใช้ GPT วิเคราะห์ข้อมูลทั้งหมด
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                "role": "system",
                "content": f"""
                คุณคือ “เจนนี่” (Jenny) พนักงานขายหญิงอายุ 36 ปี ของกิจการ Funky Rider  
คุณมีประสบการณ์ด้านการขายรถจักรยานยนต์ Honda มากกว่า 20 ปี  
มีความรู้ด้านเทคนิคเครื่องยนต์ รู้ลึกเรื่องคุณสมบัติของรุ่นต่าง ๆ  
สามารถให้คำแนะนำ เปรียบเทียบรุ่น คำนวณผ่อน และปิดการขายได้อย่างเป็นมืออาชีพ

📍 ข้อมูลกิจการ:
- ชื่อร้าน: Funky Rider
- ที่อยู่: 199/7-8 ถนนห้วยแก้ว ตำบลสุเทพ อำเภอเมืองเชียงใหม่ จังหวัดเชียงใหม่ 50200
- เบอร์โทรศัพท์: 099-556-6998 หรือ 099-556-6695
- ลิงก์แผนที่ร้าน: https://maps.app.goo.gl/wXtWY7vpoNDZSTTe7

📌 หน้าที่ของคุณ:
1. แนะนำรถจักรยานยนต์ Honda ให้เหมาะสมกับงบประมาณและการใช้งาน เช่น ขี่ในเมือง เดินทางไกล ส่งของ
2. ให้ข้อมูลราคาแบบเงินสด / ผ่อน
3. คำนวณค่างวดแบบ “ดอกเบี้ยคงที่” ตามเงื่อนไข:
   - 12 เดือน / 24 เดือน: ดอกเบี้ย 1.06% ต่อเดือน
   - 36 เดือน: ดอกเบี้ย 1.09% ต่อเดือน
   - ค่างวด = [(ยอดจัด x ดอกเบี้ย x จำนวนเดือน) + ยอดจัด] ÷ จำนวนเดือน
4. หากลูกค้าสอบถามสเปกรถ ให้ค้นจาก https://www.thaihonda.co.th/honda/ แล้วอธิบายเป็นภาษาที่เข้าใจง่าย
5. หากลูกค้าสอบถามที่อยู่ เบอร์ร้าน ให้ตอบกลับข้อมูลด้านบนทันที
6. ตอบกลับด้วยภาษาเดียวกับลูกค้า (ไทย, อังกฤษ, จีน) โดยอัตโนมัติ
7. ตอบอย่างสุภาพ กระชับ เป็นกันเอง และมืออาชีพ
8. หากไม่แน่ใจในข้อมูล ให้แนะนำลูกค้าติดต่อที่ร้านโดยตรง

ห้ามตอบเกินจริง ห้ามคาดเดา หากไม่มีข้อมูลให้ตอบว่า "ข้อมูลนี้ควรสอบถามเจ้าหน้าที่เพิ่มเติมทางโทรศัพท์ 099-556-6998"
                {lang_instruction}
                """
                },
                {"role": "user", "content": user_msg}
            ]
        )
        reply_text = response.choices[0].message.content.strip()

    except Exception as e:
        print("❌ Error calling OpenAI:", e)
        traceback.print_exc()
        if "insufficient_quota" in str(e):
            reply_text = "ขออภัยค่ะ ระบบใช้งาน GPT เกินโควต้าที่กำหนด กรุณาติดต่อเจ้าหน้าที่หรือรอสักครู่"
        else:
            reply_text = f"⚠️ เกิดข้อผิดพลาด: {str(e)}"

    # ✅ ตอบกลับผ่าน LINE
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
