import discord
import asyncio
from flask import Flask, request, render_template_string, redirect
from tinydb import TinyDB, Query
import threading
import os
import time

# --- الإعدادات ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"

# ملاحظة: قم باستبدال الروابط أدناه بروابط الصور الحقيقية بعد رفعها على موقع مثل imgur أو discord
PRODUCTS = {
    'xbox': {
        'name': 'Xbox Game Pass Premium', 
        'price': 10, 
        'file': 'xbox.txt', 
        'img': 'blob:https://gemini.google.com/1906d215-6acd-406c-8b08-8fe738d40119' # ضع رابط صورة Xbox هنا
    },
    'nitro1': {
        'name': 'Discord Nitro 1 Month', 
        'price': 5, 
        'file': 'nitro1.txt', 
        'img': 'blob:https://gemini.google.com/8a2b129a-11ba-4634-b575-77aefe313f26' # ضع رابط صورة Nitro 1 Month هنا
    },
    'nitro3': {
        'name': 'Discord Nitro 3 Months', 
        'price': 10, 
        'file': 'nitro3.txt', 
        'img': 'blob:https://gemini.google.com/073d6d4d-01ea-4c1f-be4a-6a83ca293532' # ضع رابط صورة Nitro 3 Months هنا
    }
}

app = Flask(__name__)
db_orders = TinyDB('orders.json')
db_spam = TinyDB('spam_check.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_stock(prod_key):
    filename = PRODUCTS[prod_key]['file']
    if not os.path.exists(filename): return 0
    with open(filename, 'r') as f:
        lines = [l for l in f.readlines() if l.strip()]
    return len(lines)

# --- واجهة المتجر (تصميم الكروت بالصور الشفافة) ---
HTML_STORE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo Store | متجرك المفضل</title>
    <style>
        :root { --main-color: #5865F2; --bg-gray: #0f0f0f; }
        body { background: var(--bg-gray); color: white; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; text-align: center; }
        h1 { margin-bottom: 40px; font-size: 32px; color: #fff; }
        
        .products-container { display: flex; flex-wrap: wrap; justify-content: center; gap: 25px; max-width: 1200px; margin: auto; }
        
        .product-card { 
            width: 300px; height: 450px; border-radius: 20px; 
            position: relative; overflow: hidden; cursor: pointer;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid rgba(255,255,255,0.05);
            background-color: #1a1a1a;
        }
        .product-card:hover { transform: scale(1.03); box-shadow: 0 10px 40px rgba(88, 101, 242, 0.3); }

        /* طبقة الصورة الخلفية */
        .card-bg {
            position: absolute; inset: 0;
            background-size: cover;
            background-position: center;
            opacity: 0.8; /* جعل الصورة شفافة قليلاً لتتناغم مع الخلفية */
            transition: opacity 0.3s ease;
        }
        .product-card:hover .card-bg { opacity: 1; }

        /* تدرج الألوان فوق الصورة لجعل النص واضحاً */
        .card-overlay {
            position: absolute; inset: 0;
            background: linear-gradient(to top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.5) 40%, rgba(0,0,0,0) 100%);
            display: flex; flex-direction: column; justify-content: flex-end;
            padding: 25px;
            z-index: 2;
        }

        .product-card h3 { font-size: 20px; margin: 5px 0; color: #fff; text-shadow: 2px 2px 4px rgba(0,0,0,0.7); }
        .price { font-size: 26px; font-weight: bold; color: #43b581; margin: 5px 0; }
        .stock { font-size: 14px; color: #aaa; margin-bottom: 15px; }

        .order-form { display: none; background: rgba(20, 20, 20, 0.95); padding: 15px; border-radius: 15px; border: 1px solid var(--main-color); margin-top: 10px; }
        input { width: 90%; padding: 10px; margin: 5px 0; border-radius: 8px; border: none; background: #333; color: white; text-align: center; }
        button { background: var(--main-color); color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; }
    </style>
    <script>
        function showForm(id) {
            event.stopPropagation();
            document.querySelectorAll('.order-form').forEach(f => f.style.display = 'none');
            document.getElementById('form-' + id).style.display = 'block';
        }
    </script>
</head>
<body>
    <h1>🔒 Jo Store | متجرك المفضل</h1>
    <div class="products-container">
        {% for key, info in prods.items() %}
        <div class="product-card" onclick="showForm('{{key}}')">
            <div class="card-bg" style="background-image: url('{{ info.img }}');"></div>
            <div class="card-overlay">
                <h3>{{ info.name }}</h3>
                <div class="price">{{ info.price }} جنيه</div>
                <div class="stock">المتوفر: {{ stocks[key] }} قطعة</div>
                
                <div class="order-form" id="form-{{key}}" onclick="event.stopPropagation()">
                    <form action="/place_order" method="post">
                        <input type="hidden" name="prod_key" value="{{key}}">
                        <input type="number" name="quantity" min="1" value="1">
                        <input type="text" name="discord_id" placeholder="ID الديسكورد" required>
                        <input type="text" name="cash_number" placeholder="رقم الكاش" required>
                        <button type="submit">تأكيد الشراء</button>
                    </form>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''

# --- باقي منطق البوت (نفس الكود السابق) ---
@app.route('/')
def home():
    stocks = {k: get_stock(k) for k in PRODUCTS}
    return render_template_string(HTML_STORE, prods=PRODUCTS, stocks=stocks)

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        p_key = request.form.get('prod_key')
        qty = int(request.form.get('quantity', 1))
        d_id = request.form.get('discord_id').strip()
        cash_num = request.form.get('cash_number').strip()
        stock = get_stock(p_key)
        if qty > stock: return "الكمية غير متاحة"
        total = qty * PRODUCTS[p_key]['price']
        db_orders.insert({'discord_id': d_id, 'prod_name': PRODUCTS[p_key]['name'], 'prod_key': p_key, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})
        return redirect(f'/success_page?total={total}')
    except Exception as e: return str(e)

@app.route('/success_page')
def success():
    total = request.args.get('total', '0')
    return f'<body style="background:#0f0f0f;color:white;text-align:center;padding-top:100px;"><h2>✅ تم تسجيل الطلب!</h2><p>حول {total} جنيه للرقم {PAYMENT_NUMBER}</p><a href="/" style="color:#5865F2;">رجوع للمتجر</a></body>'

def run_flask(): app.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
