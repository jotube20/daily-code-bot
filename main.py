import discord
import asyncio
from flask import Flask, request, render_template_string
from tinydb import TinyDB, Query
import threading
import os

# --- الإعدادات ---
TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
ADMIN_DISCORD_ID = 1054749887582969896  # !!! ضغ هنا الـ ID الخاص بك لتصلك رسائل الطلبات !!!
PAYMENT_NUMBER = "01007324726"
PRODUCT_PRICE = 5

app = Flask(__name__)
db_orders = TinyDB('orders.json') # قاعدة بيانات الطلبات
Order = Query()

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# --- واجهة المتجر ---
HTML_TEMPLATE = f'''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo's Store - متجر جو</title>
    <style>
        body {{ background-color: #121212; color: white; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 20px; }}
        .card {{ background: #1e1e1e; padding: 30px; border-radius: 20px; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.5); max-width: 400px; width: 90%; }}
        h2 {{ color: #5865F2; margin-bottom: 10px; }}
        .price-tag {{ font-size: 1.2em; color: #43b581; font-weight: bold; margin-bottom: 20px; }}
        input {{ width: 100%; padding: 12px; margin: 10px 0; border-radius: 8px; border: 1px solid #333; background: #2c2f33; color: white; box-sizing: border-box; }}
        button {{ background: #5865F2; color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 16px; transition: 0.3s; }}
        button:hover {{ background: #4752c4; transform: translateY(-2px); }}
        .info {{ font-size: 0.9em; color: #b9bbbe; margin-top: 15px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🛍️ متجر Jo الرقمي</h2>
        <div class="price-tag">سعر المنتج: {PRODUCT_PRICE} جنيه</div>
        <form action="/place_order" method="post">
            <input type="number" name="quantity" placeholder="الكمية المطلوبة" min="1" value="1" required>
            <input type="text" name="discord_id" placeholder="الـ Discord ID الخاص بك" required>
            <input type="text" name="cash_number" placeholder="رقم الكاش الذي ستحول منه" required>
            <button type="submit">إتمام الطلب (Complete Order)</button>
        </form>
        <div class="info">سيتم مراجعة طلبك وإرسال المنتج في الخاص فور التأكد من التحويل.</div>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/place_order', methods=['POST'])
def place_order():
    qty = int(request.form.get('quantity'))
    d_id = request.form.get('discord_id').strip()
    cash_num = request.form.get('cash_number').strip()
    total_price = qty * PRODUCT_PRICE
    
    # حفظ الطلب في قاعدة البيانات كـ "معلق"
    order_id = db_orders.insert({{
        'discord_id': d_id,
        'quantity': qty,
        'cash_number': cash_num,
        'total': total_price,
        'status': 'pending'
    }})

    # إرسال إشعار لك على ديسكورد
    async def notify_admin():
        try:
            admin = await client.fetch_user(ADMIN_DISCORD_ID)
            msg = (f"🔔 **طلب جديد معلق!**\n"
                   f"👤 العميل: <@{d_id}>\n"
                   f"📦 الكمية: {{qty}}\n"
                   f"💰 المبلغ المطلوب: {{total_price}} جنيه\n"
                   f"📱 رقم كاش العميل: {{cash_num}}\n"
                   f"---")
            await admin.send(msg)
        except Exception as e:
            print(f"Error notifying admin: {{e}}")

    asyncio.run_coroutine_threadsafe(notify_admin(), client.loop)

    return f'''
    <body style="background:#121212; color:white; text-align:center; padding-top:100px; font-family:sans-serif;">
        <div style="background:#1e1e1e; padding:40px; border-radius:20px; display:inline-block; border:2px solid #5865F2;">
            <h2 style="color:#43b581;">✅ تم تسجيل طلبك بنجاح!</h2>
            <p style="font-size:1.2em;">من فضلك قم بتحويل مبلغ <b>{{total_price}} جنيه</b></p>
            <p>إلى رقم فودافون كاش التالي:</p>
            <h1 style="background:#2c2f33; padding:10px; border-radius:10px; letter-spacing:2px;">{PAYMENT_NUMBER}</h1>
            <p style="color:#b9bbbe;">انتظر من فضلك إلى أن يتم مراجعة التحويل وقبول طلبك.</p>
        </div>
    </body>
    '''

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

@client.event
async def on_ready():
    print(f'✅ المتجر واليافظة جاهزة باسم: {{client.user}}')
    client.loop = asyncio.get_running_loop()

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    if TOKEN:
        client.run(TOKEN)
