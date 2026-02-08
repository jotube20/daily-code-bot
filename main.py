import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for, session
from tinydb import TinyDB, Query
import threading
import os
import time
from datetime import datetime, timedelta

# --- الإعدادات الأساسية ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"
ADMIN_PASSWORD = "201184"  # كلمة سر لوحة التحكم

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
app.secret_key = 'jo_store_ultimate_final_secure_v4'  # مفتاح الجلسة

db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
db_config = TinyDB('config.json')  # لحفظ إعدادات الصيانة وكوبونات الخصم
Order = Query()
Config = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية (المخزون الذكي) ---

def get_stock(prod_key):
    """حساب الكمية المتوفرة في الملف حالياً"""
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
    """يسحب الأكواد من الملف فوراً لحجزها في الطلب"""
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
    """يعيد الأكواد للمخزون في حالة الرفض"""
    filename = PRODUCTS[p_key]['file']
    try:
        with open(filename, 'a') as f:
            for c in codes:
                f.write(c + "\n")
    except:
        pass

# --- دوال الإضافات الجديدة ---

def is_maintenance_mode():
    """التحقق من حالة الصيانة"""
    res = db_config.get(Config.type == 'maintenance')
    if res:
        return res['status']
    return False

def get_discount(code, prod_key):
    """التحقق من كود الخصم: الصلاحية، الموقت، والمنتج المحدد"""
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
    """نقص عدد مرات استخدام الكود بعد التطبيق الناجح"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res and res['uses'] > 0:
        db_config.update({'uses': res['uses'] - 1}, doc_ids=[res.doc_id])

# --- واجهة المتجر الرئيسية ---

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
            --bg-color: #f0f0f0;
            --text-color: #333;
            --card-bg: #fff;
            --sidebar-bg: #fff;
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
        
        /* كبسولة التحكم الزجاجية الاحترافية */
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
            background-color: var(--sidebar-bg);
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
            margin-bottom: 10px;
            font-weight: bold;
            line-height: 1.5;
        }
        
        .stock-badge {
            font-size: 13px;
            color: #aaa;
            margin-bottom: 5px;
        }
        
        .price-tag {
            color: #43b581;
            font-weight: bold;
            font-size: 26px;
            margin: 5px 0;
        }
    </style>
</head>
<body id="body">
    <div class="glass-nav">
        <button class="nav-btn" onclick="toggleNav()" title="القائمة الرئيسية">&#9776;</button>
        <div class="nav-divider"></div>
        <button class="nav-btn" onclick="toggleTheme()" title="تغيير مظهر المتجر">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 العودة للرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 تتبع طلباتي</a>
        
        <div class="section-title">أضف تقييمك</div>
        <form action="/add_feedback" method="post" style="padding: 0 20px;">
            <input type="text" name="user_name" placeholder="اسمك المستعار" required>
            <textarea name="comment" placeholder="اكتب رأيك هنا بكل صراحة..." required style="width:90%; padding:10px; background:#1a1a1a; color:white; border:1px solid #333; border-radius:10px; height:80px; margin-top:10px;"></textarea>
            <button type="submit" style="background:var(--main-color); color:white; border:none; padding:10px; width:100%; border-radius:10px; margin-top:10px; cursor:pointer; font-weight:bold;">إرسال التقييم</button>
        </form>
        
        <div class="section-title">آراء العملاء</div>
        {% for f in feedbacks %}
        <div class="feedback-item">
            <b style="color:var(--main-color);">{{ f.name }}:</b><br>
            <span style="color:#ccc;">{{ f.comment }}</span>
        </div>
        {% endfor %}
    </div>

    <div id="main-content">
        <h1 style="font-size: 36px; margin-bottom: 10px;">Jo Store | متجرك المفضل 🔒</h1>
        <p style="color:#888;">أفضل الخدمات بأقل الأسعار وضمان كامل</p>
        
        <div class="products-container">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3 style="font-size: 22px; margin-bottom: 5px;">{{ info.name }}</h3>
                    <div class="price-tag">{{ info.price }} ج.م</div>
                    <div class="stock-badge">المتوفر حالياً: {{ stocks[key] }} قطعة</div>
                    
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <div class="warning-text">⚠️ تنبيه: يرجى كتابة بياناتك بدقة لضمان وصول طلبك.</div>
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <input type="text" name="coupon" placeholder="كود خصم؟ (اختياري)" style="border: 1px dashed #43b581;">
                            <button type="submit" class="btn-confirm">تأكيد عملية الشراء</button>
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
            if (side.style.width === "280px") { side.style.width = "0"; } 
            else { side.style.width = "280px"; }
        }
        function toggleTheme() {
            document.body.classList.toggle("light-mode");
        }
        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }
        function checkOrders() { 
            let id = prompt("يرجى إدخال معرف (ID) الديسكورد الخاص بك:"); 
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
        return render_template_string('''
        <body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;font-family:sans-serif;">
            <div style="border:1px solid #f1c40f; padding:40px; border-radius:30px;">
                <h1>🚧 الموقع في وضع الصيانة</h1>
                <p>نحن نقوم بتحديث المخزون وإضافة ميزات جديدة.. عد لاحقاً!</p>
                <a href="/admin_login" style="color:#5865F2;">Admin Login</a>
            </div>
        </body>''')
        
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    if is_maintenance_mode() and not session.get('logged_in'):
        return "الموقع في وضع الصيانة"
        
    p_key, qty = request.form.get('prod_key'), int(request.form.get('quantity', 1))
    d_id, cash_num = request.form.get('discord_id').strip(), request.form.get('cash_number').strip()
    coupon_code = request.form.get('coupon', '').strip()

    reserved = pull_codes(p_key, qty)
    if not reserved:
        return "المخزون غير كافٍ!"
    
    total_price = qty * PRODUCTS[p_key]['price']
    discount_applied_text = ""
    
    if coupon_code:
        coupon = get_discount(coupon_code, p_key)
        if coupon:
            total_price -= total_price * (coupon['discount'] / 100)
            use_coupon(coupon_code)
            discount_applied_text = f"\n🎟️ **تم استخدام كود خصم: {coupon['discount']}%**"

    db_orders.insert({
        'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 
        'quantity': qty, 'cash_number': cash_num, 'total': total_price, 
        'status': 'pending', 'time': datetime.now().strftime("%I:%M %p"),
        'reserved_codes': reserved 
    })
    
    async def notify_all():
        try:
            if not client.is_ready(): return
            user = await client.fetch_user(int(d_id))
            # رسالة العميل منظمة
            await user.send(f"✅ **تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!**\n⌛ سيتم مراجعة الدفع فوراً.")
            
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # رسالة الإدارة منظمة
            admin_msg = (
                f"🔔 **طلب جديد!**\n\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total_price} ج.م{discount_applied_text}\n"
                f"📱 **من رقم:** {cash_num}\n"
                f"⏰ **الوقت:** {datetime.now().strftime('%I:%M %p')}"
            )
            await admin.send(admin_msg)
        except: pass

    if client.loop: asyncio.run_coroutine_threadsafe(notify_all(), client.loop)
    return redirect(f'/success_page?total={total_price}')

@app.route('/success_page')
def success_page():
    """صفحة النجاح مع الملحوظات"""
    total = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:2px solid #5865F2; padding:40px; border-radius:30px; display:inline-block; max-width:550px;">
            <h2 style="color:#43b581;">تم تسجيل طلبك بنجاح! ✅</h2>
            <p>حول مبلغ <b>{{total}} جنيه</b> للرقم:</p>
            <h1 style="background:#222; padding:20px; border-radius:15px;">{{pay_num}}</h1>
            
            <div style="background:rgba(88,101,242,0.1); padding:20px; border-radius:20px; border:1px solid #5865F2; margin:25px 0;">
                🔍 تتبع حالة طلبك من <b>(صفحة الطلبات)</b>.<br>
                ✍️ نتشرف بكتابة رأيك من <b>(قسم الآراء)</b>.
            </div>

            <div style="background:rgba(255,204,0,0.1); padding:20px; border-radius:20px; border:1px solid #ffcc00; text-align:right;">
                <b style="color:#ffcc00;">⚠️ ملحوظة هامة:</b><br>
                يجب دخول سيرفرنا <a href="https://discord.gg/RYK28PNv" style="color: #5865F2;">هنا</a> 
                وتأكد أن الخاص مفتوح وإلا لن يصلك الكود.
            </div>
            <br><a href="/" style="color:#5865F2; font-weight:bold;">← العودة للمتجر</a>
        </div>
    </body>''', total=total, pay_num=PAYMENT_NUMBER)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    """تتبع الطلبات مع Progress Bar"""
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:40px 20px; font-family: sans-serif;">
        <h2 style="color:#5865F2;">📋 تتبع طلباتك</h2>
        <div style="max-width:700px; margin:auto;">
        {% for o in orders %}
            <div style="background:#111; padding:25px; margin-bottom:20px; border-radius:20px; border: 1px solid #222; text-align:right;">
                <b>{{o.prod_name}} ({{o.total}} ج.م)</b>
                <div style="height:14px; background:#333; border-radius:10px; margin:20px 0; overflow:hidden;">
                    <div style="width:{% if 'approved' in o.status %}100%{% elif 'rejected' in o.status %}100%{% else %}50%{% endif %}; 
                                height:100%; transition: 0.8s; background:{% if 'approved' in o.status %}#2ecc71{% elif 'rejected' in o.status %}#e74c3c{% else %}#f1c40f{% endif %};">
                    </div>
                </div>
                الحالة: <b>{{o.status}}</b>
            </div>
        {% endfor %}
        </div><br><a href="/" style="color:#5865F2;">← العودة للمتجر</a>
    </body>''', orders=orders)

# --- لوحة التحكم المتطورة (V4 Pro) ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """تسجيل دخول الأدمن"""
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin_jo_secret')
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; text-align:center; padding-top:120px;">
        <form method="post">
            <h2>🔐 Admin Portal</h2>
            <input type="password" name="password" style="padding:15px; width:250px; border-radius:15px; text-align:center;" autofocus>
            <br><br><button type="submit" style="padding:15px 40px; background:#5865F2; color:white; border-radius:15px;">دخول</button>
        </form>
    </body>''')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    """لوحة التحكم"""
    if not session.get('logged_in'): return redirect('/admin_login')

    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        if action == 'restock':
            new_codes = request.form.get('codes', '').strip()
            if new_codes:
                with open(PRODUCTS[p_key]['file'], 'a') as f: f.write(new_codes + "\n")
        elif action == 'edit_stock':
            content = request.form.get('full_content', '').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f: f.write(content + "\n" if content else "")
        elif action == 'clear_logs':
            u_id = request.form.get('u_id', '').strip()
            if u_id: db_orders.remove(Order.discord_id == u_id)
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
        elif action == 'add_coupon':
            c_code, c_disc, c_uses, c_prod, c_min = request.form.get('c_code'), int(request.form.get('c_discount')), int(request.form.get('c_uses')), request.form.get('c_prod'), int(request.form.get('c_minutes'))
            expire_time = (datetime.now() + timedelta(minutes=c_min)).isoformat()
            db_config.insert({'type': 'coupon', 'code': c_code, 'discount': c_disc, 'uses': c_uses, 'prod_key': c_prod, 'expires_at': expire_time})
        elif action == 'send_gift':
            g_id, g_prod, g_qty = request.form.get('g_id'), request.form.get('g_prod'), int(request.form.get('g_qty', 1))
            gift_codes = pull_codes(g_prod, g_qty)
            if gift_codes:
                async def deliver_gift():
                    try:
                        u = await client.fetch_user(int(g_id))
                        await u.send(f"🎊 **هدية من الإدارة! ({PRODUCTS[g_prod]['name']})**\n" + "\n".join([f"🔗 {c}" for c in gift_codes]))
                    except: pass
                if client.loop: asyncio.run_coroutine_threadsafe(deliver_gift(), client.loop)

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k, v in PRODUCTS.items()}
    m_status = "نشط ومفعل 🔴" if is_maintenance_mode() else "معطل حالياً 🟢"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><style>
    body { background:#0a0a0a; color:white; font-family:sans-serif; padding:30px; }
    .card { background:#111; border-radius:20px; border:1px solid #222; padding:25px; margin-bottom:20px; }
    .grid { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
    input, select, textarea { width:100%; padding:12px; background:#000; color:white; border:1px solid #333; margin-top:10px; border-radius:10px; }
    button { width:100%; padding:12px; margin-top:10px; border-radius:10px; border:none; color:white; font-weight:bold; cursor:pointer; }
    table { width:100%; text-align:center; border-collapse:collapse; margin-top:20px; }
    th { background:#5865F2; padding:18px; } td { padding:15px; border-bottom:1px solid #222; }
    .btn-back { position:absolute; top:20px; left:20px; background:#333; padding:10px 20px; border-radius:10px; text-decoration:none; color:white; }
    </style></head><body>
    <a href="/" class="btn-back">🏠 المتجر</a>
    <h2 style="text-align:center; color:#5865F2;">🛠️ لوحة التحكم الإحترافية</h2>
    <div class="grid">
        <div class="card" style="width:300px;"><h3>🛡️ الصيانة ({{m_status}})</h3><form method="post"><input type="hidden" name="action" value="toggle_maintenance"><button style="background:#f39c12;">تبديل الوضع</button></form></div>
        <div class="card" style="width:300px;"><h3>🎁 إرسال هدية</h3><form method="post"><input type="hidden" name="action" value="send_gift"><input type="text" name="g_id" placeholder="ID"><select name="g_prod">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input type="number" name="g_qty" value="1"><button style="background:#8e44ad;">إرسال</button></form></div>
        <div class="card" style="width:300px;"><h3>🎫 كود خصم</h3><form method="post"><input type="hidden" name="action" value="add_coupon"><input type="text" name="c_code" placeholder="الكود"><input type="number" name="c_discount" placeholder="%"><input type="number" name="c_uses" placeholder="مرات"><input type="number" name="c_minutes" placeholder="الدقائق"><select name="c_prod"><option value="all">الكل</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><button style="background:#27ae60;">تفعيل</button></form></div>
    </div>
    <div class="card"><h3>📝 المخزون المباشر</h3><div class="grid">{% for k, content in stock.items() %}<div style="width:300px;"><h4>{{prods[k].name}}</h4><form method="post"><input type="hidden" name="action" value="edit_stock"><input type="hidden" name="p_key" value="{{k}}"><textarea name="full_content" style="height:100px;">{{content}}</textarea><button style="background:#2ecc71;">حفظ</button></form></div>{% endfor %}</div></div>
    <div class="card"><h3>📦 سجل الطلبات</h3><table><thead><tr><th>العميل</th><th>المنتج</th><th>المبلغ</th><th>الإجراء</th></tr></thead><tbody>{% for o in orders|reverse %}<tr><td>@{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.total}} ج.م</td><td>{% if o.status == 'pending' %}<a href="/approve/{{o.doc_id}}" style="color:green;text-decoration:none;">Approve</a> | <a href="/reject/{{o.doc_id}}" style="color:red;text-decoration:none;">Decline</a>{% else %}{{o.status}}{% endif %}</td></tr>{% endfor %}</tbody></table></div>
    </body></html>
    ''', orders=orders, stock=stock_contents, prods=PRODUCTS, m_status=m_status)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                # رسالة الأكواد منظمة
                msg = f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']})**\n\n**الأكواد:**\n" + "\n".join([f"🔗 {c}" for c in order['reserved_codes']])
                await user.send(msg)
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        # إرجاع الأكواد للمخزون
        return_codes(order['prod_key'], order.get('reserved_codes', []))
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                await user.send("❌ **نعتذر، تم رفض طلبك لعدم استلام مبلغ التحويل.**")
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect('/admin_jo_secret')

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
        except Exception as e:
            while True: time.sleep(1000)

