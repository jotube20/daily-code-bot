import discord
import asyncio
from flask import Flask, request, render_template_string
from tinydb import TinyDB, Query
from datetime import date
import random
import string
import threading
import os

# جلب التوكن من الـ Secrets اللي أنت عملتها
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

app = Flask(__name__)
db = TinyDB('db.json')
User = Query()

# إعدادات صلاحيات البوت
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# تصميم الموقع (HTML + CSS)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>موقع الكود اليومي</title>
    <style>
        body { background-color: #2c2f33; color: white; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding-top: 50px; }
        .container { background: #23272a; padding: 30px; border-radius: 15px; display: inline-block; box-shadow: 0 0 20px rgba(0,0,0,0.5); max-width: 90%; }
        h2 { color: #7289da; }
        input { padding: 12px; border-radius: 5px; border: none; width: 280px; margin-bottom: 20px; font-size: 16px; color: black; outline: none; }
        button { background: #7289da; color: white; border: none; padding: 12px 25px; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; transition: 0.3s; }
        button:hover { background: #5b6eae; transform: scale(1.05); }
        p { color: #99aab5; line-height: 1.6; }
        .status { margin-top: 20px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🎁 نظام الأكواد اليومية</h2>
        <p>أهلاً بك! أدخل الـ <b>Discord User ID</b> الخاص بك<br>ليقوم البوت بإرسال كود الهدية لك في الرسائل الخاصة.</p>

        <form action="/get_code" method="post">
            <input type="text" name="discord_id" placeholder="مثال: 45829304857201243" required><br>
            <button type="submit">الحصول على الكود</button>
        </form>

        <div class="status">يُسمح بكود واحد فقط كل 24 ساعة.</div>
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

    if not user_id.isdigit():
        return "<h3>❌ خطأ: الـ ID يجب أن يتكون من أرقام فقط! راجع طريقة استخراج الـ User ID.</h3>"

    today = str(date.today())

    # التأكد من قاعدة البيانات هل الشخص طلب كود النهاردة؟
    result = db.search((User.id == user_id) & (User.date == today))
    if result:
        return "<h3>⚠️ عذراً! لقد حصلت على كودك لليوم بالفعل. عد غداً للحصول على كود جديد.</h3>"

    # توليد كود عشوائي من 10 أرقام وحروف
    new_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    async def send_to_discord():
        try:
            # محاولة الوصول للمستخدم وإرسال رسالة خاصة
            user = await client.fetch_user(int(user_id))
            await user.send(f"✅ **أهلاً بك! كودك اليومي الجديد هو:**\n\n`{new_code}`\n\n*تنبيه: هذا الكود صالح لمدة اليوم فقط.*")
            # حفظ العملية في قاعدة البيانات
            db.insert({'id': user_id, 'date': today, 'code': new_code})
            return True
        except Exception as e:
            print(f"Error sending DM: {e}")
            return False

    # تنفيذ المهمة في Loop الخاص بالبوت
    future = asyncio.run_coroutine_threadsafe(send_to_discord(), client.loop)
    try:
        success = future.result(timeout=10)
        if success:
            return "<h3>✅ مبروك! تم إرسال الكود بنجاح. تفقد رسائلك الخاصة (DMs) في ديسكورد الآن.</h3>"
        else:
            return "<h3>❌ فشل الإرسال! تأكد من:<br>1. الـ ID صحيح.<br>2. أنك موجود في سيرفر البوت.<br>3. أنك تسمح باستلام الرسائل الخاصة (DMs) من أعضاء السيرفر.</h3>"
    except:
        return "<h3>⌛ انتهى وقت المحاولة. قد يكون البوت مشغولاً، حاول مرة أخرى بعد قليل.</h3>"

def run_flask():
    # تشغيل السيرفر على بورت 8080
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    # تشغيل الموقع في خلفية الكود
    threading.Thread(target=run_flask).start()
    # تشغيل البوت
    if TOKEN:
        print("جاري تشغيل البوت والموقع...")
        client.run(TOKEN)
    else:
        print("❌ خطأ: لم يتم العثور على التوكن! تأكد من إضافة DISCORD_BOT_TOKEN في الـ Secrets.")