import discord
import asyncio
from flask import Flask, request, render_template_string, redirect, url_for
from tinydb import TinyDB, Query
import threading
import os
import time

# --- الإعدادات ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"

PRODUCTS = {
    'xbox': {'name': 'Xbox Game Pass Premium', 'price': 10, 'file': 'xbox.txt', 'img': 'https://i.postimg.cc/zD7kMz8R/Screenshot-2026-02-07-152934.png'},
    'nitro1': {'name': 'Discord Nitro 1 Month', 'price': 5, 'file': 'nitro1.txt', 'img': 'https://i.postimg.cc/jqch9xtC/Screenshot-2026-02-07-152844.png'},
    'nitro3': {'name': 'Discord Nitro 3 Months', 'price': 10, 'file': 'nitro3.txt', 'img': 'https://i.postimg.cc/xj5P7fnN/Screenshot-2026-02-07-152910.png'}
}

app = Flask(__name__)
db_orders = TinyDB('orders.json')
db_spam = TinyDB('spam_check.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# --- واجهة المتجر المتطورة ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | متجرك المفضل</title>
    <style>
        :root { --main-color: #5865F2; --bg-black: #0a0a0a; }
        body { background: var(--bg-black); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; transition: 0.5s; }
        
        .menu-btn { position: fixed; top: 20px; left: 20px; font-size: 30px; cursor: pointer; z-index: 1001; color: white; background: none; border: none; }

        .sidebar {
            height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; left: 0;
            background-color: #111; overflow-x: hidden; transition: 0.5s; padding-top: 60px;
            border-right: 1px solid #222;
        }
        .sidebar a, .sidebar .section-title { padding: 10px 20px; text-decoration: none; display: block; text-align: right; }
        .sidebar a { font-size: 18px; color: #818181; transition: 0.3s; }
        .sidebar a:hover { color: var(--main-color); background: rgba(88,101,242,0.1); }
        .section-title { font-weight: bold; color: var(--main-color); font-size: 14px; margin-top: 20px; border-bottom: 1px solid #222; }
        .sidebar .close-btn { position: absolute; top: 10px; right: 20px; font-size: 36px; color: white; cursor: pointer; }

        /* ميزة تغيير الألوان */
        .color-picker { display: flex; gap: 10px; padding: 10px 20px; }
        .dot { height: 20px; width: 20px; border-radius: 50%; cursor: pointer; border: 2px solid white; }

        #main-content { transition: margin-left .5s; padding: 20px; text-align: center; }
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; margin-top: 50px; }
        
        .product-card { 
            width: 320px; height: 480px; border-radius: 25px; 
            position: relative; overflow: hidden; cursor: pointer;
            transition: 0.4s ease; border: 1px solid #222;
        }
        .product-card:hover { transform: translateY(-10px); border-color: var(--main-color); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
        .card-image { position: absolute; inset: 0; background-size: cover; background-position: center; z-index: 1; }
        .card-overlay {
            position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.4) 40%, rgba(0,0,0,0) 100%);
            z-index: 2; display: flex; flex-direction: column; justify-content: flex-end; padding: 25px;
        }
        .price { font-size: 24px; font-weight: bold; color: #43b581; }
        .order-form { display: none; background: rgba(15, 15, 15, 0.98); padding: 15px; border-radius: 15px; border: 1px solid var(--main-color); margin-top: 10px; position: relative; z-index: 10; }
        input { width: 90%; padding: 10px; margin: 5px 0; border-radius: 8px; border: none; background: #222; color: white; text-align: center; }
        button { background: var(--main-color); color: white; border: none; padding: 12px; border-radius: 10px; cursor: pointer; width: 100%; font-weight: bold; }
        
        /* قسم FAQ والآراء الصغير */
        .info-box { font-size: 13px; color: #aaa; padding: 10px 20px; line-height: 1.6; }
    </style>
</head>
<body>
    <div id="mySidebar" class="sidebar">
        <span class="close-btn" onclick="closeNav()">&times;</span>
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkMyOrders()">📋 طلباتي</a>
        
        <div class="section-title">تخصيص اللون</div>
        <div class="color-picker">
            <div class="dot" style="background:#5865F2" onclick="changeColor('#5865F2')"></div>
            <div class="dot" style="background:#9b59b6" onclick="changeColor('#9b59b6')"></div>
            <div class="dot" style="background:#2ecc71" onclick="changeColor('#2ecc71')"></div>
        </div>

        <div class="section-title">الأسئلة الشائعة</div>
        <div class="info-box">
            ❓ <b>متى يصل الكود؟</b><br> بعد مراجعة التحويل يدوياً (خلال 5-30 دقيقة).<br>
            ❓ <b>كيف أفعل الكود؟</b><br> سنرسل لك الطريقة في الخاص.
        </div>

        <div class="section-title">آراء العملاء</div>
        <div class="info-box" id="reviews">
            ⭐ "أفضل متجر وأسرع تسليم" - <i>Abdo</i><br>
            ⭐ "ثقة ومضمون 100%" - <i>Mazen</i>
        </div>
        
        <a href="https://discord.gg/RYK28PNv" target="_blank">💬 سيرفر الديسكورد</a>
    </div>

    <button class="menu-btn" onclick="openNav()">&#9776;</button>

    <div id="main-content">
        <h1 style="margin-top:60px;">Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div class="price">{{ info.price }} جنيه</div>
                    <div class="stock">المتوفر: {{ stocks[key] }} قطعة</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش المحول منه" required>
                            <button type="submit">تأكيد الشراء الآن</button>
                        </form>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        function openNav() { document.getElementById("mySidebar").style.width = "250px"; document.getElementById("main-content").style.marginLeft = "250px"; }
        function closeNav() { document.getElementById("mySidebar").style.width = "0"; document.getElementById("main-content").style.marginLeft = "0"; }
        function showForm(id) { event.stopPropagation(); document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none'); document.getElementById('form-' + id).style.display = 'block'; }
        function changeColor(color) { document.documentElement.style.setProperty('--main-color', color); }
        function checkMyOrders() {
            let id = prompt("أدخل ID الديسكورد الخاص بك:");
            if (id) { window.location.href = "/my_orders/" + id; }
        }
    </script>
</body>
</html>
'''

# --- صفحة طلباتي المتطورة ---
@app.route('/my_orders/<user_id>')
def my_orders(user_id):
    user_orders = db_orders.search(Order.discord_id == user_id)
    return render_template_string('''
    <body style="background:#0a0a0a; color:white; font-family:sans-serif; text-align:center; padding:20px;">
        <h2 style="color:#5865F2;">📋 تتبع طلباتك</h2>
        <div style="max-width:600px; margin:auto;">
            {% for o in orders %}
            <div style="background:#111; padding:15px; border-radius:15px; margin-bottom:10px; border:1px solid #222; text-align:right;">
                <b style="font-size:18px;">{{ o.prod_name }}</b><br>
                <small>القيمة: {{ o.total }} ج.م</small><br>
                {% if 'approved' in o.status %}
                <span style="color:#2ecc71; font-weight:bold;">● تم التسليم (افحص الخاص في ديسكورد)</span>
                {% elif 'rejected' in o.status %}
                <span style="color:#e74c3c; font-weight:bold;">● مرفوض (تواصل مع الإدارة)</span>
                {% else %}
                <span style="color:#f1c40f; font-weight:bold;">● قيد المراجعة اليدوية...</span>
                {% endif %}
            </div>
            {% endfor %}
            {% if not orders %} <p>لا توجد طلبات مسجلة لهذا الـ ID</p> {% endif %}
        </div>
        <br><a href="/" style="color:#5865F2; text-decoration:none;">← العودة للمتجر</a>
    </body>
    ''', orders=user_orders)

# (باقي كود البوت والـ Flask كما هو في الرد السابق تماماً)
# ...
@app.route('/')
def home():
    stocks = {k: int(open(PRODUCTS[k]['file']).read().count('\\n'))+1 if os.path.exists(PRODUCTS[k]['file']) else 0 for k in PRODUCTS}
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks)

# (باقي الدوال: place_order, success_page, admin_panel, approve, reject, get_code_prod, run_flask, on_ready)
# تأكد من وضع الكود الباقي هنا لتشغيل البوت.
def run_flask(): app.run(host='0.0.0.0', port=10000)
@client.event
async def on_ready(): client.loop = asyncio.get_running_loop()
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
