import discord
import asyncio
from flask import Flask, request, render_template_string, redirect
from tinydb import TinyDB, Query
import threading
import os

# --- الإعدادات ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"
PRODUCT_PRICE = 5

app = Flask(__name__)
db_orders = TinyDB('orders.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# --- دالة فحص الكمية المتاحة ---
def get_stock_count():
    if not os.path.exists('codes.txt'): return 0
    with open('codes.txt', 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

# --- واجهة المتجر الحديثة (UI) ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo's Store | متجر جو</title>
    <style>
        :root { --main-color: #5865F2; --bg-dark: #0f0f0f; --card-bg: #1a1a1a; }
        body { background: var(--bg-dark); color: white; font-family: 'Segoe UI', Tahoma, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .card { background: var(--card-bg); padding: 40px; border-radius: 24px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); width: 100%; max-width: 420px; border: 1px solid #333; transition: 0.3s; }
        h2 { margin-top: 0; color: var(--main-color); font-size: 28px; }
        .stock-badge { background: #232428; padding: 5px 15px; border-radius: 20px; font-size: 14px; color: #43b581; margin-bottom: 20px; display: inline-block; }
        .input-group { text-align: right; margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-size: 14px; color: #b9bbbe; }
        input { width: 100%; padding: 14px; border-radius: 12px; border: 1px solid #333; background: #232428; color: white; font-size: 16px; box-sizing: border-box; transition: 0.3s; }
        input:focus { border-color: var(--main-color); outline: none; }
        button { background: var(--main-color); color: white; border: none; padding: 16px; width: 100%; border-radius: 12px; cursor: pointer; font-weight: bold; font-size: 18px; margin-top: 10px; transition: 0.3s; }
        button:hover { background: #4752c4; transform: translateY(-2px); box-shadow: 0 5px 15px rgba(88, 101, 242, 0.4); }
        .price-info { background: rgba(67, 181, 129, 0.1); color: #43b581; padding: 10px; border-radius: 10px; margin-bottom: 20px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🛍️ متجر Jo</h2>
        <div class="stock-badge">المتوفر حالياً: {{ stock }} قطعة</div>
        <div class="price-info">سعر القطعة: ''' + str(PRODUCT_PRICE) + ''' جنيه</div>
        <form action="/place_order" method="post">
            <div class="input-group">
                <label>الكمية المطلوبة</label>
                <input type="number" name="quantity" min="1" value="1" required>
            </div>
            <div class="input-group">
                <label>Discord ID</label>
                <input type="text" name="discord_id" placeholder="مثال: 1054749887..." required>
            </div>
            <div class="input-group">
                <label>رقم المحفظة (كاش)</label>
                <input type="text" name="cash_number" placeholder="الرقم الذي ستحول منه" required>
            </div>
            <button type="submit">إتمام الطلب الآن</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    stock = get_stock_count()
    return render_template_string(HTML_STORE, stock=stock)

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        qty = int(request.form.get('quantity', 1))
        d_id = request.form.get('discord_id').strip()
        cash_num = request.form.get('cash_number').strip()
        stock = get_stock_count()

        # --- الطلب الأول: فحص المخزون ---
        if qty > stock:
            return f'''
            <body style="background:#0f0f0f; color:white; text-align:center; padding-top:100px; font-family:sans-serif;">
                <h2 style="color:#f04747;">❌ عذراً! الكمية غير متاحة</h2>
                <p>أقصى كمية يمكنك طلبها الآن هي: <b>{stock}</b> قطعة فقط.</p>
                <a href="/" style="color:#5865F2;">العودة للمتجر</a>
            </body>
            '''

        total = qty * PRODUCT_PRICE
        db_orders.insert({'discord_id': d_id, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})

        # --- الطلب الثاني: رسالة تأكيد للعميل + إشعار لك ---
        async def send_notifications():
            try:
                # رسالة للعميل
                user = await client.fetch_user(int(d_id))
                await user.send(f"👋 أهلاً بك! لقد استلمنا طلبك لعدد ({qty}) قطعة.\n⌛ طلبك الآن **تحت المراجعة**، سيتم إرسال الأكواد فور التأكد من التحويل.")
                
                # رسالة لك
                admin = await client.fetch_user(ADMIN_DISCORD_ID)
                await admin.send(f"🔔 **طلب جديد معلق!**\n👤 المشتري: <@{d_id}>\n📦 الكمية: {qty}\n💰 المبلغ: {total} ج.م\n🔗 اللوحة: https://daily-code-bot-1.onrender.com/admin_jo_secret")
            except Exception as e: print(f"Notify Error: {e}")
        
        asyncio.run_coroutine_threadsafe(send_notifications(), client.loop)

        return f'''
        <body style="background:#0f0f0f; color:white; text-align:center; padding-top:80px; font-family:sans-serif;">
            <div style="background:#1a1a1a; padding:40px; border-radius:20px; display:inline-block; border:1px solid #5865F2;">
                <h2 style="color:#43b581;">📦 طلبك وصل يا بطل!</h2>
                <p>حول مبلغ <b>{total} جنيه</b> لرقم فودافون كاش:</p>
                <h1 style="background:#232428; padding:15px; border-radius:12px; letter-spacing:2px;">{PAYMENT_NUMBER}</h1>
                <p style="color:#b9bbbe;">تفقد رسائل الديسكورد الخاصة بك (DMs)، لقد أرسلنا لك تأكيداً هناك.</p>
            </div>
        </body>
        '''
    except Exception as e: return f"Error: {e}"

@app.route('/admin_jo_secret')
def admin_panel():
    all_orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    return render_template_string('''
    <body style="background:#0f0f0f; color:white; font-family:sans-serif; text-align:center;">
        <h2>🛠️ إدارة الطلبات</h2>
        <table border="1" style="width:95%; margin:auto; background:#1a1a1a; border-collapse:collapse;">
            <tr style="background:#5865F2;">
                <th>العميل</th><th>الكمية</th><th>رقم الكاش</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th>
            </tr>
            {% for order in orders %}
            <tr>
                <td>{{ order.discord_id }}</td><td>{{ order.quantity }}</td><td>{{ order.cash_number }}</td>
                <td>{{ order.total }}</td><td>{{ order.status }}</td>
                <td>
                    {% if order.status == 'pending' %}
                    <a href="/admin/approve/{{ order.doc_id }}" style="color:#43b581;">[قبول ✅]</a>
                    {% else %} {{ order.status }} {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    ''', orders=all_orders)

@app.route('/admin/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order:
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                qty = int(order['quantity'])
                codes = []
                for _ in range(qty):
                    c = get_code_from_file()
                    if c: codes.append(c)
                
                if codes:
                    txt = "\n".join([f"🔹 كود {i+1}: `{c}`" for i, c in enumerate(codes)])
                    await user.send(f"🔥 **تم قبول طلبك! مبروك عليك:**\n{txt}")
                else:
                    await user.send("⚠️ نعتذر، يبدو أن المخزون نفد أثناء المعالجة.")
            except: pass
        asyncio.run_coroutine_threadsafe(deliver(), client.loop)
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
    print(f'✅ Ready: {client.user}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
