import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for
from tinydb import TinyDB, Query
import threading
import os
import time

# --- الإعدادات الأساسية ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"

PRODUCTS = {
    'xbox': {'name': 'Xbox Game Pass Premium', 'price': 10, 'file': 'xbox.txt', 'img': 'https://i.postimg.cc/zD7kMz8R/Screenshot-2026-02-07-152934.png'},
    'nitro1': {'name': 'Discord Nitro 1 Month', 'price': 5, 'file': 'nitro1.txt', 'img': 'https://i.postimg.cc/jqch9xtC/Screenshot-2026-02-07-152844.png'},
    'nitro3': {'name': 'Discord Nitro 3 Months', 'price': 10, 'file': 'nitro3.txt', 'img': 'https://i.postimg.cc/xj5P7fnN/Screenshot-2026-02-07-152910.png'}
}

app = Flask(__name__)
db_orders = TinyDB('orders.json')
db_spam = TinyDB('spam_check.json')
db_feedbacks = TinyDB('feedbacks.json')
Order = Query()
Feedback = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

def get_stock(prod_key):
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename): return 0
    with open(filename, 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

def get_code_prod(p_key):
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename): return None
    with open(filename, 'r') as f: 
        lines = [l for l in f.readlines() if l.strip()]
    if not lines: return None
    code = lines[0].strip()
    with open(filename, 'w') as f: 
        f.writelines(lines[1:])
    return code

# --- واجهة المتجر الرئيسية ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | متجرك المفضل</title>
    <style>
        :root { --main-color: #5865F2; --bg-black: #0a0a0a; }
        body { background: var(--bg-black); color: white; font-family: sans-serif; margin: 0; overflow-x: hidden; transition: 0.5s; }
        .menu-btn { position: fixed; top: 20px; left: 20px; font-size: 30px; cursor: pointer; z-index: 1001; color: white; background: none; border: none; }
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; left: 0; background-color: #111; overflow-y: auto; transition: 0.5s; padding-top: 60px; border-right: 1px solid #222; }
        .sidebar a { padding: 10px 20px; text-decoration: none; display: block; text-align: right; color: #818181; font-size: 18px; }
        .sidebar .close-btn { position: absolute; top: 10px; right: 20px; font-size: 30px; cursor: pointer; color: white; }
        .section-title { padding: 10px 20px; color: var(--main-color); font-weight: bold; font-size: 14px; border-bottom: 1px solid #222; margin-top: 15px; }
        #main-content { padding: 20px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; margin-top: 50px; }
        .product-card { width: 320px; height: 480px; border-radius: 25px; position: relative; overflow: hidden; cursor: pointer; transition: 0.4s; border: 1px solid #222; }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; z-index: 1; }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.3) 35%, rgba(0,0,0,0) 70%); z-index: 2; display: flex; flex-direction: column; justify-content: flex-end; padding: 25px; }
        .order-form { display: none; background: rgba(15, 15, 15, 0.98); padding: 15px; border-radius: 15px; border: 1px solid var(--main-color); margin-top: 10px; position: relative; z-index: 10; }
        input, textarea { width: 90%; padding: 10px; margin: 5px 0; border-radius: 8px; border: none; background: #222; color: white; text-align: center; }
        button { background: var(--main-color); color: white; border: none; padding: 12px; border-radius: 10px; cursor: pointer; width: 100%; font-weight: bold; }
        .feedback-item { background: #1a1a1a; margin: 10px 20px; padding: 10px; border-radius: 10px; font-size: 12px; border-right: 3px solid var(--main-color); }
    </style>
</head>
<body>
    <div id="mySidebar" class="sidebar">
        <span class="close-btn" onclick="closeNav()">&times;</span>
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 طلباتي</a>
        <div class="section-title">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 10px 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك" required></textarea>
            <button type="submit" style="font-size: 12px; padding: 5px;">إرسال</button>
        </form>
        <div class="section-title">آراء العملاء</div>
        {% for f in feedbacks %}<div class="feedback-item"><b>{{ f.name }}:</b> {{ f.comment }}</div>{% endfor %}
    </div>
    <button class="menu-btn" onclick="openNav()">&#9776;</button>
    <div id="main-content">
        <h1>Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div style="color:#43b581; font-weight:bold; font-size:24px;">{{ info.price }} جنيه</div>
                    <div style="color:#ccc; font-size:14px; margin-bottom:10px;">المتوفر: {{ stocks[key] }} قطعة</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <button type="submit">تأكيد الشراء الآن</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
    <script>
        function openNav() { document.getElementById("mySidebar").style.width = "250px"; }
        function closeNav() { document.getElementById("mySidebar").style.width = "0"; }
        function showForm(id) { document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); document.getElementById('form-' + id).style.display = 'block'; }
        function checkOrders() { let id = prompt("أدخل ID الديسكورد:"); if(id) window.location.href="/my_orders/"+id; }
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    name, comment, ip = request.form.get('user_name'), request.form.get('comment'), request.remote_addr
    if db_feedbacks.count(Feedback.ip == ip) >= 2: return "الحد الأقصى للتعليقات هو 2."
    db_feedbacks.insert({'name': name, 'comment': comment, 'ip': ip})
    return redirect('/')

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key, qty = request.form.get('prod_key'), int(request.form.get('quantity', 1))
    d_id, cash_num = request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    total = qty * PRODUCTS[p_key]['price']
    db_orders.insert({'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})
    async def notify():
        try:
            user = await client.fetch_user(int(d_id))
            # الرسالة بالظبط زي الصورة
            await user.send(f"تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!\n⌛ سيتم مراجعة الدفع وإرسال الأكواد لك فوراً.")
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            await admin.send(f"🔔 **طلب جديد!**\n👤 **العميل:** <@{d_id}>\n📦 **المنتج:** {PRODUCTS[p_key]['name']}\n💰 **المبلغ:** {total} ج.م\n📱 **من رقم:** {cash_num}")
        except: pass
    asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    total = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:1px solid #5865F2;padding:30px;border-radius:15px;display:inline-block;max-width:500px;">
            <h2 style="color:#43b581;">إتم تسجيل الطلب</h2>
            <p>حول مبلغ <b>{{total}} جنيه</b> للرقم:</p>
            <h1 style="background:#222;padding:15px;border-radius:10px; color:#fff;">{{pay_num}}</h1>
            <div style="background:rgba(88,101,242,0.1);padding:20px;border-radius:15px;border:1px solid #5865F2;margin:20px 0;text-align:right;">
                <b style="color:#ffcc00;">⚠️ ملحوظة هامة:</b><br>
                يجب دخول سيرفر الديسكورد https://discord.gg/RYK28PNv وفتح الخاص لاستلام الكود.
            </div>
            <a href="/" style="color:#5865F2;text-decoration:none;">العودة للمتجر</a>
        </div>
    </body>''', total=total, pay_num=PAYMENT_NUMBER)

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'restock':
            with open(PRODUCTS[request.form.get('p_key')]['file'], 'a') as f: f.write("\n" + request.form.get('codes'))
        elif action == 'delete_feedback': db_feedbacks.remove(doc_ids=[int(request.form.get('f_id'))])
        elif action == 'clear_logs': db_orders.remove(Order.discord_id == request.form.get('u_id'))
    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    fbacks = [dict(item, doc_id=item.doc_id) for item in db_feedbacks.all()]
    return render_template_string('''<body style="background:#0a0a0a; color:white; padding:20px;">
        <h2>🛠️ لوحة التحكم</h2>
        <form method="post"><input type="hidden" name="action" value="restock"><select name="p_key"><option value="xbox">Xbox</option><option value="nitro1">Nitro 1</option><option value="nitro3">Nitro 3</option></select><textarea name="codes" placeholder="أكواد"></textarea><button type="submit">ريستوك</button></form>
        <form method="post"><input type="hidden" name="action" value="clear_logs"><input type="text" name="u_id" placeholder="Discord ID"><button type="submit">مسح سجلات</button></form>
        <h3>الآراء</h3>{% for f in fbacks %}<div>{{f.name}}: {{f.comment}} <form method="post" style="display:inline;"><input type="hidden" name="action" value="delete_feedback"><input type="hidden" name="f_id" value="{{f.doc_id}}"><button type="submit">حذف</button></form></div>{% endfor %}
        <h3>الطلبات</h3>{% for o in orders %}<div>{{o.discord_id}} - {{o.prod_name}} - {{o.status}} <a href="/approve/{{o.doc_id}}">قبول</a> | <a href="/reject/{{o.doc_id}}">رفض</a></div>{% endfor %}
    </body>''', orders=orders, fbacks=fbacks)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        qty = int(order.get('quantity', 1))
        # جلب عدد الأكواد المطلوب بالظبط
        codes = []
        for _ in range(qty):
            c = get_code_prod(order['prod_key'])
            if c: codes.append(c)
        
        if len(codes) > 0:
            db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
            async def deliver():
                try:
                    user = await client.fetch_user(int(order['discord_id']))
                    # الرسالة بالظبط زي الصورة لكل كود
                    codes_msg = "\n".join([f"🔹 كود {i+1}: `{c}`" for i, c in enumerate(codes)])
                    await user.send(f"🔥 **مبروك! ({order['prod_name']}) تم تأكيد الدفع لطلبك**\n{codes_msg}")
                except: pass
            asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    order = db_orders.get(doc_id=order_id)
    db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
    async def notify():
        try:
            user = await client.fetch_user(int(order['discord_id']))
            await user.send("❌ نعتذر، تم رفض طلبك.")
        except: pass
    asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''<body style="background:#0a0a0a;color:white;text-align:center;padding:20px;"><h2>📋 طلباتك</h2>{% for o in orders %}<div style="background:#111;padding:15px;margin:10px;border-radius:15px;">{{o.prod_name}} - {{o.status}}</div>{% endfor %}<br><a href="/" style="color:#5865F2;">رجوع</a></body>''', orders=orders)

def run_flask(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready(): client.loop = asyncio.get_running_loop()
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
