import discord
import asyncio
from flask import Flask, request, render_template_string, redirect
from tinydb import TinyDB, Query
import threading
import os

# --- الإعدادات (تأكد من تعديل الـ ID) ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 # تم تحديثه بناءً على صورك
PAYMENT_NUMBER = "01007324726"
PRODUCT_PRICE = 5

app = Flask(__name__)
db_orders = TinyDB('orders.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# --- واجهة المتجر الرئيسية ---
HTML_STORE = f'''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>Jo's Store</title>
    <style>
        body {{ background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 20px; }}
        .card {{ background: #1e1e1e; padding: 30px; border-radius: 20px; display: inline-block; width: 90%; max-width: 400px; }}
        input {{ width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: none; background: #2c2f33; color: white; box-sizing: border-box; }}
        button {{ background: #5865F2; color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color:#5865F2;">🛍️ Xbox codes</h2>
        <p style="color:#43b581;">سعر المنتج: {PRODUCT_PRICE} جنيه</p>
        <form action="/place_order" method="post">
            <input type="number" name="quantity" placeholder="الكمية" min="1" value="1">
            <input type="text" name="discord_id" placeholder="الـ Discord ID الخاص بك" required>
            <input type="text" name="cash_number" placeholder="رقم الكاش اللي هتحول منه" required>
            <button type="submit">إتمام الطلب (Complete Order)</button>
        </form>
    </div>
</body>
</html>
'''

# --- واجهة لوحة التحكم (للمدير فقط) ---
ADMIN_TEMPLATE = '''
<body style="background:#121212; color:white; font-family:sans-serif; text-align:center;">
    <h2>🛠️ لوحة تحكم الطلبات (خاصة بك)</h2>
    <table border="1" style="width:90%; margin:auto; background:#1e1e1e; border-collapse:collapse;">
        <tr style="background:#5865F2;">
            <th>ID العميل</th><th>الكمية</th><th>رقم الكاش</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th>
        </tr>
        {% for order in orders %}
        <tr>
            <td>{{ order.discord_id }}</td><td>{{ order.quantity }}</td><td>{{ order.cash_number }}</td>
            <td>{{ order.total }}</td><td>{{ order.status }}</td>
            <td>
                {% if order.status == 'pending' %}
                <a href="/admin/approve/{{ order.doc_id }}" style="color:#43b581;">[قبول]</a>
                <a href="/admin/reject/{{ order.doc_id }}" style="color:#f04747;">[رفض]</a>
                {% else %}
                تم المعالجة
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
'''

@app.route('/')
def home():
    return render_template_string(HTML_STORE)

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        qty = int(request.form.get('quantity', 1))
        d_id = request.form.get('discord_id').strip()
        cash_num = request.form.get('cash_number').strip()
        total = qty * PRODUCT_PRICE
        
        doc_id = db_orders.insert({'discord_id': d_id, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})

        async def notify():
            try:
                admin = await client.fetch_user(ADMIN_DISCORD_ID)
                await admin.send(f"🔔 **طلب جديد!**\nالعميل: {d_id}\nالمبلغ: {total} جنيه\nرابط لوحة التحكم: https://daily-code-bot-1.onrender.com/admin_jo_secret")
            except: pass
        
        asyncio.run_coroutine_threadsafe(notify(), client.loop)

        return f'''
        <body style="background:#121212; color:white; text-align:center; font-family:sans-serif; padding-top:50px;">
            <div style="background:#1e1e1e; padding:30px; border-radius:15px; display:inline-block; border:2px solid #5865F2;">
                <h2 style="color:#43b581;">✅ تم تسجيل طلبك!</h2>
                <p>حول مبلغ <b>{total} جنيه</b> لرقم:</p>
                <h1 style="background:#2c2f33; padding:10px;">{PAYMENT_NUMBER}</h1>
                <p>سيتم إرسال السلعة لك فور قبول الطلب.</p>
            </div>
        </body>
        '''
    except Exception as e:
        return f"Error: {str(e)}"

# --- مسارات لوحة التحكم ---
@app.route('/admin_jo_secret')
def admin_panel():
    all_orders = db_orders.all()
    # إضافة doc_id لكل طلب لعرضه
    for o in all_orders: o['doc_id'] = o.doc_id
    return render_template_string(ADMIN_TEMPLATE, orders=all_orders)

@app.route('/admin/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order:
        db_orders.update({'status': 'approved'}, doc_id=order_id)
        # إرسال السلعة للعميل آلياً
        async def send_item():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                await user.send(f"✅ تم قبول طلبك! إليك السلعة الخاصة بك: (ضع الكود هنا)")
            except: pass
        asyncio.run_coroutine_threadsafe(send_item(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/admin/reject/<int:order_id>')
def reject(order_id):
    db_orders.update({'status': 'rejected'}, doc_id=order_id)
    return redirect('/admin_jo_secret')

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
