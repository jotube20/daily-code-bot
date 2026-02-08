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
app.secret_key = 'jo_store_secret_key_pro_mode_final_v2'  # مفتاح الجلسة

db_orders = TinyDB('orders.json')
db_feedbacks = TinyDB('feedbacks.json')
db_config = TinyDB('config.json')  # لحفظ إعدادات الصيانة وكوبونات الخصم
Order = Query()
Config = Query()

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --- الدوال البرمجية (المخزون الذكي) ---
def get_stock(prod_key):
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename):
        return 0
    with open(filename, 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

def pull_codes(p_key, qty):
    """يسحب الأكواد من الملف فوراً لحجزها في الطلب"""
    filename = PRODUCTS[p_key]['file']
    if not os.path.exists(filename):
        return []
    with open(filename, 'r') as f: 
        lines = [l for l in f.readlines() if l.strip()]
    
    if len(lines) < qty:
        return []
    
    pulled = lines[:qty]
    remaining = lines[qty:]
    
    with open(filename, 'w') as f: 
        f.writelines(remaining)
    return [c.strip() for c in pulled]

def return_codes(p_key, codes):
    """يعيد الأكواد للمخزون في حالة الرفض"""
    filename = PRODUCTS[p_key]['file']
    with open(filename, 'a') as f:
        for c in codes:
            f.write(c + "\n")

# --- دوال الإضافات الجديدة ---
def is_maintenance_mode():
    res = db_config.get(Config.type == 'maintenance')
    return res['status'] if res else False

def get_discount(code, prod_key):
    """التحقق من الكود: الصلاحية، الموقت، والمنتج المحدد"""
    res = db_config.get((Config.type == 'coupon') & (Config.code == code))
    if res:
        # التحقق من المنتج المحدد
        if res['prod_key'] != 'all' and res['prod_key'] != prod_key:
            return None
        # التحقق من عدد الاستخدامات
        if res['uses'] <= 0:
            return None
        # التحقق من تاريخ الانتهاء
        expire_time = datetime.fromisoformat(res['expires_at'])
        if datetime.now() > expire_time:
            return None
        return res
    return None

def use_coupon(code):
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
            overflow-x: hidden;
            transition: 0.5s;
        }
        
        /* كبسولة التحكم الزجاجية الاحترافية */
        .glass-nav {
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1001;
            display: flex;
            gap: 15px;
            background: rgba(128, 128, 128, 0.15);
            backdrop-filter: blur(12px);
            padding: 10px 20px;
            border-radius: 25px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        }

        .nav-btn {
            background: none;
            border: none;
            color: var(--text-color);
            font-size: 26px;
            cursor: pointer;
            transition: 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .nav-btn:hover {
            color: var(--main-color);
            transform: scale(1.1);
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
            transition: 0.5s;
            padding-top: 60px;
            border-right: 1px solid #222;
        }
        
        .sidebar a {
            padding: 10px 20px;
            text-decoration: none;
            display: block;
            text-align: right;
            color: #818181;
            font-size: 18px;
        }
        
        .sidebar a:hover {
            color: var(--text-color);
            background: rgba(88,101,242,0.1);
        }
        
        .section-title {
            padding: 10px 20px;
            color: var(--main-color);
            font-weight: bold;
            font-size: 14px;
            border-bottom: 1px solid #222;
            margin-top: 15px;
        }
        
        #main-content {
            padding: 20px;
            text-align: center;
        }
        
        .products-container {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 30px;
            margin-top: 50px;
        }
        
        .product-card {
            width: 320px;
            height: 480px;
            border-radius: 25px;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: 0.4s;
            border: 1px solid #222;
            background: var(--card-bg);
        }
        
        .card-image {
            position: absolute;
            inset: 0;
            background-size: cover;
            background-position: center;
            z-index: 1;
        }
        
        .card-overlay {
            position: absolute;
            inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.3) 35%, rgba(0,0,0,0) 70%);
            z-index: 2;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: 25px;
        }
        
        .order-form {
            display: none;
            background: rgba(15, 15, 15, 0.98);
            padding: 15px;
            border-radius: 15px;
            border: 1px solid var(--main-color);
            margin-top: 10px;
            position: relative;
            z-index: 10;
        }
        
        input, textarea {
            width: 90%;
            padding: 10px;
            margin: 5px 0;
            border-radius: 8px;
            border: none;
            background: #222;
            color: white;
            text-align: center;
        }
        
        button {
            background: var(--main-color);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 10px;
            cursor: pointer;
            width: 100%;
            font-weight: bold;
        }
        
        .feedback-item {
            background: var(--card-bg);
            margin: 10px 20px;
            padding: 10px;
            border-radius: 10px;
            font-size: 12px;
            border-right: 3px solid var(--main-color);
            text-align: right;
            border: 1px solid #333;
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
        <button class="nav-btn" onclick="toggleNav()" title="خيارات القائمة">&#9776;</button>
        <div style="width: 1px; background: rgba(255,255,255,0.1); margin: 5px 0;"></div>
        <button class="nav-btn" onclick="toggleTheme()" title="تغيير الوضع الليلي">🌓</button>
    </div>

    <div id="mySidebar" class="sidebar">
        <a href="/">🏠 الرئيسية</a>
        <a href="#" onclick="checkOrders()">📋 طلباتي</a>
        <div class="section-title">أضف رأيك</div>
        <form action="/add_feedback" method="post" style="padding: 10px 20px;">
            <input type="text" name="user_name" placeholder="اسمك" required>
            <textarea name="comment" placeholder="رأيك في المتجر" required></textarea>
            <button type="submit" style="font-size: 12px; padding: 5px;">إرسال</button>
        </form>
        <div class="section-title">آراء العملاء الحقيقية</div>
        {% for f in feedbacks %}
        <div class="feedback-item">
            <b>{{ f.name }}:</b> {{ f.comment }}
        </div>
        {% endfor %}
    </div>

    <div id="main-content">
        <h1>Jo Store | متجرك المفضل 🔒</h1>
        <div class="products-container">
            {% for key, info in prods.items() %}
            <div class="product-card" onclick="showForm('{{key}}')">
                <div class="card-image" style="background-image: url('{{ info.img }}');"></div>
                <div class="card-overlay">
                    <h3>{{ info.name }}</h3>
                    <div style="color:#43b581; font-weight:bold; font-size:24px;">{{ info.price }} جنيه</div>
                    <div style="color:#ccc; font-size:14px; margin-bottom:10px;">المتوفر: {{ stocks[key] }} قطعة</div>
                    <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                        <div class="warning-text">⚠️ اكتب معلوماتك بحرص لضمان وصول السلعة لك</div>
                        <form action="/place_order" method="post">
                            <input type="hidden" name="prod_key" value="{{key}}">
                            <input type="number" name="quantity" min="1" value="1">
                            <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                            <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                            <input type="text" name="coupon" placeholder="كود الخصم (Optional)" style="border: 1px dashed #43b581;">
                            <button type="submit">تأكيد الشراء الآن</button>
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
            if (side.style.width === "250px") {
                side.style.width = "0";
            } else {
                side.style.width = "250px";
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
            let id = prompt("أدخل ID الديسكورد الخاص بك:"); 
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
        <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
            <h1 style="font-size:50px;">🚧 الموقع في وضع الصيانة حالياً</h1>
            <p>نعمل على بعض التحديثات، عد لاحقاً!</p>
        </body>''')
        
    stocks = {k: get_stock(k) for k in PRODUCTS}
    feedbacks = db_feedbacks.all()[-5:]
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks, feedbacks=feedbacks)

@app.route('/place_order', methods=['POST'])
def place_order():
    if is_maintenance_mode() and not session.get('logged_in'):
        return "الموقع في الصيانة"
        
    p_key = request.form.get('prod_key')
    qty = int(request.form.get('quantity', 1))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    coupon_code = request.form.get('coupon', '').strip()

    # حجز الأكواد فوراً من الكمية
    reserved = pull_codes(p_key, qty)
    if not reserved:
        return "عذراً، المخزون غير كافٍ حالياً."
    
    total = qty * PRODUCTS[p_key]['price']
    discount_msg = ""
    
    if coupon_code:
        # التحقق من كود الخصم (الوقت + المنتج)
        cp = get_discount(coupon_code, p_key)
        if cp:
            total -= total * (cp['discount'] / 100)
            use_coupon(coupon_code)
            discount_msg = f" (تم تطبيق خصم {cp['discount']}%)"

    db_orders.insert({
        'discord_id': d_id, 
        'prod_name': PRODUCTS[p_key]['name'], 
        'prod_key': p_key, 
        'quantity': qty, 
        'cash_number': cash_num, 
        'total': total, 
        'status': 'pending',
        'time': datetime.now().strftime("%I:%M %p"),
        'codes': reserved # حفظ الأكواد المحجوزة في الطلب
    })
    
    async def notify():
        try:
            if not client.is_ready(): return
            user = await client.fetch_user(int(d_id))
            # رسالة العميل منظمة
            await user.send(
                f"تم استلام طلبك لـ ({PRODUCTS[p_key]['name']}) بنجاح!\n"
                f"⌛ سيتم مراجعة الدفع وإرسال الأكواد لك فوراً."
            )
            
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            # رسالة الإدارة منظمة في أسطر حقيقية
            admin_msg = (
                f"🔔 **طلب جديد!**\n"
                f"👤 **العميل:** <@{d_id}>\n"
                f"📦 **المنتج:** {PRODUCTS[p_key]['name']}\n"
                f"💰 **المبلغ:** {total} ج.م{discount_msg}\n"
                f"📱 **من رقم:** {cash_num}"
            )
            await admin.send(admin_msg)
        except:
            pass

    if client.loop:
        asyncio.run_coroutine_threadsafe(notify(), client.loop)
        
    return redirect(f'/success_page?total={total}')

# --- لوحة التحكم (محمية بكلمة سر) ---
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect('/admin_jo_secret')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:100px;font-family:sans-serif;">
        <form method="post">
            <h2>🔐 تسجيل دخول الأدمن</h2>
            <input type="password" name="password" style="padding:10px;text-align:center;"><br><br>
            <button type="submit" style="padding:10px 30px;background:#5865F2;color:white;border:none;border-radius:10px;">دخول</button>
        </form>
    </body>''')

@app.route('/admin_jo_secret', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('logged_in'):
        return redirect('/admin_login')
    
    if request.method == 'POST':
        action = request.form.get('action')
        p_key = request.form.get('p_key')
        
        if action == 'restock':
            new_codes = request.form.get('codes', '').strip()
            if new_codes:
                with open(PRODUCTS[p_key]['file'], 'a') as f:
                    f.write(new_codes + "\n")
        elif action == 'edit_stock':
            content = request.form.get('full_content', '').strip()
            with open(PRODUCTS[p_key]['file'], 'w') as f:
                f.write(content + "\n")
        elif action == 'clear_logs':
            db_orders.remove(Order.discord_id == request.form.get('u_id'))
        elif action == 'toggle_maintenance':
            curr = is_maintenance_mode()
            db_config.upsert({'type': 'maintenance', 'status': not curr}, Config.type == 'maintenance')
        elif action == 'add_coupon':
            # تحديد وقت انتهاء الكود بالدقائق
            minutes = int(request.form.get('c_minutes', 60))
            expire_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
            db_config.insert({
                'type': 'coupon', 
                'code': request.form.get('c_code'), 
                'discount': int(request.form.get('c_disc')), 
                'uses': int(request.form.get('c_uses')),
                'prod_key': request.form.get('c_prod'), # المنتج المحدد
                'expires_at': expire_at
            })
        elif action == 'gift':
            g_id = request.form.get('g_id')
            g_p = request.form.get('g_p')
            g_q = int(request.form.get('g_q', 1))
            gift_codes = pull_codes(g_p, g_q)
            if gift_codes:
                async def deliver_gift():
                    try:
                        u = await client.fetch_user(int(g_id))
                        msg = (
                            f"🎁 **لقد استلمت هدية من الإدارة!**\n"
                            f"📦 **المنتج:** {PRODUCTS[g_p]['name']}\n"
                            f"الأكواد:\n" + "\n".join([f"🔗 {c}" for c in gift_codes])
                        )
                        await u.send(msg)
                    except: pass
                if client.loop: asyncio.run_coroutine_threadsafe(deliver_gift(), client.loop)

    orders = [dict(item, doc_id=item.doc_id) for item in db_orders.all()]
    stock_contents = {k: open(v['file'], 'r').read().strip() if os.path.exists(v['file']) else "" for k,v in PRODUCTS.items()}
    m_txt = "مفعل 🔴" if is_maintenance_mode() else "معطل 🟢"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <style>
            body { background:#0a0a0a; color:white; font-family:sans-serif; padding:20px; }
            .card { background:#111; padding:20px; border-radius:15px; border:1px solid #222; margin-bottom:20px; }
            .grid { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
            input, select, textarea { width:100%; padding:10px; background:#000; color:white; border:1px solid #333; margin-top:10px; border-radius:8px; }
            button { width:100%; padding:12px; margin-top:10px; border-radius:10px; border:none; color:white; font-weight:bold; cursor:pointer; }
            table { width:100%; text-align:center; border-collapse:collapse; margin-top:20px; }
            th { background:#5865F2; padding:15px; } 
            td { padding:15px; border-bottom:1px solid #222; }
            .btn-back { position:absolute; top:20px; left:20px; background:#333; padding:10px 20px; border-radius:10px; text-decoration:none; color:white; }
        </style>
    </head>
    <body>
        <a href="/" class="btn-back">⬅️ العودة للمتجر</a>
        <h2 style="text-align:center; color:#5865F2;">🛠️ لوحة التحكم الإحترافية</h2>
        
        <div class="grid">
            <div class="card" style="width:300px;">
                <h3>🛡️ الصيانة ({{m_txt}})</h3>
                <form method="post">
                    <input type="hidden" name="action" value="toggle_maintenance">
                    <button style="background:#f39c12;">تبديل الوضع</button>
                </form>
            </div>
            
            <div class="card" style="width:300px;">
                <h3>🎁 إرسال هدية</h3>
                <form method="post">
                    <input type="hidden" name="action" value="gift">
                    <input type="text" name="g_id" placeholder="ID العميل">
                    <select name="g_p">
                        {% for k,v in prods.items() %}
                        <option value="{{k}}">{{v.name}}</option>
                        {% endfor %}
                    </select>
                    <input type="number" name="g_q" value="1" placeholder="الكمية">
                    <button style="background:#8e44ad;">إرسال الهدية</button>
                </form>
            </div>
            
            <div class="card" style="width:300px;">
                <h3>🎫 كود خصم ذكي</h3>
                <form method="post">
                    <input type="hidden" name="action" value="add_coupon">
                    <input type="text" name="c_code" placeholder="الكود" required>
                    <input type="number" name="c_disc" placeholder="الخصم %" required>
                    <input type="number" name="c_uses" placeholder="عدد المرات" required>
                    <input type="number" name="c_minutes" placeholder="الصلاحية (بالدقائق)" required>
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
            <h3>📝 تعديل المخزون المباشر</h3>
            <div class="grid">
                {% for k, content in stock.items() %}
                <div style="width:300px;">
                    <h4>{{prods[k].name}}</h4>
                    <form method="post">
                        <input type="hidden" name="action" value="edit_stock">
                        <input type="hidden" name="p_key" value="{{k}}">
                        <textarea name="full_content" style="height:100px;">{{content}}</textarea>
                        <button style="background:#2ecc71;">حفظ التعديل</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="card">
            <h3>📦 طلبات الزبائن</h3>
            <table>
                <thead>
                    <tr>
                        <th>العميل</th>
                        <th>الوقت</th>
                        <th>المنتج</th>
                        <th>المبلغ</th>
                        <th>الإجراء</th>
                    </tr>
                </thead>
                <tbody>
                    {% for o in orders|reverse %}
                    <tr>
                        <td>@{{o.discord_id}}</td>
                        <td>{{o.time}}</td>
                        <td>{{o.prod_name}}</td>
                        <td>{{o.total}} ج.م</td>
                        <td>
                            {% if o.status == 'pending' %}
                            <a href="/approve/{{o.doc_id}}" style="color:green;text-decoration:none;font-weight:bold;">Approve</a> | 
                            <a href="/reject/{{o.doc_id}}" style="color:red;text-decoration:none;font-weight:bold;">Decline</a>
                            {% else %}
                            {{o.status}}
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </body>
    </html>''', orders=orders, stock=stock_contents, prods=PRODUCTS, m_txt=m_txt)

@app.route('/approve/<int:order_id>')
def approve(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        db_orders.update({'status': 'approved ✅'}, doc_ids=[order_id])
        async def deliver():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                codes_msg = "\n".join([f"🔗 {c}" for c in order['codes']])
                await user.send(
                    f"🔥 **مبروك! تم تأكيد طلبك لـ ({order['prod_name']})**\n\n"
                    f"**إليك الأكواد الخاصة بك:**\n{codes_msg}\n\n"
                    f"*يمكنك نسخ الروابط مباشرة بالضغط عليها.*"
                )
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(deliver(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/reject/<int:order_id>')
def reject(order_id):
    if not session.get('logged_in'): return redirect('/admin_login')
    order = db_orders.get(doc_id=order_id)
    if order and order['status'] == 'pending':
        return_codes(order['prod_key'], order.get('codes', []))
        db_orders.update({'status': 'rejected ❌'}, doc_ids=[order_id])
        async def notify():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                await user.send("❌ **نعتذر، تم رفض طلبك لعدم استلام مبلغ التحويل.**")
            except: pass
        if client.loop: asyncio.run_coroutine_threadsafe(notify(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/success_page')
def success_page():
    total = request.args.get('total')
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding-top:60px;font-family:sans-serif;">
        <div style="border:1px solid #5865F2;padding:30px;border-radius:15px;display:inline-block;max-width:500px;">
            <h2 style="color:#43b581;">تم تسجيل الطلب بنجاح</h2>
            <p>حول مبلغ <b>{{total}} جنيه</b> للرقم:</p>
            <h1 style="background:#222;padding:15px;border-radius:10px; color:#fff;">{{pay_num}}</h1>
            
            <div style="background:rgba(88,101,242,0.1);padding:15px;border-radius:10px;border:1px solid #5865F2;margin:20px 0;text-align:center; font-size:14px; line-height:1.6;">
                🔍 يمكنك تتبع حالة طلبك من <b>(صفحة الطلبات)</b> في القائمة.<br>
                ✍️ يسعدنا كتابة رأيك في الخدمة من <b>(مكان الآراء في الـ Options)</b>.
            </div>

            <div style="background:rgba(255,204,0,0.1);padding:15px;border-radius:10px;border:1px solid #ffcc00;margin:20px 0;text-align:right; font-size:13px;">
                <b style="color:#ffcc00;">⚠️ ملحوظة هامة:</b><br>
                يجب عليك دخول سيرفر الديسكورد <a href="https://discord.gg/RYK28PNv" style="color: #5865F2; font-weight: bold;">هنا</a> 
                ليستطيع البوت إرسال الكود لك وتأكد أن خاصك مفتوح وإلا لن يصلك الكود.
            </div>
            <a href="/" style="color:#5865F2;text-decoration:none; font-weight: bold;">العودة للمتجر</a>
        </div>
    </body>''', total=total, pay_num=PAYMENT_NUMBER)

@app.route('/my_orders/<uid>')
def my_orders(uid):
    orders = db_orders.search(Order.discord_id == uid)
    return render_template_string('''
    <body style="background:#0a0a0a;color:white;text-align:center;padding:20px; font-family: sans-serif;">
        <h2 style="color:#5865F2;">📋 تتبع طلباتك</h2>
        <div style="max-width:600px; margin:auto;">
        {% for o in orders %}
            <div style="background:#111;padding:15px;margin:10px;border-radius:15px; border: 1px solid #222; text-align:right;">
                <b>{{o.prod_name}}</b><br>
                <small>المبلغ: {{o.total}} ج.م</small>
                <div style="height:12px; background:#333; border-radius:6px; margin:15px 0; overflow:hidden; border: 1px solid #444;">
                    <div style="width:{% if 'approved' in o.status %}100%{% elif 'rejected' in o.status %}100%{% else %}50%{% endif %}; height:100%; transition: 0.5s; background:{% if 'approved' in o.status %}#2ecc71{% elif 'rejected' in o.status %}#e74c3c{% else %}#f1c40f{% endif %};"></div>
                </div>
                الحالة: {{o.status}}
            </div>
        {% endfor %}
        {% if not orders %} <p>لا توجد طلبات لهذا الـ ID</p> {% endif %}
        </div>
        <br><a href="/" style="color:#5865F2; font-weight:bold; text-decoration:none;">← العودة للمتجر</a>
    </body>''', orders=orders)

@app.route('/add_feedback', methods=['POST'])
def add_feedback():
    ip = request.remote_addr
    db_feedbacks.insert({'name': request.form.get('user_name'), 'comment': request.form.get('comment'), 'ip': ip})
    return redirect('/')

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

