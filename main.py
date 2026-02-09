import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from tinydb import TinyDB, Query
import threading
import os
import time
from datetime import datetime, timedelta
import pytz

# --- الإعدادات الأساسية ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"
ADMIN_PASSWORD = "201184" 

# توقيت القاهرة لضبط الرسائل بدقة
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# تعريف المنتجات
PRODUCTS = {
    'xbox': {
        'name': 'Xbox Game Pass Premium',
        'price': 10,
        'file': 'xbox.txt',
        'img': 'https://media.discordapp.net/attachments/111/xbox_bg.png' # رابط افتراضي
    },
    'nitro1': {
        'name': 'Discord Nitro 1 Month',
        'price': 5,
        'file': 'nitro1.txt',
        'img': 'https://media.discordapp.net/attachments/111/nitro1_bg.png'
    },
    'nitro3': {
        'name': 'Discord Nitro 3 Months',
        'price': 10,
        'file': 'nitro3.txt',
        'img': 'https://media.discordapp.net/attachments/111/nitro3_bg.png'
    }
}

app = Flask(__name__)
app.secret_key = 'jo_store_v24_trust_restored_final'

# قواعد البيانات
db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
db_config = TinyDB('config.json') 
Order = Query()
Config = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية (المخزون والخصم) ---

def get_stock(prod_key):
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename): return 0
    try:
        with open(filename, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
        return len(lines)
    except: return 0

def pull_codes(p_key, qty):
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename): return []
    try:
        with open(filename, 'r') as f: 
            lines = [l for l in f.readlines() if l.strip()]
        if len(lines) < qty: return []
        pulled = lines[:qty]
        remaining = lines[qty:]
        with open(filename, 'w') as f: 
            f.writelines(remaining)
        return [c.strip() for c in pulled]
    except: return []

def return_codes(p_key, codes):
    """إرجاع الأكواد مع منع التكرار"""
    filename = PRODUCTS[p_key]['file']
    existing_codes = []
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            existing_codes = [line.strip() for line in f.readlines()]
    
    with open(filename, 'a') as f:
        for c in codes:
            if c.strip() not in existing_codes: # منع التكرار البرمجي
                f.write(c.strip() + "\n")

def is_maintenance_mode():
    res = db_config.get(Config.type == 'maintenance')
    return res['status'] if res else False

def get_discount(code, prod_key):
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res:
        if res['prod_key'] != 'all' and res['prod_key'] != prod_key: return None
        if res['uses'] <= 0: return None
        return res
    return None

def use_coupon(code):
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res and res['uses'] > 0:
        db_config.update({'uses': res['uses'] - 1}, doc_ids=[res.doc_id])

# --- واجهة المتجر الرئيسية (مفرودة HTML & CSS & JS) ---

HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | متجرك المفضل</title>
    <style>
        :root {
            --main-color: #5865F2;
            --bg-color: #0a0a0a;
            --text-color: white;
            --card-bg: #111;
        }
        body.light-mode {
            --bg-color: #f4f4f4;
            --text-color: #333;
            --card-bg: #ffffff;
        }
        body {
            background: var(--bg-color);
            color: var(--text-color);
            font-family: sans-serif;
            margin: 0;
            overflow-x: hidden;
            transition: 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        /* كبسولة التحكم */
        .glass-nav {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1001;
            display: flex;
            align-items: center;
            gap: 15px;
            background: rgba(128, 128, 128, 0.15);
            backdrop-filter: blur(15px);
            padding: 12px 25px;
            border-radius: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .nav-btn {
            background: none;
            border: none;
            color: var(--text-color);
            font-size: 28px;
            cursor: pointer;
            transition: 0.3s;
        }
        .sidebar {
            height: 100%;
            width: 0;
            position: fixed;
            z-index: 1000;
            top: 0;
            left: 0;
            background-color: var(--card-bg);
            overflow-y: auto;
            transition: 0.5s ease;
            padding-top: 80px;
            border-right: 1px solid rgba(128, 128, 128, 0.1);
        }
        .sidebar a {
            padding: 18px 25px;
            text-decoration: none;
            display: block;
            text-align: right;
            color: #888;
            font-size: 18px;
        }
        
        /* المنتجات */
        #main-content {
            padding: 40px 20px;
            text-align: center;
            padding-top: 100px;
        }
        .products-container {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 45px;
            margin-top: 60px;
        }
        .product-card {
            width: 320px;
            height: 520px;
            border-radius: 40px;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            border: 1px solid rgba(128, 128, 128, 0.1);
            background: var(--card-bg);
            transition: 0.5s;
        }
        .product-card:hover { transform: translateY(-15px); border-color: var(--main-color); }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; z-index: 1; transition: 1s; }
        .card-overlay {
            position: absolute; inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.5) 45%, transparent 85%);
            z-index: 2; display: flex; flex-direction: column; justify-content: flex-end; padding: 35px;
        }
        .order-form {
            display: none; background: rgba(10, 10, 10, 0.98);
            padding: 20px; border-radius: 25px; border: 1px solid var(--main-color); margin-top: 15px;
        }
        input {
            width: 90%; padding: 14px; margin: 8px 0; border-radius: 12px;
            border: 1px solid #333; background: #1a1a1a; color: white; text-align: center;
        }
        .btn-purchase {
            background: var(--main-color); color: white; border: none;
            padding: 16px; border-radius: 15px; cursor: pointer; width: 100%; font-weight: bold;
        }

        /* Spotlight Tutorial System */
        #tut-overlay {
            display: none; position: fixed; inset: 0;
            background: rgba(0,0,0,0.85); z-index: 5000;
        }
        .spotlight {
            position: absolute; border: 4px solid #f1c40f; border-radius: 20px;
            box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.85); z-index: 5001; transition: 0.4s; pointer-events: none;
        }
        .tut-card {
            position: absolute; background: white; color: black; padding: 25px;
            border-radius: 20px; width: 280px; z-index: 5002; text-align: center; font-weight: bold;
        }

        /* Countdown Modal */
        #wait-overlay {
            display: none; position: fixed; inset: 0; z-index: 4000;
            background: rgba(0,0,0,0.9); flex-direction: column; align-items: center; justify-content: center; color: white;
        }
        .timer-box {
            width: 120px; height: 120px; border: 6px solid var(--main-color); border-radius: 50%;
            display: flex; align-items: center; justify-content: center; font-size: 42px; color: var(--main-color); margin-bottom: 25px;
        }
    </style>
</head>
<body id="body">
    <div id="wait-overlay">
        <div class="timer-box" id="timer-val">60</div>
        <h3>انتظر من فضلك.. ⌛</h3>
        <p style="color: #888;">نظام الحماية من السبام يعمل.</p>
        <button class="btn-purchase" id="ok-btn" style="display: none; width: auto; padding: 10px 40px;" onclick="document.getElementById('wait-overlay').style.display='none'">OK</button>
    </div>

    <div id="tut-overlay">
        <div id="spotlight" class="spotlight"></div>
        <div id="tut-tooltip" class="tut-card">
            <div id="tut-text"></div>
            <button class="btn-purchase" style="padding: 5px 15px; font-size: 13px; margin-top: 15px;" onclick="nextStep()">التالي</button>
        </div>
    </div>

    <div class="glass-nav">
        <button class="nav-btn" id="menu-trigger" onclick="toggleNav()">&#9776;</button>
        <button class="nav-btn" onclick="toggleTheme()">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 طلباتي</a>
        <form action="/add_feedback" method="post" style="padding: 20px;">
            <input name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك..." style="width:100%; background:#1a1a1a; color:white; height:80px;"></textarea>
            <button type="submit" class="btn-purchase">إرسال</button>
        </form>
    </div>

    <div id="main-content">
        <h1 id="header-text">Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container" id="prod-list">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div style="color:#43b581; font-weight:bold; font-size:28px;">{{ info.price }} ج.م</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post" onsubmit="return checkWait()">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <input type="text" name="coupon" placeholder="كود الخصم (إن وجد)">
                            <button type="submit" class="btn-purchase">تأكيد عملية الشراء</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        // --- Dark/Light Mode Fix ---
        function toggleTheme() {
            document.body.classList.toggle("light-mode");
            localStorage.setItem('theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
        }
        if(localStorage.getItem('theme') === 'light') document.body.classList.add('light-mode');

        function toggleNav() { var s = document.getElementById("mySidebar"); s.style.width = s.style.width === "300px" ? "0" : "300px"; }
        function showForm(id) { document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); document.getElementById('form-' + id).style.display = 'block'; }
        function checkOrders() { let id = prompt("أدخل معرف الديسكورد:"); if(id) window.location.href="/my_orders/"+id; }

        function checkWait() {
            let last = localStorage.getItem('last_order');
            let now = Date.now();
            if(last && (now - last < 60000)) {
                document.getElementById('wait-overlay').style.display = 'flex';
                let sec = 60 - Math.floor((now - last)/1000);
                let t = setInterval(() => { sec--; document.getElementById('timer-val').innerText = sec; if(sec<=0){clearInterval(t); document.getElementById('ok-btn').style.display='block';} }, 1000);
                return false;
            }
            localStorage.setItem('last_order', now);
            return true;
        }

        // --- Spotlight Tutorial Logic ---
        let step = 0;
        function nextStep() {
            step++;
            const spotlight = document.getElementById('spotlight');
            const tooltip = document.getElementById('tut-tooltip');
            if(step===1) {
                let rect = document.getElementById('prod-list').getBoundingClientRect();
                updateSpot(rect, "هنا تظهر المنتجات، اضغط على المنتج لإتمام الشراء.");
            } else if(step===2) {
                let rect = document.getElementById('menu-trigger').getBoundingClientRect();
                updateSpot(rect, "من هنا يمكنك تتبع طلباتك والأكواد السابقة.");
            } else { document.getElementById('tut-overlay').style.display = 'none'; localStorage.setItem('tut_v24', 'done'); }
        }
        function updateSpot(rect, txt) {
            const s = document.getElementById('spotlight');
            const t = document.getElementById('tut-tooltip');
            s.style.top = rect.top-10+'px'; s.style.left = rect.left-10+'px'; s.style.width = rect.width+20+'px'; s.style.height = rect.height+20+'px';
            document.getElementById('tut-text').innerText = txt;
            t.style.top = rect.bottom+30+'px'; t.style.left = rect.left+'px';
        }
        window.onload = function() { if(!localStorage.getItem('tut_v24')){ document.getElementById('tut-overlay').style.display = 'block'; nextStep(); } };
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;"><h1>🚧 الموقع تحت الصيانة</h1></body>')
    stocks = {k: get_stock(k) for k in PRODUCTS}
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=db_feedbacks.all()[-5:])

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key, qty, d_id, cash_num = request.form.get('prod_key'), int(request.form.get('quantity', 1)), request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    coupon = request.form.get('coupon', '').strip()
    reserved = pull_codes(p_key, qty)
    if not reserved: return "Out of Stock"
    total = qty * PRODUCTS[p_key]['price']
    disc_txt = ""
    if coupon:
        cp = get_discount(coupon, p_key)
        if cp:
            total -= total * (cp['discount'] / 100)
            use_coupon(coupon)
            disc_txt = f"\n🎟️ كود خصم: {cp['discount']}%"

    db_orders.insert({'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 'total': total, 'status': 'pending', 'time': datetime.now(EGYPT_TZ).strftime("%I:%M %p"), 'reserved_codes': reserved, 'cash_number': cash_num, 'quantity': qty})
    
    async def notify():
        try:
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # رسالة البوت المنظمة سطر بسطر
            msg = (f"🔔 **طلب جديد!**\n\n"
                   f"👤 **العميل:** <@{d_id}>\n"
                   f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                   f"💰 **المبلغ:** {total} ج.م"
                   f"{disc_txt}\n"
                   f"📱 **من رقم:** {cash_num}\n"
                   f"⏰ **الوقت:** {datetime.now(EGYPT_TZ).strftime('%I:%M %p')}")
            await admin.send(msg)
        except: pass
    if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    t = request.args.get('total')
    return render_template_string(f'''<body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;">
        <div style="border:3px solid #5865F2; padding:40px; border-radius:30px; display:inline-block;">
            <h2>✅ تم تسجيل الطلب</h2>
            <p>حول <b>{t} ج.م</b> للرقم: <h1>{PAYMENT_NUMBER}</h1>
            <div style="background:rgba(88,101,242,0.1); padding:15px; border-radius:15px; border:1px solid #5865F2;">تتبع حالة طلبك من القائمة الجانبية (طلباتي).</div>
            <br><a href="/" style="color:#5865F2;">← العودة للمتجر</a>
        </div></body>''')

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    # شكل طلب الكود الاحتياطي
    return render_template_string('''<body style="background:#0a0a0a;color:white;text-align:center;padding:20px;">
        <div style="background:rgba(88,101,242,0.06); border:2px solid #5865F2; padding:30px; border-radius:30px; max-width:750px; margin:20px auto;"><h3>🔍 تتبع طلباتك</h3></div>
        {% for o in orders %}<div style="background:#111; padding:30px; margin-bottom:15px; border-radius:25px; text-align:right;">
        <b>{{o.prod_name}}</b> | الحالة: {{o.status}}
        {% if 'approved' in o.status %}<button onclick="alert('أكوادك:\\n' + '{{ o.reserved_codes|join("\\n") }}')" style="background:#43b581; color:white; border:none; padding:10px 20px; border-radius:12px; float:left; font-weight:bold; cursor:pointer;">📦 عرض الكود</button>{% endif %}</div>{% endfor %}
        <br><a href="/" style="color:#5865F2;">رجوع للمتجر</a></body>''', orders=orders)

# --- لوحة التحكم (إصلاح الكوبونات والتوست) ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST' and request.form.get('password') == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect('/admin_jo_secret')
    return '<body style="background:black; color:white; text-align:center; padding-top:100px;"><form method="post"><h2>🔐 Admin Access</h2><input type="password" name="password" style="padding:10px;"><br><br><button>Login</button></form></body>'

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'): return redirect('/admin_login')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'gift':
            g_id, g_p, g_q = request.form.get('gid'), request.form.get('gp'), int(request.form.get('gq', 1))
            codes = pull_codes(g_p, g_q)
            if codes:
                async def deliver():
                    u = await client.fetch_user(int(g_id))
                    await u.send(f"🎁 هدية! ({PRODUCTS[g_p]['name']})\\n" + "\\n".join(codes))
                asyncio.run_coroutine_threadsafe(deliver(), client.loop)
                flash("تم إرسال الجيفت ✅", "success")
        elif action == 'add_coupon':
            # استعادة الشكل القديم - بدون تاريخ انتهاء
            db_config.insert({'type':'coupon', 'code':request.form.get('c'), 'discount':int(request.form.get('d')), 'uses':int(request.form.get('u')), 'prod_key':request.form.get('p')})
            flash("تم إضافة الكوبون ✅", "success")
        elif action == 'edit_stock':
            with open(PRODUCTS[request.form.get('pk')]['file'], 'w') as f: f.write(request.form.get('cont').strip() + "\n")
            flash("تحديث المخزن ✅", "success")
        elif action == 'toggle_m':
            db_config.upsert({'type':'maintenance', 'status': not is_maintenance_mode()}, Config.type=='maintenance')

    # واجهة لوحة التحكم المستقرة
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; font-family:sans-serif; padding:20px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div style="position:fixed; top:20px; right:20px; z-index:9999;">
              {% for category, message in messages %}
                <div style="background:#43b581; padding:15px; border-radius:10px; margin-bottom:10px; box-shadow:0 0 15px rgba(0,0,0,0.5);">{{ message }}</div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}

        <h1 style="text-align:center; color:#5865F2;">🛠️ لوحة التحكم V24</h1>
        <div style="display:flex; gap:20px; flex-wrap:wrap; justify-content:center;">
            <div style="background:#111; padding:20px; border-radius:20px; width:320px; border:1px solid #333;">
                <h3>🎁 إرسال جيفت</h3>
                <form method="post"><input type="hidden" name="action" value="gift"><input name="gid" placeholder="ID العميل"><select name="gp">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input name="gq" type="number" value="1"><button style="background:#8e44ad; color:white; border:none; padding:10px; width:100%; border-radius:10px; margin-top:10px;">إرسال الآن</button></form>
            </div>
            <div style="background:#111; padding:20px; border-radius:20px; width:320px; border:1px solid #333;">
                <h3>🎫 إدارة الكوبونات</h3>
                <div style="height:80px; overflow-y:auto; margin-bottom:10px;">
                    {% for c in coupons %}
                    <div style="display:flex; justify-content:space-between; background:#000; padding:5px; margin-bottom:5px;">
                        <span>{{c.code}} ({{c.discount}}%)</span>
                        <a href="/del_c/{{c.doc_id}}" style="color:red; text-decoration:none;">[X]</a>
                    </div>
                    {% endfor %}
                </div>
                <form method="post"><input type="hidden" name="action" value="add_coupon"><input name="c" placeholder="الكود"><input name="d" placeholder="الخصم %" type="number"><input name="u" placeholder="المرات" type="number"><select name="p"><option value="all">الكل</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><button style="background:#2ecc71; color:white; border:none; padding:10px; width:100%; border-radius:10px; margin-top:10px;">إضافة</button></form>
            </div>
        </div>
        <br>
        <div style="display:flex; gap:10px; flex-wrap:wrap; justify-content:center;">
        {% for k,v in prods.items() %}
            <div style="background:#111; padding:20px; border-radius:20px; width:300px; border:1px solid #222;">
                <h4>{{v.name}}</h4>
                <form method="post"><input type="hidden" name="action" value="edit_stock"><input type="hidden" name="pk" value="{{k}}"><textarea name="cont" style="width:100%; height:80px; background:black; color:#43b581;">{{stocks[k]}}</textarea><button style="background:#2ecc71; width:100%; border:none; padding:10px; border-radius:10px; color:white; margin-top:5px;">حفظ</button></form>
            </div>
        {% endfor %}
        </div>
        <br><table border="1" width="100%" style="text-align:center; background:#111; border-radius:15px; overflow:hidden;"><tr><th>العميل</th><th>المنتج</th><th>الحالة</th><th>الإجراء</th></tr>
        {% for o in orders|reverse %}<tr><td>@{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.status}}</td><td>{% if o.status == 'pending' %}<a href="/app/{{o.doc_id}}" style="color:#43b581;">[قبول]</a> | <a href="/rej/{{o.doc_id}}" style="color:red;">[رفض]</a>{% else %}-{% endif %}</td></tr>{% endfor %}</table>
    </body>''', prods=PRODUCTS, orders=db_orders.all(), coupons=db_config.search(Config.type=='coupon'), stocks={k:open(v['file']).read() if os.path.exists(v['file']) else "" for k,v in PRODUCTS.items()})

@app.route('/del_c/<int:id>')
def del_c(id):
    if session.get('logged_in'): db_config.remove(doc_ids=[id])
    return redirect('/admin_jo_secret')

@app.route('/app/<int:id>')
def approve(id):
    order = db_orders.get(doc_id=id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[id])
        async def deliver():
            u = await client.fetch_user(int(order['discord_id']))
            await u.send(f"🔥 **تم تأكيد طلبك بنجاح!**\\n" + "\\n".join([f"🔗 {c}" for c in order['reserved_codes']]))
        asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/rej/<int:id>')
def reject(id):
    order = db_orders.get(doc_id=id)
    if order and order['status'] == 'pending':
        # استخدام دالة الإرجاع الآمنة لمنع التكرار
        return_codes(order['prod_key'], order['reserved_codes'])
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[id])
    return redirect('/admin_jo_secret')

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment')})
    return redirect('/')

def run_flask(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready(): client.loop = asyncio.get_running_loop(); print(f"✅ Jo Store Online!")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    client.run(TOKEN)
