import discord
import asyncio
from flask import Flask, request, render_template_string
from tinydb import TinyDB, Query
from datetime import date
import threading
import os

# الإعدادات الأساسية
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
app = Flask(__name__)
db = TinyDB('db.json')
User = Query()

# إعداد البوت بصلاحيات كاملة للرسائل
intents = discord.Intents.default()
intents.members = True 
client = discord.Client(intents=intents)

# دالة سحب الأكواد
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
        print(f"File Error: {e}")
        return None

# واجهة الموقع
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>موقع استلام الأكواد</title>
    <style>
        body { background-color: #1a1a1a; color: white; font-family: Arial, sans-serif; text-align: center; padding-top: 50px; }
        .container { background: #2d2d2d; padding: 40px; border-radius: 20px; display: inline-block; box-shadow: 0 0 20px rgba(0,0,0,0.5); }
        h2 { color: #5865F2; }
        input { padding: 15px; border-radius: 8px; border: none; width: 280px; margin-bottom: 20px; font-size: 16px; }
        button { background: #5865F2; color: white; border: none; padding: 15px 30px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; transition: 0.3s; }
        button:hover { background: #4752c4; transform: scale(1.05); }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎁 نظام الأكواد اليومي</h2>
        <p>أدخل الـ ID الخاص بك لاستلام الهدية في الخاص</p>
        <form action="/get_code" method="post">
            <input type="text" name="discord_id" placeholder="مثال: 45829304857201243" required><br>
            <button type="submit">الحصول على الكود</button>
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
        return "<h3>⚠️ عذراً! لقد حصلت على كودك لليوم بالفعل.</h3>"

    code_to_send = get_and_remove_code()
    if not code_to_send:
        return "<h3>❌ نعتذر، نفدت الأكواد حالياً. حاول لاحقاً!</h3>"

    # إرسال الرسالة عبر الـ Loop الخاص بالبوت
    async def send_dm():
        try:
            user = await client.fetch_user(int(user_id))
            await user.send(f"✅ **أهلاً بك! كودك اليومي هو:**\n`{code_to_send}`")
            db.insert({'id': user_id, 'date': today, 'code': code_to_send})
            return True
        except Exception as e:
            print(f"Discord DM Error: {e}")
            return False

    if client.is_closed():
        return "<h3>❌ البوت غير متصل حالياً، جرب كمان دقيقة.</h3>"

    # تنفيذ الإرسال بشكل آمن
    try:
        future = asyncio.run_coroutine_threadsafe(send_dm(), client.loop)
        if future.result(timeout=15):
            return "<h3>✅ تم إرسال الكود بنجاح! تفقد رسائلك الخاصة.</h3>"
        else:
            return "<h3>❌ فشل الإرسال، تأكد من الـ ID وفتح الـ DMs.</h3>"
    except Exception as e:
        return f"<h3>❌ حدث خطأ فني، حاول مرة أخرى.</h3>"

# تشغيل البوت
@client.event
async def on_ready():
    print(f'✅ البوت يعمل الآن باسم: {client.user}')

def run_flask():
    # Render يحتاج تشغيل الموقع على البورت المخصص له
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # تشغيل الموقع في خلفية الكود
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # تشغيل البوت (هذا السطر يجب أن يكون الأخير)
    if TOKEN:
        client.run(TOKEN)
    else:
        print("❌ خطأ: لم يتم العثور على التوكن!")
