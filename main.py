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
# ⚠️ ضع هنا الآيدي الرقمي لسيرفرك
SERVER_ID = 1272670682324533333 

# توقيت القاهرة
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# المنتجات
PRODUCTS = {
    'xbox': {
        'name': 'Xbox Game Pass Premium',
        'price': 10,
        'file': 'xbox.txt',
        'img': 'https://media.discordapp.net/attachments/111/xbox_bg.png'
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
app.secret_key = 'jo_store_v32_final_fix'

# قواعد البيانات
db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
db_config = TinyDB('config.json') 
Order = Query()
Config = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال ---
def get_stock(prod_key):
    if not os.path.exists(PRODUCTS[prod_key]['file']): return 0
    try:
        with open(PRODUCTS[prod_key]['file'], 'r') as f: return len([l for l in f.readlines() if l.strip()])
    except: return 0

def pull_codes(p_key, qty):
    if not os.path.exists(PRODUCTS[p_key]['file']): return []
    try:
        with open(PRODUCTS[p_key]['file'], 'r') as f: lines = [l for l in f.readlines() if l.strip()]
        if len(lines) < qty: return []
        pulled = lines[:qty]
        remaining = lines[qty:]
        with open(PRODUCTS[p_key]['file'], 'w') as f: f.writelines(remaining)
        return [c.strip() for c in pulled]
    except: return []

def return_codes(p_key, codes):
    fname = PRODUCTS[p_key]['file']
    existing = []
    if os.path.exists(fname):
        with open(fname, 'r') as f: existing = [l.strip() for l in f.readlines()]
    with open(fname, 'a') as f:
        for c in codes:
            if c.strip() not in existing: f.write(c.strip() + "\n")

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

# --- الواجهة (HTML STORE - V30 Spotlight) ---
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
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; margin: 0; overflow-x: hidden; transition: 0.3s; }
        
        .glass-nav { position: fixed; top: 20px; left: 20px; z-index: 1001; display: flex; align-items: center; gap: 15px; background: rgba(128,128,128,0.15); backdrop-filter: blur(15px); padding: 10px 25px; border-radius: 30px; border: 1px solid rgba(255,255,255,0.1); }
        .nav-btn { background: none; border: none; color: var(--text); font-size: 28px; cursor: pointer; }
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; left: 0; background: var(--card); overflow-y: auto; transition: 0.5s ease; padding-top: 80px; border-right: 1px solid #333; }
        .sidebar a { padding: 15px 25px; display: block; text-align: right; color: #888; text-decoration: none; font-size: 18px; border-bottom: 1px solid #222; }
        #main-content { padding: 100px 20px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 45px; margin-top: 60px; }
        .product-card { width: 320px; height: 520px; border-radius: 40px; position: relative; overflow: hidden; cursor: pointer; border: 1px solid #333; background: var(--card); transition: 0.5s; }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; z-index: 1; transition: 1s; }
        .card-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.5) 45%, transparent 85%); z-index: 2; display: flex; flex-direction: column; justify-content: flex-end; padding: 35px; }
        .order-form { display: none; background: rgba(12, 12, 12, 0.98); padding: 20px; border-radius: 25px; border: 1px solid var(--main); margin-top: 15px; }
        input, textarea { width: 90%; padding: 12px; margin: 6px 0; border-radius: 10px; border: 1px solid #333; background: #1a1a1a; color: white; text-align: center; font-family: inherit; }
        .btn-purchase { background: var(--main); color: white; border: none; padding: 14px; border-radius: 12px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 5px; }

        /* --- نظام التوتوريال الجديد --- */
        #tut-overlay { display: none; position: fixed; inset: 0; z-index: 15000; }
        
        .spotlight-hole {
            position: absolute;
            border-radius: 50%;
            box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.92); /* تعتيم قوي */
            pointer-events: none;
            transition: all 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            z-index: 15001;
        }

        .tut-arrow {
            position: absolute;
            font-size: 40px;
            color: #f1c40f;
            z-index: 15003;
            animation: bounce 1s infinite;
            text-shadow: 0 5px 15px black;
            transition: all 0.5s ease;
        }
        @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-15px);} }

        .tut-card {
            position: absolute; background: white; color: black; padding: 20px;
            border-radius: 20px; width: 280px; z-index: 15002; text-align: center;
            box-shadow: 0 0 30px rgba(255,255,255,0.2);
            transition: all 0.5s ease; top: 50%; left: 50%; transform: translate(-50%, -50%);
        }

        /* نافذة البداية والنهاية */
        .modal-box {
            display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.95);
            z-index: 16000; align-items: center; justify-content: center; flex-direction: column;
        }
        .modal-content { background: #111; padding: 40px; border-radius: 30px; border: 2px solid var(--main); text-align: center; max-width: 90%; }

        /* تعديل العداد و زر الـ OK */
        #wait-overlay { display: none; position: fixed; inset: 0; z-index: 20000; background: rgba(0,0,0,0.96); flex-direction: column; align-items: center; justify-content: center; color: white; }
        .timer-circle { width: 100px; height: 100px; border: 5px solid var(--main); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 35px; margin-top: 20px; }
        /* زر الموافقة في الأعلى للموبايل */
        .top-ok-btn {
            position: absolute; top: 10%; right: 50%; transform: translateX(50%);
            background: #e74c3c; padding: 10px 30px; border-radius: 20px; color: white; border: none; font-weight: bold; cursor: pointer; display: none; z-index: 20001;
        }
    </style>
</head>
<body id="body">

    <div id="server-error-modal" class="modal-box">
        <div class="modal-content">
            <div style="font-size: 60px; margin-bottom: 10px;">❌</div>
            <h3 style="color: #e74c3c; margin-top:0;">عذراً لا يمكنك اتمام العملية</h3>
            <p style="color:#ccc; line-height: 1.6;">يجب عليك دخول سيرفر الديسكورد اولا من هنا ليستطيع البوت ارسال السلعه اليك.</p>
            <a href="https://discord.gg/db2sGRbrnJ" target="_blank" class="btn-purchase" style="background:#5865F2; display:inline-block; text-decoration:none; width:auto; padding:10px 40px;">دخول السيرفر</a>
            <button onclick="window.location.href='/'" class="btn-purchase" style="background:#333; width:auto; padding:10px 40px; margin-top:10px;">رجوع</button>
        </div>
    </div>

    <div id="start-modal" class="modal-box" style="display: flex;">
        <div class="modal-content">
            <h2 style="color:var(--main)">أهلاً بك في Jo Store 👋</h2>
            <p style="color:#ccc; margin: 20px 0;">هل ترغب في جولة سريعة لمعرفة كيفية الشراء؟</p>
            <div style="display:flex; gap:10px;">
                <button class="btn-purchase" onclick="startTutorial()">نعم، ابدأ الجولة</button>
                <button class="btn-purchase" style="background:#333;" onclick="skipTutorial()">لا شكراً</button>
            </div>
        </div>
    </div>

    <div id="end-modal" class="modal-box">
        <div class="modal-content">
            <h1>🎊 تهانينا!</h1>
            <p style="color:#ccc;">أنت الآن جاهز للتسوق في متجرنا بأمان.</p>
            <button class="btn-purchase" onclick="finishTutorial()">إنهاء</button>
        </div>
    </div>

    <div id="tut-overlay">
        <div id="spotlight" class="spotlight-hole"></div>
        <div id="arrow" class="tut-arrow">⬆️</div>
        <div id="tut-card" class="tut-card" style="display:none;">
            <div id="tut-text"></div>
            <button class="btn-purchase" style="padding: 8px 20px; margin-top: 10px; font-size:14px;" onclick="nextStep()">التالي</button>
        </div>
    </div>

    <div id="wait-overlay">
        <button id="wait-ok" class="top-ok-btn" onclick="document.getElementById('wait-overlay').style.display='none'">إغلاق النافذة (OK)</button>
        <div class="timer-circle" id="timer-val">60</div>
        <h3 style="margin-top:20px;">يرجى الانتظار دقيقة بين الطلبات.. ⌛</h3>
    </div>

    <div class="glass-nav">
        <button class="nav-btn" id="menu-btn" onclick="toggleNav()">&#9776;</button>
        <div style="width:1px; height:25px; background:#555; margin:0 10px;"></div>
        <button class="nav-btn" onclick="toggleTheme()">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" id="track-btn" onclick="checkOrders()">📋 تتبع طلباتي</a>
        <a href="https://discord.gg/db2sGRbrnJ" target="_blank" style="color:#5865F2;">💬 سيرفر المتجر</a>
        
        <div id="feedback-area">
            <div style="padding:20px 20px 10px; color:var(--main); font-weight:bold;">رأيك يهمنا</div>
            <form action="/add_feedback" method="post" style="padding:0 20px;">
                <input name="user_name" placeholder="الاسم" required>
                <textarea name="comment" placeholder="رأيك..." style="height:60px; background:#222; color:white; border:1px solid #444; width:90%;"></textarea>
                <button class="btn-purchase">إرسال</button>
            </form>
        </div>
    </div>

    <div id="main-content">
        <h1>Jo Store 🔒</h1>
        <div class="products-container" id="prod-list">
            {% for key, info in prods.items() %}
            <div class="product-card" id="card-{{key}}" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <h2 style="color:#43b581">{{ info.price }} ج.م</h2>
                    <small style="color:#ccc">متاح: {{ stocks[key] }}</small>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post" onsubmit="return checkWait()">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <div id="tut-inputs-{{key}}">
                                <input type="number" name="quantity" min="1" value="1" placeholder="الكمية">
                                <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                                <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            </div>
                            <input type="text" name="coupon" placeholder="كود الخصم">
                            <button class="btn-purchase">تأكيد الشراء</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        // Check URL for Error
        if(new URLSearchParams(window.location.search).get('error') === 'not_in_server'){
            document.getElementById('server-error-modal').style.display = 'flex';
        }

        function toggleTheme() { document.body.classList.toggle("light-mode"); localStorage.setItem('theme', document.body.classList.contains('light-mode') ? 'light' : 'dark'); }
        if(localStorage.getItem('theme') === 'light') document.body.classList.add('light-mode');
        
        function toggleNav() { 
            var s = document.getElementById("mySidebar"); 
            s.style.width = s.style.width === "300px" ? "0" : "300px"; 
        }
        
        function showForm(id) { 
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); 
            document.getElementById('form-' + id).style.display = 'block'; 
        }
        
        function checkOrders() { 
            let id = prompt("أدخل معرف الديسكورد:"); 
            if(id) window.location.href="/my_orders/"+id; 
        }

        // --- Spam Logic (Fixed Button) ---
        function checkWait() {
            let last = localStorage.getItem('last_buy');
            let now = Date.now();
            if(last && (now - last < 60000)) {
                document.getElementById('wait-overlay').style.display='flex';
                let sec = 60 - Math.floor((now - last)/1000);
                let t = setInterval(() => {
                    sec--; document.getElementById('timer-val').innerText = sec;
                    if(sec<=0) { clearInterval(t); document.getElementById('wait-ok').style.display='block'; }
                }, 1000);
                return false;
            }
            localStorage.setItem('last_buy', now);
            return true;
        }

        // --- Tutorial Logic (Specific Scenario) ---
        
        // التحقق من الزيارة الأولى
        window.onload = function() {
            if(localStorage.getItem('tut_completed_v30')) {
                document.getElementById('start-modal').style.display = 'none';
            }
        };

        function skipTutorial() {
            document.getElementById('start-modal').style.display = 'none';
            localStorage.setItem('tut_completed_v30', 'true');
        }

        function startTutorial() {
            document.getElementById('start-modal').style.display = 'none';
            document.getElementById('tut-overlay').style.display = 'block';
            nextStep();
        }

        function finishTutorial() {
            document.getElementById('end-modal').style.display = 'none';
            localStorage.setItem('tut_completed_v30', 'true');
            // إعادة الصفحة لوضعها الطبيعي
            document.getElementById('mySidebar').style.width = '0';
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none');
        }

        let step = 0;
        function nextStep() {
            step++;
            const spot = document.getElementById('spotlight');
            const arrow = document.getElementById('arrow');
            const card = document.getElementById('tut-card');
            const txt = document.getElementById('tut-text');
            const sidebar = document.getElementById('mySidebar');

            card.style.display = 'block'; // إظهار الشرح

            if(step === 1) {
                // 1. زر القائمة
                let el = document.getElementById('menu-btn');
                let rect = el.getBoundingClientRect();
                spot.style.top = (rect.top-5)+'px'; spot.style.left = (rect.left-5)+'px';
                spot.style.width = (rect.width+10)+'px'; spot.style.height = (rect.height+10)+'px';
                spot.style.borderRadius = "50%";
                
                arrow.innerText = "⬆️";
                arrow.style.top = (rect.bottom + 10) + 'px'; arrow.style.left = (rect.left + 10) + 'px';
                
                txt.innerHTML = "<b>هذا هو زر الاختيارات</b><br>اضغط هنا لفتح القائمة الجانبية.";
                card.style.top = (rect.bottom + 80) + 'px'; card.style.left = "20px"; card.style.transform = "none";
            
            } else if(step === 2) {
                // 2. فتح القائمة + زر التتبع
                sidebar.style.width = "300px"; // فتح القائمة
                setTimeout(() => {
                    let el = document.getElementById('track-btn');
                    let rect = el.getBoundingClientRect();
                    spot.style.top = (rect.top)+'px'; spot.style.left = (rect.left)+'px';
                    spot.style.width = (rect.width)+'px'; spot.style.height = (rect.height)+'px';
                    spot.style.borderRadius = "0";

                    arrow.innerText = "⬅️";
                    arrow.style.top = (rect.top) + 'px'; arrow.style.left = (rect.left - 50) + 'px';

                    txt.innerText = "يمكنك تتبع حالة طلبك ومعرفة الأكواد من هنا.";
                    card.style.top = (rect.bottom + 20) + 'px'; card.style.left = "20px";
                }, 300);

            } else if(step === 3) {
                // 3. الفيدباك
                let el = document.getElementById('feedback-area');
                let rect = el.getBoundingClientRect();
                spot.style.top = (rect.top)+'px'; spot.style.left = (rect.left)+'px';
                spot.style.width = (rect.width)+'px'; spot.style.height = (rect.height)+'px';
                
                arrow.innerText = "⬅️";
                arrow.style.top = (rect.top + 50) + 'px'; arrow.style.left = (rect.left - 50) + 'px';

                txt.innerText = "يمكنك إبداء رأيك عن الخدمة من هنا.";
            
            } else if(step === 4) {
                // 4. قفل القائمة + فتح منتج
                sidebar.style.width = "0"; // قفل القائمة
                setTimeout(() => {
                    let cardEl = document.querySelector('.product-card'); 
                    if(cardEl) {
                        let rect = cardEl.getBoundingClientRect();
                        // فتح الفورم برمجياً
                        cardEl.click(); 
                        
                        spot.style.top = (rect.top-10)+'px'; spot.style.left = (rect.left-10)+'px';
                        spot.style.width = (rect.width+20)+'px'; spot.style.height = (rect.height+20)+'px';
                        spot.style.borderRadius = "40px";

                        arrow.innerText = "⬇️";
                        arrow.style.top = (rect.top - 60) + 'px'; arrow.style.left = (rect.left + rect.width/2) + 'px';

                        txt.innerHTML = "هنا المنتجات..<br>للشراء قم بكتابة <b>الكمية</b> و <b>ID الديسكورد</b> و <b>رقم الكاش</b>.<br><small>⚠️ تأكد أنك داخل سيرفر الديسكورد الخاص بنا لتستلم الطلب.</small>";
                        card.style.top = (window.innerHeight - 200) + 'px'; card.style.left = "50%"; card.style.transform = "translateX(-50%)";
                    }
                }, 400);

            } else {
                // النهاية
                document.getElementById('tut-overlay').style.display = 'none';
                document.getElementById('end-modal').style.display = 'flex';
            }
        }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('<body style="background:#0a0a0a;color:white;text-align:center;padding-top:150px;"><h1>🚧 الموقع في الصيانة</h1><a href="/admin_login">Portal</a></body>')
    stocks = {k: get_stock(k) for k in PRODUCTS}
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=db_feedbacks.all()[-5:])

@app.route('/place_order', methods=['POST'])
def place_order():
    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon = request.form.get('coupon', '').strip()

    # --- التحقق من السيرفر ---
    if SERVER_ID:
        try:
            future = asyncio.run_coroutine_threadsafe(client.fetch_guild(SERVER_ID), client.loop)
            guild = future.result()
            member_future = asyncio.run_coroutine_threadsafe(guild.fetch_member(int(d_id)), client.loop)
            try:
                member_future.result() 
            except:
                return redirect('/?error=not_in_server') # العضو مش موجود
        except Exception as e:
            print(f"Server check ignored: {e}")
            pass

    reserved = pull_codes(p_key, qty)
    if not reserved: return "نفذت الكمية!"
    
    total = qty * PRODUCTS[p_key]['price']
    disc_txt = ""
    
    if coupon:
        cp = get_discount(coupon, p_key)
        if cp:
            total -= total * (cp['discount'] / 100)
            use_coupon(coupon)
            disc_txt = f"\n🎟️ خصم: {cp['discount']}%"

    db_orders.insert({
        'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 
        'total': total, 'status': 'pending', 'time': datetime.now(EGYPT_TZ).strftime("%I:%M %p"), 
        'reserved_codes': reserved, 'cash_number': cash_num, 'quantity': qty
    })
    
    async def notify():
        try:
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            msg = (f"🔔 **طلب جديد!**\n\n👤 **العميل:** <@{d_id}>\n📦 **المنتج:** {PRODUCTS[p_key]['name']}\n💰 **المبلغ:** {total} ج.م\n{disc_txt}\n📱 **رقم:** {cash_num}\n⏰ **الوقت:** {datetime.now(EGYPT_TZ).strftime('%I:%M %p')}")
            await admin.send(msg)
        except: pass
    if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

@app.route('/success_page')
def success_page():
    t = request.args.get('total')
    return render_template_string(f'''<body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;">
        <div style="border:2px solid #5865F2; padding:40px; border-radius:30px; display:inline-block;">
            <h2>✅ تم تسجيل الطلب</h2>
            <p>حول <b>{t} ج.م</b> للرقم: <h1>{PAYMENT_NUMBER}</h1></p>
            <div style="background:rgba(88,101,242,0.1); padding:15px; border-radius:15px; color:#f1c40f;">تتبع طلبك من القائمة الجانبية.</div>
            <br><a href="/" style="color:#5865F2;">رجوع</a>
        </div></body>''')

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''<body style="background:#0a0a0a;color:white;text-align:center;padding:20px;">
        <h3>🔍 تتبع طلباتك</h3>
        {% for o in orders %}<div style="background:#111; padding:20px; margin-bottom:10px; border-radius:15px; text-align:right;">
        <b>{{o.prod_name}}</b> | الحالة: {{o.status}}
        {% if 'approved' in o.status %}<button onclick="alert('{{o.reserved_codes|join('\\n')}}')" style="background:#43b581; padding:5px 15px; border:none; color:white; cursor:pointer;">عرض الكود</button>{% endif %}</div>{% endfor %}
        <a href="/" style="color:#5865F2;">رجوع</a></body>''', orders=orders)

# --- لوحة التحكم ---

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST' and request.form.get('password') == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect('/admin_jo_secret')
    return '<body style="background:black; color:white; text-align:center; padding-top:100px"><form method="post"><input type="password" name="password"><button>Login</button></form></body>'

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'): return redirect('/admin_login')
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'gift':
            g_id = request.form.get('gid')
            codes = pull_codes(request.form.get('gp'), int(request.form.get('gq')))
            if codes:
                async def send_gift():
                    try:
                        u = await client.fetch_user(int(g_id))
                        await u.send(f"🎁 هدية! ({PRODUCTS[request.form.get('gp')]['name']})\\n" + "\\n".join(codes))
                    except: pass
                asyncio.run_coroutine_threadsafe(send_gift(), client.loop)
                flash("تم الإرسال ✅", "success")
        elif action == 'add_coupon':
            db_config.insert({'type':'coupon', 'code':request.form.get('c'), 'discount':int(request.form.get('d')), 'uses':int(request.form.get('u')), 'prod_key':request.form.get('p')})
            flash("تمت الإضافة ✅", "success")
        elif action == 'edit_stock':
            with open(PRODUCTS[request.form.get('pk')]['file'], 'w') as f: f.write(request.form.get('cont').strip() + "\n")
            flash("تم التحديث ✅", "success")
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
            flash("تم تغيير الحالة ✅", "success")
    
    coupons = db_config.search(Config.type=='coupon')
    stocks = {k: open(v['file']).read() if os.path.exists(v['file']) else "" for k,v in PRODUCTS.items()}
    is_maint = is_maintenance_mode()
    
    return render_template_string('''<body style="background:#0a0a0a; color:white; padding:20px; font-family:sans-serif;">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}<div style="position:fixed; top:20px; right:20px;">{% for c, m in messages %}<div style="background:#43b581; padding:15px; margin-bottom:5px; border-radius:10px;">{{m}}</div>{% endfor %}</div>{% endif %}
        {% endwith %}

        <h1 style="text-align:center;">🛠️ لوحة التحكم V32</h1>
        
        <div style="text-align:center; margin-bottom:20px;">
            <form method="post" style="display:inline;"><input type="hidden" name="action" value="toggle_maintenance"><button style="padding:10px; background:{{ '#e74c3c' if maint else '#f39c12' }}; color:white; border:none; border-radius:10px;">{{ '🔴 إيقاف الصيانة' if maint else '🟢 تفعيل الصيانة' }}</button></form>
        </div>

        <div style="display:flex; gap:20px; justify-content:center; flex-wrap:wrap;">
            <div style="background:#111; padding:20px; border-radius:20px; width:300px; border:1px solid #333;">
                <h3>🎁 جيفت</h3>
                <form method="post"><input type="hidden" name="action" value="gift"><input name="gid" placeholder="ID العميل" style="width:90%; padding:10px; margin:5px 0;"><select name="gp" style="width:95%; padding:10px;">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input name="gq" type="number" value="1" style="width:90%; padding:10px; margin:5px 0;"><button style="width:100%; padding:10px; background:#8e44ad; color:white; border:none; border-radius:5px;">إرسال</button></form>
            </div>
            <div style="background:#111; padding:20px; border-radius:20px; width:300px; border:1px solid #333;">
                <h3>🎫 الكوبونات</h3>
                <div style="height:100px; overflow-y:auto; margin-bottom:10px;">
                    {% for c in coupons %}<div style="background:#000; padding:5px; margin-bottom:5px; display:flex; justify-content:space-between;"><span>{{c.code}} ({{c.discount}}%)</span><a href="/del_c/{{c.doc_id}}" style="color:red; text-decoration:none;">[X]</a></div>{% endfor %}
                </div>
                <form method="post"><input type="hidden" name="action" value="add_coupon"><input name="c" placeholder="الكود" style="width:90%; padding:10px;"><input name="d" placeholder="%" type="number" style="width:40%; padding:10px;"><input name="u" placeholder="العدد" type="number" style="width:40%; padding:10px;"><select name="p" style="width:95%; padding:10px;"><option value="all">الكل</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><button style="width:100%; padding:10px; background:#2ecc71; color:white; border:none; border-radius:5px; margin-top:5px;">إضافة</button></form>
            </div>
        </div>
        <br>
        <div style="display:flex; gap:10px; flex-wrap:wrap; justify-content:center;">
            {% for k,v in prods.items() %}<div style="background:#111; padding:15px; border-radius:15px; border:1px solid #222; width:250px;">
                <h4>{{v.name}}</h4><form method="post"><input type="hidden" name="action" value="edit_stock"><input type="hidden" name="pk" value="{{k}}"><textarea name="cont" style="width:90%; height:60px; background:black; color:#43b581;">{{stocks[k]}}</textarea><button style="width:100%; background:#2ecc71; color:white; border:none; padding:5px;">حفظ</button></form>
            </div>{% endfor %}
        </div>
        <br><table border="1" width="100%" style="text-align:center; background:#111;"><tr><th>العميل</th><th>المنتج</th><th>السعر</th><th>الحالة</th><th>الإجراء</th></tr>
        {% for o in orders|reverse %}<tr><td>{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.total}}</td><td>{{o.status}}</td><td>{% if o.status == 'pending' %}<a href="/app/{{o.doc_id}}" style="color:green;">[قبول]</a> <a href="/rej/{{o.doc_id}}" style="color:red;">[رفض]</a>{% endif %}</td></tr>{% endfor %}</table>
    </body>''', prods=PRODUCTS, orders=db_orders.all(), coupons=coupons, stocks=stocks, maint=is_maint)

@app.route('/del_c/<int:id>')
def del_c(id):
    if session.get('logged_in'): db_config.remove(doc_ids=[id])
    return redirect('/admin_jo_secret')

@app.route('/app/<int:id>')
def approve(id):
    if session.get('logged_in'):
        o = db_orders.get(doc_id=id)
        db_orders.update({'status': 'approved ✅'}, doc_ids=[id])
        async def send():
            try:
                u = await client.fetch_user(int(o['discord_id']))
                await u.send(f"🔥 تم تأكيد طلبك:\\n" + "\\n".join(o['reserved_codes']))
            except: pass
        asyncio.run_coroutine_threadsafe(send(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/rej/<int:id>')
def reject(id):
    if session.get('logged_in'):
        o = db_orders.get(doc_id=id)
        return_codes(o['prod_key'], o['reserved_codes'])
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[id])
    return redirect('/admin_jo_secret')

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment')})
    return redirect('/')

def run_flask(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready(): client.loop = asyncio.get_running_loop(); print(f"✅ Bot Online!")

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    client.run(TOKEN)
