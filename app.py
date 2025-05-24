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
คุณคือพนักงานขายของร้าน Funky Rider
ร้านของคุณจำหน่ายรถจักรยานยนต์ Honda พร้อมข้อมูลจากหลายแหล่ง เช่น:
- แท็บ 'prices': ราคาเงินสดและผ่อน
- แท็บ 'specs': คุณสมบัติทางเทคนิค
- แท็บ 'โปรโมชั่น': โปรล่าสุด
- แท็บอื่น ๆ: FAQ, ข้อมูลร้าน

ต่อไปนี้คือข้อมูลจาก Google Sheet:
{sheet_text}

หน้าที่ของคุณคือ:
- วิเคราะห์คำถามจากลูกค้า
- ตอบกลับโดยอ้างอิงข้อมูลที่เกี่ยวข้องจากชีตต่าง ๆ
- ช่วยแนะนำรุ่นรถที่เหมาะสม ปิดการขาย และพูดอย่างมืออาชีพ
- {lang_instruction}
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
