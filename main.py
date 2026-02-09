import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for, session, flash, make_response
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

# تحديد توقيت القاهرة
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# تعريف المنتجات
PRODUCTS = {
    'xbox': {
        'name': 'Xbox Game Pass Premium',
        'price': 10,
        'file': 'xbox.txt',
        'img': 'رابط_صورة_الاكس_بوكس'
    },
    'nitro1': {
        'name': 'Discord Nitro 1 Month',
        'price': 5,
        'file': 'nitro1.txt',
        'img': 'رابط_صورة_نيترو_شهر'
    },
    'nitro3': {
        'name': 'Discord Nitro 3 Months',
        'price': 10,
        'file': 'nitro3.txt',
        'img': 'رابط_صورة_نيترو_3_شهور'
    }
}

app = Flask(__name__)
app.secret_key = 'jo_store_v16_fully_extended_code_1200_lines'

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
    """حساب الكمية المتوفرة"""
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename):
        return 0
    try:
        with open(filename, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
        return len(lines)
    except:
        return 0

def pull_codes(p_key, qty):
    """حجز الأكواد فور الطلب"""
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, 'r') as f: 
            lines = [l for l in f.readlines() if l.strip()]
        if len(lines) < qty:
            return []
        pulled = lines[:qty]
        remaining = lines[qty:]
        with open(filename, 'w') as f: 
            f.writelines(remaining)
        return [c.strip() for c in pulled]
    except:
        return []

def return_codes(p_key, codes):
    """إرجاع الأكواد في حالة الرفض"""
    filename = PRODUCTS[p_key]['file']
    try:
        with open(filename, 'a') as f:
            for c in codes:
                f.write(c + "\n")
    except:
        pass

def is_maintenance_mode():
    """فحص الصيانة"""
    res = db_config.get(Config.type == 'maintenance')
    if res:
        return res['status']
    return False

def get_discount(code, prod_key):
    """فحص كود الخصم"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res:
        if res['prod_key'] != 'all' and res['prod_key'] != prod_key:
            return None
        if res['uses'] <= 0:
            return None
        try:
            expire_time = datetime.fromisoformat(res['expires_at'])
            now_egypt = datetime.now(EGYPT_TZ).replace(tzinfo=None)
            if now_egypt > expire_time:
                return None
        except:
            return None
        return res
    return None

def use_coupon(code):
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res and res['uses'] > 0:
        db_config.update({'uses': res['uses'] - 1}, doc_ids=[res.doc_id])

# --- واجهة المتجر الرئيسية (مفرودة HTML & CSS بالكامل) ---

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
            --sidebar-bg: #111;
        }
        
        body.light-mode {
            --bg-color: #f4f4f4;
            --text-color: #333;
            --card-bg: #ffffff;
            --sidebar-bg: #ffffff;
        }
        
        body {
            background: var(--bg-color);
            color: var(--text-color);
            font-family: sans-serif;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
            transition: 0.5s ease-in-out;
        }
        
        /* كبسولة التحكم الاحترافية */
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
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        }

        .nav-btn {
            background: none;
            border: none;
            color: var(--text-color);
            font-size: 28px;
            cursor: pointer;
            transition: 0.4s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .nav-btn:hover {
            color: var(--main-color);
            transform: scale(1.15);
        }
        
        .nav-divider {
            width: 1px;
            height: 30px;
            background: rgba(255, 255, 255, 0.1);
            margin: 0 5px;
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
            transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            padding-top: 80px;
            border-right: 1px solid rgba(128, 128, 128, 0.1);
            box-shadow: 5px 0 25px rgba(0,0,0,0.6);
        }
        
        .sidebar a {
            padding: 18px 25px;
            text-decoration: none;
            display: block;
            text-align: right;
            color: #888;
            font-size: 18px;
            transition: 0.3s;
            border-bottom: 1px solid rgba(128, 128, 128, 0.05);
        }
        
        .sidebar a:hover {
            color: var(--main-color);
            background: rgba(88, 101, 242, 0.1);
            padding-right: 40px;
        }
        
        .section-title {
            padding: 25px 25px 10px 25px;
            color: var(--main-color);
            font-weight: bold;
            font-size: 15px;
            text-transform: uppercase;
        }
        
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
            animation: fadeInUp 0.8s ease-out;
        }
        
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(40px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .product-card {
            width: 320px;
            height: 520px;
            border-radius: 40px;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid rgba(128, 128, 128, 0.1);
            background: var(--card-bg);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }
        
        .product-card:hover {
            transform: translateY(-15px);
            border-color: var(--main-color);
            box-shadow: 0 20px 60px rgba(88, 101, 242, 0.25);
        }
        
        .card-image {
            position: absolute;
            inset: 0;
            background-size: cover;
            background-position: center;
            z-index: 1;
            transition: 1s;
        }
        
        .product-card:hover .card-image {
            transform: scale(1.15);
        }
        
        .card-overlay {
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.5) 45%, transparent 85%);
            z-index: 2;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: 35px;
        }
        
        .order-form {
            display: none;
            background: rgba(12, 12, 12, 0.98);
            padding: 20px;
            border-radius: 25px;
            border: 1px solid var(--main-color);
            margin-top: 15px;
            position: relative;
            z-index: 10;
            animation: zoomIn 0.3s ease;
        }
        
        @keyframes zoomIn {
            from { transform: scale(0.9); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        
        input {
            width: 90%;
            padding: 14px;
            margin: 8px 0;
            border-radius: 12px;
            border: 1px solid #333;
            background: #1a1a1a;
            color: white;
            text-align: center;
            font-size: 15px;
            transition: 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: var(--main-color);
            box-shadow: 0 0 15px rgba(88, 101, 242, 0.2);
        }
        
        .btn-purchase {
            background: var(--main-color);
            color: white;
            border: none;
            padding: 16px;
            border-radius: 15px;
            cursor: pointer;
            width: 100%;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
            transition: 0.3s;
        }
        
        .btn-purchase:hover {
            background: #4752c4;
            transform: scale(1.02);
        }
        
        .feedback-item {
            background: var(--card-bg);
            margin: 15px 20px;
            padding: 20px;
            border-radius: 20px;
            font-size: 13px;
            border-right: 5px solid var(--main-color);
            text-align: right;
            box-shadow: 0 5px 15px rgba(0,0,0,0.15);
        }
        
        .warning-text {
            color: #f1c40f;
            font-size: 11px;
            margin-bottom: 12px;
            font-weight: bold;
            line-height: 1.6;
        }
        
        .price-text {
            color: #43b581;
            font-weight: bold;
            font-size: 30px;
            margin: 5px 0;
        }
        
        .stock-info {
            color: #888;
            font-size: 14px;
            margin-bottom: 15px;
        }

        /* Countdown Popup */
        #wait-overlay {
            display: none;
            position: fixed;
            inset: 0;
            z-index: 4000;
            background: rgba(0,0,0,0.9);
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
            backdrop-filter: blur(5px);
        }
        
        .timer-box {
            width: 120px;
            height: 120px;
            border: 6px solid var(--main-color);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 42px;
            font-weight: bold;
            color: var(--main-color);
            margin-bottom: 25px;
            box-shadow: 0 0 30px rgba(88,101,242,0.4);
        }
        
        .btn-ok {
            background: var(--main-color);
            color: white;
            padding: 12px 40px;
            border-radius: 12px;
            border: none;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
        }

        /* Tutorial Modal */
        .tut-modal {
            display: none;
            position: fixed;
            inset: 0;
            z-index: 3000;
            background: rgba(0,0,0,0.92);
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(8px);
        }
        
        .tut-content {
            background: var(--card-bg);
            padding: 45px;
            border-radius: 35px;
            text-align: center;
            max-width: 420px;
            border: 2px solid var(--main-color);
            color: white;
        }
    </style>
</head>
<body id="body">
    <div id="wait-overlay">
        <div class="timer-box" id="timer-val">60</div>
        <h3 style="font-size: 24px;">انتظر من فضلك.. ⌛</h3>
        <p style="color: #888; text-align:center;">لمنع السبام، يرجى الانتظار دقيقة واحدة بين كل محاولة شراء.</p>
        <button class="btn-ok" id="ok-btn" style="display: none;" onclick="document.getElementById('wait-overlay').style.display='none'">OK</button>
    </div>

    <div id="tut-popup" class="tut-modal">
        <div class="tut-content">
            <h2 style="color: var(--main-color); font-size: 30px;">مرحباً بك في Jo Store! 🌟</h2>
            <p style="font-size: 18px; line-height: 1.6;">Are you new in the website and need a quick tutorial?</p>
            <br>
            <button class="btn-purchase" onclick="startTutorial()">Yes, I need tutorial</button>
            <button class="btn-purchase" style="background: #333; margin-top: 10px;" onclick="closeTut()">No, thanks</button>
        </div>
    </div>

    <div class="glass-nav">
        <button class="nav-btn" onclick="toggleNav()">&#9776;</button>
        <div class="nav-divider"></div>
        <button class="nav-btn" onclick="toggleTheme()">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="/orders" id="orders-link">📋 تتبع طلباتي</a>
        <div class="section-title">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 0 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك..." required style="width: 90%; background: #1a1a1a; color: white; border: 1px solid #333; padding: 12px; border-radius: 15px; height: 100px; margin-top: 10px; resize: none;"></textarea>
            <button type="submit" class="btn-purchase" style="padding: 10px;">إرسال</button>
        </form>
        <div class="section-title">آراء الزبائن</div>
        {% for f in feedbacks %}
        <div class="feedback-item">
            <b style="color:var(--main-color);">{{ f.name }}:</b><br>
            <span style="color:#aaa;">{{ f.comment }}</span>
        </div>
        {% endfor %}
    </div>

    <div id="main-content">
        <h1>Jo Store | متجرك المفضل 🔒</h1>
        <p style="color:#777; font-size: 20px;">أفضل المنتجات الرقمية بضمان كامل وأسرع تسليم</p>
        
        <div class="products-container" id="products-area">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div class="price-text">{{ info.price }} ج.م</div>
                    <div class="stock-info">المتوفر حالياً: {{ stocks[key] }} قطعة</div>
                    
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <div class="warning-text">⚠️ يرجى التأكد من كتابة ID الديسكورد ورقم الكاش بدقة لضمان وصول طلبك.</div>
                        <form action="/place_order" method="post" onsubmit="return checkWait()">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش المحول منه" required>
                            <input type="text" name="coupon" placeholder="كود الخصم (إن وجد)" style="border: 1px dashed #43b581;">
                            <button type="submit" class="btn-purchase">تأكيد عملية الشراء</button>
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
            if (side.style.width === "300px") { side.style.width = "0"; } 
            else { side.style.width = "300px"; }
        }
        function toggleTheme() {
            document.body.classList.toggle("light-mode");
            localStorage.setItem('jo_theme_v16', document.body.classList.contains('light-mode') ? 'light' : 'dark');
        }
        if (localStorage.getItem('jo_theme_v16') === 'light') { document.body.classList.add('light-mode'); }

        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }

        // Tutorial
        window.onload = function() { if(!localStorage.getItem('tut_v16')) document.getElementById('tut-popup').style.display = 'flex'; };
        function closeTut() { document.getElementById('tut-popup').style.display = 'none'; localStorage.setItem('tut_v16', 'true'); }
        function startTutorial() {
            closeTut();
            alert("الخطوة 1: من هنا تظهر المنتجات، اضغط على المنتج لإتمام الشراء.");
            setTimeout(() => {
                alert("الخطوة 2: يمكنك تتبع حالة طلبك ورؤية الأكواد من صفحة (طلباتي) في القائمة الجانبية.");
                toggleNav();
            }, 1000);
        }

        // Countdown
        function checkWait() {
            let last = localStorage.getItem('last_buy');
            let now = Date.now();
            if(last && (now - last < 60000)) {
                document.getElementById('wait-overlay').style.display = 'flex';
                let sec = 60 - Math.floor((now - last)/1000);
                let timer = setInterval(() => {
                    sec--; document.getElementById('timer-val').innerText = sec;
                    if(sec <= 0) { clearInterval(timer); document.getElementById('ok-btn').style.display = 'block'; }
                }, 1000);
                return false;
            }
            localStorage.setItem('last_buy', now);
            return true;
        }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;"><h1>🚧 الموقع تحت الصيانة حالياً</h1></body>')
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/orders', methods=['GET', 'POST'])
def orders_page():
    """صفحة الطلبات المنفصلة"""
    uid = request.args.get('uid') or request.form.get('uid')
    orders_list = db_orders.search(Order.discord_id == uid) if uid else []
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:50px;">
        <div style="background:rgba(88,101,242,0.06); border:2px solid #5865F2; padding:30px; border-radius:30px; max-width:750px; margin:0 auto 50px auto; line-height:1.8;">
            <h3 style="color:#5865F2; margin-top:0; font-size:24px;">🔍 تتبع ومعالجة طلباتك</h3>
            <p style="color:#bbb; font-size:16px;">هنا يمكنك معرفة أين وصل طلبك حالياً.. كما يسعدنا جداً أن نسمع رأيك في الخدمة من خلال <b>(قسم التقييمات)</b> لتطوير متجرنا.</p>
            <form method="post">
                <input name="uid" placeholder="ID الديسكورد" style="padding:15px; border-radius:15px; width:60%; text-align:center; background:#111; color:white; border:1px solid #333;">
                <button type="submit" style="padding:15px 30px; background:#5865F2; color:white; border:none; border-radius:15px; margin-right:10px; font-weight:bold;">بـحـث</button>
            </form>
        </div>
        
        <div style="max-width:750px; margin:auto;">
        {% for o in orders %}
            <div style="background:#111; padding:35px; margin-bottom:25px; border-radius:30px; border: 1px solid #222; text-align:right;">
                <div style="display:flex; justify-content:space-between;">
                    <b style="font-size:22px;">{{o.prod_name}}</b>
                    <span style="color:#43b581; font-weight:bold;">{{o.total}} ج.م</span>
                </div>
                <div style="height:14px; background:#333; border-radius:10px; margin:20px 0; overflow:hidden;">
                    <div style="width:{{ '100%' if 'approved' in o.status else '50%' }}; height:100%; transition: 1.2s; background:{{ '#2ecc71' if 'approved' in o.status else '#e74c3c' if 'rejected' in o.status else '#f1c40f' }};"></div>
                </div>
                <span>الحالة: <b>{{o.status}}</b></span>
                {% if 'approved' in o.status %}
                <button onclick="alert('أكوادك المشتراة:\\n' + '{{ o.reserved_codes|join("\\\n") }}')" 
                            style="background:#43b581; color:white; border:none; padding:10px 20px; border-radius:12px; float:left; font-weight:bold;">📦 عرض الكود الاحتياطي</button>
                {% endif %}
            </div>
        {% endfor %}
        </div>
        <br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none; font-size:20px;">← العودة للمتجر</a>
    </body>''', orders=orders_list)

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key, qty, d_id, cash_num = request.form.get('prod_key'), int(request.form.get('quantity', 1)), request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    cp_code = request.form.get('coupon', '').strip()
    
    codes = pull_codes(p_key, qty)
    if not codes: return "المخزون نفذ!"
    
    total = qty * PRODUCTS[p_key]['price']
    discount_txt = ""
    if cp_code:
        cp = get_discount(cp_code, p_key)
        if cp:
            total -= total * (cp['discount'] / 100)
            use_coupon(cp_code)
            discount_txt = f"\n🎟️ **تم استخدام كود خصم: {cp['discount']}%**"

    db_orders.insert({
        'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 
        'total': total, 'status': 'pending', 'time': datetime.now(EGYPT_TZ).strftime("%I:%M %p"), 
        'reserved_codes': codes, 'cash_number': cash_num, 'quantity': qty, 'discount_applied': discount_txt
    })
    
    async def notify():
        try:
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # رسالة منظمة فوق بعضها
            msg = (f"🔔 **طلب جديد!**\n\n"
                   f"👤 **العميل:** <@{d_id}>\n"
                   f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                   f"💰 **المبلغ:** {total} ج.م"
                   f"{discount_txt}\n"
                   f"📱 **من رقم:** {cash_num}\n"
                   f"⏰ **الوقت:** {datetime.now(EGYPT_TZ).strftime('%I:%M %p')}")
            await admin.send(msg)
        except: pass
    if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    t_val = request.args.get('total')
    #
    return render_template_string(f'''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
        <div style="border:3px solid #5865F2; padding:50px; border-radius:45px; display:inline-block; max-width:580px; background: rgba(88,101,242,0.01);">
            <h2 style="color:#43b581; font-size:36px;">✅ تم تسجيل الطلب بنجاح</h2>
            <p style="font-size:20px;">حول مبلغ <b>{t_val} جنيه</b> للرقم التالي:</p>
            <h1 style="background:#222; padding:30px; border-radius:25px; border:1px solid #333; font-size:46px; letter-spacing:4px;">{PAYMENT_NUMBER}</h1>
            
            <div style="margin: 40px 0; border: 3px solid #5865F2; border-radius: 40px; padding: 15px 30px; background: rgba(88,101,242,0.05); display: inline-flex; align-items: center; justify-content: center; gap: 15px;">
                <div style="background: #f1c40f; height: 6px; width: 60px; border-radius: 10px;"></div>
                <span style="color: #f1c40f; font-weight: bold; font-size: 16px;">تنبيه: تتبع حالة طلبك ومعرفة الأكواد من <a href="/orders" style="color:#5865F2; text-decoration:none;">[ هـنـا ]</a></span>
                <div style="background: #f1c40f; height: 6px; width: 60px; border-radius: 10px;"></div>
            </div>
            
            <div style="background:rgba(255,204,0,0.1); padding:25px; border-radius:25px; border:1px solid #ffcc00; text-align:right; margin: 20px 0; line-height:1.8;">
                <b style="color:#ffcc00; font-size:18px;">⚠️ ملحوظة هامة جداً:</b><br>
                يجب الانضمام للسيرفر بالضغط <a href="https://discord.gg/RYK28PNv" style="color:#5865F2; font-weight:bold; text-decoration:none;">[ هـنـا ]</a> وتأكد أن الخاص مفتوح.
            </div>
            <br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none; font-size:20px;">← العودة للمتجر الرئيسي</a>
        </div>
    </body>''')

# --- لوحة التحكم وإدارة الأدمن ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin_jo_secret')
    return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:120px;"><form method="post"><h2>🔐 Admin Portal</h2><input type="password" name="password" style="padding:15px; border-radius:15px; text-align:center;" autofocus><br><br><button type="submit" style="padding:15px 50px; background:#5865F2; color:white; border-radius:15px;">دخول</button></form></body>')

@app.route('/delete_coupon/<int:code_id>')
def delete_coupon(code_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    db_config.remove(doc_ids=[code_id])
    flash("تم حذف الكود ✅", 'success')
    return redirect('/admin_jo_secret')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'): return redirect('/admin_login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        if action == 'add_coupon':
            c_code = request.form.get('c_code', '').strip()
            if not db_config.get((Config.type == 'coupon') & (Config.code == c_code)):
                mins = int(request.form.get('c_minutes', 60))
                exp_at = (datetime.now(EGYPT_TZ).replace(tzinfo=None) + timedelta(minutes=mins)).isoformat()
                db_config.insert({'type': 'coupon', 'code': c_code, 'discount': int(request.form.get('c_disc')), 'uses': int(request.form.get('c_uses')), 'prod_key': request.form.get('c_prod'), 'expires_at': exp_at})
                flash("تم تفعيل كود الخصم '{c_code}' ✅", 'success')
            else: flash("الكود موجود!", 'error')
        elif action == 'edit_stock':
            content = request.form.get('full_content', '').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f: f.write(content + "\n" if content else "")
            flash("تحديث ✅", 'success')
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
            flash("الصيانة ✅", 'success')
        elif action == 'gift':
            g_id, g_p, g_q = request.form.get('g_id'), request.form.get('g_prod'), int(request.form.get('g_qty', 1))
            codes = pull_codes(g_p, g_q)
            if codes:
                async def deliver():
                    try:
                        u = await client.fetch_user(int(g_id))
                        msg = f"🎁 هدية! ({PRODUCTS[g_p]['name']})\\n" + "\\n".join([f"🔗 {c}" for c in codes])
                        await u.send(msg)
                    except: pass
                if client.loop: asyncio.run_coroutine_threadsafe(deliver(), client.loop)
                flash(f"إرسال لـ {g_id} ✅", 'success')

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    active_coupons = [{**item, 'id': item.doc_id} for item in db_config.search(Config.type == 'coupon')]
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k, v in PRODUCTS.items()}
    m_txt = "مفعل 🔴" if is_maintenance_mode() else "معطل 🟢"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl"><head><meta charset="UTF-8">
    <style>
        :root { --main: #5865F2; --success: #43b581; --danger: #f04747; --bg: #0a0a0a; }
        body { background: var(--bg); color: white; font-family: sans-serif; padding: 40px; }
        .card { background:#111; padding:30px; border-radius:30px; border:1px solid #222; margin-bottom:30px; box-shadow:0 0 20px rgba(0,0,0,0.5); }
        .grid { display: flex; gap: 30px; flex-wrap: wrap; justify-content: center; }
        input, select, textarea { width:100%; padding:15px; background:#000; color:white; border:1px solid #333; margin-top:10px; border-radius:12px; }
        button { width:100%; padding:15px; margin-top:10px; border-radius:12px; border:none; color:white; font-weight:bold; cursor:pointer; transition:0.3s; }
        table { width:100%; text-align:center; border-collapse:collapse; margin-top:20px; border-radius:20px; overflow:hidden; }
        th { background:var(--main); padding:20px; } td { padding:15px; border-bottom:1px solid #222; background: #111; }
        #toast-container { position: fixed; top: 30px; right: 30px; z-index: 9999; }
        .toast { width: 340px; padding: 20px; border-radius: 20px; margin-bottom: 15px; position: relative; animation: slideIn 0.5s ease; background: var(--main); overflow: hidden; }
        .toast-progress { position: absolute; bottom: 0; left: 0; height: 6px; background: rgba(255,255,255,0.9); width: 100%; }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
    </style>
    </head><body>
        <div id="toast-container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="toast" style="background:{{'var(--success)' if category=='success' else 'var(--danger)'}}">
                            <b>{{'✅ نجاح' if category=='success' else '❌ تنبيه'}}</b><br>{{message}}
                            <div class="toast-progress"></div>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        <a href="/" style="background:#222; color:white; padding:15px 35px; border-radius:20px; text-decoration:none; float:left; font-weight:bold; border:1px solid #333;">🏠 العودة للمتجر</a>
        <h1 style="text-align:center; color:var(--main); font-size: 42px; margin-bottom:60px;">🛠️ لوحة التحكم V16 Pro</h1>
        
        <div class="grid">
            <div class="card" style="width:320px;"><h3>🛡️ الصيانة ({{m_txt}})</h3><form method="post"><input type="hidden" name="action" value="toggle_maintenance"><button style="background:#f39c12;">تبديل</button></form></div>
            <div class="card" style="width:320px;"><h3>🎁 جيفت</h3><form method="post"><input type="hidden" name="action" value="gift"><input type="text" name="g_id" placeholder="ID"><select name="g_prod">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input type="number" name="g_qty" value="1"><button style="background:#8e44ad;">إرسال</button></form></div>
            <div class="card" style="width:420px;"><h3>🎫 الكوبونات</h3><div style="max-height:200px; overflow-y:auto;">{% for c in active_coupons %}<div style="background:#000; padding:15px; border-radius:18px; margin-bottom:15px; border:1px solid #333; display:flex; justify-content:space-between;"><div><b>{{ c.code }}</b> | {{ c.discount }}%</div><a href="/delete_coupon/{{c.id}}" style="color:var(--danger);">حذف</a></div>{% endfor %}</div></div>
        </div>

        <div class="card"><h3>📝 ملفات المخزن</h3><div class="grid">{% for k, content in stock.items() %}<div style="width:340px; background:#000; padding:25px; border-radius:25px; border:1px solid #222;"><h4>{{prods[k].name}}</h4><form method="post"><input type="hidden" name="action" value="edit_stock"><input type="hidden" name="p_key" value="{{k}}"><textarea name="full_content" style="height:140px; color:#43b581;">{{content}}</textarea><button style="background:#2ecc71;">حفظ</button></form></div>{% endfor %}</div></div>

        <div class="card" style="overflow-x:auto;"><h3>📦 سجل الطلبات</h3><table><thead><tr><th>العميل</th><th>المنتج</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th></tr></thead><tbody>{% for o in orders|reverse %}<tr><td>@{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.total}} ج.م</td><td>{{o.status}}</td><td>{% if o.status == 'pending' %}<a href="/approve/{{o.doc_id}}" style="color:var(--success);">[قبول]</a> <a href="/reject/{{o.doc_id}}" style="color:var(--danger);">[رفض]</a>{% else %}-{% endif %}</td></tr>{% endfor %}</tbody></table></div>

        <script>
            document.querySelectorAll('.toast').forEach((toast) => {
                let progress = toast.querySelector('.toast-progress');
                progress.style.width = '100%';
                setTimeout(() => { progress.style.width = '0%'; progress.style.transition = 'width 5s linear'; }, 10);
                setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.7s ease-in-out'; setTimeout(() => toast.remove(), 800); }, 5000);
            });
        </script>
    </body></html>
    ''', orders=orders, active_coupons=active_coupons, stock=stock_contents, prods=PRODUCTS, m_txt=m_txt)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver():
            try:
                u = await client.fetch_user(int(order['discord_id']))
                #
                msg = f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']}) بنجاح**\n" + "\n".join([f"🔗 {c}" for c in order['reserved_codes']])
                await u.send(msg)
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        return_codes(order['prod_key'], order.get('reserved_codes', []))
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
    return redirect('/admin_jo_secret')

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    ip_addr = request.remote_addr
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment'), 'ip': ip_addr})
    return redirect('/')

def run_web_server(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready():
    client.loop = asyncio.get_running_loop()
    print(f"✅ Bot is ready! {client.user}")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    if TOKEN:
        try: client.run(TOKEN)
        except: time.sleep(1000)
