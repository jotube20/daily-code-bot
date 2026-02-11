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
# ⚠️ هام: ضع هنا الآيدي الرقمي لسيرفرك
SERVER_ID = 1272670682324533333 

# توقيت القاهرة
EGYPT_TZ = pytz.timezone('Africa/Cairo')

# المنتجات (تم تحديث الوصف وإضافة شارة 'badge' للأكثر مبيعاً)
PRODUCTS = {
    'nitro1': {
        'name': 'Discord Nitro 1 Month',
        'price': 5,
        'desc': 'اشتراك ديسكورد نيترو لمدة شهر. مميزات إضافية، جودة بث أعلى، والمزيد.',
        'file': 'nitro1.txt',
        'img': 'https://media.discordapp.net/attachments/111/nitro1_bg.png',
        'badge': 'الاكثر مبيعا' # الشريط الأصفر المميز
    },
    'xbox': {
        'name': 'Xbox Game Pass Premium',
        'price': 10,
        'desc': 'اشتراك Xbox Game Pass Premium لمدة شهر. استمتع بمكتبة ضخمة من الألعاب.',
        'file': 'xbox.txt',
        'img': 'https://media.discordapp.net/attachments/111/xbox_bg.png',
        'badge': None
    },
    'nitro3': {
        'name': 'Discord Nitro 3 Months',
        'price': 10,
        'desc': 'اشتراك ديسكورد نيترو لمدة 3 أشهر. أفضل قيمة لعشاق ديسكورد.',
        'file': 'nitro3.txt',
        'img': 'https://media.discordapp.net/attachments/111/nitro3_bg.png',
        'badge': None
    }
}

app = Flask(__name__)
app.secret_key = 'jo_store_v33_classic_full'

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
    <title>Jo Store</title>
    <style>
        :root { --main: #5865F2; --bg: #0a0a0a; --card: #111; --text: white; --accent: #43b581; }
        body.light-mode { --bg: #f4f4f4; --card: #fff; --text: #333; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; margin: 0; overflow-x: hidden; transition: 0.3s; }

        .glass-nav { position: fixed; top: 20px; left: 20px; z-index: 1001; display: flex; align-items: center; gap: 15px; background: rgba(128,128,128,0.15); backdrop-filter: blur(15px); padding: 10px 25px; border-radius: 30px; border: 1px solid rgba(255,255,255,0.1); }
        .nav-btn { background: none; border: none; color: var(--text); font-size: 24px; cursor: pointer; transition: 0.3s; }
        .right-nav { position: fixed; top: 20px; right: 20px; z-index: 1001; display: flex; align-items: center; gap: 10px; background: rgba(128,128,128,0.15); backdrop-filter: blur(15px); padding: 8px 20px; border-radius: 30px; border: 1px solid rgba(255,255,255,0.1); }
        .beta-badge { color: #f1c40f; font-weight: bold; font-family: monospace; letter-spacing: 1px; }

        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; left: 0; background: var(--card); overflow-y: auto; transition: 0.5s ease; padding-top: 80px; border-right: 1px solid #333; }
        .sidebar a { padding: 15px 25px; display: block; text-align: right; color: #888; text-decoration: none; font-size: 18px; border-bottom: 1px solid #222; }
        #main-content { padding: 100px 20px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 45px; margin-top: 60px; }

        /* الكروت (إضاءة زرقاء + شريط أصفر) */
        .product-card { width: 320px; height: 480px; border-radius: 30px; position: relative; overflow: hidden; cursor: pointer; border: 1px solid rgba(255,255,255,0.1); background: var(--card); transition: 0.3s; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .product-card:hover { transform: translateY(-10px); box-shadow: 0 0 20px rgba(88, 101, 242, 0.6); border-color: var(--main); }
        .card-image { height: 65%; background-size: cover; background-position: center; position: relative; }
        .card-image::after { content: ''; position: absolute; inset: 0; background: linear-gradient(to top, var(--card) 5%, transparent 70%); }
        .card-info { padding: 20px; text-align: right; }
        .card-info h3 { margin: 0; font-size: 22px; }
        .card-info h2 { color: var(--accent); margin: 5px 0; }
        .card-info small { color: #888; }
        
        /* شريط الأكثر مبيعاً */
        .badge { position: absolute; top: 20px; left: -35px; background: #f1c40f; color: black; padding: 5px 40px; transform: rotate(-45deg); font-weight: bold; font-size: 14px; z-index: 10; box-shadow: 0 5px 10px rgba(0,0,0,0.3); }

        /* نوافذ منبثقة */
        #product-modal, #out-of-stock-modal { display: none; position: fixed; inset: 0; z-index: 11000; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; backdrop-filter: blur(8px); }
        
        /* تكبير القائمة (Modal) */
        .modal-content-prod { background: var(--card); width: 600px; max-width: 95%; border-radius: 35px; overflow: hidden; position: relative; box-shadow: 0 25px 50px rgba(0,0,0,0.5); animation: zoomIn 0.3s ease; border: 1px solid rgba(255,255,255,0.1); }
        @keyframes zoomIn { from{transform:scale(0.9);opacity:0} to{transform:scale(1);opacity:1} }
        .modal-header-prod { height: 200px; background-size: cover; background-position: center; position: relative; }
        .modal-header-prod::after { content: ''; position: absolute; inset: 0; background: linear-gradient(to top, var(--card) 10%, transparent); }
        .modal-body-prod { padding: 30px 40px; text-align: right; }
        .close-modal-prod { position: absolute; top: 20px; right: 25px; background: rgba(0,0,0,0.6); color: white; border: none; font-size: 20px; cursor: pointer; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; z-index: 2; transition: 0.3s; }
        .close-modal-prod:hover { background: #e74c3c; transform: rotate(90deg); }
        
        /* رسالة نفاد الكمية */
        .oos-content { background: #111; padding: 40px; border-radius: 25px; text-align: center; border: 2px solid #e74c3c; width: 400px; }
        .oos-icon { font-size: 50px; margin-bottom: 20px; }

        input, textarea { width: 100%; padding: 15px; margin: 10px 0; border-radius: 12px; border: 1px solid #333; background: #1a1a1a; color: white; text-align: center; font-family: inherit; box-sizing: border-box; font-size: 16px; }
        input:focus { border-color: var(--main); outline: none; }
        .btn-purchase { background: var(--main); color: white; border: none; padding: 18px; border-radius: 15px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 20px; font-size: 18px; transition: 0.3s; }
        .btn-purchase:hover { background: #4752c4; }

        .modal-box { display: none; position: fixed; inset: 0; z-index: 15000; background: rgba(0,0,0,0.95); align-items: center; justify-content: center; flex-direction: column; color: white; }
        .modal-content { background: #111; padding: 40px; border-radius: 30px; border: 2px solid var(--main); text-align: center; max-width: 90%; }
        #news-modal { display: none; position: fixed; inset: 0; z-index: 12000; background: rgba(0,0,0,0.85); align-items: center; justify-content: center; backdrop-filter: blur(5px); }
        .news-content { background: #111; width: 400px; padding: 0; border-radius: 25px; border: 1px solid #333; position: relative; overflow: hidden; }
        .news-header { background: var(--main); padding: 20px; text-align: center; } .news-body { padding: 25px; color: white; text-align: right; }
        .close-news { position: absolute; top: 15px; right: 20px; background: none; border: none; color: white; font-size: 20px; cursor: pointer; }
        #tut-overlay { display: none; position: fixed; inset: 0; z-index: 15000; }
        .spotlight-hole { position: absolute; border-radius: 50%; box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.92); pointer-events: none; transition: 0.6s; z-index: 15001; }
        .tut-arrow { position: absolute; font-size: 40px; color: #f1c40f; z-index: 15003; animation: bounce 1s infinite; }
        @keyframes bounce { 0%, 100% {transform: translateY(0);} 50% {transform: translateY(-15px);} }
        .tut-card { position: absolute; background: white; color: black; padding: 20px; border-radius: 20px; width: 280px; z-index: 15002; text-align: center; }
        #wait-overlay { display: none; position: fixed; inset: 0; z-index: 20000; background: rgba(0,0,0,0.96); flex-direction: column; align-items: center; justify-content: center; color: white; }
        .timer-circle { width: 100px; height: 100px; border: 5px solid var(--main); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 35px; margin-top: 20px; }
        .top-ok-btn { position: absolute; top: 10%; right: 50%; transform: translateX(50%); background: #e74c3c; padding: 10px 30px; border-radius: 20px; color: white; border: none; font-weight: bold; cursor: pointer; display: none; z-index: 20001; }
    </style>
</head>
<body id="body">

    <div id="product-modal">
        <div class="modal-content-prod">
            <button class="close-modal-prod" onclick="closeProdModal()">✕</button>
            <div id="pm-header" class="modal-header-prod"></div>
            <div class="modal-body-prod">
                <h2 id="pm-name" style="margin:0; font-size:28px;"></h2>
                <h1 id="pm-price" style="color:var(--accent); margin:10px 0; font-size:32px;"></h1>
                <div id="pm-desc" style="color:#ccc; font-size:16px; line-height:1.6; margin-bottom:25px; padding-bottom:20px; border-bottom:1px solid #333;"></div>
                <div class="order-form">
                    <form action="/place_order" method="post" onsubmit="return checkWait()">
                        <input type="hidden" id="pm-key" name="prod_key">
                        <div id="tut-inputs-modal">
                            <input type="number" name="quantity" min="1" value="1" placeholder="الكمية" required style="font-size:18px;">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required style="font-size:18px;">
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required style="font-size:18px;">
                        </div>
                        <input type="text" name="coupon" placeholder="كود الخصم (اختياري)" style="font-size:18px;">
                        <button class="btn-purchase">تأكيد الشراء Now</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div id="out-of-stock-modal">
        <div class="oos-content">
            <div class="oos-icon">❌</div>
            <h3 style="color:#e74c3c; margin-top:0;">عفواً، نفذت الكمية</h3>
            <p style="color:#ccc; line-height:1.6;">لا يوجد كمية من هذا المنتج حالياً.<br>يمكنك الشراء حين توفر كمية وسنقوم بتنبيهك.</p>
            <button onclick="document.getElementById('out-of-stock-modal').style.display='none'" class="btn-purchase" style="background:#333; margin-top:10px;">حسناً</button>
        </div>
    </div>

    <div id="news-modal"><div class="news-content"><button class="close-news" onclick="toggleNews()">✕</button><div class="news-header"><h2>What is new?</h2><div style="color:rgba(255,255,255,0.7); font-size:12px;">Latest Update - <span id="current-date"></span></div></div><div class="news-body"><div style="color:#f1c40f; font-weight:bold; font-size:18px; margin-bottom:10px;">✨ Beta Update V1</div><ul style="list-style:none; padding:0; line-height:1.8; color:#ccc;"><li>🌓 إطلاق الوضع الليلي.</li><li>🎟️ إضافة نظام الكوبونات.</li><li>⏳ نظام حماية (Countdown).</li><li>🛡️ التحقق من الـ ID.</li><li>✨ تصميم جديد كلياً للمنتجات.</li></ul><button class="btn-purchase" onclick="toggleNews()" style="margin-top:15px;">فهمت، شكراً!</button></div></div></div>
    <div class="right-nav"><span class="beta-badge">Beta</span><div style="width:1px; height:20px; background:rgba(255,255,255,0.2); margin:0 10px;"></div><button class="nav-btn" onclick="toggleNews()">📢</button></div>
    <div class="glass-nav"><button class="nav-btn" id="menu-btn" onclick="toggleNav()">&#9776;</button><div style="width:1px; height:25px; background:#555; margin:0 10px;"></div><button class="nav-btn" onclick="toggleTheme()">🌓</button></div>
    <div id="server-error-modal" class="modal-box"><div class="modal-content"><div style="font-size:60px;">❌</div><h3 style="color:#e74c3c;">عذراً لا يمكنك اتمام العملية</h3><p style="color:#ccc;">يجب عليك دخول سيرفر الديسكورد أولاً.</p><a href="https://discord.gg/db2sGRbrnJ" target="_blank" class="btn-purchase" style="background:#5865F2; display:inline-block; text-decoration:none; width:auto; padding:10px 40px;">دخول السيرفر</a><button onclick="window.location.href='/'" class="btn-purchase" style="background:#333; width:auto; padding:10px 40px; margin-top:10px;">رجوع</button></div></div>
    <div id="wait-overlay"><button id="wait-ok" class="top-ok-btn" onclick="document.getElementById('wait-overlay').style.display='none'">إغلاق النافذة (OK)</button><div class="timer-circle" id="timer-val">60</div><h3>يرجى الانتظار دقيقة.. ⌛</h3></div>
    <div id="start-modal" class="modal-box" style="display:flex;"><div class="modal-content"><h2 style="color:var(--main)">أهلاً بك في Jo Store 👋</h2><p style="color:#ccc;">هل ترغب في جولة سريعة؟</p><div style="display:flex; gap:10px;"><button class="btn-purchase" onclick="startTutorial()">نعم، ابدأ الجولة</button><button class="btn-purchase" style="background:#333;" onclick="skipTutorial()">لا شكراً</button></div></div></div>
    <div id="end-modal" class="modal-box"><div class="modal-content"><h1>🎊 تهانينا!</h1><p style="color:#ccc;">أنت الآن جاهز للتسوق.</p><button class="btn-purchase" onclick="finishTutorial()">إنهاء</button></div></div>
    <div id="tut-overlay"><div id="spotlight" class="spotlight-hole"></div><div id="arrow" class="tut-arrow">⬆️</div><div id="tut-card" class="tut-card" style="display:none;"><div id="tut-text"></div><button class="btn-purchase" style="padding:8px 20px; margin-top:10px;" onclick="nextStep()">التالي</button></div></div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="/my_orders_page" id="track-btn">📋 تتبع طلباتي</a>
        <a href="https://discord.gg/db2sGRbrnJ" target="_blank" style="color:#5865F2;">💬 سيرفر المتجر</a>
        <div id="feedback-area" style="padding:20px;">
            <div style="color:var(--main); font-weight:bold; margin-bottom:10px;">رأيك يهمنا</div>
            <form action="/add_feedback" method="post"><input name="user_name" placeholder="الاسم" required><textarea name="comment" placeholder="رأيك..." style="height:60px;"></textarea><button class="btn-purchase">إرسال</button></form>
        </div>
    </div>

    <div id="main-content">
        <h1>Jo Store 🔒</h1>
        <div class="products-container" id="prod-list">
            {% for key, info in prods.items() %}
            <div class="product-card" id="card-{{key}}" onclick="handleProductClick('{{key}}', '{{info.name}}', '{{info.price}}', '{{info.img}}', '{{info.desc}}', {{ stocks[key] }})">
                {% if info.badge %}
                <div class="badge">{{ info.badge }}</div>
                {% endif %}
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-info">
                    <h3>{{ info.name }}</h3>
                    <h2>{{ info.price }} ج.م</h2>
                    <small>متاح: {{ stocks[key] }}</small>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        const d = new Date(); document.getElementById('current-date').innerText = d.getDate() + "/" + (d.getMonth()+1) + "/" + d.getFullYear();
        function toggleNews() { let m = document.getElementById('news-modal'); m.style.display = (m.style.display === 'flex') ? 'none' : 'flex'; }
        if(new URLSearchParams(window.location.search).get('error') === 'not_in_server'){ document.getElementById('server-error-modal').style.display = 'flex'; }
        function toggleTheme() { document.body.classList.toggle("light-mode"); localStorage.setItem('theme', document.body.classList.contains('light-mode') ? 'light' : 'dark'); }
        if(localStorage.getItem('theme') === 'light') document.body.classList.add('light-mode');
        function toggleNav() { var s = document.getElementById("mySidebar"); s.style.width = s.style.width === "300px" ? "0" : "300px"; }

        // دالة التحقق من المخزون
        function handleProductClick(key, name, price, img, desc, stock) {
            if (stock <= 0) {
                document.getElementById('out-of-stock-modal').style.display = 'flex';
            } else {
                openProdModal(key, name, price, img, desc);
            }
        }

        function openProdModal(key, name, price, img, desc) {
            document.getElementById('pm-key').value = key;
            document.getElementById('pm-name').innerText = name;
            document.getElementById('pm-price').innerText = price + ' ج.م';
            document.getElementById('pm-header').style.backgroundImage = `url('${img}')`;
            document.getElementById('pm-desc').innerText = desc;
            document.getElementById('product-modal').style.display = 'flex';
        }
        function closeProdModal() { document.getElementById('product-modal').style.display = 'none'; }

        function checkWait() {
            let last = localStorage.getItem('last_buy'); let now = Date.now();
            if(last && (now - last < 60000)) {
                document.getElementById('wait-overlay').style.display='flex';
                let sec = 60 - Math.floor((now - last)/1000);
                let t = setInterval(() => { sec--; document.getElementById('timer-val').innerText = sec; if(sec<=0) { clearInterval(t); document.getElementById('wait-ok').style.display='block'; } }, 1000);
                return false;
            }
            localStorage.setItem('last_buy', now); return true;
        }

        window.onload = function() { if(localStorage.getItem('tut_completed_v30')) { document.getElementById('start-modal').style.display = 'none'; } };
        function skipTutorial() { document.getElementById('start-modal').style.display = 'none'; localStorage.setItem('tut_completed_v30', 'true'); }
        function startTutorial() { document.getElementById('start-modal').style.display = 'none'; document.getElementById('tut-overlay').style.display = 'block'; nextStep(); }
        function finishTutorial() { document.getElementById('end-modal').style.display = 'none'; localStorage.setItem('tut_completed_v30', 'true'); document.getElementById('mySidebar').style.width = '0'; closeProdModal(); }

        let step = 0;
        function nextStep() {
            step++; const s = document.getElementById('spotlight'); const a = document.getElementById('arrow'); const c = document.getElementById('tut-card'); const t = document.getElementById('tut-text'); const sb = document.getElementById('mySidebar');
            c.style.display = 'block';
            if(step === 1) {
                let el = document.getElementById('menu-btn'); let rect = el.getBoundingClientRect();
                s.style.top = (rect.top-5)+'px'; s.style.left = (rect.left-5)+'px'; s.style.width = (rect.width+10)+'px'; s.style.height = (rect.height+10)+'px'; s.style.borderRadius = "50%"; a.innerText = "⬆️"; a.style.top = (rect.bottom + 10) + 'px'; a.style.left = (rect.left + 10) + 'px'; t.innerHTML = "<b>هذا هو زر الاختيارات</b><br>اضغط هنا لفتح القائمة الجانبية."; c.style.top = (rect.bottom + 80) + 'px'; c.style.left = "20px"; c.style.transform = "none";
            } else if(step === 2) {
                sb.style.width = "300px"; setTimeout(() => { let el = document.getElementById('track-btn'); let rect = el.getBoundingClientRect(); s.style.top = (rect.top)+'px'; s.style.left = (rect.left)+'px'; s.style.width = (rect.width)+'px'; s.style.height = (rect.height)+'px'; s.style.borderRadius = "0"; a.innerText = "⬅️"; a.style.top = (rect.top) + 'px'; a.style.left = (rect.left - 50) + 'px'; t.innerText = "يمكنك تتبع طلبك من هنا."; c.style.top = (rect.bottom + 20) + 'px'; c.style.left = "20px"; }, 300);
            } else if(step === 3) {
                let el = document.getElementById('feedback-area'); let rect = el.getBoundingClientRect(); s.style.top = (rect.top)+'px'; s.style.left = (rect.left)+'px'; s.style.width = (rect.width)+'px'; s.style.height = (rect.height)+'px'; a.innerText = "⬅️"; a.style.top = (rect.top + 50) + 'px'; a.style.left = (rect.left - 50) + 'px'; t.innerText = "يمكنك إبداء رأيك عن الخدمة من هنا.";
            } else if(step === 4) {
                sb.style.width = "0"; setTimeout(() => { let cardEl = document.querySelector('.product-card'); if(cardEl) { cardEl.click(); setTimeout(() => { let el = document.getElementById('tut-inputs-modal'); let rect = el.getBoundingClientRect(); s.style.top = (rect.top-10)+'px'; s.style.left = (rect.left-10)+'px'; s.style.width = (rect.width+20)+'px'; s.style.height = (rect.height+20)+'px'; s.style.borderRadius = "15px"; a.innerText = "⬇️"; a.style.top = (rect.top - 60) + 'px'; a.style.left = (rect.left + rect.width/2) + 'px'; t.innerHTML = "هنا تقوم بإدخال بياناتك للشراء.<br><small>⚠️ تأكد أنك داخل سيرفر الديسكورد.</small>"; c.style.top = (rect.bottom + 20) + 'px'; c.style.left = "50%"; c.style.transform = "translateX(-50%)"; }, 500); } }, 400);
            } else { document.getElementById('tut-overlay').style.display = 'none'; document.getElementById('end-modal').style.display = 'flex'; }
        }
    </script>
</body>
</html>
'''

# --- الروابط (Routes) ---

@app.route('/')
def home():
    # صفحة الصيانة (التصميم الجديد - الإطار الذهبي)
    if is_maintenance_mode() and not session.get('logged_in'):
        return render_template_string('''
        <!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>الصيانة</title><style>body { background: #000; color: white; height: 100vh; margin: 0; display: flex; align-items: center; justify-content: center; font-family: 'Segoe UI', sans-serif; } .maint-card { border: 2px solid #f1c40f; padding: 40px; border-radius: 20px; text-align: center; max-width: 90%; background: rgba(241, 196, 15, 0.02); box-shadow: 0 0 30px rgba(241, 196, 15, 0.1); } h1 { font-size: 32px; margin-bottom: 10px; } p { color: #888; font-size: 14px; }</style></head><body><div class="maint-card"><h1>🚧 الموقع في وضع الصيانة</h1><p>نحن نعمل على تحسين المتجر يرجى العودة لاحقاً</p></div></body></html>''')
    
    stocks = {k: get_stock(k) for k in PRODUCTS}
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=db_feedbacks.all()[-5:])

@app.route('/place_order', methods=['POST'])
def place_order():
    if is_maintenance_mode() and not session.get('logged_in'): return "Maintenance Mode"

    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon = request.form.get('coupon', '').strip()

    # فحص السيرفر
    if SERVER_ID:
        try:
            future = asyncio.run_coroutine_threadsafe(client.fetch_guild(SERVER_ID), client.loop)
            guild = future.result()
            member_future = asyncio.run_coroutine_threadsafe(guild.fetch_member(int(d_id)), client.loop)
            try: member_future.result()
            except: return redirect('/?error=not_in_server')
        except: pass

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

    # إرسال Embed للآدمن (ذهبي)
    async def notify():
        try:
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            embed = discord.Embed(title="🔔 طلب جديد!", color=0xf1c40f)
            embed.add_field(name="👤 العميل:", value=f"<@{d_id}> (`{d_id}`)", inline=False)
            embed.add_field(name="📦 المنتج:", value=PRODUCTS[p_key]['name'], inline=False)
            embed.add_field(name="💰 المبلغ:", value=f"{total} ج.م {disc_txt}", inline=False)
            embed.add_field(name="📱 رقم الكاش:", value=cash_num, inline=False)
            embed.set_footer(text=datetime.now(EGYPT_TZ).strftime('%I:%M %p'))
            await admin.send(embed=embed)
        except: pass
    if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect(f'/success_page?total={total}')

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
    # التصحيح: شلنا حرف f واستخدمنا Jinja2 {{ }} للمتغيرات عشان الجافاسكريبت يشتغل صح
    return render_template_string('''
    <!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تم الطلب</title><style>body{background:#0a0a0a;color:white;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}.success-card{border:2px solid #5865F2;padding:40px;border-radius:30px;text-align:center;background:rgba(88,101,242,0.05);box-shadow:0 0 30px rgba(88,101,242,0.2);max-width:90%}.checkmark{font-size:60px;color:#43b581;margin-bottom:10px}.btn{display:block;width:100%;padding:12px;border-radius:12px;border:none;font-weight:bold;cursor:pointer;margin-top:15px;text-decoration:none}.btn-track{background:rgba(88,101,242,0.2);color:#5865F2}.btn-back{background:#333;color:#888;cursor:not-allowed}</style></head><body>
        <div class="success-card">
            <div class="checkmark">✅</div>
            <h2 style="margin:0;">تم تسجيل الطلب</h2>
            <p style="font-size:18px;">حول <b style="color:#43b581;">{{ t }} ج.م</b> للرقم:</p>
            <h1 style="font-size:40px; margin:10px 0; letter-spacing:2px;">{{ payment_number }}</h1>
            <a href="/my_orders_page" class="btn btn-track">تتبع طلبك الآن</a>
            <button id="back-btn" class="btn btn-back" disabled>العودة للرئيسية (10)</button>
        </div>
        <script>
            let sec = 10; const btn = document.getElementById('back-btn');
            const timer = setInterval(() => { sec--; btn.innerText = `العودة للرئيسية (${sec})`; if(sec<=0){ clearInterval(timer); btn.removeAttribute('disabled'); btn.style.background='#5865F2'; btn.style.color='white'; btn.style.cursor='pointer'; btn.innerText='العودة للرئيسية'; btn.onclick=()=>window.location.href='/'; } }, 1000);
        </script>
    </body></html>''', t=t, payment_number=PAYMENT_NUMBER)

# --- 1. صفحة البحث عن الطلب (اللي الزبون بيدخل فيها الايدي) ---
@app.route('/my_orders_page')
def my_orders_page():
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تتبع الطلبات</title>
        <style>
            body{background:#0a0a0a;color:white;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
            .track-card{background:#111;padding:40px;border-radius:30px;text-align:center;border:1px solid #333;width:400px;max-width:90%; box-shadow: 0 10px 30px rgba(0,0,0,0.5);}
            input{width:100%;padding:15px;margin:20px 0;border-radius:12px;border:1px solid #333;background:#1a1a1a;color:white;text-align:center;font-size:16px;box-sizing:border-box; transition:0.3s;}
            input:focus{border-color:#5865F2; outline:none;}
            button{width:100%;padding:15px;border-radius:12px;border:none;font-weight:bold;cursor:pointer;background:#5865F2;color:white;font-size:16px; transition:0.3s;}
            button:hover{background:#4752c4;}
            a{color:#888; text-decoration:none; transition:0.3s;}
            a:hover{color:white;}
        </style>
    </head>
    <body>
        <div class="track-card">
            <h2 style="margin-bottom:10px;">📋 تتبع طلباتك</h2>
            <p style="color:#888; margin-top:0;">أدخل معرف الديسكورد (ID) الخاص بك لعرض طلباتك.</p>
            <input type="text" id="discord-id" placeholder="Discord ID e.g. 123456789">
            <button onclick="let id=document.getElementById('discord-id').value; if(id) window.location.href='/my_orders/'+id">عرض الطلبات</button>
            <br><br>
            <a href="/">← العودة للرئيسية</a>
        </div>
    </body>
    </html>''')

# --- 2. صفحة عرض النتائج (اللي بتظهر فيها الكروت والبروجرس بار) ---
@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>طلباتي</title>
        <style>
            body { background: #0a0a0a; color: white; font-family: 'Segoe UI', sans-serif; padding: 20px; }
            .container { max-width: 600px; margin: 0 auto; }
            .header-box { border: 1px solid #5865F2; background: rgba(88,101,242,0.05); border-radius: 20px; padding: 20px; text-align: center; margin-bottom: 30px; }
            .order-card { background: #111; border: 1px solid #333; border-radius: 20px; padding: 25px; margin-bottom: 20px; transition:0.3s; }
            .order-card:hover { border-color: #555; }
            .top-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
            .prod-name { font-weight: bold; font-size: 18px; }
            .prod-price { color: #43b581; font-weight: bold; font-size: 18px; }
            
            /* Progress Bar Styles */
            .progress-bg { background: #222; height: 10px; border-radius: 10px; overflow: hidden; margin-bottom: 10px; position: relative; }
            .progress-fill { height: 100%; border-radius: 10px; transition: 1s; }
            
            .status-row { display: flex; justify-content: space-between; font-size: 13px; color: #888; align-items: center; }
            
            .show-code-btn { background: #43b581; color: white; border: none; padding: 10px 20px; border-radius: 10px; cursor: pointer; font-size: 14px; margin-top: 15px; width: 100%; font-weight:bold; }
            .show-code-btn:hover { background: #3aa673; }
            
            .code-reveal { display: none; background: #000; padding: 15px; border-radius: 10px; margin-top: 10px; border: 1px dashed #43b581; color: #f1c40f; font-family: monospace; word-break: break-all; line-height: 1.6; }
            
            .no-orders { text-align: center; color: #777; margin-top: 50px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-box">
                <h3 style="margin:0; color:#5865F2;">🔍 سجل الطلبات لـ {{uid}}</h3>
                <p style="margin:5px 0 0; color:#888; font-size:12px;">هنا يمكنك متابعة حالة طلباتك واستلام الأكواد.</p>
            </div>

            {% for o in orders|reverse %}
                <div class="order-card">
                    <div class="top-row">
                        <div class="prod-name">{{o.prod_name}} <span style="font-size:14px; color:#777;">(x{{o.quantity}})</span></div>
                        <div class="prod-price">{{o.total}} ج.م</div>
                    </div>

                    {% if 'approved' in o.status %}
                        <div class="progress-bg"><div class="progress-fill" style="width:100%; background:#43b581;"></div></div>
                        <div class="status-row">
                            <div>الحالة: <span style="color:#43b581">مكتمل ✅</span></div>
                            <div>{{o.time}}</div>
                        </div>
                        <button class="show-code-btn" onclick="let c=document.getElementById('code-{{loop.index}}'); c.style.display = c.style.display==='block'?'none':'block';">عرض الكود / التفاصيل</button>
                        <div id="code-{{loop.index}}" class="code-reveal">
                            {% for c in o.reserved_codes %}
                                {{c}}<br>
                            {% endfor %}
                        </div>

                    {% elif 'rejected' in o.status %}
                        <div class="progress-bg"><div class="progress-fill" style="width:100%; background:#e74c3c;"></div></div>
                        <div class="status-row">
                            <div>الحالة: <span style="color:#e74c3c">مرفوض ❌</span></div>
                            <div>{{o.time}}</div>
                        </div>

                    {% else %}
                        <div class="progress-bg"><div class="progress-fill" style="width:60%; background:#f1c40f;"></div></div>
                        <div class="status-row">
                            <div>الحالة: <span style="color:#f1c40f">قيد المراجعة ⏳</span></div>
                            <div>{{o.time}}</div>
                        </div>
                    {% endif %}
                </div>
            {% else %}
                <div class="no-orders">
                    <h2>📭</h2>
                    <p>لا توجد طلبات مسجلة لهذا الحساب.</p>
                </div>
            {% endfor %}
            
            <div style="text-align:center; margin-top:30px;">
                <a href="/" style="color:#5865F2; text-decoration:none; font-weight:bold;">العودة للمتجر</a>
            </div>
        </div>
    </body>
    </html>
    ''', orders=orders, uid=uid)
    
# --- لوحة التحكم (Classic UI) ---

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
        
        # 1. إرسال الهدايا
        if action == 'gift':
            try:
                g_id = request.form.get('gid')
                g_qty = int(request.form.get('gq', 1))
                codes = pull_codes(request.form.get('gp'), g_qty)
                if codes:
                    async def send_gift():
                        try:
                            u = await client.fetch_user(int(g_id))
                            await u.send(f"🎁 **هدية من الإدارة!** ({PRODUCTS[request.form.get('gp')]['name']})\n" + "\n".join(codes))
                        except: pass
                    asyncio.run_coroutine_threadsafe(send_gift(), client.loop)
                    flash("تم الإرسال بنجاح ✅", "success")
                else: flash("المخزون غير كافي ❌", "error")
            except: flash("خطأ في البيانات ❌", "error")

        # 2. إضافة كوبون
        elif action == 'add_coupon':
            try:
                db_config.insert({'type':'coupon', 'code':request.form.get('c'), 'discount':int(request.form.get('d')), 'uses':int(request.form.get('u')), 'prod_key':request.form.get('p')})
                flash("تم إضافة الكوبون ✅", "success")
            except: flash("خطأ في الإدخال ❌", "error")

        # 3. تعديل المخزون
        elif action == 'edit_stock':
            try:
                with open(PRODUCTS[request.form.get('pk')]['file'], 'w') as f: f.write(request.form.get('cont').strip() + "\n")
                flash("تم تحديث المخزون ✅", "success")
            except: flash("خطأ في الحفظ ❌", "error")

        # 4. وضع الصيانة
        elif action == 'toggle_m':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
            flash("تم تغيير حالة الصيانة ⚙️", "success")

        # 5. مسح سجل المحادثة (جديد)
        elif action == 'del_history':
            try:
                target_id = int(request.form.get('target_id'))
                async def clear_dm():
                    try:
                        u = await client.fetch_user(target_id)
                        if u.dm_channel is None: await u.create_dm()
                        async for msg in u.dm_channel.history(limit=50):
                            if msg.author == client.user: await msg.delete()
                    except: pass
                asyncio.run_coroutine_threadsafe(clear_dm(), client.loop)
                flash(f"جاري مسح رسائل البوت مع {target_id} 🧹", "success")
            except: flash("ID غير صحيح ❌", "error")

        # 6. نظام الإذاعة (جديد)
        elif action == 'broadcast':
            try:
                b_type = request.form.get('b_type')
                msg_body = request.form.get('msg')
                if b_type == 'single':
                    t_id = int(request.form.get('target_id'))
                    async def send_one():
                        try:
                            u = await client.fetch_user(t_id)
                            await u.send(f"📢 **إعلان هام:**\n{msg_body}")
                        except: pass
                    asyncio.run_coroutine_threadsafe(send_one(), client.loop)
                    flash("تم الإرسال للعضو ✅", "success")
                elif b_type == 'all':
                    # إرسال لكل من اشترى سابقاً (لتجنب الحظر)
                    all_customers = set([o['discord_id'] for o in db_orders.all()])
                    async def send_all():
                        for cid in all_customers:
                            try:
                                u = await client.fetch_user(int(cid))
                                await u.send(f"📢 **إعلان عام من المتجر:**\n{msg_body}")
                                await asyncio.sleep(1) # تأخير لمنع الحظر
                            except: pass
                    asyncio.run_coroutine_threadsafe(send_all(), client.loop)
                    flash(f"جاري الإرسال لـ {len(all_customers)} عميل 📨", "success")
            except: flash("خطأ في الإرسال ❌", "error")

    # تجهيز البيانات
    coupons = db_config.search(Config.type=='coupon')
    stocks = {k: open(v['file']).read() if os.path.exists(v['file']) else "" for k,v in PRODUCTS.items()}
    
    # واجهة الأدمن (Tabs Layout)
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>Admin Panel V36</title>
        <style>
            body { background:#0a0a0a; color:white; font-family:sans-serif; margin:0; padding:20px; }
            /* Toast Notification */
            .toast-container { position:fixed; top:20px; right:20px; z-index:1000; }
            .toast { background:#111; color:white; padding:15px 25px; border-radius:10px; margin-bottom:10px; border-right:5px solid; position:relative; overflow:hidden; animation: slideIn 0.5s; width:300px; box-shadow:0 5px 15px rgba(0,0,0,0.5); }
            .toast.success { border-color:#43b581; } .toast.error { border-color:#e74c3c; }
            .toast-timer { position:absolute; bottom:0; right:0; height:3px; background:rgba(255,255,255,0.7); width:100%; animation: timer 5s linear forwards; }
            @keyframes slideIn { from{transform:translateX(100%)} to{transform:translateX(0)} }
            @keyframes timer { from{width:100%} to{width:0%} }

            /* Tabs Navigation */
            .nav-tabs { display:flex; gap:10px; justify-content:center; margin-bottom:30px; background:#111; padding:10px; border-radius:15px; border:1px solid #333; }
            .tab-btn { background:none; border:none; color:#888; padding:10px 25px; cursor:pointer; font-size:16px; border-radius:10px; transition:0.3s; }
            .tab-btn:hover { color:white; background:rgba(255,255,255,0.05); }
            .tab-btn.active { background:#5865F2; color:white; font-weight:bold; }
            
            /* Content Sections */
            .tab-content { display:none; animation: fadeIn 0.5s; }
            .tab-content.active { display:block; }
            @keyframes fadeIn { from{opacity:0; transform:translateY(10px)} to{opacity:1; transform:translateY(0)} }

            /* Cards & Tables */
            .card { background:#111; padding:25px; border-radius:20px; border:1px solid #333; margin-bottom:20px; }
            input, select, textarea { width:90%; padding:12px; margin:5px 0; background:#000; border:1px solid #333; color:white; border-radius:8px; }
            button { padding:10px 20px; border-radius:8px; border:none; cursor:pointer; font-weight:bold; margin-top:10px; }
            .btn-green { background:#43b581; color:white; width:100%; }
            .btn-blue { background:#5865F2; color:white; width:100%; }
            .btn-red { background:#e74c3c; color:white; }
            table { width:100%; text-align:center; border-collapse:collapse; } th { padding:15px; background:#222; } td { padding:15px; border-bottom:1px solid #333; }
        </style>
    </head>
    <body>
        <div class="toast-container">
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for c, m in messages %}
                  <div class="toast {{c}}">
                      <div style="font-weight:bold; margin-bottom:5px;">{{ 'عملية ناجحة' if c=='success' else 'تنبيه' }}</div>
                      <div>{{m}}</div>
                      <div class="toast-timer"></div>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
        </div>

        <h1 style="text-align:center; color:#5865F2;">لوحة التحكم V36 💎</h1>

        <div class="nav-tabs">
            <button class="tab-btn active" onclick="openTab('home')">🏠 الرئيسية</button>
            <button class="tab-btn" onclick="openTab('orders')">📦 الطلبات</button>
            <button class="tab-btn" onclick="openTab('stock')">📦 المخزون</button>
            <button class="tab-btn" onclick="openTab('tools')">🛠️ الأدوات</button>
            <button class="tab-btn" onclick="openTab('settings')">⚙️ الإعدادات</button>
        </div>

        <div id="home" class="tab-content active">
            <div style="display:flex; gap:20px; justify-content:center; flex-wrap:wrap;">
                <div class="card" style="width:300px;">
                    <h3 style="margin-top:0; color:#8e44ad;">🎁 إرسال هدية</h3>
                    <form method="post"><input type="hidden" name="action" value="gift"><input name="gid" placeholder="ID العميل"><select name="gp">{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><input name="gq" type="number" value="1"><button class="btn-blue" style="background:#8e44ad;">إرسال</button></form>
                </div>
                <div class="card" style="width:350px;">
                    <h3 style="margin-top:0; color:#2ecc71;">🎫 الكوبونات</h3>
                    <div style="height:100px; overflow-y:auto; border:1px solid #333; margin-bottom:10px; padding:5px;">{% for c in coupons %}<div>{{c.code}} ({{c.discount}}%) <a href="/del_c/{{c.doc_id}}" style="color:red;">[x]</a></div>{% endfor %}</div>
                    <form method="post"><input type="hidden" name="action" value="add_coupon"><input name="c" placeholder="الكود"><div style="display:flex; gap:5px;"><input name="d" placeholder="%"><input name="u" placeholder="العدد"></div><select name="p"><option value="all">الكل</option>{% for k,v in prods.items() %}<option value="{{k}}">{{v.name}}</option>{% endfor %}</select><button class="btn-green">إضافة</button></form>
                </div>
            </div>
        </div>

        <div id="orders" class="tab-content">
            <div class="card">
                <h3>📋 آخر الطلبات</h3>
                <table>
                    <tr style="color:#888;"><th>العميل</th><th>المنتج</th><th>السعر</th><th>الحالة</th><th>الإجراء</th></tr>
                    {% for o in orders|reverse %}<tr><td>{{o.discord_id}}</td><td>{{o.prod_name}}</td><td>{{o.total}}</td><td>{{o.status}}</td><td>{% if o.status=='pending' %}<a href="/app/{{o.doc_id}}" style="color:#2ecc71;">[قبول]</a> <a href="/rej/{{o.doc_id}}" style="color:#e74c3c;">[رفض]</a>{% endif %}</td></tr>{% endfor %}
                </table>
            </div>
        </div>

        <div id="stock" class="tab-content">
            <div style="display:flex; gap:15px; flex-wrap:wrap; justify-content:center;">
                {% for k,v in prods.items() %}<div class="card" style="width:280px;"><h4>{{v.name}}</h4><form method="post"><input type="hidden" name="action" value="edit_stock"><input type="hidden" name="pk" value="{{k}}"><textarea name="cont" style="height:80px; font-family:monospace; color:#43b581;">{{stocks[k]}}</textarea><button class="btn-green">حفظ</button></form></div>{% endfor %}
            </div>
        </div>

        <div id="tools" class="tab-content">
            <div style="display:flex; gap:20px; justify-content:center; flex-wrap:wrap;">
                <div class="card" style="width:300px;">
                    <h3 style="margin-top:0; color:#e74c3c;">🗑️ مسح الرسايل</h3>
                    <p style="font-size:12px; color:#888;">يمسح رسائل البوت فقط من الخاص مع العضو</p>
                    <form method="post"><input type="hidden" name="action" value="del_history"><input name="target_id" placeholder="Discord ID"><button class="btn-red">مسح السجل</button></form>
                </div>
                <div class="card" style="width:350px;">
                    <h3 style="margin-top:0; color:#f39c12;">📢 الإذاعة (Broadcast)</h3>
                    <form method="post">
                        <input type="hidden" name="action" value="broadcast">
                        <select name="b_type" onchange="this.value=='single'?document.getElementById('bid').style.display='block':document.getElementById('bid').style.display='none'">
                            <option value="single">عضو محدد</option>
                            <option value="all">كل العملاء السابقين</option>
                        </select>
                        <input name="target_id" id="bid" placeholder="Discord ID">
                        <textarea name="msg" placeholder="اكتب رسالتك هنا.." style="height:80px;"></textarea>
                        <button class="btn-blue" style="background:#f39c12;">إرسال</button>
                    </form>
                </div>
            </div>
        </div>

        <div id="settings" class="tab-content">
            <div class="card" style="text-align:center; max-width:400px; margin:auto;">
                <h3>⚠️ وضع الصيانة</h3>
                <p style="color:#888;">عند التفعيل، لن يظهر زر الشراء للأعضاء.</p>
                <form method="post"><input type="hidden" name="action" value="toggle_m"><button class="btn-blue" style="background:orange; color:black;">تغيير الحالة (تشغيل/إيقاف)</button></form>
            </div>
        </div>

        <script>
            function openTab(id) {
                document.querySelectorAll('.tab-content').forEach(d => d.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.getElementById(id).classList.add('active');
                event.target.classList.add('active');
            }
            // Auto hide toasts
            setTimeout(() => { document.querySelectorAll('.toast').forEach(t => t.style.display='none') }, 5000);
        </script>
    </body></html>
    ''', prods=PRODUCTS, orders=db_orders.all(), coupons=coupons, stocks=stocks)

@app.route('/app/<int:id>')
def approve(id):
    if session.get('logged_in'):
        o = db_orders.get(doc_id=id)
        db_orders.update({'status': 'approved ✅'}, doc_ids=[id])
        
        # إرسال Embed للعميل (أخضر)
        async def send():
            try:
                u = await client.fetch_user(int(o['discord_id']))
                embed = discord.Embed(title="🔥 مبروك! تم تأكيد طلبك", description=f"تم استلام طلبك لـ **{o['prod_name']}** بنجاح!", color=0x43b581)
                codes_str = "\n".join(o['reserved_codes'])
                embed.add_field(name="📦 إليك الأكواد الخاصة بك:", value=f"```{codes_str}```", inline=False)
                embed.set_footer(text="شكراً لثقتك بنا! ❤️")
                await u.send(embed=embed)
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
