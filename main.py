import discord
import asyncio
from flask import Flask, request, render_template_string, redirect
from tinydb import TinyDB, Query
import threading
import os

# --- الإعدادات ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896 
PAYMENT_NUMBER = "01007324726"
PRODUCT_PRICE = 5

app = Flask(__name__)
db_orders = TinyDB('orders.json')
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# --- الواجهة الرئيسية ---
HTML_STORE = f'''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>متجر جو الرقمي</title>
    <style>
        body {{ background: #121212; color: white; font-family: sans-serif; text-align: center; padding: 20px; }}
        .card {{ background: #1e1e1e; padding: 30px; border-radius: 20px; display: inline-block; width: 90%; max-width: 400px; border: 1px solid #333; }}
        input {{ width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: none; background: #2c2f33; color: white; box-sizing: border-box; }}
        button {{ background: #5865F2; color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2 style="color:#5865F2;">🛍️ Xbox Codes Shop</h2>
        <p style="color:#43b581;">السعر الحالي: {PRODUCT_PRICE} جنيه</p>
        <form action="/place_order" method="post">
            <input type="number" name="quantity" placeholder="الكمية" min="1" value="1">
            <input type="text" name="discord_id" placeholder="الـ Discord ID الخاص بك" required>
            <input type="text" name="cash_number" placeholder="رقم الكاش المحول منه" required>
            <button type="submit">إتمام الطلب</button>
        </form>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_STORE)

@app.route('/place_order', methods=['POST'])
def place_order():
    try:
        qty = int(request.form.get('quantity', 1))
        d_id = request.form.get('discord_id').strip()
        cash_num = request.form.get('cash_number').strip()
        total = qty * PRODUCT_PRICE
        
        # حفظ الطلب
        doc_id = db_orders.insert({'discord_id': d_id, 'quantity': qty, 'cash_number': cash_num, 'total': total, 'status': 'pending'})

        async def notify():
            try:
                admin = await client.fetch_user(ADMIN_DISCORD_ID)
                await admin.send(f"🔔 **طلب جديد!**\nالمبلغ: {total} جنيه\nلوحة التحكم: https://daily-code-bot-1.onrender.com/admin_jo_secret")
            except: pass
        
        asyncio.run_coroutine_threadsafe(notify(), client.loop)

        return f'''
        <body style="background:#121212; color:white; text-align:center; padding-top:50px; font-family:sans-serif;">
            <div style="background:#1e1e1e; padding:30px; border-radius:15px; display:inline-block; border:2px solid #5865F2;">
                <h2 style="color:#43b581;">✅ تم تسجيل طلبك!</h2>
                <p>حول مبلغ <b>{total} جنيه</b> لرقم:</p>
                <h1 style="background:#2c2f33; padding:10px;">{PAYMENT_NUMBER}</h1>
                <p>سيتم إرسال السلعة لك فور قبول الطلب.</p>
            </div>
        </body>
        '''
    except Exception as e: return f"Error: {e}"

# --- لوحة التحكم ---
@app.route('/admin_jo_secret')
def admin_panel():
    all_orders = []
    for item in db_orders.all():
        item['doc_id'] = item.doc_id
        all_orders.append(item)
    
    return render_template_string('''
    <body style="background:#121212; color:white; font-family:sans-serif; text-align:center;">
        <h2>🛠️ لوحة تحكم الطلبات</h2>
        <table border="1" style="width:95%; margin:auto; background:#1e1e1e; border-collapse:collapse;">
            <tr style="background:#5865F2;">
                <th>الكمية</th><th>رقم الكاش</th><th>المبلغ</th><th>الحالة</th><th>الإجراء</th>
            </tr>
            {% for order in orders %}
            <tr>
                <td>{{ order.quantity }}</td><td>{{ order.cash_number }}</td>
                <td>{{ order.total }}</td><td>{{ order.status }}</td>
                <td>
                    {% if order.status == 'pending' %}
                    <a href="/admin/approve/{{ order.doc_id }}" style="color:#43b581; text-decoration:none;">[قبول ✅]</a> | 
                    <a href="/admin/reject/{{ order.doc_id }}" style="color:#f04747; text-decoration:none;">[رفض ❌]</a>
                    {% else %} {{ order.status }} {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
        <br><a href="/" style="color:#5865F2;">العودة للمتجر</a>
    </body>
    ''', orders=all_orders)

@app.route('/admin/approve/<int:order_id>')
def approve(order_id):
    order = db_orders.get(doc_id=order_id)
    if order:
        db_orders.update({'status': 'approved ✅'}, doc_id=order_id)
        
        async def send_item():
            try:
                user = await client.fetch_user(int(order['discord_id']))
                # هنا بنسحب أول كود من الملف عشان نبعته
                item_to_send = "شكراً لشرائك! إليك الكود الخاص بك: " + (get_code_from_file() or "عذراً، نفدت الأكواد!")
                await user.send(f"✅ **تم قبول طلبك بنجاح!**\n{item_to_send}")
            except Exception as e: print(f"DM Error: {e}")
            
        asyncio.run_coroutine_threadsafe(send_item(), client.loop)
    return redirect('/admin_jo_secret')

@app.route('/admin/reject/<int:order_id>')
def reject(order_id):
    db_orders.update({'status': 'rejected ❌'}, doc_id=order_id)
    return redirect('/admin_jo_secret')

def get_code_from_file():
    if not os.path.exists('codes.txt'): return None
    with open('codes.txt', 'r') as f: lines = f.readlines()
    if not lines: return None
    code = lines[0].strip()
    with open('codes.txt', 'w') as f: f.writelines(lines[1:])
    return code

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

@client.event
async def on_ready():
    print(f'✅ المتجر يعمل: {client.user}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN: client.run(TOKEN)
