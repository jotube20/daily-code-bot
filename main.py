import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for
from tinydb import TinyDB, Query
import threading
import os
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"

PRODUCTS = {
    'xbox': {'name': 'Xbox Game Pass Premium', 'price': 10, 'file': 'xbox.txt', 'img': 'رابط_صورة_الاكس_بوكس'},
    'nitro1': {'name': 'Discord Nitro 1 Month', 'price': 5, 'file': 'nitro1.txt', 'img': 'رابط_صورة_نيترو_شهر'},
    'nitro3': {'name': 'Discord Nitro 3 Months', 'price': 10, 'file': 'nitro3.txt', 'img': 'رابط_صورة_نيترو_3_شهور'}
}

app = Flask(__name__)
db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
Order = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية (المخزون الذكي) ---
def get_stock(prod_key):
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename): return 0
    with open(filename, 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

def pull_codes(p_key, qty):
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename): return []
    with open(filename, 'r') as f: 
        lines = [l for l in f.readlines() if l.strip()]
    if len(lines) < qty: return []
    pulled = lines[:qty]
    remaining = lines[qty:]
    with open(filename, 'w') as f: f.writelines(remaining)
    return [c.strip() for c in pulled]

def return_codes(p_key, codes):
    filename = PRODUCTS[p_key]['file']
    with open(filename, 'a') as f:
        for c in codes: f.write(c + "\n")

# --- واجهة المتجر الرئيسية ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | متجرك المفضل</title>
    <style>
        :root { --main: #5865F2; --bg: #0a0a0a; }
        body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; overflow-x: hidden; }
        .menu-btn { position: fixed; top: 20px; left: 20px; font-size: 30px; cursor: pointer; z-index: 1001; color: white; background: none; border: none; }
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; left: 0; background-color: #111; transition: 0.5s; padding-top: 60px; border-right: 1px solid #222; overflow-x: hidden; }
        .sidebar a { padding: 15px 25px; text-decoration: none; display: block; color: #818181; font-size: 18px; text-align: right; }
        .sidebar a:hover { color: white; background: rgba(88,101,242,0.1); }
        #main-content { padding: 20px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; margin-top: 50px; }
        .product-card { width: 310px; height: 450px; border-radius: 20px; position: relative; overflow: hidden; cursor: pointer; border: 1px solid #222; transition: 0.3s; }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; z-index: 1; }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, transparent 100%); z-index: 2; display: flex; flex-direction: column; justify-content: flex-end; padding: 20px; }
        .order-form { display: none; background: rgba(10,10,10,0.95); padding: 15px; border-radius: 15px; border: 1px solid var(--main); margin-top: 10px; position: relative; z-index: 10; }
        input { width: 85%; padding: 10px; margin: 5px 0; border-radius: 8px; border: none; background: #222; color: white; text-align: center; }
        button { background: var(--main); color: white; border: none; padding: 12px; border-radius: 10px; cursor: pointer; width: 100%; font-weight: bold; }
        .warning { color: #f1c40f; font-size: 11px; font-weight: bold; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 طلباتي</a>
        <div style="padding: 20px; color: var(--main); border-top: 1px solid #222;">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 0 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك" style="width:85%; background:#222; color:white; border:none; padding:10px; border-radius:8px;"></textarea>
            <button type="submit" style="margin-top:10px;">إرسال</button>
        </form>
    </div>
    <button class="menu-btn" onclick="toggleNav()">&#9776;</button>
    <div id="main-content">
        <h1>Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div style="color:#43b581; font-weight:bold; font-size:22px;">{{ info.price }} ج.م</div>
                    <div style="color:#ccc; font-size:13px; margin-bottom:10px;">المتوفر: {{ stocks[key] }}</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <div class="warning">⚠️ اكتب معلوماتك بحرص لضمان وصول السلعة</div>
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <button type="submit">تأكيد الشراء</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        function toggleNav() {
            var side = document.getElementById("mySidebar");
            side.style.width = side.style.width === "250px" ? "0" : "250px";
        }
        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }
        function checkOrders() { let id = prompt("أدخل ID الديسكورد:"); if(id) window.location.href="/my_orders/"+id; }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key, qty = request.form.get('prod_key'), int(request.form.get('quantity', 1))
    d_id, cash_num = request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    
    # حجز الأكواد فوراً
    reserved = pull_codes(p_key, qty)
    if not reserved: return "عذراً، المخزون غير كافٍ حالياً."
    
    total = qty * PRODUCTS[p_key]['price']
    buy_time = datetime.now().strftime("%I:%M %p")
    
    db_orders.insert({
        'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key,
        'quantity': qty, 'cash_number': cash_num, 'total': total, 
        'status': 'pending', 'time': buy_time, 'codes': reserved
    })
    
    async def notify():
        try:
            if not client.is_ready(): return
            user = await client.fetch_user(int(d_id))
            # تم إصلاح الرسالة لأسطر حقيقية
            await user.send(
                f"تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!\n"
                f"⌛ سيتم مراجعة الدفع وإرسال الأكواد لك فوراً."
            )
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # تم إصلاح رسالة الإدارة لأسطر حقيقية
            await admin.send(
                f"🔔 **طلب جديد!**\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total} ج.م\n"
                f"📱 **من رقم:** {cash_num}"
            )
        except: pass

    if client.loop and client.loop.is_running():
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    total = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:50px;font-family:sans-serif;">
        <div style="border:1px solid #5865F2;padding:30px;border-radius:15px;display:inline-block;max-width:500px;">
            <h2 style="color:#43b581;">تم تسجيل الطلب!</h2>
            <p>حول مبلغ <b>{{total}} جنيه</b> للرقم:</p>
            <h1 style="background:#222;padding:15px;border-radius:10px;">{{pay_num}}</h1>
            <div style="background:rgba(88,101,242,0.1);padding:15px;border-radius:10px;border:1px solid #5865F2;margin:20px 0;font-size:14px;">
                🔍 تتبع طلبك من <b>(صفحة الطلبات)</b> في القائمة.<br>
                ✍️ يسعدنا رأيك من <b>(مكان الآراء في الـ Options)</b>.
            </div>
            <a href="/" style="color:#5865F2;text-decoration:none;font-weight:bold;">العودة للمتجر</a>
        </div>
    </body>''', total=total, pay_num=PAYMENT_NUMBER)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                codes_msg = "\n".join([f"🔗 {c}" for c in order['codes']])
                await user.send(f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']})**\n\n**الأكواد:**\n{codes_msg}")
            except: pass
        if client.loop and client.loop.is_running():
            asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        return_codes(order['prod_key'], order['codes'])
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                await user.send("❌ **نعتذر، تم رفض طلبك لعدم استلام المبلغ.**")
            except: pass
        if client.loop and client.loop.is_running():
            asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect('/admin_jo_secret')

# --- لوحة التحكم وتتبع الطلبات ---
@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        if action == 'restock':
            new_codes = request.form.get('codes').strip()
            if new_codes:
                with open(PRODUCTS[p_key]['file'], 'a') as f: f.write(new_codes + "\n")
        elif action == 'edit_stock':
            content = request.form.get('full_content').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f: f.write(content + "\n" if content else "")
        elif action == 'clear_logs': db_orders.remove(Order.discord_id == request.form.get('u_id'))

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k, v in PRODUCTS.items()}
    return render_template_string('''<body style="background:#0a0a0a;color:white;padding:20px;font-family:sans-serif;">
        <h2 style="text-align:center;color:#5865F2;">🛠️ لوحة التحكم</h2>
        <div style="display:flex;gap:20px;justify-content:center;flex-wrap:wrap;">
            <div style="background:#111;padding:20px;border-radius:15px;width:300px;">
                <h3>📦 ريستوك</h3>
                <form method="post"><input type="hidden" name="action" value="restock"><select name="p_key" style="width:100%;padding:10px;"><option value="xbox">Xbox</option><option value="nitro1">Nitro 1</option><option value="nitro3">Nitro 3</option></select><textarea name="codes" style="width:100%;margin-top:10px;"></textarea><button type="submit" style="width:100%;margin-top:10px;background:#5865F2;color:white;border:none;padding:10px;border-radius:5px;">إضافة</button></form>
            </div>
            <div style="background:#111;padding:20px;border-radius:15px;width:300px;">
                <h3>🗑️ حذف سجل</h3>
                <form method="post"><input type="hidden" name="action" value="clear_logs"><input type="text" name="u_id" placeholder="Discord ID" style="width:90%;padding:10px;"><button type="submit" style="width:100%;margin-top:10px;background:red;color:white;border:none;padding:10px;border-radius:5px;">حذف</button></form>
            </div>
        </div>
        <div style="background:#111;padding:20px;border-radius:15px;margin-top:30px;">
            <h3>📦 الطلبات</h3>
            <table border="1" style="width:100%;text-align:center;border-collapse:collapse;">
                <tr style="background:#5865F2;"><th>العميل</th><th>الوقت</th><th>المنتج</th><th>الإجراء</th></tr>
                {% for o in orders|reverse %}
                <tr><td>@{{o.discord_id}}</td><td>{{o.time}}</td><td>{{o.prod_name}}</td><td>{% if o.status == 'pending' %}<a href="/approve/{{o.doc_id}}" style="color:green;">Approve</a> | <a href="/reject/{{o.doc_id}}" style="color:red;">Decline</a>{% else %}{{o.status}}{% endif %}</td></tr>
                {% endfor %}
            </table>
        </div>
    </body>''', orders=orders, stock_contents=stock_contents, prods=PRODUCTS)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''<body style="background:#0a0a0a;color:white;text-align:center;padding:20px;font-family:sans-serif;">
        <h2 style="color:#5865F2;">📋 طلباتك</h2>
        {% for o in orders %}<div style="background:#111;padding:15px;margin:10px;border-radius:15px;text-align:right;">
            <b>{{o.prod_name}}</b><br>
            <div style="height:12px;background:#333;border-radius:6px;margin:10px 0;overflow:hidden;">
                <div style="width:{% if 'approved' in o.status %}100%{% elif 'rejected' in o.status %}100%{% else %}50%{% endif %};height:100%;background:{% if 'approved' in o.status %}#2ecc71{% elif 'rejected' in o.status %}#e74c3c{% else %}#f1c40f{% endif %};"></div>
            </div> الحـالـة: {{o.status}}</div>{% endfor %}
        <br><a href="/" style="color:#5865F2;text-decoration:none;">العودة</a></body>''', orders=orders)

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment')})
    return redirect('/')

def run_flask(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready():
    client.loop = asyncio.get_running_loop()
    print(f"✅ Bot is ready as {client.user}")

if __name__ == '__main__':
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    if TOKEN:
        try: client.run(TOKEN)
        except:
            while True: time.sleep(1000)
