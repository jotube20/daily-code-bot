import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for, session, flash
from tinydb import TinyDB, Query
import threading
import os
import time
from datetime import datetime, timedelta

# --- الإعدادات الأساسية ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"
ADMIN_PASSWORD = "201184" 

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
app.secret_key = 'jo_store_ultimate_v8_super_pro_900_lines'

db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
db_config = TinyDB('config.json') 
Order = Query()
Config = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية (المخزون الذكي) ---

def get_stock(prod_key):
    """حساب الكمية المتوفرة في الملف"""
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
    """سحب وحجز الأكواد فور الطلب"""
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
    """إرجاع الأكواد للمخزن عند الرفض"""
    filename = PRODUCTS[p_key]['file']
    try:
        with open(filename, 'a') as f:
            for c in codes:
                f.write(c + "\n")
    except:
        pass

# --- دوال الخصم والصيانة ---

def is_maintenance_mode():
    """التحقق من حالة الصيانة"""
    res = db_config.get(Config.type == 'maintenance')
    if res:
        return res['status']
    return False

def get_discount(code, prod_key):
    """فحص صلاحية الكود"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res:
        if res['prod_key'] != 'all' and res['prod_key'] != prod_key:
            return None
        if res['uses'] <= 0:
            return None
        try:
            expire_time = datetime.fromisoformat(res['expires_at'])
            if datetime.now() > expire_time:
                return None
        except:
            return None
        return res
    return None

def use_coupon(code):
    """نقص استخدام الكود"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res and res['uses'] > 0:
        db_config.update({'uses': res['uses'] - 1}, doc_ids=[res.doc_id])

# --- واجهة المتجر الرئيسية (مفرودة CSS بالكامل) ---

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
            --card-bg: #fff;
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
            backdrop-filter: blur(12px);
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
            padding: 0;
            margin: 0;
        }
        
        .nav-btn:hover {
            color: var(--main-color);
            transform: scale(1.2);
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
            box-shadow: 4px 0 15px rgba(0,0,0,0.5);
        }
        
        .sidebar a {
            padding: 15px 25px;
            text-decoration: none;
            display: block;
            text-align: right;
            color: #888;
            font-size: 18px;
            transition: 0.3s;
            border-bottom: 1px solid rgba(128, 128, 128, 0.05);
        }
        
        .sidebar a:hover {
            color: var(--text-color);
            background: rgba(88, 101, 242, 0.1);
            padding-right: 35px;
        }
        
        .section-title {
            padding: 20px 25px;
            color: var(--main-color);
            font-weight: bold;
            font-size: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        #main-content {
            padding: 40px 20px;
            text-align: center;
        }
        
        .products-container {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 35px;
            margin-top: 60px;
            animation: fadeInUp 0.8s ease;
        }
        
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .product-card {
            width: 320px;
            height: 500px;
            border-radius: 30px;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid rgba(128, 128, 128, 0.1);
            background: var(--card-bg);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .product-card:hover {
            transform: translateY(-15px);
            border-color: var(--main-color);
            box-shadow: 0 15px 45px rgba(88, 101, 242, 0.2);
        }
        
        .card-image {
            position: absolute;
            inset: 0;
            background-size: cover;
            background-position: center;
            z-index: 1;
            transition: 0.8s;
        }
        
        .product-card:hover .card-image {
            transform: scale(1.1);
        }
        
        .card-overlay {
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.98) 0%, rgba(0,0,0,0.4) 40%, transparent 80%);
            z-index: 2;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: 30px;
        }
        
        .order-form {
            display: none;
            background: rgba(10, 10, 10, 0.95);
            padding: 20px;
            border-radius: 20px;
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
            padding: 12px;
            margin: 8px 0;
            border-radius: 10px;
            border: 1px solid #333;
            background: #1a1a1a;
            color: white;
            text-align: center;
            font-size: 14px;
            transition: 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: var(--main-color);
            background: #222;
        }
        
        .btn-confirm {
            background: var(--main-color);
            color: white;
            border: none;
            padding: 14px;
            border-radius: 12px;
            cursor: pointer;
            width: 100%;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
            transition: 0.3s;
        }
        
        .btn-confirm:hover {
            background: #4752c4;
            transform: translateY(-2px);
        }
        
        .feedback-item {
            background: var(--card-bg);
            margin: 15px 20px;
            padding: 15px;
            border-radius: 15px;
            font-size: 13px;
            border-right: 4px solid var(--main-color);
            text-align: right;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }
        
        .warning-text {
            color: #f1c40f;
            font-size: 11px;
            margin-bottom: 8px;
            font-weight: bold;
            line-height: 1.4;
        }
    </style>
</head>
<body id="body">
    <div class="glass-nav">
        <button class="nav-btn" onclick="toggleNav()">&#9776;</button>
        <div class="nav-divider"></div>
        <button class="nav-btn" onclick="toggleTheme()">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 طلباتي</a>
        <div class="section-title">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 0 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك" required style="width: 90%; background: #222; color: white; border: none; padding: 10px; border-radius: 10px; height: 60px;"></textarea>
            <button type="submit" class="btn-confirm" style="margin-top: 10px;">إرسال</button>
        </form>
        <div class="section-title">الآراء</div>
        {% for f in feedbacks %}
        <div class="feedback-item">
            <b>{{ f.name }}:</b> {{ f.comment }}
        </div>
        {% endfor %}
    </div>

    <div id="main-content" style="padding-top: 80px;">
        <h1>Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div style="color:#43b581; font-weight:bold; font-size:24px;">{{ info.price }} ج.م</div>
                    <div style="color:#ccc; font-size:13px; margin-bottom:10px;">المتوفر: {{ stocks[key] }}</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <div class="warning-text">⚠️ تأكد من بياناتك لضمان وصول الطلب.</div>
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <input type="text" name="coupon" placeholder="كود الخصم (Optional)">
                            <button type="submit" class="btn-confirm">تأكيد الشراء</button>
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
            if (side.style.width === "280px") {
                side.style.width = "0";
            } else {
                side.style.width = "280px";
            }
        }
        function toggleTheme() {
            document.body.classList.toggle("light-mode");
        }
        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }
        function checkOrders() { 
            let id = prompt("أدخل ID الديسكورد:"); 
            if(id) window.location.href="/my_orders/"+id; 
        }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;"><h1>🚧 الموقع في وضع الصيانة حالياً</h1></body>')
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key, qty = request.form.get('prod_key'), int(request.form.get('quantity', 1))
    d_id, cash_num = request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    cp_code = request.form.get('coupon', '').strip()

    # حجز الأكواد فوراً
    reserved = pull_codes(p_key, qty)
    if not reserved:
        return "المخزون نفذ!"
    
    total = qty * PRODUCTS[p_key]['price']
    discount_line = ""
    discount_val = 0
    
    if cp_code:
        cp = get_discount(cp_code, p_key)
        if cp:
            discount_val = cp['discount']
            total -= total * (discount_val / 100)
            use_coupon(cp_code)
            # تنسيق سطر الخصم ليتوافق مع الصورة
            discount_line = f"🎟️ **تم استخدام كود خصم: {discount_val}%**"

    db_orders.insert({
        'discord_id': d_id, 
        'prod_name': PRODUCTS[p_key]['name'], 
        'prod_key': p_key, 
        'total': total, 
        'status': 'pending', 
        'time': datetime.now().strftime("%I:%M %p"), 
        'codes': reserved, 
        'cash_number': cash_num, 
        'quantity': qty,
        'discount_line': discount_line,
        'discount_percent': discount_val
    })
    
    async def notify():
        try:
            if not client.is_ready(): return
            user = await client.fetch_user(int(d_id))
            await user.send(f"✅ **تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!**\n⌛ سيتم مراجعة الدفع وإرسال الأكواد لك فوراً.")
            
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            
            # بناء الرسالة بدقة لتطابق الصورة
            final_discount_txt = ""
            if discount_val > 0:
                final_discount_txt = f"\n🎟️ **تم استخدام كود خصم: {discount_val}%**"
            
            admin_msg = (
                f"🔔 **طلب جديد!**\n\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total} ج.م"
                f"{final_discount_txt}\n"
                f"📱 **من رقم:** {cash_num}\n"
                f"⏰ **الوقت:** {datetime.now().strftime('%I:%M %p')}"
            )
            await admin.send(admin_msg)
        except: pass

    if client.loop:
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
        
    return redirect(f'/success_page?total={total}')

# --- لوحة التحكم المتطورة V8 Pro ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin_jo_secret')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;">
        <form method="post">
            <h2>🔐 دخول الأدمن</h2>
            <input type="password" name="password" style="padding:10px; text-align:center;"><br><br>
            <button type="submit" style="padding:10px 30px; background:#5865F2; color:white; border:none; border-radius:10px;">دخول</button>
        </form>
    </body>''')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'):
        return redirect('/admin_login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        
        if action == 'add_coupon':
            c_code = request.form.get('c_code', '').strip()
            # منع تكرار الكود
            if db_config.get((Config.type == 'coupon') & (Config.code == c_code)):
                flash(f"فشل: الكود '{c_code}' موجود بالفعل!", 'error')
            else:
                minutes = int(request.form.get('c_minutes', 60))
                expire_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
                db_config.insert({
                    'type': 'coupon', 
                    'code': c_code, 
                    'discount': int(request.form.get('c_disc')), 
                    'uses': int(request.form.get('c_uses')), 
                    'prod_key': request.form.get('c_prod'), 
                    'expires_at': expire_at
                })
                flash(f"نجاح: تم إنشاء كود الخصم '{c_code}' بنجاح ✅", 'success')

        elif action == 'restock':
            new_codes = request.form.get('codes', '').strip()
            if new_codes:
                with open(PRODUCTS[p_key]['file'], 'a') as f:
                    f.write(new_codes + "\n")
                flash(f"نجاح: تمت إضافة المخزون ✅", 'success')
        
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
            flash("نجاح: تم تغيير حالة الصيانة ✅", 'success')

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    active_coupons = db_config.search(Config.type == 'coupon')
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k,v in PRODUCTS.items()}
    m_txt = "مفعل 🔴" if is_maintenance_mode() else "معطل 🟢"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <style>
            :root {
                --main: #5865F2;
                --success: #43b581;
                --danger: #f04747;
                --bg: #0a0a0a;
            }
            
            body {
                background: var(--bg);
                color: white;
                font-family: sans-serif;
                padding: 20px;
            }
            
            .card {
                background: #111;
                padding: 25px;
                border-radius: 20px;
                border: 1px solid #222;
                margin-bottom: 20px;
            }
            
            .grid {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
                justify-content: center;
            }
            
            input, select, textarea {
                width: 100%;
                padding: 12px;
                background: #000;
                color: white;
                border: 1px solid #333;
                margin-top: 10px;
                border-radius: 8px;
            }
            
            button {
                width: 100%;
                padding: 12px;
                margin-top: 10px;
                border-radius: 10px;
                border: none;
                color: white;
                font-weight: bold;
                cursor: pointer;
            }
            
            /* نظام الإشعارات المتطور */
            #toast-container {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
            }
            
            .toast {
                width: 320px;
                padding: 18px;
                border-radius: 12px;
                margin-bottom: 12px;
                position: relative;
                animation: slideIn 0.5s ease;
                overflow: hidden;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            }
            
            .toast-success { background: var(--success); }
            .toast-error { background: var(--danger); }
            
            .toast-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                height: 5px;
                background: rgba(255,255,255,0.8);
                width: 100%;
            }
            
            @keyframes slideIn {
                from { transform: translateX(100%); }
                to { transform: translateX(0); }
            }
            
            table {
                width: 100%;
                text-align: center;
                border-collapse: collapse;
                margin-top: 20px;
            }
            
            th {
                background: var(--main);
                padding: 18px;
            }
            
            td {
                padding: 15px;
                border-bottom: 1px solid #222;
                background: #111;
            }
            
            .btn-back {
                background: #333;
                color: white;
                padding: 12px 25px;
                border-radius: 12px;
                text-decoration: none;
                float: left;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div id="toast-container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="toast toast-{{ 'success' if category == 'success' else 'error' }}">
                            <div style="font-weight:bold;">{{ '✅ نجاح' if category == 'success' else '❌ خطأ' }}</div>
                            <div style="font-size:13px; margin-top:5px;">{{ message }}</div>
                            <div class="toast-progress" id="progress-{{ loop.index }}"></div>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>

        <a href="/" class="btn-back">🏠 العودة للمتجر</a>
        <h2 style="text-align:center; color:var(--main);">🛠️ لوحة التحكم الإحترافية V8</h2>
        
        <div class="grid">
            <div class="card" style="width:300px;">
                <h3>🛡️ الصيانة ({{m_txt}})</h3>
                <form method="post">
                    <input type="hidden" name="action" value="toggle_maintenance">
                    <button style="background:#f39c12;">تبديل الوضع الآن</button>
                </form>
            </div>

            <div class="card" style="width:350px;">
                <h3>🎫 الأكواد الفعالة حالياً</h3>
                <div style="max-height:220px; overflow-y:auto; font-size:11px;">
                    {% for c in active_coupons %}
                    <div style="background:#000; padding:10px; border-radius:10px; margin-bottom:8px; border:1px solid #333; border-left: 4px solid var(--success);">
                        <b style="color:var(--success);">{{ c.code }}</b> | خصم: {{ c.discount }}%<br>
                        باقي: {{ c.uses }} استخدام | منتج: {{ c.prod_key }}
                    </div>
                    {% endfor %}
                    {% if not active_coupons %}
                        <p style="text-align:center; color:#555;">لا توجد أكواد نشطة</p>
                    {% endif %}
                </div>
            </div>

            <div class="card" style="width:350px;">
                <h3>🎫 كود خصم جديد</h3>
                <form method="post">
                    <input type="hidden" name="action" value="add_coupon">
                    <input type="text" name="c_code" placeholder="الاسم" required>
                    <input type="number" name="c_disc" placeholder="الخصم %" required>
                    <input type="number" name="c_uses" placeholder="المرات" required>
                    <input type="number" name="c_minutes" placeholder="الدقائق" value="60">
                    <select name="c_prod">
                        <option value="all">كل المنتجات</option>
                        {% for k,v in prods.items() %}
                        <option value="{{k}}">{{v.name}}</option>
                        {% endfor %}
                    </select>
                    <button style="background:#27ae60;">تفعيل الكود</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h3>📝 المخزون المباشر</h3>
            <div class="grid">
                {% for k, content in stock.items() %}
                <div style="width:320px; background:#000; padding:15px; border-radius:15px;">
                    <h4 style="margin:0; color:#888;">{{prods[k].name}}</h4>
                    <form method="post">
                        <input type="hidden" name="action" value="edit_stock">
                        <input type="hidden" name="p_key" value="{{k}}">
                        <textarea name="full_content" style="height:100px;">{{content}}</textarea>
                        <button style="background:#2ecc71;">حفظ التعديلات</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="card">
            <h3>📦 سجل الطلبات</h3>
            <table>
                <thead>
                    <tr>
                        <th>العميل</th>
                        <th>المنتج</th>
                        <th>المبلغ</th>
                        <th>الإجراء</th>
                    </tr>
                </thead>
                <tbody>
                    {% for o in orders|reverse %}
                    <tr>
                        <td>@{{o.discord_id}}</td>
                        <td>{{o.prod_name}}</td>
                        <td>{{o.total}} ج.م</td>
                        <td>
                            {% if o.status == 'pending' %}
                                <a href="/approve/{{o.doc_id}}" style="color:var(--success); font-weight:bold; text-decoration:none;">[قبول]</a> | 
                                <a href="/reject/{{o.doc_id}}" style="color:var(--danger); font-weight:bold; text-decoration:none;">[رفض]</a>
                            {% else %}
                                {{o.status}}
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <script>
            // تحريك الخط الأبيض
            document.querySelectorAll('.toast').forEach((toast) => {
                let progress = toast.querySelector('.toast-progress');
                progress.style.width = '100%';
                setTimeout(() => { 
                    progress.style.width = '0%'; 
                    progress.style.transition = 'width 5s linear'; 
                }, 10);
                setTimeout(() => { 
                    toast.style.opacity = '0'; 
                    toast.style.transition = 'opacity 0.6s ease'; 
                    setTimeout(() => toast.remove(), 600); 
                }, 5000);
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
                user = await client.fetch_user(int(order['discord_id']))
                #
                msg = f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']})**\n\n**الأكواد:**\n" + "\n".join([f"🔗 {c}" for c in order['codes']])
                await user.send(msg)
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(deliver(), client.loop)
        flash(f"نجاح: تم قبول طلب @{order['discord_id']}!", 'success')
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        # إرجاع الأكواد
        return_codes(order['prod_key'], order.get('codes', []))
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify():
            try:
                u = await client.fetch_user(int(order['discord_id']))
                await u.send("❌ **نعتذر، تم رفض طلبك لعدم استلام مبلغ التحويل.**")
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
        flash(f"تم الرفض وإرجاع المخزن لـ {order['prod_name']}", 'error')
    return redirect('/admin_jo_secret')

# --- صفحات النجاح والطلبات ---

@app.route('/success_page')
def success_page():
    t = request.args.get('total')
    #
    return render_template_string('''<body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;"><div style="border:2px solid #5865F2; padding:40px; border-radius:30px; display:inline-block; max-width:550px;"><h2>تم تسجيل الطلب بنجاح! ✅</h2><p>حول مبلغ <b>{{total}} جنيه</b> للرقم: <h1>{{pay_num}}</h1><div style="background:rgba(88,101,242,0.1); padding:20px; border-radius:20px; border:1px solid #5865F2; margin:25px 0;">🔍 تتبع حالة طلبك من (صفحة الطلبات) وتأكد من دخول السيرفر وفتح الخاص.</div><a href="/" style="color:#5865F2; font-weight:bold;">← العودة للمتجر</a></div></body>''', total=t, pay_num=PAYMENT_NUMBER)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    #
    return render_template_string('''<body style="background:#0a0a0a;color:white;text-align:center;padding:40px 20px;"><h2>📋 طلباتك</h2>{% for o in orders %}<div style="background:#111; padding:25px; margin-bottom:20px; border-radius:20px; border: 1px solid #222; text-align:right;"><b>{{o.prod_name}}</b><div style="height:14px; background:#333; border-radius:10px; margin:20px 0; overflow:hidden;"><div style="width:{{ '100%' if o.status != 'pending' else '50%' }}; height:100%; transition: 0.8s; background:{{ '#2ecc71' if 'approved' in o.status else '#e74c3c' if 'rejected' in o.status else '#f1c40f' }};"></div></div>الحالة: <b>{{o.status}}</b></div>{% endfor %}<br><a href="/" style="color:#5865F2;">العودة</a></body>''', orders=orders)

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    ip = request.remote_addr
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment'), 'ip': ip})
    return redirect('/')

def run_flask(): 
    app.run(host='0.0.0.0', port=10000)

@client.event
async def on_ready():
    client.loop = asyncio.get_running_loop()
    print(f"✅ Bot is ready as: {client.user}")

if __name__ == '__main__':
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    if TOKEN:
        try: client.run(TOKEN)
        except Exception as e:
            print(f"❌ Error: {e}")
            while True: time.sleep(1000)
