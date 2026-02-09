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

# توقيت مصر لضبط رسائل الإشعارات
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# تعريف المنتجات بدقة
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
app.secret_key = 'jo_store_ultimate_v11_pro_max_long_code'

# قواعد البيانات المحلية
db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
db_config = TinyDB('config.json') 
Order = Query()
Config = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية (نظام حجز المخزون الذكي) ---

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
    """سحب وحجز الأكواد فور الطلب (يبقى مسحوب في Pending/Approved)"""
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename):
        return []
    
    try:
        with open(filename, 'r') as f: 
            lines = [l for l in f.readlines() if l.strip()]
        
        if len(lines) < qty:
            return []
            
        pulled_codes = lines[:qty]
        remaining_codes = lines[qty:]
        
        with open(filename, 'w') as f: 
            f.writelines(remaining_codes)
            
        return [c.strip() for c in pulled_codes]
    except:
        return []

def return_codes(p_key, codes_to_return):
    """إعادة الأكواد للمخزن فقط في حالة الرفض (Reject)"""
    filename = PRODUCTS[p_key]['file']
    try:
        with open(filename, 'a') as f:
            for c in codes_to_return:
                f.write(c + "\n")
    except:
        pass

# --- دوال الصيانة والخصومات ---

def is_maintenance_mode():
    """التحقق من حالة الصيانة"""
    res = db_config.get(Config.type == 'maintenance')
    if res:
        return res['status']
    return False

def get_discount(coupon_code, target_prod):
    """فحص صلاحية الكوبون"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == coupon_code))
    if res:
        # فحص توافق المنتج
        if res['prod_key'] != 'all' and res['prod_key'] != target_prod:
            return None
        # فحص عدد الاستخدامات
        if res['uses'] <= 0:
            return None
        # فحص الموقت الزمني
        try:
            expire_at = datetime.fromisoformat(res['expires_at'])
            if datetime.now() > expire_at:
                return None
        except:
            return None
        return res
    return None

def use_coupon(code_to_update):
    """نقص استخدام الكوبون"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == code_to_update))
    if res and res['uses'] > 0:
        db_config.update({'uses': res['uses'] - 1}, doc_ids=[res.doc_id])

# --- واجهة المتجر الرئيسية (مفرودة بالكامل) ---

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
            transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
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
            padding: 0;
            margin: 0;
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
            background-color: var(--sidebar-bg);
            overflow-y: auto;
            transition: 0.5s ease;
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

        /* --- Tutorial / Spotlight Styling --- */
        #tut-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.85);
            z-index: 5000;
        }

        .spotlight {
            position: absolute;
            border: 4px solid #f1c40f;
            border-radius: 20px;
            box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.85);
            z-index: 5001;
            transition: all 0.5s ease;
            pointer-events: none;
        }

        .tut-card {
            position: absolute;
            background: white;
            color: black;
            padding: 25px;
            border-radius: 20px;
            width: 280px;
            z-index: 5002;
            text-align: center;
            font-weight: bold;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            transition: all 0.5s ease;
        }

        /* --- Welcome / Countdown Modals --- */
        .modal-base {
            display: none;
            position: fixed;
            inset: 0;
            z-index: 6000;
            background: rgba(0,0,0,0.9);
            align-items: center;
            justify-content: center;
        }

        .modal-content {
            background: #111;
            padding: 40px;
            border-radius: 30px;
            text-align: center;
            max-width: 400px;
            border: 2px solid var(--main-color);
        }

        .timer-circle {
            width: 100px;
            height: 100px;
            border: 6px solid var(--main-color);
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 36px;
            font-weight: bold;
            color: var(--main-color);
            margin-bottom: 20px;
        }
    </style>
</head>
<body id="body">

    <div id="countdownModal" class="modal-base" style="z-index: 7000;">
        <div class="modal-content">
            <div class="timer-circle" id="timerDisplay">60</div>
            <h3 style="color: white;">انتظر من فضلك.. ⌛</h3>
            <p style="color: #888;">لمنع السبام، يرجى الانتظار دقيقة بين كل عملية شراء.</p>
            <button class="btn-purchase" id="closeCountdown" style="display: none; width: auto; padding: 10px 40px;" onclick="document.getElementById('countdownModal').style.display='none'">OK</button>
        </div>
    </div>

    <div id="welcomeModal" class="modal-base">
        <div class="modal-content">
            <h2 style="color: var(--main-color);">مرحباً بك في Jo Store! 🌟</h2>
            <p style="color: #ccc; margin: 20px 0;">هل أنت جديد في الموقع وتحتاج لدليل إرشادي سريع؟</p>
            <button class="btn-purchase" onclick="startTutorial()">نعم، ابدأ الجولة</button>
            <button class="btn-purchase" style="background: #333; margin-top: 10px;" onclick="closeWelcome()">لا، شكراً</button>
        </div>
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
        <div class="nav-divider"></div>
        <button class="nav-btn" onclick="toggleTheme()">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" id="orders-link" onclick="checkOrders()">📋 تتبع طلباتي</a>
        <div class="section-title">أضف تقييمك</div>
        <form action="/add_feedback" method="post" style="padding: 0 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك..." required style="width: 90%; background: #1a1a1a; color: white; border: 1px solid #333; padding: 12px; border-radius: 15px; height: 80px; margin-top: 10px; resize: none;"></textarea>
            <button type="submit" class="btn-purchase" style="padding: 10px;">إرسال</button>
        </form>
        <div class="section-title">الآراء</div>
        {% for f in feedbacks %}
        <div class="feedback-item"><b>{{ f.name }}:</b> {{ f.comment }}</div>
        {% endfor %}
    </div>

    <div id="main-content">
        <h1 id="site-header">Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container" id="products-list">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div class="price-text">{{ info.price }} ج.م</div>
                    <div class="stock-info">المتوفر: {{ stocks[key] }}</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post" onsubmit="return handlePurchase()">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <input type="text" name="coupon" placeholder="كود الخصم (اختياري)">
                            <button type="submit" class="btn-purchase">تأكيد عملية الشراء</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        // --- UI Logic ---
        function toggleNav() {
            var side = document.getElementById("mySidebar");
            side.style.width = side.style.width === "300px" ? "0" : "300px";
        }
        function toggleTheme() { document.body.classList.toggle("light-mode"); }
        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }
        function checkOrders() { 
            let id = prompt("أدخل معرف الديسكورد الخاص بك:"); 
            if(id) window.location.href="/my_orders/"+id; 
        }

        // --- Spam Prevention Countdown ---
        function handlePurchase() {
            let lastBuy = localStorage.getItem('last_buy_ts');
            let now = Date.now();
            if (lastBuy && (now - lastBuy < 60000)) {
                document.getElementById('countdownModal').style.display = 'flex';
                let remaining = 60 - Math.floor((now - lastBuy) / 1000);
                let timer = setInterval(() => {
                    remaining--;
                    document.getElementById('timerDisplay').innerText = remaining;
                    if (remaining <= 0) {
                        clearInterval(timer);
                        document.getElementById('closeCountdown').style.display = 'block';
                    }
                }, 1000);
                return false;
            }
            localStorage.setItem('last_buy_ts', now);
            return true;
        }

        // --- Smart Tutorial Spotlight Logic ---
        window.onload = function() {
            if (!localStorage.getItem('tut_v20_done')) {
                document.getElementById('welcomeModal').style.display = 'flex';
            }
        };

        function closeWelcome() {
            document.getElementById('welcomeModal').style.display = 'none';
            localStorage.setItem('tut_v20_done', 'true');
        }

        let currentStep = 0;
        function startTutorial() {
            document.getElementById('welcomeModal').style.display = 'none';
            document.getElementById('tut-overlay').style.display = 'block';
            nextStep();
        }

        function nextStep() {
            currentStep++;
            const spot = document.getElementById('spotlight');
            const tool = document.getElementById('tut-tooltip');
            const text = document.getElementById('tut-text');

            if (currentStep === 1) {
                const target = document.getElementById('products-list');
                const rect = target.getBoundingClientRect();
                updateSpotlight(rect, "هنا تجد جميع منتجاتنا. اضغط على المنتج لإتمام الشراء.");
            } else if (currentStep === 2) {
                const target = document.querySelector('.glass-nav');
                const rect = target.getBoundingClientRect();
                updateSpotlight(rect, "من هنا يمكنك فتح القائمة للوصول إلى تتبع طلباتك والأكواد السابقة.");
            } else {
                document.getElementById('tut-overlay').style.display = 'none';
                closeWelcome();
            }
        }

        function updateSpotlight(rect, desc) {
            const spot = document.getElementById('spotlight');
            const tool = document.getElementById('tut-tooltip');
            spot.style.top = rect.top - 10 + 'px';
            spot.style.left = rect.left - 10 + 'px';
            spot.style.width = rect.width + 20 + 'px';
            spot.style.height = rect.height + 20 + 'px';
            
            document.getElementById('tut-text').innerText = desc;
            tool.style.top = rect.bottom + 30 + 'px';
            tool.style.left = rect.left + 'px';
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

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon_code = request.form.get('coupon', '').strip()

    reserved = pull_codes(p_key, qty)
    if not reserved:
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;"><h1>❌ المخزون نفذ!</h1><a href="/" style="color:#5865F2;">العودة</a></body>')
    
    total = qty * PRODUCTS[p_key]['price']
    disc_line = ""
    if coupon_code:
        cp = get_discount(coupon_code, p_key)
        if cp:
            total -= total * (cp['discount'] / 100)
            use_coupon(coupon_code)
            disc_line = f"🎟️ كود خصم: {cp['discount']}%"

    db_orders.insert({
        'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 'total': total,
        'status': 'pending', 'time': datetime.now(EGYPT_TZ).strftime("%I:%M %p"), 'reserved_codes': reserved,
        'cash_number': cash_num, 'quantity': qty, 'discount_applied': disc_line
    })
    
    async def notify():
        try:
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # رسالة البوت منظمة فوق بعضها بدقة
            msg = (f"🔔 **طلب جديد!**\n\n"
                   f"👤 **العميل:** <@{d_id}>\n"
                   f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                   f"💰 **المبلغ:** {total} ج.م\n"
                   f"{disc_line}\n"
                   f"📱 **من رقم:** {cash_num}\n"
                   f"⏰ **الوقت:** {datetime.now(EGYPT_TZ).strftime('%I:%M %p')}")
            await admin.send(msg)
        except: pass

    if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    t = request.args.get('total')
    # كبسولة تتبع الطلب
    return render_template_string(f'''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
        <div style="border:3px solid #5865F2; padding:50px; border-radius:45px; display:inline-block; max-width:580px; background: rgba(88,101,242,0.01);">
            <h2 style="color:#43b581;">✅ تم تسجيل طلبك بنجاح</h2>
            <p>حول مبلغ <b>{t} جنيه</b> للرقم التالي: <h1>{PAYMENT_NUMBER}</h1></p>
            <div style="margin: 30px 0; border: 3px solid #5865F2; border-radius: 40px; padding: 15px 30px; background: rgba(88,101,242,0.05); display: inline-flex; align-items: center; justify-content: center; gap: 15px;">
                <span style="color: #f1c40f; font-weight: bold; font-size: 16px;">تنبيه: يمكنك تتبع حالة طلبك ومعرفة الأكواد من القائمة الجانبية (طلباتي).</span>
            </div>
            <br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none;">← العودة للمتجر</a>
        </div>
    </body>''')

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:50px 20px;">
        <div style="background:rgba(88,101,242,0.06); border:2px solid #5865F2; padding:30px; border-radius:30px; max-width:750px; margin:0 auto 50px auto;">
            <h3 style="color:#5865F2;">🔍 تتبع طلباتك</h3>
            <p style="color:#bbb;">هنا تظهر حالة طلباتك.. شكراً لاختيارك متجرنا.</p>
        </div>
        {% for o in orders %}
            <div style="background:#111; padding:30px; margin-bottom:20px; border-radius:25px; border: 1px solid #222; text-align:right;">
                <b>{{o.prod_name}}</b> | المبلغ: {{o.total}} ج.م
                <div style="height:12px; background:#333; border-radius:10px; margin:15px 0; overflow:hidden;">
                    <div style="width:{{ '100%' if 'approved' in o.status else '50%' }}; height:100%; transition: 1s; background:{{ '#2ecc71' if 'approved' in o.status else '#f1c40f' }};"></div>
                </div>
                <span>الحالة: <b>{{o.status}}</b></span>
                {% if 'approved' in o.status %}
                <button onclick="alert('أكوادك:\\n' + '{{ o.reserved_codes|join("\\n") }}')" style="background:#43b581; color:white; border:none; padding:10px 20px; border-radius:12px; float:left; font-weight:bold; cursor:pointer;">عرض الكود الاحتياطي</button>
                {% endif %}
            </div>
        {% endfor %}
        <br><a href="/" style="color:#5865F2; font-weight:bold;">← العودة</a>
    </body>''', orders=orders)

# --- لوحة التحكم وإدارة الأدمن ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin_panel')
    return '<body style="background:black; color:white; text-align:center; padding-top:100px"><form method="post"><input type="password" name="password" style="padding:10px;"><button>دخول</button></form></body>'

@app.route('/admin_panel', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'): return redirect('/admin_login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'gift':
            g_id, g_p, g_q = request.form.get('g_id'), request.form.get('g_p'), int(request.form.get('g_q', 1))
            codes = pull_codes(g_p, g_q)
            if codes:
                async def deliver():
                    try:
                        u = await client.fetch_user(int(g_id))
                        await u.send(f"🎁 **هدية من الإدارة! ({PRODUCTS[g_p]['name']})**\\n" + "\\n".join(codes))
                    except: pass
                asyncio.run_coroutine_threadsafe(deliver(), client.loop)
                flash("تم إرسال الهدية ✅")
        elif action == 'add_coupon':
            # منطق إضافة الكوبون (رجوع للميزتين المطلوبتين)
            db_config.insert({'type':'coupon', 'code':request.form.get('c'), 'discount':int(request.form.get('d')), 'uses':int(request.form.get('u')), 'prod_key':request.form.get('p'), 'expires_at':(datetime.now()+timedelta(minutes=60)).isoformat()})
            flash("تم إضافة الكود ✅")
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type':'maintenance', 'status':not curr}, Config.type=='maintenance')

    # جلب البيانات للعرض
    orders = db_orders.all()
    coupons = db_config.search(Config.type == 'coupon')
    stocks = {k: open(v['file']).read() if os.path.exists(v['file']) else "" for k,v in PRODUCTS.items()}
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; font-family:sans-serif; padding:20px;">
        <h1 style="text-align:center; color:#5865F2;">لوحة التحكم V20</h1>
        <div style="display:flex; gap:20px; flex-wrap:wrap; justify-content:center;">
            <div style="background:#111; padding:20px; border-radius:20px; border:1px solid #333; width:300px;">
                <h3>🎁 إرسال جيفت</h3>
                <form method="post"><input type="hidden" name="action" value="gift"><input name="g_id" placeholder="ID العميل"><select name="g_p">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input name="g_q" type="number" value="1"><button style="background:#8e44ad; color:white; border:none; padding:10px; width:100%; border-radius:10px; margin-top:10px;">إرسال الآن</button></form>
            </div>
            <div style="background:#111; padding:20px; border-radius:20px; border:1px solid #333; width:300px;">
                <h3>🎫 إدارة الكوبونات</h3>
                <form method="post"><input type="hidden" name="action" value="add_coupon"><input name="c" placeholder="الكود"><input name="d" placeholder="الخصم %" type="number"><input name="u" placeholder="العدد" type="number"><select name="p"><option value="all">الكل</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><button style="background:#2ecc71; color:white; border:none; padding:10px; width:100%; border-radius:10px; margin-top:10px;">إضافة كود</button></form>
            </div>
        </div>
        <br><div style="background:#111; padding:20px; border-radius:20px;"><h3>📦 سجل الطلبات</h3><table border="1" width="100%" style="text-align:center;"><tr><th>العميل</th><th>المنتج</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th></tr>{% for o in orders|reverse %}<tr><td>@{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.total}}</td><td>{{o.status}}</td><td>{% if o.status == 'pending' %}<a href="/approve/{{o.doc_id}}" style="color:green;">[قبول]</a> <a href="/reject/{{o.doc_id}}" style="color:red;">[رفض]</a>{% else %}-{% endif %}</td></tr>{% endfor %}</table></div>
    </body>
    ''', prods=PRODUCTS, orders=orders, coupons=coupons, stocks=stocks)

@app.route('/approve/<int:id>')
def approve(id):
    order = db_orders.get(doc_id=id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[id])
        async def deliver():
            u = await client.fetch_user(int(order['discord_id']))
            await u.send(f"🔥 **مبروك! تم تأكيد طلبك**\\n" + "\\n".join(order['reserved_codes']))
        asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_panel')

@app.route('/reject/<int:id>')
def reject(id):
    order = db_orders.get(doc_id=id)
    if order and order['status'] == 'pending':
        return_codes(order['prod_key'], order['reserved_codes'])
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[id])
    return redirect('/admin_panel')

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment')})
    return redirect('/')

def run_flask(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready():
    client.loop = asyncio.get_running_loop()
    print(f"✅ Bot Online: {client.user}")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    client.run(TOKEN)
