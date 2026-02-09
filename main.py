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
        :root { --main: #5865F2; --bg: #0a0a0a; --card: #111; --text: white; }
        body.light-mode { --bg: #f4f4f4; --card: #fff; --text: #333; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; transition: 0.3s; overflow-x: hidden; }
        
        /* Navbar */
        .glass-nav { position: fixed; top: 20px; left: 20px; z-index: 1000; display: flex; align-items: center; gap: 15px; background: rgba(128,128,128,0.15); backdrop-filter: blur(10px); padding: 10px 25px; border-radius: 30px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        .nav-btn { background: none; border: none; color: var(--text); font-size: 24px; cursor: pointer; transition: 0.3s; }
        .nav-btn:hover { color: var(--main); transform: scale(1.1); }
        .divider { width: 1px; height: 25px; background: rgba(255,255,255,0.2); }

        /* Sidebar */
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 999; top: 0; left: 0; background-color: var(--card); overflow-y: auto; transition: 0.4s; padding-top: 80px; box-shadow: 5px 0 15px rgba(0,0,0,0.5); border-left: 1px solid rgba(255,255,255,0.05); }
        .sidebar a { padding: 15px 25px; text-decoration: none; display: block; text-align: right; color: #888; font-size: 18px; transition: 0.3s; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .sidebar a:hover { color: var(--main); background: rgba(88,101,242,0.1); padding-right: 35px; }
        
        /* Content */
        #main-content { padding: 100px 20px 50px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; margin-top: 40px; }
        
        /* Cards */
        .product-card { width: 300px; height: 480px; border-radius: 30px; position: relative; overflow: hidden; cursor: pointer; border: 1px solid rgba(255,255,255,0.05); background: var(--card); transition: 0.4s; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .product-card:hover { transform: translateY(-10px); border-color: var(--main); box-shadow: 0 15px 40px rgba(88,101,242,0.2); }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; transition: 0.5s; }
        .product-card:hover .card-image { transform: scale(1.1); }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.95), transparent); display: flex; flex-direction: column; justify-content: flex-end; padding: 25px; }
        
        /* Forms */
        .order-form { display: none; background: rgba(20,20,20,0.95); padding: 20px; border-radius: 20px; border: 1px solid var(--main); margin-top: 15px; animation: popUp 0.3s ease; }
        @keyframes popUp { from{transform:scale(0.8);opacity:0} to{transform:scale(1);opacity:1} }
        input, textarea { width: 90%; padding: 12px; margin: 6px 0; border-radius: 10px; border: 1px solid #333; background: #222; color: white; text-align: center; font-family: inherit; }
        input:focus { border-color: var(--main); outline: none; }
        .btn-buy { background: var(--main); color: white; border: none; padding: 12px; border-radius: 10px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; transition: 0.3s; }
        .btn-buy:hover { background: #4752c4; }

        /* --- MODERN TUTORIAL SYSTEM --- */
        .tut-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 9999; display: none; opacity: 0; transition: opacity 0.5s; }
        .tut-active { display: block; opacity: 1; }
        
        /* Spotlight Effect */
        .tut-spotlight { position: absolute; border: 3px solid #f1c40f; border-radius: 15px; box-shadow: 0 0 0 9999px rgba(0,0,0,0.85), 0 0 30px rgba(241,196,15,0.5); pointer-events: none; transition: all 0.5s ease; z-index: 10000; }
        
        /* Tooltip Card */
        .tut-card { position: absolute; width: 300px; background: #fff; color: #000; padding: 25px; border-radius: 20px; z-index: 10001; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.5); transition: all 0.5s ease; }
        .tut-card h3 { color: var(--main); margin-top: 0; }
        .tut-card p { color: #555; font-size: 14px; line-height: 1.5; }
        .tut-btn { background: var(--main); color: white; border: none; padding: 8px 25px; border-radius: 20px; cursor: pointer; font-weight: bold; margin-top: 15px; }
        
        /* Welcome Modal */
        .welcome-modal { display: none; position: fixed; inset: 0; z-index: 11000; background: rgba(0,0,0,0.9); align-items: center; justify-content: center; }
        .welcome-box { background: #111; padding: 40px; border-radius: 30px; text-align: center; border: 2px solid var(--main); max-width: 400px; animation: zoomIn 0.4s; }
        
        /* Spam Timer */
        .timer-modal { display: none; position: fixed; inset: 0; z-index: 12000; background: rgba(0,0,0,0.95); align-items: center; justify-content: center; color: white; flex-direction: column; }
        .timer-circle { width: 100px; height: 100px; border: 5px solid var(--main); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 35px; margin-bottom: 20px; }
    </style>
</head>
<body>

    <div id="waitModal" class="timer-modal">
        <div class="timer-circle" id="timerCount">60</div>
        <h2>⏳ يرجى الانتظار</h2>
        <p>لمنع السبام، يجب الانتظار دقيقة بين الطلبات.</p>
        <button onclick="document.getElementById('waitModal').style.display='none'" class="btn-buy" style="width: auto; padding: 10px 40px; display: none;" id="waitClose">حسناً</button>
    </div>

    <div id="welcomeModal" class="welcome-modal">
        <div class="welcome-box">
            <h2 style="color:var(--main)">مرحباً بك في Jo Store! 👋</h2>
            <p style="color:#ccc; margin: 20px 0;">هل أنت جديد هنا؟ دعنا نأخذك في جولة سريعة لنشرح لك كيفية الطلب والتتبع.</p>
            <button onclick="startTour()" class="btn-buy">نعم، ابدأ الجولة</button>
            <button onclick="skipTour()" class="btn-buy" style="background:#333; margin-top:10px">تخطى</button>
        </div>
    </div>

    <div id="tutOverlay" class="tut-overlay">
        <div id="spotlight" class="tut-spotlight"></div>
        <div id="tutCard" class="tut-card">
            <h3 id="tutTitle">العنوان</h3>
            <p id="tutDesc">الوصف</p>
            <button onclick="nextStep()" class="tut-btn">التالي</button>
        </div>
    </div>

    <div class="glass-nav" id="navBar">
        <button class="nav-btn" onclick="toggleNav()">&#9776;</button>
        <div class="divider"></div>
        <button class="nav-btn" onclick="toggleTheme()">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="trackOrderPrompt()">📋 تتبع طلباتي</a>
        <div style="padding:20px; color:var(--main); font-weight:bold;">أضف تقييمك</div>
        <form action="/add_feedback" method="post" style="padding:0 20px">
            <input name="user_name" placeholder="الاسم" required>
            <textarea name="comment" placeholder="رأيك..." required></textarea>
            <button class="btn-buy">إرسال</button>
        </form>
        <div style="padding:20px; font-weight:bold;">آراء العملاء</div>
        {% for f in feedbacks %}
        <div style="padding:15px; border-bottom:1px solid #333; font-size:13px; text-align:right;">
            <b style="color:var(--main)">{{f.name}}:</b> {{f.comment}}
        </div>
        {% endfor %}
    </div>

    <div id="main-content">
        <h1>Jo Store | متجرك المفضل 🔒</h1>
        <p style="color:#888">أفضل المنتجات الرقمية بضمان كامل</p>
        
        <div class="products-container" id="productsArea">
            {% for key, val in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{val.img}}')"></div>
                <div class="card-overlay">
                    <h3>{{val.name}}</h3>
                    <h2 style="color:#43b581; margin:5px 0">{{val.price}} ج.م</h2>
                    <small style="color:#ccc">المتوفر: {{stocks[key]}}</small>
                    
                    <div id="form-{{key}}" class="order-form" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post" onsubmit="return checkSpam()">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" value="1" min="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <input type="text" name="coupon" placeholder="كود الخصم (اختياري)">
                            <button class="btn-buy">تأكيد الشراء</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        // --- UI Functions ---
        function toggleNav() {
            let s = document.getElementById("mySidebar");
            s.style.width = s.style.width === "300px" ? "0" : "300px";
        }
        function toggleTheme() { document.body.classList.toggle("light-mode"); }
        function showForm(id) {
            document.querySelectorAll('.order-form').forEach(f => f.style.display='none');
            document.getElementById('form-'+id).style.display='block';
        }
        function trackOrderPrompt() {
            let id = prompt("أدخل معرف الديسكورد (ID) الخاص بك:");
            if(id) window.location.href = "/my_orders/"+id;
        }

        // --- Spam Protection ---
        function checkSpam() {
            let last = localStorage.getItem('last_buy_time');
            let now = Date.now();
            if(last && (now - last < 60000)) {
                let modal = document.getElementById('waitModal');
                let timer = document.getElementById('timerCount');
                let btn = document.getElementById('waitClose');
                modal.style.display = 'flex';
                let rem = 60 - Math.floor((now - last)/1000);
                let interval = setInterval(() => {
                    rem--; timer.innerText = rem;
                    if(rem <= 0) { clearInterval(interval); btn.style.display='block'; }
                }, 1000);
                return false;
            }
            localStorage.setItem('last_buy_time', now);
            return true;
        }

        // --- Modern Tutorial System ---
        let currentStep = 0;
        const steps = [
            {
                el: 'productsArea',
                title: '🛒 اختر منتجك',
                desc: 'هنا تجد جميع المنتجات. اضغط على أي كارت لفتح استمارة الشراء وكتابة بياناتك.'
            },
            {
                el: 'navBar',
                title: '📋 القائمة الجانبية',
                desc: 'اضغط هنا لفتح القائمة. منها يمكنك (تتبع طلباتك) ومعرفة الأكواد، أو إضافة تقييمك.'
            },
            {
                el: null, // No spotlight, center modal
                title: '⚠️ هام جداً',
                desc: 'بعد الشراء، تأكد من الانضمام لسيرفر الديسكورد وفتح الخاص لاستلام الكود فوراً!'
            }
        ];

        window.onload = function() {
            if(!localStorage.getItem('tut_done_v2')) {
                document.getElementById('welcomeModal').style.display = 'flex';
            }
        }

        function skipTour() {
            document.getElementById('welcomeModal').style.display = 'none';
            localStorage.setItem('tut_done_v2', 'true');
        }

        function startTour() {
            document.getElementById('welcomeModal').style.display = 'none';
            document.getElementById('tutOverlay').classList.add('tut-active');
            renderStep();
        }

        function renderStep() {
            if (currentStep >= steps.length) {
                document.getElementById('tutOverlay').classList.remove('tut-active');
                localStorage.setItem('tut_done_v2', 'true');
                return;
            }

            let s = steps[currentStep];
            let spot = document.getElementById('spotlight');
            let card = document.getElementById('tutCard');
            
            document.getElementById('tutTitle').innerText = s.title;
            document.getElementById('tutDesc').innerText = s.desc;

            if (s.el) {
                let target = document.getElementById(s.el);
                let rect = target.getBoundingClientRect();
                spot.style.width = (rect.width + 20) + 'px';
                spot.style.height = (rect.height + 20) + 'px';
                spot.style.top = (rect.top - 10) + 'px';
                spot.style.left = (rect.left - 10) + 'px';
                spot.style.display = 'block';
                
                // Position card below or above
                let cardTop = rect.bottom + 20;
                if (cardTop + 200 > window.innerHeight) cardTop = rect.top - 200;
                card.style.top = cardTop + 'px';
                card.style.left = (window.innerWidth/2 - 150) + 'px'; // Center horizontally
            } else {
                // Center Screen
                spot.style.display = 'none';
                card.style.top = '40%';
                card.style.left = (window.innerWidth/2 - 150) + 'px';
            }
        }

        function nextStep() {
            currentStep++;
            renderStep();
        }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    """الصفحة الرئيسية وفحص الصيانة"""
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('''
        <body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;font-family:sans-serif;">
            <div style="border:1px solid #f1c40f; display:inline-block; padding:60px; border-radius:45px; background:rgba(241,196,15,0.03); border: 2px solid rgba(241,196,15,0.2);">
                <h1 style="font-size:90px; margin-bottom:20px;">🚧</h1>
                <h2 style="color:#f1c40f; font-size:38px; margin-bottom:15px;">نحن في وضع الصيانة حالياً</h2>
                <p style="color:#888; font-size:20px; line-height:1.8;">نقوم بتحديث المخزون وإضافة ميزات جديدة مذهلة لمتجرنا.<br>نعتذر عن الإزعاج المؤقت، سنعود خلال وقت قصير جداً.</p>
                <br><br><a href="/admin_login" style="color:#222; text-decoration:none; font-size:10px;">Portal</a>
            </div>
        </body>''')
        
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    """معالجة الطلب وحجز المخزون فوراً"""
    if is_maintenance_mode() and not session.get('logged_in'):
        return "Maintenance Active"
        
    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon_code = request.form.get('coupon', '').strip()

    # حجز الأكواد فوراً من الكمية
    codes_to_reserve = pull_codes(p_key, qty)
    if not codes_to_reserve:
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;"><h1>❌ عذراً، الكمية المطلوبة غير متوفرة!</h1><a href="/" style="color:#5865F2;">العودة للمتجر</a></body>')
    
    unit_price = PRODUCTS[p_key]['price']
    total_amount = qty * unit_price
    discount_line_text = ""
    discount_applied_val = 0
    
    if coupon_code:
        # التحقق من الكوبون (المنتج + الوقت)
        cp_data = get_discount(coupon_code, p_key)
        if cp_data:
            discount_applied_val = cp_data['discount']
            total_amount -= total_amount * (discount_applied_val / 100)
            use_coupon(coupon_code)
            discount_line_text = f"🎟️ **تم استخدام كود خصم: {discount_applied_val}%**"

    # حفظ الطلب في القاعدة مع الأكواد المحجوزة
    db_orders.insert({
        'discord_id': d_id, 
        'prod_name': PRODUCTS[p_key]['name'], 
        'prod_key': p_key, 
        'total': total_amount, 
        'status': 'pending', 
        'time': datetime.now().strftime("%I:%M %p"), 
        'reserved_codes': codes_to_reserve, 
        'cash_number': cash_num, 
        'quantity': qty,
        'discount_info': discount_line_text,
        'discount_percent': discount_applied_val
    })
    
    async def notify_all():
        """إرسال إشعارات الديسكورد المنظمة"""
        try:
            if not client.is_ready(): return
            
            # إشعار العميل
            u = await client.fetch_user(int(d_id))
            await u.send(f"✅ **تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!**\n⌛ سيتم مراجعة عملية الدفع وإرسال الأكواد لك فوراً.")
            
            # إشعار الأدمن (مطابق للصورة تماماً)
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            d_txt = f"\n{discount_line_text}" if discount_line_text else ""
            
            admin_msg = (
                f"🔔 **طلب جديد!**\n\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total_amount} ج.م"
                f"{d_txt}\n"
                f"📱 **من رقم:** {cash_num}\n"
                f"⏰ **الوقت:** {datetime.now().strftime('%I:%M %p')}"
            )
            await admin.send(admin_msg)
        except: pass

    if client.loop: asyncio.run_coroutine_threadsafe(notify_all(), client.loop)
    return redirect(f'/success_page?total={total_amount}')

# --- لوحة التحكم المتطورة V11 Pro ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """الدخول للأدمن بكلمة السر"""
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect('/admin_jo_secret')
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; text-align:center; padding-top:120px; font-family:sans-serif;">
        <div style="border:2px solid #5865F2; display:inline-block; padding:60px; border-radius:40px; background:rgba(88,101,242,0.02);">
            <h1 style="font-size:45px; margin-bottom:15px;">🔐 Admin Access</h1>
            <p style="color:#555; margin-bottom:40px;">يرجى إدخال رمز المرور للتحقق من هويتك</p>
            <form method="post">
                <input type="password" name="password" style="padding:20px; width:280px; border-radius:20px; border:1px solid #333; background:#000; color:white; text-align:center; font-size:26px; letter-spacing:10px;" autofocus required>
                <br><br><button type="submit" style="padding:15px 60px; background:#5865F2; color:white; border:none; border-radius:15px; cursor:pointer; font-weight:bold; font-size:20px; transition:0.3s;">دخول</button>
            </form>
        </div>
    </body>''')

@app.route('/delete_coupon/<int:code_id>')
def delete_coupon(code_id):
    """حذف الكوبون بضغطة زر"""
    if not session.get('logged_in'): return redirect('/admin_login')
    db_config.remove(doc_ids=[code_id])
    flash("نجاح: تم حذف كود الخصم نهائياً من النظام ✅", 'success')
    return redirect('/admin_jo_secret')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    """لوحة التحكم الشاملة والمفصلة"""
    if not session.get('logged_in'): return redirect('/admin_login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        
        if action == 'add_coupon':
            c_code = request.form.get('c_code', '').strip()
            # فحص التكرار
            if db_config.get((Config.type == 'coupon') & (Config.code == c_code)):
                flash(f"فشل: الكود '{c_code}' مستخدم بالفعل لخصم آخر!", 'error')
            else:
                mins = int(request.form.get('c_minutes', 60))
                exp_at = (datetime.now() + timedelta(minutes=mins)).isoformat()
                db_config.insert({
                    'type': 'coupon', 
                    'code': c_code, 
                    'discount': int(request.form.get('c_disc')), 
                    'uses': int(request.form.get('c_uses')), 
                    'prod_key': request.form.get('c_prod'), 
                    'expires_at': exp_at
                })
                flash(f"نجاح: تم تفعيل كود الخصم '{c_code}' في المتجر ✅", 'success')

        elif action == 'edit_stock':
            new_content = request.form.get('full_content', '').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f: f.write(new_content + "\n" if new_content else "")
            flash(f"نجاح: تم تحديث ملف مخزن {PRODUCTS[p_key]['name']} ✅", 'success')
            
        elif action == 'toggle_maintenance':
            status_curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not status_curr}, Config.type == 'maintenance')
            flash("نجاح: تم تغيير حالة وضع الصيانة للموقع ✅", 'success')

        elif action == 'gift':
            g_id, g_p, g_q = request.form.get('g_id'), request.form.get('g_p'), int(request.form.get('g_q', 1))
            gift_pulled = pull_codes(g_p, g_q)
            if gift_pulled:
                async def deliver_gift_now():
                    try:
                        user_obj = await client.fetch_user(int(g_id))
                        # رسالة الهدايا المنظمة
                        msg_gift = f"🎊 **مبروك! لقد استلمت هدية مميزة من الإدارة! ({PRODUCTS[g_p]['name']})**\n" + "\n".join([f"🔗 {c}" for c in gift_pulled])
                        await user_obj.send(msg_gift)
                    except: pass
                if client.loop: asyncio.run_coroutine_threadsafe(deliver_gift_now(), client.loop)
                flash(f"نجاح: تم إرسال {g_q} كود كهدية لـ @{g_id} 🎁", 'success')
            else: flash("خطأ: المخزون الحالي لا يكفي لإرسال هذه الهدية!", 'error')

    # جلب البيانات بالكامل
    all_orders_db = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    current_active_coupons = [{**item, 'id': item.doc_id} for item in db_config.search(Config.type == 'coupon')]
    stock_raw_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k, v in PRODUCTS.items()}
    m_txt_val = "نشط وفعال 🔴" if is_maintenance_mode() else "معطل ومغلق 🟢"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl"><head><meta charset="UTF-8">
    <style>
        :root { --main: #5865F2; --success: #43b581; --danger: #f04747; --bg: #0a0a0a; }
        body { background: var(--bg); color: white; font-family: sans-serif; padding: 40px; }
        .card { background:#111; padding:30px; border-radius:30px; border:1px solid #222; margin-bottom:30px; box-shadow:0 10px 30px rgba(0,0,0,0.4); }
        .grid { display: flex; gap: 30px; flex-wrap: wrap; justify-content: center; }
        input, select, textarea { width:100%; padding:15px; background:#000; color:white; border:1px solid #333; margin-top:10px; border-radius:12px; font-size:14px; }
        button { width:100%; padding:15px; margin-top:15px; border-radius:15px; border:none; color:white; font-weight:bold; cursor:pointer; transition: 0.3s; font-size:15px; }
        
        /* Toast Notification System */
        #toast-container { position: fixed; top: 30px; right: 30px; z-index: 9999; }
        .toast { width: 350px; padding: 25px; border-radius: 20px; margin-bottom: 20px; position: relative; animation: slideIn 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55); overflow: hidden; box-shadow: 0 20px 50px rgba(0,0,0,0.7); }
        .toast-success { background: var(--success); }
        .toast-error { background: var(--danger); }
        .toast-progress { position: absolute; bottom: 0; left: 0; height: 8px; background: rgba(255,255,255,0.9); width: 100%; transition: width linear; }
        @keyframes slideIn { from { transform: translateX(120%); opacity:0; } to { transform: translateX(0); opacity:1; } }
        
        table { width:100%; text-align:center; border-collapse:collapse; margin-top:30px; border-radius: 25px; overflow: hidden; }
        th { background:var(--main); padding:25px; font-size:16px; } td { padding:20px; border-bottom:1px solid #222; background: #111; font-size:15px; }
        .delete-btn-coupon { background: var(--danger); width: auto; padding: 8px 18px; font-size: 13px; border-radius: 12px; transition: 0.2s; }
        .btn-top-back { background:#222; color:white; padding:15px 35px; border-radius:20px; text-decoration:none; float:left; font-weight:bold; border:1px solid #333; transition: 0.3s; }
        .btn-top-back:hover { background:var(--main); border-color:var(--main); }
    </style>
    </head><body>
        <div id="toast-container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="toast toast-{{ 'success' if category == 'success' else 'error' }}">
                            <div style="font-weight:bold; font-size:18px; margin-bottom:5px;">{{ '✅ نجاح مذهل' if category == 'success' else '❌ تنبيه هام' }}</div>
                            <div style="font-size:15px; opacity:0.9;">{{ message }}</div>
                            <div class="toast-progress"></div>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>

        <a href="/" class="btn-top-back">🏠 العودة للمتجر الرئيسي</a>
        <h2 style="text-align:center; color:var(--main); font-size: 42px; margin-bottom:60px; text-shadow: 0 0 20px rgba(88,101,242,0.3);">🛠️ لوحة التحكم الشاملة V11</h2>
        
        <div class="grid">
            <div class="card" style="width:340px;">
                <h3>🛡️ حالة وضع الصيانة ({{m_txt_val}})</h3>
                <form method="post"><input type="hidden" name="action" value="toggle_maintenance"><button style="background:#f39c12;">تبديل وضع الموقع الآن</button></form>
            </div>

            <div class="card" style="width:340px;">
                <h3>🎁 إرسال هدية (جيفت) مباشرة</h3>
                <form method="post">
                    <input type="hidden" name="action" value="gift">
                    <input type="text" name="g_id" placeholder="ID الزبون" required>
                    <select name="g_p">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select>
                    <input type="number" name="g_q" value="1" min="1" placeholder="الكمية">
                    <button style="background:#8e44ad; box-shadow: 0 5px 15px rgba(142,68,173,0.3);">إرسال الهدية خاص فوراً</button>
                </form>
            </div>

            <div class="card" style="width:420px;">
                <h3>🎫 إدارة الكوبونات النشطة</h3>
                <div style="max-height:280px; overflow-y:auto; padding-right:5px;">
                    {% for c in active_coupons %}
                    <div style="background:#000; padding:18px; border-radius:18px; margin-bottom:15px; border:1px solid #333; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <b style="color:var(--success); font-size:18px;">{{ c.code }}</b> <span style="font-size:12px; color:#666;">({{ c.discount }}%)</span><br>
                            <small style="color:#888;">باقي: {{ c.uses }} استخدام | منتج: {{ c.prod_key }}</small>
                        </div>
                        <a href="/delete_coupon/{{c.id}}" class="delete-btn-coupon" style="text-decoration:none; color:white;">حذف 🗑️</a>
                    </div>
                    {% endfor %}
                    {% if not active_coupons %} <p style="text-align:center; color:#555; padding:30px;">لا توجد أكواد خصم نشطة حالياً</p> {% endif %}
                </div>
            </div>

            <div class="card" style="width:400px;">
                <h3>🎫 إنشاء كود خصم مخصص</h3>
                <form method="post">
                    <input type="hidden" name="action" value="add_coupon">
                    <input type="text" name="c_code" placeholder="اسم الكود" required>
                    <input type="number" name="c_disc" placeholder="نسبة الخصم %" required>
                    <input type="number" name="c_uses" placeholder="عدد مرات الاستخدام" required>
                    <input type="number" name="c_minutes" placeholder="الصلاحية بالدقائق" value="60">
                    <select name="c_prod"><option value="all">كل المنتجات</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select>
                    <button style="background:#27ae60;">تفعيل الكود الجديد</button>
                </form>
            </div>
        </div>

        <div class="card">
            <h3>📝 تعديل ملفات المخزن بشكل مفرود</h3>
            <div class="grid">
                {% for k, content in stock.items() %}
                <div style="width:360px; background:#000; padding:25px; border-radius:30px; border:1px solid #222;">
                    <h4 style="margin:0; color:#888; border-bottom: 2px solid #111; padding-bottom: 15px; margin-bottom: 20px;">{{prods[k].name}}</h4>
                    <form method="post">
                        <input type="hidden" name="action" value="edit_stock">
                        <input type="hidden" name="p_key" value="{{k}}">
                        <textarea name="full_content" style="height:160px; font-family:monospace; color:#43b581; font-size:14px; line-height:1.6;">{{content}}</textarea>
                        <button style="background:#2ecc71; box-shadow:0 5px 15px rgba(46,204,113,0.2);">حفظ التغييرات</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="card" style="overflow-x:auto;">
            <h3>📦 أرشيف طلبات الزبائن (V11)</h3>
            <table><thead><tr><th>العميل (ID)</th><th>المنتج المطلوب</th><th>المبلغ الإجمالي</th><th>الحالة</th><th>الإجراء المتاح</th></tr></thead><tbody>
                {% for o in orders|reverse %}
                <tr>
                    <td><b style="color:var(--main);">@{{o.discord_id}}</b></td>
                    <td>{{o.prod_name}} ({{o.quantity}})</td>
                    <td style="color:#43b581; font-weight:bold;">{{o.total}} ج.م</td>
                    <td><span style="font-size:12px; background:rgba(255,255,255,0.08); padding:6px 12px; border-radius:10px;">{{o.status}}</span></td>
                    <td>
                        {% if o.status == 'pending' %}
                        <a href="/approve/{{o.doc_id}}" style="color:var(--success); font-weight:bold; text-decoration:none; margin-right:20px;">[ قبول الطلب ]</a>
                        <a href="/reject/{{o.doc_id}}" style="color:var(--danger); font-weight:bold; text-decoration:none;">[ رفض الطلب ]</a>
                        {% else %}-{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody></table>
        </div>

        <script>
            // تحريك العداد الأبيض للإشعارات
            document.querySelectorAll('.toast').forEach((toast) => {
                let progress = toast.querySelector('.toast-progress');
                progress.style.width = '100%';
                setTimeout(() => { 
                    progress.style.width = '0%'; 
                    progress.style.transition = 'width 5s linear'; 
                }, 10);
                setTimeout(() => { 
                    toast.style.opacity = '0'; 
                    toast.style.transform = 'translateY(-20px)';
                    toast.style.transition = '0.7s ease-in-out'; 
                    setTimeout(() => toast.remove(), 800); 
                }, 5000);
            });
        </script>
    </body></html>
    ''', orders=all_orders_db, active_coupons=current_active_coupons, stock=stock_raw_contents, prods=PRODUCTS, maint_status=m_txt_val, m_txt_val=m_txt_val)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    """تأكيد الطلب وتسليم الأكواد المحجوزة"""
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver_codes_to_user():
            try:
                user_client = await client.fetch_user(int(order['discord_id']))
                # تحويل الأكواد لروابط تسليم منظمة
                all_reserved = order.get('reserved_codes', [])
                msg_ready = f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']}) بنجاح**\n\n**إليك الأكواد الخاصة بك:**\n" + "\n".join([f"🔗 {c}" for c in all_reserved])
                await user_client.send(msg_ready)
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(deliver_codes_to_user(), client.loop)
        flash(f"تم قبول الطلب بنجاح وتسليم الأكواد لـ @{order['discord_id']} ✅", 'success')
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    """رفض الطلب وإعادة الأكواد للمخزن فوراً"""
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        # استعادة الأكواد المحجوزة
        reserved_list = order.get('reserved_codes', [])
        return_codes(order['prod_key'], reserved_list)
        
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify_user_fail():
            try:
                u_obj = await client.fetch_user(int(order['discord_id']))
                await u_obj.send("❌ **نعتذر منك، تم رفض طلبك لعدم استلام مبلغ التحويل الصحيح على محفظتنا.**")
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(notify_user_fail(), client.loop)
        flash(f"تم رفض الطلب وإرجاع {len(reserved_list)} قطعة لمخزن {order['prod_name']} 🔄", 'error')
    return redirect('/admin_jo_secret')

# --- صفحات النجاح والطلبات ---

@app.route('/success_page')
def success_page():
    """صفحة ما بعد الشراء مع كبسولة تتبع الطلب الجديدة"""
    total_val = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:3px solid #5865F2; padding:50px; border-radius:45px; display:inline-block; max-width:580px; background: rgba(88,101,242,0.01); box-shadow: 0 0 50px rgba(88,101,242,0.1);">
            <h2 style="color:#43b581; font-size:36px; margin-bottom:10px;">✅ تم تسجيل طلبك بنجاح</h2>
            <p style="font-size:20px; color:#888;">يرجى تحويل مبلغ <b>{{total}} جنيه</b> إلى الرقم التالي:</p>
            <h1 style="background:#222; padding:30px; border-radius:25px; border:1px solid #444; font-size:46px; letter-spacing:4px; color:#fff; box-shadow: inset 0 0 15px rgba(0,0,0,0.5);">{{pay_num}}</h1>
            
            <div style="margin: 40px 0; border: 3px solid #5865F2; border-radius: 40px; padding: 15px 30px; background: rgba(88,101,242,0.05); display: inline-flex; align-items: center; justify-content: center; gap: 15px;">
                <div style="background: #f1c40f; height: 6px; width: 60px; border-radius: 10px;"></div>
                <span style="color: #f1c40f; font-weight: bold; font-size: 16px;">تنبيه: يمكنك تتبع حالة طلبك ومعرفة الأكواد فور صدورها من (صفحة الطلبات) في القائمة الجانبية.</span>
                <div style="background: #f1c40f; height: 6px; width: 60px; border-radius: 10px;"></div>
            </div>

            <div style="background:rgba(255,204,0,0.1); padding:25px; border-radius:25px; border:1px solid #ffcc00; text-align:right; margin: 20px 0; line-height:1.8;">
                <b style="color:#ffcc00; font-size:18px;">⚠️ ملحوظة هامة جداً:</b><br>
                يجب عليك الانضمام لسيرفر الديسكورد بالضغط <a href="https://discord.gg/RYK28PNv" style="color:#5865F2; font-weight:bold; text-decoration:none;">[ هـنـا ]</a> 
                وتأكد من أن "الرسائل الخاصة" مفعلة لديك حتى يتمكن البوت من تسليمك الأكواد.
            </div>
            
            <br><a href="/" style="color:#5865F2; font-weight:bold; font-size:20px; text-decoration:none;">← العودة للمتجر الرئيسي</a>
        </div>
    </body>''', total=total_val, pay_num=PAYMENT_NUMBER)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    """تتبع حالة الطلبات مع الملحوظة العلوية"""
    orders_list = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:50px 20px;">
        <div style="background:rgba(88,101,242,0.06); border:2px solid #5865F2; padding:30px; border-radius:30px; max-width:750px; margin:0 auto 50px auto; line-height:1.8;">
            <h3 style="color:#5865F2; margin-top:0; font-size:24px;">🔍 تتبع ومعالجة طلباتك</h3>
            <p style="color:#bbb; font-size:16px;">هنا يمكنك معرفة أين وصل طلبك حالياً.. كما يسعدنا جداً أن نسمع رأيك في الخدمة من خلال <b>(قسم التقييمات)</b> في القائمة الجانبية لتطوير متجرنا.</p>
        </div>

        <div style="max-width:750px; margin:auto;">
        {% for o in orders %}
            <div style="background:#111; padding:35px; margin-bottom:30px; border-radius:30px; border: 1px solid #222; text-align:right; box-shadow:0 15px 40px rgba(0,0,0,0.5);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:22px; color:var(--text-color);">{{o.prod_name}} ({{o.quantity}} قطعة)</b>
                    <span style="color:#43b581; font-weight:bold; font-size:20px;">{{o.total}} ج.م</span>
                </div>
                <div style="height:18px; background:#333; border-radius:12px; margin:25px 0; overflow:hidden; border: 1px solid #444;">
                    <div style="width:{{ '100%' if o.status != 'pending' else '50%' }}; height:100%; transition: 1.2s cubic-bezier(0.4, 0, 0.2, 1); background:{{ '#2ecc71' if 'approved' in o.status else '#e74c3c' if 'rejected' in o.status else '#f1c40f' }};"></div>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; font-size:16px; opacity:0.8;">
                    <span>الحالة الحالية للطلب: <b>{{o.status}}</b></span>
                    <span style="font-size:12px; color:#666;">طلب في: {{o.time}}</span>
                </div>
            </div>
        {% endfor %}
        </div><br><br><a href="/" style="color:#5865F2; font-weight:bold; font-size:20px; text-decoration:none;">← العودة للمتجر لشراء المزيد</a>
    </body>''', orders=orders_list)

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    """إضافة تقييم جديد"""
    ip_addr = request.remote_addr
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment'), 'ip': ip_addr})
    return redirect('/')

def run_web_server(): 
    """بدء تشغيل Flask"""
    app.run(host='0.0.0.0', port=10000)

@client.event
async def on_ready():
    """حدث تشغيل البوت"""
    client.loop = asyncio.get_running_loop()
    print(f"=====================================")
    print(f"✅ Jo Store Bot V11 is now ONLINE!")
    print(f"✅ Authenticated as: {client.user}")
    print(f"=====================================")

if __name__ == '__main__':
    # تشغيل الخادم في ثريد منفصل
    thread_web = threading.Thread(target=run_web_server, daemon=True)
    thread_web.start()
    
    # تشغيل الديسكورد
    if TOKEN:
        try: client.run(TOKEN)
        except Exception as err:
            print(f"❌ Critical Connection Error: {err}")
            while True: time.sleep(1000)
