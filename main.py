import discord
import asyncio
from flask import Flask, request, render_template_string, redirect
from tinydb import TinyDB, Query
import threading
import os
import time

# --- الإعدادات ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"

# تعريف المنتجات وأسعارها وملفاتها
PRODUCTS = {
    'xbox': {'name': 'Xbox Game Pass Premium', 'price': 10, 'file': 'xbox.txt'},
    'nitro1': {'name': 'Discord Nitro 1 Month', 'price': 5, 'file': 'nitro1.txt'},
    'nitro3': {'name': 'Discord Nitro 3 Months', 'price': 10, 'file': 'nitro3.txt'}
}

app = Flask(__name__)
db_orders = TinyDB('orders.json')
db_spam = TinyDB('spam_check.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_stock(prod_key):
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename): return 0
    with open(filename, 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

# --- واجهة المتجر الحديثة (التصميم المطلوب) ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | اختر منتجك</title>
    <style>
        :root { --main-color: #5865F2; --bg-gray: #1e1e1e; --card-bg: #2d2d2d; }
        body { background: var(--bg-gray); color: white; font-family: sans-serif; margin: 0; padding: 20px; text-align: center; }
        h1 { margin-bottom: 40px; font-size: 32px; color: #fff; text-shadow: 2px 2px 10px rgba(0,0,0,0.5); }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 25px; max-width: 1200px; margin: auto; }
        .product-card { 
            background: var(--card-bg); width: 300px; padding: 30px; border-radius: 20px; 
            border: 2px solid #3d3d3d; transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            cursor: pointer; position: relative; overflow: hidden;
        }
        .product-card:hover { 
            transform: scale(1.05) translateY(-10px); border-color: var(--main-color);
            box-shadow: 0 15px 35px rgba(88, 101, 242, 0.3);
        }
        .product-card h3 { color: var(--main-color); font-size: 22px; margin-bottom: 10px; }
        .price { font-size: 24px; font-weight: bold; color: #43b581; margin: 15px 0; }
        .stock { font-size: 14px; color: #b9bbbe; }
        .order-form { display: none; margin-top: 20px; border-top: 1px solid #444; padding-top: 20px; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from {opacity: 0;} to {opacity: 1;} }
        input { width: 90%; padding: 12px; margin: 8px 0; border-radius: 10px; border: none; background: #3d3d3d; color: white; text-align: center; }
        button { background: var(--main-color); color: white; border: none; padding: 12px 25px; border-radius: 10px; cursor: pointer; font-weight: bold; width: 95%; margin-top: 10px; }
    </style>
    <script>
        function showForm(id) {
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none');
            document.getElementById('form-' + id).style.display = 'block';
        }
    </script>
</head>
<body>
    <h1>🔒 اختر منتجك المفضل</h1>
    <div class="products-container">
        {% for key, info in prods.items() %}
        <div class="product-card" onclick="showForm('{{key}}')">
            <h3>{{ info.name }}</h3>
            <div class="price">{{ info.price }} جنيه</div>
            <div class="stock">المتوفر: {{ stocks[key] }} قطعة</div>
            
            <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                <form action="/place_order" method="post">
                    <input type="hidden" name="prod_key" value="{{key}}">
                    <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                    <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                    <input type="text" name="cash_number" placeholder="رقم الكاش المحول منه" required>
                    <button type="submit">تأكيد الطلب</button>
                </form>
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    stocks = {k: get_stock(k) for k in PRODUCTS}
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks)

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        p_key = request.form.get('prod_key')
        qty = int(request.form.get('quantity', 1))
        d_id = request.form.get('discord_id').strip()
        cash_num = request.form.get('cash_number').strip()
        
        stock = get_stock(p_key)
        if qty > stock:
            return f'<body style="background:#1e1e1e;color:white;text-align:center;padding-top:100px;"><h2>❌ الكمية غير متاحة</h2><p>المتوفر من {PRODUCTS[p_key]["name"]} هو {stock} فقط.</p><a href="/" style="color:#5865F2;">رجوع</a></body>'

        # حماية السبام
        current_time = time.time()
        user_record = db_spam.get(Order.id == d_id)
        if user_record and current_time - user_record['last_order'] < 30:
            return f'<body style="background:#1e1e1e;color:white;text-align:center;padding-top:100px;"><h2>⏳ حماية السبام!</h2><p>انتظر 30 ثانية.</p></body>'

        total = qty * PRODUCTS[p_key]['price']
        db_orders.insert({'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})
        db_spam.upsert({'id': d_id, 'last_order': current_time}, Order.id == d_id)

        async def notify():
            try:
                # رسالة العميل
                user = await client.fetch_user(int(d_id))
                await user.send(f"👋 **أهلاً بك! لقد استلمنا طلبك لـ ({PRODUCTS[p_key]['name']})**\\n⌛ **طلبك الآن تحت المراجعة**، سيتم الإرسال فور التأكد من التحويل.")
                # رسالة المدير
                admin = await client.fetch_user(ADMIN_DISCORD_ID)
                await admin.send(f"🔔 **طلب جديد!**\\n👤 العميل: <@{d_id}>\\n📦 المنتج: {PRODUCTS[p_key]['name']}\\n💰 المبلغ: {total} ج.م\\n🔗 اللوحة: https://daily-code-bot-1.onrender.com/admin_jo_secret")
            except: pass
        
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
        return redirect(f'/success_page?total={total}')
    except Exception as e: return f"Error: {e}"

@app.route('/success_page')
def success():
    total = request.args.get('total', '0')
    return f'''
    <body style="background:#1e1e1e;color:white;text-align:center;padding-top:80px;font-family:sans-serif;">
        <div style="background:#2d2d2d;padding:40px;border-radius:20px;display:inline-block;border:1px solid #5865F2;">
            <h2 style="color:#43b581;">✅ تم تسجيل الطلب!</h2>
            <p>حول مبلغ <b>{total} جنيه</b> لرقم:</p>
            <h1 style="background:#3d3d3d;padding:15px;border-radius:12px;letter-spacing:2px;">{PAYMENT_NUMBER}</h1>
            <p style="color:#b9bbbe;">البوت أرسل لك رسالة تأكيد في الخاص.</p>
        </div>
    </body>
    '''

@app.route('/admin_jo_secret')
def admin_panel():
    all_orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    return render_template_string('''
    <body style="background:#1e1e1e; color:white; font-family:sans-serif; text-align:center;">
        <h2>🛠️ لوحة إدارة متجر Jo</h2>
        <table border="1" style="width:95%; margin:auto; background:#2d2d2d; border-collapse:collapse; border-color:#444;">
            <tr style="background:#5865F2; height:50px;">
                <th>العميل</th><th>المنتج</th><th>الكمية</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th>
            </tr>
            {% for order in orders %}
            <tr style="height:50px;">
                <td><@{{ order.discord_id }}></td><td>{{ order.prod_name }}</td><td>{{ order.quantity }}</td>
                <td>{{ order.total }} ج.م</td><td>{{ order.status }}</td>
                <td>
                    {% if order.status == 'pending' %}
                    <a href="/admin/approve/{{ order.doc_id }}" style="color:#43b581;">[قبول ✅]</a> | 
                    <a href="/admin/reject/{{ order.doc_id }}" style="color:#f04747;">[رفض ❌]</a>
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
                p_key = order['prod_key']
                codes = [get_code_prod(p_key) for _ in range(qty)]
                valid = [c for c in codes if c]
                if valid:
                    txt = "\\n".join([f"🔹 كود {i+1}: `{c}`" for i, c in enumerate(valid)])
                    await user.send(f"🔥 **مبروك! تم قبول طلبك لـ {order['prod_name']}:**\\n{txt}")
                else: await user.send("⚠️ نعتذر، المخزون نفد!")
            except: pass
        asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/admin/reject/<int:order_id>')
def reject(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                await user.send("❌ **نعتذر، تم رفض طلبك لعدم استلام مبلغ التحويل.**")
            except: pass
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect('/admin_jo_secret')

def get_code_prod(p_key):
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename): return None
    with open(filename, 'r') as f: lines = [l for l in f.readlines() if l.strip()]
    if not lines: return None
    code = lines[0].strip()
    with open(filename, 'w') as f: f.writelines(lines[1:])
    return code

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

@client.event
async def on_ready():
    print(f'✅ Bot live: {client.user}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
