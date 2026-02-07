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

PRODUCTS = {
    'xbox': {
        'name': 'Xbox Game Pass Premium', 
        'price': 10, 
        'file': 'xbox.txt', 
        'img': 'https://i.postimg.cc/zD7kMz8R/Screenshot-2026-02-07-152934.png'
    },
    'nitro1': {
        'name': 'Discord Nitro 1 Month', 
        'price': 5, 
        'file': 'nitro1.txt', 
        'img': 'https://i.postimg.cc/jqch9xtC/Screenshot-2026-02-07-152844.png'
    },
    'nitro3': {
        'name': 'Discord Nitro 3 Months', 
        'price': 10, 
        'file': 'nitro3.txt', 
        'img': 'https://i.postimg.cc/xj5P7fnN/Screenshot-2026-02-07-152910.png'
    }
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

# --- واجهة المتجر ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | متجرك المفضل</title>
    <style>
        :root { --main-color: #5865F2; --bg-black: #0a0a0a; }
        body { background: var(--bg-black); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
        h1 { text-align: center; margin-bottom: 40px; font-size: 32px; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; max-width: 1200px; margin: auto; }
        .product-card { 
            width: 320px; height: 480px; border-radius: 25px; 
            position: relative; overflow: hidden; cursor: pointer;
            transition: 0.4s ease; border: 1px solid #222;
        }
        .product-card:hover { transform: translateY(-10px); border-color: var(--main-color); }
        .card-image { 
            position: absolute; inset: 0; background-size: cover; background-repeat: no-repeat; background-position: center; 
            image-rendering: -webkit-optimize-contrast; z-index: 1; 
        }
        .card-overlay {
            position: absolute; inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.3) 35%, rgba(0,0,0,0) 70%);
            z-index: 2; display: flex; flex-direction: column; justify-content: flex-end;
            padding: 25px; text-align: center;
        }
        .product-card h3 { font-size: 22px; margin-bottom: 10px; }
        .price { font-size: 24px; font-weight: bold; color: #43b581; margin-bottom: 5px; }
        .stock { font-size: 14px; color: #ccc; margin-bottom: 15px; }
        .order-form { display: none; background: rgba(15, 15, 15, 0.98); padding: 15px; border-radius: 15px; border: 1px solid var(--main-color); margin-top: 10px; position: relative; z-index: 10; }
        input { width: 90%; padding: 10px; margin: 5px 0; border-radius: 8px; border: none; background: #222; color: white; text-align: center; }
        button { background: var(--main-color); color: white; border: none; padding: 12px; border-radius: 10px; cursor: pointer; width: 100%; font-weight: bold; }
    </style>
    <script>
        function showForm(id) {
            event.stopPropagation();
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none');
            document.getElementById('form-' + id).style.display = 'block';
        }
    </script>
</head>
<body>
    <h1>Jo Store | متجرك المفضل 🔒</h1>
    <div class="products-container">
        {% for key, info in prods.items() %}
        <div class="product-card" onclick="showForm('{{key}}')">
            <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
            <div class="card-overlay">
                <h3>{{ info.name }}</h3>
                <div class="price">{{ info.price }} جنيه</div>
                <div class="stock">المتوفر: {{ stocks[key] }} قطعة</div>
                <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                    <form action="/place_order" method="post">
                        <input type="hidden" name="prod_key" value="{{key}}">
                        <input type="number" name="quantity" min="1" value="1">
                        <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                        <input type="text" name="cash_number" placeholder="رقم الكاش المحول منه" required>
                        <button type="submit">تأكيد الشراء الآن</button>
                    </form>
                </div>
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
        if qty > stock: return "الكمية غير متاحة"
        current_time = time.time()
        user_record = db_spam.get(Order.id == d_id)
        if user_record and current_time - user_record['last_order'] < 30: return "انتظر 30 ثانية"
        total = qty * PRODUCTS[p_key]['price']
        db_orders.insert({'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})
        db_spam.upsert({'id': d_id, 'last_order': current_time}, Order.id == d_id)
        
        async def notify():
            try:
                user = await client.fetch_user(int(d_id))
                # رسالة العميل (مطابقة للصورة 100%)
                await user.send(f"👋 **بنجاح! تم استلام طلبك لـ ({PRODUCTS[p_key]['name']})**\n⌛ **سيتم مراجعة الدفع وإرسال الأكواد لك فوراً.**")
                
                admin = await client.fetch_user(ADMIN_DISCORD_ID)
                # رسالة الإدارة (مطابقة للصورة 100%)
                await admin.send(f"🔔 **طلب جديد!**\n👤 **العميل:** <@{d_id}>\n📦 **المنتج:** {PRODUCTS[p_key]['name']}\n💰 **المبلغ:** {total} ج.م\n📱 **من رقم:** {cash_num}")
            except: pass
        
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
        return redirect(f'/success_page?total={total}')
    except Exception as e: return str(e)

@app.route('/success_page')
def success():
    total = request.args.get('total', '0')
    return f'''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:1px solid #5865F2; padding:30px; border-radius:15px; display:inline-block; max-width: 500px;">
            <h2 style="color:#43b581;">✅ تم تسجيل الطلب!</h2>
            <p>حول مبلغ <b>{total} جنيه</b> للرقم:</p>
            <h1 style="background:#222; padding:15px; border-radius:10px;">{PAYMENT_NUMBER}</h1>
            <div style="background: rgba(88, 101, 242, 0.1); padding: 15px; border-radius: 10px; border: 1px solid #5865F2; margin: 20px 0; text-align: right;">
                <b style="color: #ffcc00;">⚠️ ملحوظة هامة:</b><br>
                يجب عليك دخول سيرفر الديسكورد <a href="https://discord.gg/RYK28PNv" style="color: #5865F2;">https://discord.gg/RYK28PNv</a> 
                ليستطيع البوت ان يرسل لك طلبيتك
                و تأكد ان خاصك مفتوح و الا لم يصلك الكود.
            </div>
            <a href="/" style="color:#5865F2; text-decoration:none;">← العودة للمتجر</a>
        </div>
    </body>
    '''

@app.route('/admin_jo_secret')
def admin_panel():
    all_orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; text-align:center; padding:20px;">
        <h2>🛠️ لوحة الإدارة</h2>
        <table border="1" style="width:95%; margin:auto; background:#111; border-collapse:collapse;">
            <tr style="background:#5865F2; height:50px;">
                <th>العميل</th><th>المنتج</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th>
            </tr>
            {% for order in orders %}
            <tr style="height:50px;">
                <td>{{ order.discord_id }}</td><td>{{ order.prod_name }}</td><td>{{ order.total }} ج.م</td><td>{{ order.status }}</td>
                <td>
                    {% if order.status == 'pending' %}
                    <a href="/admin/approve/{{ order.doc_id }}" style="color:#43b581;">[قبول]</a> | 
                    <a href="/admin/reject/{{ order.doc_id }}" style="color:#f04747;">[رفض]</a>
                    {% endif %}
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
                codes = [get_code_prod(order['prod_key']) for _ in range(qty)]
                valid = [c for c in codes if c]
                if valid:
                    txt = "\\n".join([f"🔹 كود {i+1}: `{c}`" for i, c in enumerate(valid)])
                    # رسالة النجاح (مطابقة للصورة 100%)
                    await user.send(f"🔥 **مبروك! ({order['prod_name']}) تم تأكيد الدفع لطلبك:**\\n{txt}")
                else: await user.send("⚠️ نفد المخزون!")
            except: pass
        asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/admin/reject/<int:order_id>')
def reject(order_id):
    order = db_orders.get(doc_id=order_id)
    if order:
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

def run_flask(): app.run(host='0.0.0.0', port=10000)

@client.event
async def on_ready():
    print(f'✅ Bot live: {client.user}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
