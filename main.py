import discord
import asyncio
from flask import Flask, request, render_template_string
from tinydb import TinyDB, Query
from datetime import date
import threading
import os

# الإعدادات
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
app = Flask(__name__)
db = TinyDB('db.json')
User = Query()

# إعداد البوت
intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_and_remove_code():
    try:
        if not os.path.exists('codes.txt'):
            return None
        with open('codes.txt', 'r') as f:
            codes = f.readlines()
        if not codes:
            return None
        selected_code = codes[0].strip()
        with open('codes.txt', 'w') as f:
            f.writelines(codes[1:])
        return selected_code
    except Exception as e:
        print(f"Error in codes file: {e}")
        return None

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>موقع استلام الأكواد</title>
    <style>
        body { background-color: #1a1a1a; color: white; font-family: Arial; text-align: center; padding-top: 50px; }
        .container { background: #2d2d2d; padding: 30px; border-radius: 15px; display: inline-block; box-shadow: 0 0 10px rgba(0,0,0,0.5); }
        input { padding: 12px; border-radius: 5px; border: none; width: 250px; margin-bottom: 20px; font-size: 16px; }
        button { background: #5865F2; color: white; border: none; padding: 12px 25px; border-radius: 5px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎁 استلم كودك اليومي</h2>
        <form action="/get_code" method="post">
            <input type="text" name="discord_id" placeholder="ادخل الـ Discord ID" required><br>
            <button type="submit">اطلب الكود الآن</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_code', methods=['POST'])
def get_code():
    user_id = request.form.get('discord_id').strip()
    today = str(date.today())
    
    if db.search((User.id == user_id) & (User.date == today)):
        return "<h3>⚠️ لقد حصلت على كودك بالفعل اليوم!</h3>"

    code_to_send = get_and_remove_code()
    if not code_to_send:
        return "<h3>❌ نعتذر، نفدت الأكواد حالياً.</h3>"

    # الطريقة الأضمن لإرسال الرسالة من Flask إلى Discord
    async def send_to_discord():
        try:
            user = await client.fetch_user(int(user_id))
            await user.send(f"✅ كودك الجديد هو: `{code_to_send}`")
            db.insert({'id': user_id, 'date': today, 'code': code_to_send})
            return True
        except Exception as e:
            print(f"Detailed Error: {e}")
            return False

    # محاولة الحصول على الـ loop بطريقة آمنة
    try:
        loop = client.loop # سيتم تعريفه في on_ready
        future = asyncio.run_coroutine_threadsafe(send_to_discord(), loop)
        if future.result(timeout=15):
            return "<h3>✅ تم إرسال الكود بنجاح! تفقد الـ DMs.</h3>"
        else:
            return "<h3>❌ فشل الإرسال، تأكد من فتح الـ DMs.</h3>"
    except Exception as e:
        print(f"Loop Error: {e}")
        return "<h3>❌ السيرفر لسه بيقوم، جرب تاني كمان 10 ثواني.</h3>"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    # هذه الخطوة هي الأهم: تثبيت الـ loop داخل الكلاينت
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN:
        client.run(TOKEN)
