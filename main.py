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

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# دالة لجلب كود من الملف وحذفه لعدم التكرار
def get_and_remove_code():
    if not os.path.exists('codes.txt'):
        return None
    
    with open('codes.txt', 'r') as f:
        codes = f.readlines()
    
    if not codes:
        return None
    
    # أخذ أول كود وحذف المسافات
    selected_code = codes[0].strip()
    
    # إعادة كتابة بقية الأكواد للملف
    with open('codes.txt', 'w') as f:
        f.writelines(codes[1:])
    
    return selected_code

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>موقع استلام الأكواد</title>
    <style>
        body { background-color: #1a1a1a; color: white; font-family: Arial; text-align: center; padding-top: 50px; }
        .container { background: #2d2d2d; padding: 30px; border-radius: 15px; display: inline-block; }
        input { padding: 10px; border-radius: 5px; border: none; width: 250px; margin-bottom: 20px; }
        button { background: #5865F2; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎁 استلم كودك اليومي</h2>
        <form action="/get_code" method="post">
            <input type="text" name="discord_id" placeholder="ادخل الـ Discord ID" required><br>
            <button type="submit">اطلب الكود</button>
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
    
    # التأكد من عدم طلب كود مسبقاً اليوم
    if db.search((User.id == user_id) & (User.date == today)):
        return "<h3>⚠️ لقد حصلت على كودك بالفعل اليوم! عد غداً.</h3>"

    # سحب كود من الملف
    code_to_send = get_and_remove_code()
    
    if not code_to_send:
        return "<h3>❌ نعتذر، نفدت الأكواد حالياً. حاول لاحقاً!</h3>"

    async def send_to_discord():
        try:
            user = await client.fetch_user(int(user_id))
            await user.send(f"✅ كودك الجديد هو: `{code_to_send}`")
            db.insert({'id': user_id, 'date': today, 'code': code_to_send})
            return True
        except:
            return False

    future = asyncio.run_coroutine_threadsafe(send_to_discord(), client.loop)
    if future.result(timeout=10):
        return "<h3>✅ تم إرسال الكود بنجاح إلى حسابك في ديسكورد!</h3>"
    return "<h3>❌ فشل الإرسال، تأكد من الـ ID ومن فتح الـ DMs.</h3>"

def run_flask():
    # Render يستخدم بورت 10000 غالباً
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    if TOKEN:
        client.run(TOKEN)
