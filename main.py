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
db_spam = TinyDB('spam_check.json')
db_feedbacks = TinyDB('feedbacks.json')
Order = Query()
Feedback = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية ---
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
    with open(filename, 'w') as f: f.writelines(lines[1:])
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
        
        /* تعديل زرار القائمة لليسار */
        .menu-btn { position: fixed; top: 20px; left: 20px; font-size: 30px; cursor: pointer; z-index: 1001; color: white; background: none; border: none; transition: 0.3s; }
        .menu-btn:hover { color: var(--main-color); }
        
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; left: 0; background-color: #111; overflow-y: auto; transition: 0.5s; padding-top: 60px; border-right: 1px solid #222; }
        .sidebar a { padding: 10px 20px; text-decoration: none; display: block; text-align: right; color: #818181; font-size: 18px; }
        .sidebar a:hover { color: white; background: rgba(88,101,242,0.1); }
        
        .section-title { padding: 10px 20px; color: var(--main-color); font-weight: bold; font-size: 14px; border-bottom: 1px solid #222; margin-top: 15px; }
        #main-content { padding: 20px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; margin-top: 50px; }
        .product-card { width: 320px; height: 480px; border-radius: 25px; position: relative; overflow: hidden; cursor: pointer; transition: 0.4s; border: 1px solid #222; }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; z-index: 1; }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.3) 35%, rgba(0,0,0,0) 70%); z-index: 2; display: flex; flex-direction: column; justify-content: flex-end; padding: 25px; }
        .order-form { display: none; background: rgba(15, 15, 15, 0.98); padding: 15px; border-radius: 15px; border: 1px solid var(--main-color); margin-top: 10px; position: relative; z-index: 10; }
        input, textarea { width: 90%; padding: 10px; margin: 5px 0; border-radius: 8px; border: none; background: #222; color: white; text-align: center; }
        button { background: var(--main-color); color: white; border: none; padding: 12px; border-radius: 10px; cursor: pointer; width: 100%; font-weight: bold; }
        .feedback-item { background: #1a1a1a; margin: 10px 20px; padding: 10px; border-radius: 10px; font-size: 12px; border-right: 3px solid var(--main-color); text-align: right; }
        .warning-text { color: #f1c40f; font-size: 11px; margin-bottom: 8px; font-weight: bold; line-height: 1.4; }
    </style>
</head>
<body>
    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 طلباتي</a>
        <div class="section-title">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 10px 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك في المتجر" required></textarea>
            <button type="submit" style="font-size: 12px; padding: 5px;">إرسال</button>
        </form>
        <div class="section-title">آراء العملاء الحقيقية</div>
        {% for f in feedbacks %}<div class="feedback-item"><b>{{ f.name }}:</b> {{ f.comment }}</div>{% endfor %}
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
                    <div style="color:#43b581; font-weight:bold; font-size:24px;">{{ info.price }} جنيه</div>
                    <div style="color:#ccc; font-size:14px; margin-bottom:10px;">المتوفر: {{ stocks[key] }} قطعة</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <div class="warning-text">⚠️ اكتب معلوماتك بحرص لضمان وصول السلعة لك</div>
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
        function toggleNav() {
            var side = document.getElementById("mySidebar");
            if (side.style.width === "250px") { side.style.width = "0"; } 
            else { side.style.width = "250px"; }
        }
        function showForm(id) { document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); document.getElementById('form-' + id).style.display = 'block'; }
        function checkOrders() { let id = prompt("أدخل ID الديسكورد الخاص بك:"); if(id) window.location.href="/my_orders/"+id; }
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

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    ip = request.remote_addr
    if db_feedbacks.count(Feedback.ip == ip) >= 2: return "لقد كتبت رأيين بالفعل."
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment'), 'ip': ip})
    return redirect('/')

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key, qty = request.form.get('prod_key'), int(request.form.get('quantity', 1))
    d_id, cash_num = request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    total = qty * PRODUCTS[p_key]['price']
    buy_time = datetime.now().strftime("%I:%M %p")
    
    db_orders.insert({
        'discord_id': d_id, 
        'prod_name': PRODUCTS[p_key]['name'], 
        'prod_key': p_key, 
        'quantity': qty, 
        'cash_number': cash_num, 
        'total': total, 
        'status': 'pending',
        'time': buy_time
    })
    
    async def notify():
        try:
            if not client.is_ready(): return
            user = await client.fetch_user(int(d_id))
            user_msg = (
                f"تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!\n"
                f"⌛ سيتم مراجعة الدفع وإرسال الأكواد لك فوراً."
            )
            await user.send(user_msg)
            
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            admin_msg = (
                f"🔔 **طلب جديد!**\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total} ج.م\n"
                f"📱 **من رقم:** {cash_num}"
            )
            await admin.send(admin_msg)
        except: pass

    if client.loop and client.loop.is_running():
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
        
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    total = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:1px solid #5865F2;padding:30px;border-radius:15px;display:inline-block;max-width:550px;">
            <h2 style="color:#43b581;">تم تسجيل الطلب بنجاح</h2>
            <p>حول مبلغ <b>{{total}} جنيه</b> للرقم:</p>
            <h1 style="background:#222;padding:15px;border-radius:10px; color:#fff;">{{pay_num}}</h1>
            
            <div style="background:rgba(88,101,242,0.1);padding:15px;border-radius:10px;border:1px solid #5865F2;margin:20px 0;text-align:center; font-size:14px; line-height:1.6;">
                🔍 يمكنك تتبع حالة طلبك من <b>(صفحة الطلبات)</b> في القائمة.<br>
                ✍️ يسعدنا كتابة رأيك في الخدمة من <b>(مكان الآراء في الـ Options)</b>.
            </div>

            <div style="background:rgba(255,204,0,0.1);padding:15px;border-radius:10px;border:1px solid #ffcc00;margin:20px 0;text-align:right; font-size:13px;">
                <b style="color:#ffcc00;">⚠️ ملحوظة هامة:</b><br>
                يجب عليك دخول سيرفر الديسكورد <a href="https://discord.gg/RYK28PNv" style="color: #5865F2; font-weight: bold;">هنا</a> 
                ليستطيع البوت إرسال الكود لك.
            </div>
            <a href="/" style="color:#5865F2;text-decoration:none; font-weight: bold;">العودة للمتجر</a>
        </div>
    </body>''', total=total, pay_num=PAYMENT_NUMBER)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:20px; font-family: sans-serif;">
        <h2 style="color:#5865F2;">📋 تتبع طلباتك</h2>
        <div style="max-width:600px; margin:auto;">
        {% for o in orders %}
            <div style="background:#111;padding:15px;margin:10px;border-radius:15px; border: 1px solid #222; text-align:right;">
                <b>{{o.prod_name}}</b><br>
                <small>المبلغ: {{o.total}} ج.م</small>
                <div style="height:12px; background:#333; border-radius:6px; margin:15px 0; overflow:hidden; border: 1px solid #444;">
                    <div style="width:{% if 'approved' in o.status %}100%{% elif 'rejected' in o.status %}100%{% else %}50%{% endif %}; height:100%; transition: 0.5s; background:{% if 'approved' in o.status %}#2ecc71{% elif 'rejected' in o.status %}#e74c3c{% else %}#f1c40f{% endif %};"></div>
                </div>
                الحالة: {{o.status}}
            </div>
        {% endfor %}
        {% if not orders %} <p>لا توجد طلبات لهذا الـ ID</p> {% endif %}
        </div>
        <br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none;">← العودة للمتجر</a>
    </body>''', orders=orders)

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        if action == 'restock':
            new_codes = request.form.get('codes').strip()
            if new_codes:
                with open(PRODUCTS[p_key]['file'], 'a') as f:
                    f.write(new_codes + "\n")
        elif action == 'edit_stock':
            content = request.form.get('full_content').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f:
                f.write(content + "\n" if content else "")
        elif action == 'clear_logs': db_orders.remove(Order.discord_id == request.form.get('u_id'))

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    stock_contents = {}
    for k, v in PRODUCTS.items():
        if os.path.exists(v['file']):
            with open(v['file'], 'r') as f: stock_contents[k] = f.read().strip()
        else: stock_contents[k] = ""

    return render_template_string('''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <style>
        :root { --main: #5865F2; --success: #43b581; --danger: #f04747; --bg: #0a0a0a; }
        body { background: var(--bg); color: white; font-family: sans-serif; padding: 20px; animation: fadeIn 0.8s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .card { background: #111; border-radius: 15px; border: 1px solid #222; padding: 20px; margin-bottom: 20px; transition: 0.3s; }
        .card:hover { border-color: var(--main); box-shadow: 0 0 15px rgba(88,101,242,0.2); }
        h2, h3 { color: var(--main); text-align: center; }
        .grid { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
        textarea, select, input { width: 100%; padding: 12px; background: #000; color: white; border: 1px solid #333; border-radius: 8px; margin-top: 10px; }
        button { cursor: pointer; border: none; font-weight: bold; transition: 0.3s; }
        button:hover { opacity: 0.8; transform: scale(1.02); }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; border-radius: 10px; overflow: hidden; }
        th { background: var(--main); color: white; padding: 15px; }
        td { background: #111; padding: 15px; border-bottom: 1px solid #222; text-align: center; }
        .status-badge { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .pending { background: rgba(241, 196, 15, 0.1); color: #f1c40f; border: 1px solid #f1c40f; }
        .approved { background: rgba(67, 181, 129, 0.1); color: var(--success); border: 1px solid var(--success); }
        .rejected { background: rgba(240, 71, 71, 0.1); color: var(--danger); border: 1px solid var(--danger); }
        .btn-act { padding: 8px 15px; text-decoration: none; border-radius: 5px; font-size: 13px; font-weight: bold; }
    </style>
</head>
<body>
    <h2>🛠️ لوحة تحكم Jo Store</h2>
    
    <div class="grid">
        <div class="card" style="width: 350px;">
            <h3>📦 إضافة مخزون سريع</h3>
            <form method="post">
                <input type="hidden" name="action" value="restock">
                <select name="p_key">
                    <option value="xbox">Xbox</option>
                    <option value="nitro1">Nitro 1</option>
                    <option value="nitro3">Nitro 3</option>
                </select>
                <textarea name="codes" placeholder="ضع الأكواد هنا"></textarea>
                <button type="submit" style="background: var(--main); color: white; width: 100%; padding: 12px; border-radius: 8px;">إضافة فورية</button>
            </form>
        </div>

        <div class="card" style="width: 350px;">
            <h3>🗑️ تنظيف السجلات</h3>
            <form method="post">
                <input type="hidden" name="action" value="clear_logs">
                <input type="text" name="u_id" placeholder="أدخل ID الديسكورد">
                <button type="submit" style="background: var(--danger); color: white; width: 100%; padding: 12px; border-radius: 8px;">حذف سجلات المستخدم</button>
            </form>
        </div>
    </div>

    <div class="card">
        <h3>📝 إدارة المخزون الحالي (تعديل مباشر)</h3>
        <div class="grid">
            {% for k, content in stock_contents.items() %}
            <div style="width: 300px; background: #000; padding: 15px; border-radius: 10px;">
                <h4 style="margin: 0 0 10px 0;">{{ prods[k].name }}</h4>
                <form method="post">
                    <input type="hidden" name="action" value="edit_stock">
                    <input type="hidden" name="p_key" value="{{k}}">
                    <textarea name="full_content" style="height: 100px;">{{content}}</textarea>
                    <button type="submit" style="background: var(--success); color: white; width: 100%; padding: 8px; border-radius: 5px;">حفظ</button>
                </form>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="card" style="overflow-x: auto;">
        <h3>📦 طلبات الزبائن ({{ orders|length }})</h3>
        <table>
            <thead>
                <tr>
                    <th>العميل (ID)</th>
                    <th>الوقت</th>
                    <th>المنتج</th>
                    <th>حالة الطلب / الإجراء</th>
                </tr>
            </thead>
            <tbody>
                {% for o in orders|reverse %}
                <tr>
                    <td><b style="color:var(--main)">@{{ o.discord_id }}</b></td>
                    <td>{{ o.time or 'غير مسجل' }}</td>
                    <td>{{ o.prod_name }}</td>
                    <td>
                        {% if o.status == 'pending' %}
                        <div style="display: flex; gap: 5px; justify-content: center;">
                            <a href="/approve/{{o.doc_id}}" class="btn-act" style="background: var(--success); color: white;">Approve</a>
                            <a href="/reject/{{o.doc_id}}" class="btn-act" style="background: var(--danger); color: white;">Decline</a>
                        </div>
                        {% elif o.status == 'approved ✅' %}
                        <span class="status-badge approved">Approved</span>
                        {% else %}
                        <span class="status-badge rejected">Declined</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>''', orders=orders, stock_contents=stock_contents, prods=PRODUCTS)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        qty = int(order.get('quantity', 1))
        codes = [get_code_prod(order['prod_key']) for _ in range(qty)]
        valid_codes = [c for c in codes if c]
        if valid_codes:
            db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
            async def deliver():
                try:
                    user = await client.fetch_user(int(order['discord_id']))
                    codes_msg = "\n".join([f"🔗 {c}" for c in valid_codes])
                    await user.send(f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']})**\n\n**إليك الأكواد الخاصة بك:**\n{codes_msg}\n\n*يمكنك نسخ الروابط مباشرة بالضغط عليها.*")
                except: pass
            if client.loop and client.loop.is_running():
                asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    order = db_orders.get(doc_id=order_id)
    db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
    async def notify():
        try:
            user = await client.fetch_user(int(order['discord_id']))
            await user.send("❌ **نعتذر، تم رفض طلبك لعدم استلام مبلغ التحويل.**")
        except: pass
    if client.loop and client.loop.is_running():
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect('/admin_jo_secret')

def run_flask():
    app.run(host='0.0.0.0', port=10000)

@client.event
async def on_ready():
    client.loop = asyncio.get_running_loop()
    print(f"✅ Bot is ready as {client.user}")

if __name__ == '__main__':
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    if TOKEN:
        try:
            client.run(TOKEN)
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            while True:
                time.sleep(1000)
