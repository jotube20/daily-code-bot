import discord
import asyncio
from flask import Flask, request, render_template_string, redirect
from tinydb import TinyDB, Query
import threading
import os
import time

# --- الإعدادات الثابتة ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"
PRODUCT_PRICE = 5

app = Flask(__name__)
db_orders = TinyDB('orders.json')
db_spam = TinyDB('spam_check.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_stock_count():
    if not os.path.exists('codes.txt'): return 0
    with open('codes.txt', 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

# --- واجهة المتجر الحديثة ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo's Store | متجر جو</title>
    <style>
        :root { --main-color: #5865F2; --bg-dark: #0f0f0f; --card-bg: #1a1a1a; }
        body { background: var(--bg-dark); color: white; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .card { background: var(--card-bg); padding: 40px; border-radius: 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); width: 100%; max-width: 420px; border: 1px solid #333; text-align: center; }
        .stock-badge { background: #232428; padding: 5px 15px; border-radius: 20px; font-size: 14px; color: #43b581; margin-bottom: 20px; display: inline-block; }
        input { width: 100%; padding: 14px; margin: 10px 0; border-radius: 12px; border: 1px solid #333; background: #232428; color: white; box-sizing: border-box; font-size: 16px; }
        button { background: var(--main-color); color: white; border: none; padding: 16px; width: 100%; border-radius: 12px; cursor: pointer; font-weight: bold; font-size: 18px; transition: 0.3s; }
        button:hover { background: #4752c4; transform: translateY(-2px); }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color:var(--main-color)">🛍️ متجر Jo الرقمي</h2>
        <div class="stock-badge">المخزون المتوفر: {{ stock }} قطعة</div>
        <form action="/place_order" method="post">
            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية المطلوبة">
            <input type="text" name="discord_id" placeholder="ID الديسكورد الخاص بك" required>
            <input type="text" name="cash_number" placeholder="رقم الكاش المحول منه" required>
            <button type="submit">إتمام الطلب الآن</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_STORE, stock=get_stock_count())

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        qty = int(request.form.get('quantity', 1))
        d_id = request.form.get('discord_id').strip()
        cash_num = request.form.get('cash_number').strip()
        current_time = time.time()

        # حماية السبام (30 ثانية)
        user_record = db_spam.get(Order.id == d_id)
        if user_record:
            if current_time - user_record['last_order'] < 30:
                return f'<body style="background:#0f0f0f;color:white;text-align:center;padding-top:100px;"><h2>⏳ هدي اللعب شوية!</h2><p>استنى 30 ثانية بين كل طلب.</p><a href="/" style="color:#5865F2;">رجوع</a></body>'

        # فحص المخزون
        stock = get_stock_count()
        if qty > stock:
            return f'<body style="background:#0f0f0f;color:white;text-align:center;padding-top:100px;"><h2>❌ الكمية غير متاحة</h2><p>المخزون المتوفر هو {stock} فقط.</p></body>'

        total = qty * PRODUCT_PRICE
        db_orders.insert({'discord_id': d_id, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})
        db_spam.upsert({'id': d_id, 'last_order': current_time}, Order.id == d_id)

        async def send_initial_msgs():
            try:
                # رسالة العميل (نفس ستايل الصور)
                user = await client.fetch_user(int(d_id))
                cust_msg = (f"👋 **أهلاً بك! لقد استلمنا طلبك لعدد ({qty}) قطعة**\n"
                            f"⌛ **طلبك الآن تحت المراجعة**، سيتم إرسال الأكواد فور التأكد من التحويل.")
                await user.send(cust_msg)
                
                # رسالة المدير
                admin = await client.fetch_user(ADMIN_DISCORD_ID)
                adm_msg = (f"🔔 **طلب جديد معلق!**\n"
                           f"👤 **المشتري:** <@{d_id}>\n"
                           f"📦 **الكمية:** {qty}\n"
                           f"💰 **المبلغ:** {total} ج.م\n"
                           f"🔗 **اللوحة:** https://daily-code-bot-1.onrender.com/admin_jo_secret")
                await admin.send(adm_msg)
            except: pass
        
        asyncio.run_coroutine_threadsafe(send_initial_msgs(), client.loop)
        return redirect(f'/success_page?total={total}')
    except Exception as e: return f"Error: {e}"

@app.route('/success_page')
def success():
    total = request.args.get('total', '5')
    return f'''
    <body style="background:#0f0f0f;color:white;text-align:center;font-family:sans-serif;padding-top:80px;">
        <div style="background:#1a1a1a;padding:40px;border-radius:20px;display:inline-block;border:1px solid #5865F2;">
            <h2 style="color:#43b581;">✅ تم تسجيل الطلب!</h2>
            <p>حول مبلغ <b>{total} جنيه</b> لرقم كاش:</p>
            <h1 style="background:#232428;padding:15px;border-radius:12px;letter-spacing:2px;">{PAYMENT_NUMBER}</h1>
            <p style="color:#b9bbbe;">البوت أرسل لك رسالة تأكيد في الديسكورد الآن.</p>
        </div>
    </body>
    '''

@app.route('/admin_jo_secret')
def admin_panel():
    all_orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    return render_template_string('''
    <body style="background:#0f0f0f; color:white; font-family:sans-serif; text-align:center;">
        <h2 style="padding:20px;">🛠️ لوحة إدارة متجر Jo</h2>
        <table border="1" style="width:95%; margin:auto; background:#1a1a1a; border-collapse:collapse; border-color:#333;">
            <tr style="background:#5865F2; height:50px;">
                <th>العميل</th><th>الكمية</th><th>رقم الكاش</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th>
            </tr>
            {% for order in orders %}
            <tr style="height:50px;">
                <td><@{{ order.discord_id }}></td><td>{{ order.quantity }}</td><td>{{ order.cash_number }}</td>
                <td>{{ order.total }} ج.م</td><td>{{ order.status }}</td>
                <td>
                    {% if order.status == 'pending' %}
                    <a href="/admin/approve/{{ order.doc_id }}" style="color:#43b581; text-decoration:none; font-weight:bold;">[قبول ✅]</a> | 
                    <a href="/admin/reject/{{ order.doc_id }}" style="color:#f04747; text-decoration:none; font-weight:bold;">[رفض ❌]</a>
                    {% else %} - {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    ''', orders=all_orders)

@app.route('/admin/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                qty = int(order['quantity'])
                codes = [get_code_from_file() for _ in range(qty)]
                valid_codes = [c for c in codes if c]
                if valid_codes:
                    txt = "\\n".join([f"🔹 كود {i+1}: `{c}`" for i, c in enumerate(valid_codes)])
                    await user.send(f"🔥 **مبروك! تم قبول طلبك واستلام التحويل:**\\n{txt}")
                else: await user.send("⚠️ نعتذر، المخزون نفد أثناء المعالجة.")
            except: pass
        asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/admin/reject/<int:order_id>')
def reject(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify_reject():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                await user.send(f"❌ **نعتذر، تم رفض طلبك لعدد ({order['quantity']}) قطعة لعدم استلام مبلغ التحويل.**")
            except: pass
        asyncio.run_coroutine_threadsafe(notify_reject(), client.loop)
    return redirect('/admin_jo_secret')

def get_code_from_file():
    if not os.path.exists('codes.txt'): return None
    with open('codes.txt', 'r') as f: lines = [l for l in f.readlines() if l.strip()]
    if not lines: return None
    code = lines[0].strip()
    with open('codes.txt', 'w') as f: f.writelines(lines[1:])
    return code

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

@client.event
async def on_ready():
    print(f'✅ Bot is live: {client.user}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
