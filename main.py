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
app.secret_key = 'jo_store_ultimate_pro_final_v3'  # مفتاح الجلسة

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
        # 1. التحقق من المنتج المحدد
        if res['prod_key'] != 'all' and res['prod_key'] != prod_key:
            return None
        
        # 2. التحقق من عدد الاستخدامات المتبقية
        if res['uses'] <= 0:
            return None
            
        # 3. التحقق من تاريخ الانتهاء الزمني
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

# --- واجهة المتجر الرئيسية (مفرودة CSS) ---

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
                        <div class="warning-text">⚠️ تنبيه: يرجى كتابة بياناتك بدقة متناهية لضمان وصول طلبك آلياً فور تأكيد الدفع.</div>
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد (مثال: 1054...)" required>
                            <input type="text" name="cash_number" placeholder="رقم المحفظة المحول منها" required>
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
            if (side.style.width === "280px") {
                side.style.width = "0";
            } else {
                side.style.width = "280px";
            }
        }
        
        function toggleTheme() {
            document.body.classList.toggle("light-mode");
            localStorage.setItem('theme', document.body.classList.contains('light-mode') ? 'light' : 'dark');
        }

        // حفظ الثيم المختار
        if (localStorage.getItem('theme') === 'light') {
            document.body.classList.add('light-mode');
        }

        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }

        function checkOrders() { 
            let id = prompt("يرجى إدخال معرف (ID) الديسكورد الخاص بك لتتبع طلباتك:"); 
            if(id) window.location.href="/my_orders/"+id; 
        }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    """الصفحة الرئيسية مع فحص وضع الصيانة"""
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('''
        <body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;font-family:sans-serif;">
            <div style="border:1px solid #f1c40f; display:inline-block; padding:40px; border-radius:30px; background:rgba(241,196,15,0.05);">
                <h1 style="font-size:60px; margin-bottom:10px;">🚧</h1>
                <h1 style="color:#f1c40f;">الموقع في وضع الصيانة</h1>
                <p style="color:#888; font-size:18px;">نحن نقوم بتحديث المخزون وإضافة ميزات جديدة..<br>ساعتان ونعود للعمل بشكل طبيعي، شكراً لصبركم!</p>
                <br>
                <a href="/admin_login" style="color:#5865F2; text-decoration:none; font-size:12px;">Admin Login</a>
            </div>
        </body>''')
        
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    """معالجة الطلب وحجز الأكواد فوراً"""
    if is_maintenance_mode() and not session.get('logged_in'):
        return "الموقع في وضع الصيانة حالياً، لا يمكن استقبال طلبات جديدة."
        
    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon_code = request.form.get('coupon', '').strip()

    # حجز الأكواد فوراً من الكمية لمنع البيع المزدوج
    reserved_codes = pull_codes(p_key, qty)
    if not reserved_codes:
        return render_template_string('''
        <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
            <h2 style="color:#f04747;">❌ عذراً، الكمية المتوفرة نفدت!</h2>
            <p>يبدو أن هناك شخصاً آخر قد اشترى آخر القطع للتو.. يرجى المحاولة لاحقاً.</p>
            <a href="/" style="color:#5865F2;">العودة للمتجر</a>
        </body>''')
    
    # حساب السعر النهائي بعد الخصم
    unit_price = PRODUCTS[p_key]['price']
    total_price = qty * unit_price
    discount_applied_text = ""
    
    if coupon_code:
        # فحص صلاحية الكوبون
        coupon = get_discount(coupon_code, p_key)
        if coupon:
            discount_val = total_price * (coupon['discount'] / 100)
            total_price -= discount_val
            use_coupon(coupon_code)
            discount_applied_text = f"\n🎟️ **تم استخدام كود خصم بنجاح: {coupon['discount']}%**"

    # تسجيل الطلب في قاعدة البيانات مع الأكواد المحجوزة
    db_orders.insert({
        'discord_id': d_id, 
        'prod_name': PRODUCTS[p_key]['name'], 
        'prod_key': p_key, 
        'quantity': qty, 
        'cash_number': cash_num, 
        'total': total_price, 
        'status': 'pending',
        'time': datetime.now().strftime("%I:%M %p"),
        'reserved_codes': reserved_codes # تخزين الأكواد داخل الطلب نفسه
    })
    
    async def notify_all():
        """إرسال الإشعارات للعميل والأدمن"""
        try:
            if not client.is_ready(): return
            
            # إشعار العميل
            user = await client.fetch_user(int(d_id))
            user_notif = (
                f"✅ **تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!**\n"
                f"⌛ سيتم مراجعة عملية الدفع بواسطة الإدارة.\n"
                f"📦 بمجرد التأكيد، سيقوم البوت بإرسال الأكواد لك هنا تلقائياً."
            )
            await user.send(user_notif)
            
            # إشعار الأدمن
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            admin_msg = (
                f"🔔 **طلب جديد في الانتظار!**\n\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"🔢 **الكمية:** {qty}\n"
                f"💰 **المبلغ المطلوب:** {total_price} ج.م{discount_applied_text}\n"
                f"📱 **من رقم كاش:** {cash_num}\n"
                f"⏰ **الوقت:** {datetime.now().strftime('%I:%M %p')}"
            )
            await admin.send(admin_msg)
        except:
            pass

    if client.loop and client.loop.is_running():
        asyncio.run_coroutine_threadsafe(notify_all(), client.loop)
        
    return redirect(f'/success_page?total={total_price}')

@app.route('/success_page')
def success_page():
    """صفحة ما بعد الطلب مع الملحوظات الهامة"""
    total = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:2px solid #5865F2; padding:40px; border-radius:30px; display:inline-block; max-width:550px; background:rgba(88,101,242,0.02);">
            <h2 style="color:#43b581; font-size:32px; margin-bottom:10px;">تم تسجيل طلبك بنجاح! ✅</h2>
            <p style="font-size:18px;">يرجى تحويل مبلغ <b>{{total}} جنيه</b> إلى الرقم التالي:</p>
            <h1 style="background:#222; padding:20px; border-radius:15px; color:#fff; border:1px solid #444; letter-spacing:2px;">{{pay_num}}</h1>
            
            <div style="background:rgba(88,101,242,0.1); padding:20px; border-radius:20px; border:1px solid #5865F2; margin:25px 0; text-align:center; font-size:15px; line-height:1.8;">
                🔍 يمكنك تتبع حالة طلبك في أي وقت من <b>(صفحة الطلبات)</b> في القائمة الجانبية.<br>
                ✍️ نتشرف بكتابة رأيك في الخدمة من <b>(قسم الآراء)</b> لتعم الفائدة.
            </div>

            <div style="background:rgba(255,204,0,0.1); padding:20px; border-radius:20px; border:1px solid #ffcc00; margin:25px 0; text-align:right; font-size:14px; line-height:1.7;">
                <b style="color:#ffcc00;">⚠️ ملحوظة هامة جداً:</b><br>
                يجب أن تكون متواجداً في سيرفر الديسكورد الرسمي الخاص بنا <a href="https://discord.gg/RYK28PNv" style="color: #5865F2; font-weight: bold; text-decoration:none;">[ اضغط هنا للدخول ]</a> 
                ليتمكن البوت من مراسلتك، وتأكد أن "الرسائل الخاصة" (DMs) مفتوحة لديك، وإلا فلن تصلك الأكواد.
            </div>
            
            <br>
            <a href="/" style="color:#5865F2; text-decoration:none; font-weight: bold; font-size:18px;">← العودة إلى المتجر الرئيسية</a>
        </div>
    </body>''', total=total, pay_num=PAYMENT_NUMBER)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    """تتبع طلبات المستخدم مع شريط التقدم"""
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:40px 20px; font-family: sans-serif;">
        <h2 style="color:#5865F2; font-size:30px; margin-bottom:30px;">📋 تتبع حالة طلباتك</h2>
        <div style="max-width:700px; margin:auto;">
        {% for o in orders %}
            <div style="background:#111; padding:25px; margin-bottom:20px; border-radius:20px; border: 1px solid #222; text-align:right; box-shadow:0 10px 20px rgba(0,0,0,0.3);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:18px;">{{o.prod_name}} ({{o.quantity}} قطعة)</b>
                    <span style="color:#888; font-size:12px;">{{o.time}}</span>
                </div>
                <small style="color:#888;">المبلغ الكلي: {{o.total}} ج.م</small>
                
                <div style="height:14px; background:#333; border-radius:10px; margin:20px 0; overflow:hidden; border: 1px solid #444;">
                    <div style="width:{% if 'approved' in o.status %}100%{% elif 'rejected' in o.status %}100%{% else %}50%{% endif %}; 
                                height:100%; transition: 0.8s cubic-bezier(0.4, 0, 0.2, 1); 
                                background:{% if 'approved' in o.status %}#2ecc71{% elif 'rejected' in o.status %}#e74c3c{% else %}#f1c40f{% endif %};">
                    </div>
                </div>
                
                <div style="display:flex; justify-content:space-between; font-size:14px;">
                    <span>الحالة الحالية: <b>{{o.status}}</b></span>
                    {% if 'pending' in o.status %} <span style="color:#f1c40f;">جاري مراجعة التحويل..</span> {% endif %}
                </div>
            </div>
        {% endfor %}
        
        {% if not orders %}
            <div style="padding:100px; color:#555;">
                <h1 style="font-size:80px;">Empty</h1>
                <p>لا توجد أي طلبات مسجلة لهذا الـ ID حالياً.</p>
            </div>
        {% endif %}
        </div>
        <br><br>
        <a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none;">← العودة للمتجر لشراء المزيد</a>
    </body>''', orders=orders)

# --- لوحة التحكم المتطورة (فوق الـ 700 سطر مع الفرد) ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """تسجيل دخول الأدمن بكلمة السر الجديدة"""
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect('/admin_jo_secret')
        else:
            return render_template_string('<body style="background:#0a0a0a; color:white; text-align:center; padding-top:100px;"><h1>❌ كلمة السر خطأ!</h1><a href="/admin_login" style="color:#5865F2;">حاول مرة أخرى</a></body>')
            
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; text-align:center; padding-top:120px; font-family:sans-serif;">
        <div style="border:1px solid #5865F2; display:inline-block; padding:50px; border-radius:30px; background:rgba(88,101,242,0.02);">
            <h1 style="font-size:40px; margin-bottom:20px;">🔐 Admin Portal</h1>
            <p style="color:#888; margin-bottom:30px;">يرجى إدخال رمز التحقق للوصول إلى لوحة التحكم</p>
            <form method="post">
                <input type="password" name="password" style="padding:15px; width:250px; border-radius:15px; border:1px solid #333; background:#000; color:white; text-align:center; font-size:20px; letter-spacing:5px;" autofocus required>
                <br><br>
                <button type="submit" style="padding:15px 40px; background:#5865F2; color:white; border:none; border-radius:15px; cursor:pointer; font-weight:bold; font-size:18px;">تسجيل الدخول</button>
            </form>
        </div>
    </body>''')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    """لوحة التحكم الاحترافية الشاملة"""
    if not session.get('logged_in'):
        return redirect('/admin_login')

    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        
        # 1. إضافة مخزون (Restock)
        if action == 'restock':
            new_codes = request.form.get('codes', '').strip()
            if new_codes:
                with open(PRODUCTS[p_key]['file'], 'a') as f:
                    f.write(new_codes + "\n")
                    
        # 2. تعديل المخزون بالكامل
        elif action == 'edit_stock':
            content = request.form.get('full_content', '').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f:
                f.write(content + "\n" if content else "")
                
        # 3. مسح سجلات مستخدم معين
        elif action == 'clear_logs':
            u_id = request.form.get('u_id', '').strip()
            if u_id:
                db_orders.remove(Order.discord_id == u_id)
                
        # 4. تبديل وضع الصيانة
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
            
        # 5. إضافة كود خصم جديد (مؤقت ولمنتج معين)
        elif action == 'add_coupon':
            c_code = request.form.get('c_code', '').strip()
            c_disc = int(request.form.get('c_discount', 0))
            c_uses = int(request.form.get('c_uses', 1))
            c_prod = request.form.get('c_prod', 'all')
            c_min = int(request.form.get('c_minutes', 60))
            
            expire_time = (datetime.now() + timedelta(minutes=c_min)).isoformat()
            
            if c_code:
                db_config.insert({
                    'type': 'coupon', 
                    'code': c_code, 
                    'discount': c_disc, 
                    'uses': c_uses,
                    'prod_key': c_prod,
                    'expires_at': expire_time
                })
                
        # 6. إرسال هدية مباشرة لـ ID معين (Gift System)
        elif action == 'send_gift':
            g_id = request.form.get('g_id', '').strip()
            g_prod = request.form.get('g_prod')
            g_qty = int(request.form.get('g_qty', 1))
            
            # سحب الأكواد فوراً من الملف للهديّة
            gift_pulled_codes = pull_codes(g_prod, g_qty)
            
            if gift_pulled_codes:
                async def deliver_direct_gift():
                    try:
                        user = await client.fetch_user(int(g_id))
                        gift_list = "\n".join([f"🎁 🔗 {c}" for c in gift_pulled_codes])
                        msg = (
                            f"🎊 **مبروك! لقد استلمت هدية مباشرة من الإدارة!**\n\n"
                            f"📦 **المنتج:** {PRODUCTS[g_prod]['name']}\n"
                            f"**الأكواد الخاصة بك:**\n{gift_list}\n\n"
                            f"*شكراً لكونك عميلاً مميزاً في متجرنا!*"
                        )
                        await user.send(msg)
                    except:
                        pass
                if client.loop and client.loop.is_running():
                    asyncio.run_coroutine_threadsafe(deliver_direct_gift(), client.loop)

    # جلب البيانات للعرض
    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k, v in PRODUCTS.items()}
    m_status_text = "نشط ومفعل 🔴" if is_maintenance_mode() else "معطل حالياً 🟢"
    m_btn_color = "#e74c3c" if is_maintenance_mode() else "#2ecc71"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>Admin Dashboard | Jo Store</title>
        <style>
            :root { --main: #5865F2; --success: #43b581; --danger: #f04747; --bg: #0a0a0a; }
            body { background: var(--bg); color: white; font-family: sans-serif; padding: 30px; }
            
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; border-bottom: 1px solid #222; padding-bottom: 20px; }
            .btn-home { text-decoration: none; color: white; background: #333; padding: 12px 25px; border-radius: 12px; font-weight: bold; transition: 0.3s; }
            .btn-home:hover { background: #444; transform: translateX(-5px); }
            
            .grid-admin { display: flex; gap: 25px; flex-wrap: wrap; justify-content: center; }
            .admin-card { background: #111; border-radius: 20px; border: 1px solid #222; padding: 25px; width: 320px; transition: 0.3s; }
            .admin-card:hover { border-color: var(--main); }
            
            h3 { color: var(--main); margin-top: 0; border-bottom: 1px solid #222; padding-bottom: 10px; display: flex; align-items: center; gap: 10px; }
            
            input, select, textarea { 
                width: 100%; padding: 12px; background: #000; color: white; border: 1px solid #333; 
                border-radius: 10px; margin-top: 10px; box-sizing: border-box; font-size: 14px;
            }
            
            .btn-admin-submit { 
                width: 100%; padding: 12px; border-radius: 10px; border: none; color: white; 
                font-weight: bold; cursor: pointer; margin-top: 15px; transition: 0.3s;
            }
            
            table { width: 100%; border-collapse: collapse; margin-top: 30px; border-radius: 15px; overflow: hidden; }
            th { background: var(--main); color: white; padding: 18px; font-size: 15px; }
            td { background: #111; padding: 15px; border-bottom: 1px solid #222; text-align: center; font-size: 14px; }
            
            .badge-p { padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
            .status-approved { background: rgba(46, 204, 113, 0.1); color: #2ecc71; border: 1px solid #2ecc71; }
            .status-pending { background: rgba(241, 196, 15, 0.1); color: #f1c40f; border: 1px solid #f1c40f; }
            .status-rejected { background: rgba(231, 76, 60, 0.1); color: #e74c3c; border: 1px solid #e74c3c; }
            
            .action-link { text-decoration: none; font-weight: bold; padding: 5px 10px; border-radius: 6px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header">
            <a href="/" class="btn-home">🏠 العودة للمتجر الرئيسي</a>
            <h2 style="margin:0;">🛠️ لوحة التحكم الإحترافية (V3 Pro)</h2>
        </div>

        <div class="grid-admin">
            <div class="admin-card">
                <h3>🛡️ وضع الصيانة</h3>
                <p style="font-size:13px; color:#888;">عند تفعيل هذا الوضع، سيمنع الزوار من تصفح الموقع وسيقفل نظام الطلبات تماماً.</p>
                <div style="background:#000; padding:15px; border-radius:12px; text-align:center; border: 1px solid #333;">
                    الحالة: <b style="color:{{m_btn_color}};">{{ m_status_text }}</b>
                </div>
                <form method="post">
                    <input type="hidden" name="action" value="toggle_maintenance">
                    <button type="submit" class="btn-admin-submit" style="background:{{m_btn_color}};">تبديل حالة الموقع الآن</button>
                </form>
            </div>

            <div class="admin-card">
                <h3>🎁 إرسال هدية مباشرة</h3>
                <form method="post">
                    <input type="hidden" name="action" value="send_gift">
                    <input type="text" name="g_id" placeholder="Discord ID للعميل" required>
                    <select name="g_prod">
                        {% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}
                    </select>
                    <input type="number" name="g_qty" value="1" min="1" placeholder="الكمية">
                    <button type="submit" class="btn-admin-submit" style="background:#9b59b6;">إرسال الهدية خاص فوراً</button>
                </form>
            </div>

            <div class="admin-card">
                <h3>🎫 إنشاء كود خصم ذكي</h3>
                <form method="post">
                    <input type="hidden" name="action" value="add_coupon">
                    <input type="text" name="c_code" placeholder="رمز الكود (مثلاً: SAVE20)" required>
                    <input type="number" name="c_discount" placeholder="نسبة الخصم %" min="1" max="99" required>
                    <input type="number" name="c_uses" placeholder="عدد مرات الاستخدام الكلية" required>
                    <input type="number" name="c_minutes" placeholder="مدة الصلاحية (بالدقائق)" value="60" required>
                    <select name="c_prod">
                        <option value="all">يعمل على كل المنتجات</option>
                        {% for k,v in prods.items() %}<option value="{{k}}">لـ {{v.name}} فقط</option>{% endfor %}
                    </select>
                    <button type="submit" class="btn-admin-submit" style="background:#27ae60;">تفعيل كود الخصم الآن</button>
                </form>
            </div>
        </div>

        <br><br>

        <div class="admin-card" style="width:100%; box-sizing:border-box;">
            <h3>📝 إدارة وتعديل المخزون المباشر</h3>
            <div style="display:flex; gap:20px; flex-wrap:wrap; justify-content:center;">
                {% for k, content in stock.items() %}
                <div style="width:320px; background:#000; padding:15px; border-radius:15px; border:1px solid #222;">
                    <h4 style="margin-top:0; color:#888;">{{ prods[k].name }}</h4>
                    <form method="post">
                        <input type="hidden" name="action" value="edit_stock">
                        <input type="hidden" name="p_key" value="{{k}}">
                        <textarea name="full_content" style="height:120px; font-family:monospace; font-size:12px; color:#43b581;">{{content}}</textarea>
                        <button type="submit" class="btn-admin-submit" style="background:#2ecc71; font-size:13px; padding:8px;">حفظ التعديلات للملف</button>
                    </form>
                    
                    <form method="post" style="margin-top:20px; border-top: 1px solid #222; padding-top:15px;">
                        <input type="hidden" name="action" value="restock">
                        <input type="hidden" name="p_key" value="{{k}}">
                        <textarea name="codes" placeholder="أضف أكواد جديدة هنا (كود في كل سطر)" style="height:60px;"></textarea>
                        <button type="submit" class="btn-admin-submit" style="background:var(--main); font-size:13px; padding:8px;">إضافة للمخزون</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>

        <br><br>

        <div class="admin-card" style="width:100%; box-sizing:border-box;">
            <h3>📦 سجل طلبات الزبائن وتأكيد الدفع</h3>
            <table>
                <thead>
                    <tr>
                        <th>العميل (ID)</th>
                        <th>وقت الطلب</th>
                        <th>المنتج المطلوب</th>
                        <th>المبلغ النهائي</th>
                        <th>رقم الكاش</th>
                        <th>حالة الطلب / الإجراء</th>
                    </tr>
                </thead>
                <tbody>
                    {% for o in orders|reverse %}
                    <tr>
                        <td><b style="color:var(--main);">@{{ o.discord_id }}</b></td>
                        <td>{{ o.time }}</td>
                        <td>{{ o.prod_name }} ({{ o.quantity }})</td>
                        <td style="color:#43b581; font-weight:bold;">{{ o.total }} ج.م</td>
                        <td><code style="background:#000; padding:4px 8px; border-radius:5px;">{{ o.cash_number }}</code></td>
                        <td>
                            {% if o.status == 'pending' %}
                            <div style="display:flex; gap:10px; justify-content:center;">
                                <a href="/approve/{{o.doc_id}}" class="action-link" style="background:#2ecc71; color:white;">Approve (تأكيد)</a>
                                <a href="/reject/{{o.doc_id}}" class="action-link" style="background:#e74c3c; color:white;">Decline (رفض)</a>
                            </div>
                            {% elif 'approved' in o.status %}
                            <span class="badge-p status-approved">Approved ✅</span>
                            {% else %}
                            <span class="badge-p status-rejected">Rejected ❌</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <div style="margin-top:30px; text-align:left;">
                <form method="post" style="display:inline-block; width:300px;">
                    <input type="hidden" name="action" value="clear_logs">
                    <input type="text" name="u_id" placeholder="Discord ID لمسح سجلاته">
                    <button type="submit" style="background:#333; color:#f04747; border:1px solid #444; padding:10px; border-radius:10px; cursor:pointer; width:100%; font-size:12px;">🗑️ مسح سجلات هذا المستخدم</button>
                </form>
            </div>
        </div>
    </body>
    </html>''', orders=orders, stock=stock_contents, prods=PRODUCTS, maint_status=maint_status, m_status_text=m_status_text, m_btn_color=m_btn_color)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    """تأكيد الطلب وإرسال الأكواد المحجوزة للعميل"""
    if not session.get('logged_in'): return redirect('/admin_login')
    
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        codes = order.get('reserved_codes', [])
        
        if codes:
            # تحديث الحالة في القاعدة
            db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
            
            async def deliver_codes():
                try:
                    user = await client.fetch_user(int(order['discord_id']))
                    # تحويل الأكواد لروابط زرقاء منظمة
                    codes_msg = "\n".join([f"🔗 {c}" for c in codes])
                    
                    final_msg = (
                        f"🔥 **مبروك! تم تأكيد استلام الدفع لطلبك لـ ({order['prod_name']})**\n\n"
                        f"**إليك الأكواد الخاصة بك:**\n{codes_msg}\n\n"
                        f"*يمكنك الضغط على الروابط أعلاه لنسخها أو تفعيلها مباشرة.*\n"
                        f"نتمنى لك تجربة ممتعة! لا تنسَ كتابة رأيك في المتجر."
                    )
                    await user.send(final_msg)
                except:
                    pass
            
            if client.loop:
                asyncio.run_coroutine_threadsafe(deliver_codes(), client.loop)
                
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    """رفض الطلب وإرجاع الأكواد للمخزن تلقائياً"""
    if not session.get('logged_in'): return redirect('/admin_login')
    
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        # 1. استعادة الأكواد المحجوزة وإرجاعها للملف
        pulled_codes = order.get('reserved_codes', [])
        return_codes(order['prod_key'], pulled_codes)
        
        # 2. تحديث الحالة للرفض
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        
        async def notify_rejection():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                fail_msg = (
                    f"❌ **نعتذر، لقد تم رفض طلبك لـ ({order['prod_name']})**\n\n"
                    f"**السبب:** لم يتم استلام مبلغ التحويل الصحيح على محفظتنا، أو أن الرقم المرسل غير مطابق.\n"
                    f"يرجى مراجعة الإدارة إذا كنت تعتقد أن هناك خطأ."
                )
                await user.send(fail_msg)
            except:
                pass
                
        if client.loop:
            asyncio.run_coroutine_threadsafe(notify_rejection(), client.loop)
            
    return redirect('/admin_jo_secret')

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    """إضافة تقييم مع حماية بسيطة"""
    ip = request.remote_addr
    name = request.form.get('user_name', 'عميل مجهول').strip()
    comment = request.form.get('comment', '').strip()
    
    if len(comment) > 5:
        db_feedbacks.insert({'name': name, 'comment': comment, 'ip': ip})
        
    return redirect('/')

def run_flask():
    """تشغيل خادم الويب"""
    app.run(host='0.0.0.0', port=10000)

@client.event
async def on_ready():
    """حدث تشغيل البوت"""
    client.loop = asyncio.get_running_loop()
    print(f"-------------------------------")
    print(f"✅ Jo Store Bot is ONLINE!")
    print(f"✅ Logged in as: {client.user}")
    print(f"-------------------------------")

if __name__ == '__main__':
    # بدء تشغيل Flask في ثريد منفصل
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    
    # بدء تشغيل بوت الديسكورد
    if TOKEN:
        try:
            client.run(TOKEN)
        except Exception as e:
            print(f"❌ Discord Connection Error: {e}")
            while True:
                time.sleep(1000)

