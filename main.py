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

# توقيت القاهرة لضبط الرسائل
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
app.secret_key = 'jo_store_v21_fully_expanded_code'

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
    if not os.path.exists(filename):
        return 0
    try:
        with open(filename, 'r') as f:
            lines = [l for l in f.readlines() if l.strip()]
        return len(lines)
    except:
        return 0

def pull_codes(p_key, qty):
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
    filename = PRODUCTS[p_key]['file']
    try:
        with open(filename, 'a') as f:
            for c in codes:
                f.write(c + "\n")
    except:
        pass

def is_maintenance_mode():
    res = db_config.get(Config.type == 'maintenance')
    if res:
        return res['status']
    return False

def get_discount(code, prod_key):
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

# --- واجهة المتجر الرئيسية (فرد كامل للـ CSS والـ HTML) ---

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
        
        body {
            background: var(--bg-color);
            color: var(--text-color);
            font-family: sans-serif;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
            transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
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
            background: rgba(10, 10, 10, 0.98);
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
        
        /* --- Countdown Popup Styling --- */
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

        /* --- Advanced Tutorial Spotlight Styling --- */
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
    </style>
</head>
<body id="body">

    <div id="wait-overlay">
        <div class="timer-box" id="timer-val">60</div>
        <h3 style="font-size: 24px;">انتظر من فضلك.. ⌛</h3>
        <p style="color: #888; text-align:center;">لمنع السبام، يرجى الانتظار دقيقة واحدة بين كل محاولة شراء.</p>
        <button class="btn-ok" id="ok-btn" style="display: none;" onclick="document.getElementById('wait-overlay').style.display='none'">OK</button>
    </div>

    <div id="welcome-popup" class="modal-base">
        <div class="modal-content">
            <h2 style="color: var(--main-color); font-size: 28px;">مرحباً بك في Jo Store! 🌟</h2>
            <p style="color: #aaa; line-height: 1.6;">هل أنت جديد في الموقع وتحتاج لدليل إرشادي سريع لمعرفة كيفية الطلب؟</p>
            <br>
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
        <a href="#" id="orders-btn" onclick="checkOrders()">📋 تتبع طلباتي</a>
        <div class="section-title">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 0 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك..." required style="width: 90%; background: #1a1a1a; color: white; border: 1px solid #333; padding: 12px; border-radius: 15px; height: 80px; margin-top: 10px; resize: none;"></textarea>
            <button type="submit" class="btn-purchase" style="padding: 10px;">إرسال التقييم</button>
        </form>
    </div>

    <div id="main-content">
        <h1 id="main-header">Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container" id="products-list">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div style="color:#43b581; font-weight:bold; font-size:32px;">{{ info.price }} ج.م</div>
                    <div style="color:#aaa; font-size:14px; margin-bottom:15px;">المتوفر: {{ stocks[key] }} قطعة</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post" onsubmit="return checkWait()">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                            <input type="text" name="discord_id" placeholder="معرف الديسكورد (ID)" required>
                            <input type="text" name="cash_number" placeholder="رقم المحفظة (فون كاش)" required>
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
        
        function toggleTheme() { document.body.classList.toggle("light-mode"); }
        
        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }

        function checkOrders() { 
            let id = prompt("أدخل معرف (ID) الديسكورد الخاص بك:"); 
            if(id) window.location.href="/my_orders/"+id; 
        }

        // --- Countdown Logic ---
        function checkWait() {
            let last = localStorage.getItem('last_order');
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
            localStorage.setItem('last_order', now);
            return true;
        }

        // --- Spotlight Tutorial Logic ---
        window.onload = function() {
            if(!localStorage.getItem('tut_v21_done')) {
                document.getElementById('welcome-popup').style.display = 'flex';
            }
        };

        function closeWelcome() {
            document.getElementById('welcome-popup').style.display = 'none';
            localStorage.setItem('tut_v21_done', 'true');
        }

        let tutStep = 0;
        function startTutorial() {
            document.getElementById('welcome-popup').style.display = 'none';
            document.getElementById('tut-overlay').style.display = 'block';
            nextStep();
        }

        function nextStep() {
            tutStep++;
            const spotlight = document.getElementById('spotlight');
            const tooltip = document.getElementById('tut-tooltip');
            const text = document.getElementById('tut-text');

            if (tutStep === 1) {
                const el = document.getElementById('products-list');
                const rect = el.getBoundingClientRect();
                updateSpot(rect, "هنا تظهر جميع المنتجات. اضغط على أي منتج لكتابة بياناتك وإتمام الشراء.");
            } else if (tutStep === 2) {
                const el = document.querySelector('.glass-nav');
                const rect = el.getBoundingClientRect();
                updateSpot(rect, "من هنا يمكنك فتح القائمة للوصول إلى صفحة تتبع طلباتك والأكواد السابقة.");
            } else {
                document.getElementById('tut-overlay').style.display = 'none';
                closeWelcome();
            }
        }

        function updateSpot(rect, desc) {
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

# --- الروابط ومعالجة البيانات (Routes) ---

@app.route('/')
def home():
    """الصفحة الرئيسية وفحص الصيانة"""
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('''
        <body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;font-family:sans-serif;">
            <div style="border:1px solid #f1c40f; display:inline-block; padding:60px; border-radius:45px; background:rgba(241,196,15,0.03);">
                <h1>🚧 الموقع تحت الصيانة حالياً</h1>
                <p style="color:#888;">نقوم بتحديث المخزون وإضافة ميزات جديدة مذهلة.<br>نعتذر عن الإزعاج، نعود قريباً.</p>
                <br><a href="/admin_login" style="color:#222; text-decoration:none; font-size:10px;">Portal</a>
            </div>
        </body>''')
        
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    """معالجة الطلب وحجز المخزون فوراً"""
    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon_code = request.form.get('coupon', '').strip()

    # حجز الأكواد فوراً من الكمية
    reserved_list = pull_codes(p_key, qty)
    if not reserved_list:
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;"><h1>❌ عذراً، الكمية المطلوبة غير متوفرة حالياً!</h1><a href="/" style="color:#5865F2;">العودة</a></body>')
    
    total = qty * PRODUCTS[p_key]['price']
    discount_txt = ""
    if coupon_code:
        cp_data = get_discount(coupon_code, p_key)
        if cp_data:
            total -= total * (cp_data['discount'] / 100)
            use_coupon(coupon_code)
            discount_txt = f"\n🎟️ **تم استخدام كود خصم: {cp_data['discount']}%**"

    # حفظ الطلب
    db_orders.insert({
        'discord_id': d_id, 
        'prod_name': PRODUCTS[p_key]['name'], 
        'prod_key': p_key, 
        'total': total, 
        'status': 'pending', 
        'time': datetime.now(EGYPT_TZ).strftime("%I:%M %p"), 
        'reserved_codes': reserved_list, 
        'cash_number': cash_num, 
        'quantity': qty,
        'discount_applied': discount_txt
    })
    
    async def notify_order():
        """إرسال إشعارات الديسكورد المنظمة فوق بعضها"""
        try:
            if not client.is_ready(): return
            user = await client.fetch_user(int(d_id))
            await user.send(f"✅ **تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!**\n⌛ سيتم مراجعة الدفع وإرسال الأكواد لك فوراً.")
            
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # رسالة البوت الاحترافية مصححة
            msg_content = (
                f"🔔 **طلب جديد!**\n\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total} ج.م"
                f"{discount_txt}\n"
                f"📱 **من رقم:** {cash_num}\n"
                f"⏰ **الوقت:** {datetime.now(EGYPT_TZ).strftime('%I:%M %p')}"
            )
            await admin.send(msg_content)
        except: pass

    if client.loop: asyncio.run_coroutine_threadsafe(notify_order(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    """صفحة النجاح مع كبسولة التتبع الاحترافية"""
    total_val = request.args.get('total')
    return render_template_string(f'''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
        <div style="border:3px solid #5865F2; padding:50px; border-radius:45px; display:inline-block; max-width:580px; background: rgba(88,101,242,0.01);">
            <h2 style="color:#43b581; font-size:36px;">✅ تم تسجيل الطلب بنجاح</h2>
            <p style="font-size:20px;">حول مبلغ <b>{total_val} جنيه</b> للرقم التالي:</p>
            <h1 style="background:#222; padding:30px; border-radius:25px; border:1px solid #333; font-size:46px; letter-spacing:4px;">{PAYMENT_NUMBER}</h1>
            
            <div style="margin: 40px 0; border: 3px solid #5865F2; border-radius: 40px; padding: 15px 30px; background: rgba(88,101,242,0.05); display: inline-flex; align-items: center; justify-content: center; gap: 15px;">
                <div style="background: #f1c40f; height: 6px; width: 60px; border-radius: 10px;"></div>
                <span style="color: #f1c40f; font-weight: bold; font-size: 16px;">تنبيه: يمكنك تتبع حالة طلبك ومعرفة الأكواد من القائمة الجانبية (تتبع طلباتي).</span>
                <div style="background: #f1c40f; height: 6px; width: 60px; border-radius: 10px;"></div>
            </div>

            <div style="background:rgba(255,204,0,0.1); padding:25px; border-radius:25px; border:1px solid #ffcc00; text-align:right; margin: 20px 0; line-height:1.8;">
                <b style="color:#ffcc00; font-size:18px;">⚠️ ملحوظة هامة جداً:</b><br>
                يجب الانضمام لسيرفرنا بالضغط <a href="https://discord.gg/RYK28PNv" style="color:#5865F2; font-weight:bold; text-decoration:none;">[ هـنـا ]</a> وتأكد أن الخاص مفتوح وإلا لن يصلك الكود.
            </div>
            <br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none; font-size:20px;">← العودة للمتجر الرئيسي</a>
        </div>
    </body>''')

@app.route('/my_orders/<uid>')
def my_orders(uid):
    """تتبع حالة الطلبات مع رأس الصفحة المطلوب"""
    orders_list = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:50px 20px;">
        <div style="background:rgba(88,101,242,0.06); border:2px solid #5865F2; padding:30px; border-radius:30px; max-width:750px; margin:0 auto 50px auto; line-height:1.8;">
            <h3 style="color:#5865F2; margin-top:0; font-size:24px;">🔍 تتبع ومعالجة طلباتك</h3>
            <p style="color:#bbb; font-size:16px;">هنا يمكنك معرفة أين وصل طلبك حالياً.. كما يسعدنا جداً أن نسمع رأيك في الخدمة من خلال <b>(أضف تقييمك)</b> في القائمة الجانبية.</p>
        </div>
        {% for o in orders %}
            <div style="background:#111; padding:35px; margin-bottom:25px; border-radius:30px; border: 1px solid #222; text-align:right; box-shadow:0 10px 30px rgba(0,0,0,0.4);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:22px;">{{o.prod_name}} ({{o.quantity}} قطعة)</b>
                    <span style="color:#43b581; font-weight:bold; font-size:20px;">{{o.total}} ج.م</span>
                </div>
                <div style="height:16px; background:#333; border-radius:10px; margin:20px 0; overflow:hidden; border: 1px solid #444;">
                    <div style="width:{{ '100%' if 'approved' in o.status else '50%' }}; height:100%; transition: 1s ease; 
                                background:{{ '#2ecc71' if 'approved' in o.status else '#e74c3c' if 'rejected' in o.status else '#f1c40f' }};">
                    </div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span>الحالة الحالية: <b>{{o.status}}</b></span>
                    {% if 'approved' in o.status %}
                    <button onclick="alert('أكوادك المشتراة لهذا الطلب:\\n' + '{{ o.reserved_codes|join("\\\n") }}')" 
                            style="background:#43b581; color:white; border:none; padding:12px 25px; border-radius:15px; font-weight:bold; cursor:pointer;">
                        📦 عرض الكود الاحتياطي
                    </button>
                    {% endif %}
                </div>
            </div>
        {% endfor %}
        <br><br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none; font-size:18px;">← العودة للمتجر الرئيسي</a>
    </body>''', orders=orders_list)

# --- لوحة التحكم V21 (كاملة الميزات) ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin_jo_secret')
    return render_template_string('<body style="background:black; color:white; text-align:center; padding-top:120px;"><form method="post"><h2>🔐 Admin Access</h2><input type="password" name="password" style="padding:15px; border-radius:15px; text-align:center;" autofocus><br><br><button type="submit" style="padding:15px 50px; background:#5865F2; color:white; border-radius:15px; border:none; font-weight:bold; cursor:pointer;">دخول</button></form></body>')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'): return redirect('/admin_login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        if action == 'add_coupon':
            exp = (datetime.now(EGYPT_TZ).replace(tzinfo=None) + timedelta(minutes=60)).isoformat()
            db_config.insert({'type':'coupon', 'code':request.form.get('c'), 'discount':int(request.form.get('d')), 'uses':int(request.form.get('u')), 'prod_key':request.form.get('p'), 'expires_at':exp})
            flash("تم تفعيل كود الخصم الجديد ✅")
        elif action == 'edit_stock':
            content = request.form.get('full_content', '').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f: f.write(content + "\n" if content else "")
            flash("تم تحديث ملف المخزن ✅")
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
            flash("تم تغيير حالة وضع الصيانة ✅")
        elif action == 'gift':
            g_id, g_p, g_q = request.form.get('g_id'), request.form.get('g_prod'), int(request.form.get('g_qty', 1))
            gift_codes = pull_codes(g_p, g_q)
            if gift_codes:
                async def deliver_gift():
                    try:
                        u = await client.fetch_user(int(g_id))
                        await u.send(f"🎁 **مبروك! لقد استلمت هدية من الإدارة! ({PRODUCTS[g_p]['name']})**\\n" + "\\n".join([f"🔗 {c}" for c in gift_codes]))
                    except: pass
                if client.loop: asyncio.run_coroutine_threadsafe(deliver_gift(), client.loop)
                flash(f"تم إرسال الهدية لـ {g_id} بنجاح ✅")

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    active_coupons = db_config.search(Config.type == 'coupon')
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k, v in PRODUCTS.items()}
    m_txt = "مفعل 🔴" if is_maintenance_mode() else "معطل 🟢"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl"><head><meta charset="UTF-8">
    <style>
        :root { --main: #5865F2; --bg: #0a0a0a; }
        body { background: var(--bg); color: white; font-family: sans-serif; padding: 40px; }
        .card { background:#111; padding:30px; border-radius:30px; border:1px solid #222; margin-bottom:30px; box-shadow:0 0 20px rgba(0,0,0,0.5); }
        .grid { display: flex; gap: 30px; flex-wrap: wrap; justify-content: center; }
        input, select, textarea { width:100%; padding:15px; background:#000; color:white; border:1px solid #333; margin-top:10px; border-radius:12px; }
        button { width:100%; padding:15px; margin-top:10px; border-radius:12px; border:none; color:white; font-weight:bold; cursor:pointer; }
        table { width:100%; text-align:center; border-collapse:collapse; margin-top:20px; border-radius: 20px; overflow: hidden; }
        th { background:var(--main); padding:20px; } td { padding:15px; border-bottom:1px solid #222; background: #111; }
    </style>
    </head><body>
        <center><h1>🛠️ لوحة التحكم الإحترافية V21</h1><a href="/" style="color:#888; text-decoration:none;">العودة للمتجر الرئيسي</a></center><br>
        <div class="grid">
            <div class="card" style="width:320px;"><h3>🛡️ الصيانة ({{m_txt}})</h3><form method="post"><input type="hidden" name="action" value="toggle_maintenance"><button style="background:#f39c12;">تبديل وضع الصيانة</button></form></div>
            <div class="card" style="width:320px;"><h3>🎁 إرسال هدية (جيفت)</h3><form method="post"><input type="hidden" name="action" value="gift"><input name="g_id" placeholder="ID العميل"><select name="g_prod">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input type="number" name="g_qty" value="1"><button style="background:#8e44ad;">إرسال خاص</button></form></div>
            <div class="card" style="width:400px;"><h3>🎫 إدارة الكوبونات النشطة</h3><div style="max-height:200px; overflow-y:auto;">{% for c in active_coupons %}<div><b>{{ c.code }}</b> | {{ c.discount }}%</div>{% endfor %}</div><br><form method="post"><input type="hidden" name="action" value="add_coupon"><input name="c" placeholder="اسم الكود"><input name="d" placeholder="الخصم %" type="number"><input name="u" placeholder="العدد" type="number"><select name="p"><option value="all">الكل</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><button style="background:#27ae60;">تفعيل</button></form></div>
        </div>
        <div class="card"><h3>📝 تعديل المخزن المباشر</h3><div class="grid">{% for k, content in stock.items() %}<div style="width:340px; background:#000; padding:25px; border-radius:25px; border:1px solid #222;"><h4>{{prods[k].name}}</h4><form method="post"><input type="hidden" name="action" value="edit_stock"><input type="hidden" name="p_key" value="{{k}}"><textarea name="full_content" style="height:140px; color:#43b581;">{{content}}</textarea><button style="background:#2ecc71;">حفظ</button></form></div>{% endfor %}</div></div>
        <div class="card" style="overflow-x:auto;"><h3>📦 سجل الطلبات الأخيرة</h3><table><thead><tr><th>العميل (ID)</th><th>المنتج</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th></tr></thead><tbody>{% for o in orders|reverse %}<tr><td>@{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.total}} ج.م</td><td>{{o.status}}</td><td>{% if o.status == 'pending' %}<a href="/approve/{{o.doc_id}}" style="color:var(--main); font-weight:bold; text-decoration:none;">[ قبول ]</a> | <a href="/reject/{{o.doc_id}}" style="color:red; font-weight:bold; text-decoration:none;">[ رفض ]</a>{% else %}-{% endif %}</td></tr>{% endfor %}</tbody></table></div>
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
                msg = f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']}) بنجاح**\\n" + "\\n".join([f"🔗 {c}" for c in order['reserved_codes']])
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
    print(f"✅ Bot is now ONLINE! Logged in as: {client.user}")

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    if TOKEN:
        try: client.run(TOKEN)
        except: time.sleep(1000)
