import os
import sqlite3
import uuid
import json
import time
import threading
import random
import string
import requests
import telebot
from telebot import types
from datetime import datetime, timedelta
import logging

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Configuration ---
API_TOKEN = "8908241166:AAFoTfQNX4lRyeKz5dfJamgfuYrKUFZ1WFA"
ADMIN_ID = int(os.getenv("ADMIN_ID", "8766653823"))
PAYMENT_CHANNEL_ID = -1004325941237

DB_PATH = os.getenv("DB_PATH", "users.db")
FF_FILE = os.getenv("FF_FILE", "prices_ff.json")

# --- API Base URLs ---
G2BULK_BASE_URL = "https://api.g2bulk.com/v1"
BAY2GAME_BASE_URL = "https://api.bay2game.xyz/api"
ZINIPAY_BASE_URL = "https://api.zinipay.com"
OXAPAY_BASE_URL = "https://api.oxapay.com"
ZINIPAY_REDIRECT_URL = "https://t.me/freefiretopup_bd_bot"

# --- API Keys ---
DEFAULT_G2BULK_KEY = os.getenv("G2BULK_API_KEY", "")
DEFAULT_BAY2GAME_KEY = os.getenv("BAY2GAME_API_KEY", "")
DEFAULT_ZINIPAY_KEY = os.getenv("ZINIPAY_API_KEY", "")
DEFAULT_OXAPAY_KEY = os.getenv("OXAPAY_API_KEY", "")

bot = telebot.TeleBot(API_TOKEN)

# --- Safe Database Connection ---
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception as e:
        logger.error(f"Error setting SQLite PRAGMAs: {e}")
    return conn

# --- Utility Functions ---
def f_num(n):
    try:
        n = float(n)
        return int(n) if n == int(n) else round(n, 2)
    except: 
        return n

def generate_serial():
    return "#" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def format_status(status):
    st = str(status).lower()
    if "complete" in st: return "✅ Complete"
    elif "looking" in st: return "⏳ Looking"
    elif "cancel" in st or "fail" in st: return "❌ Canceled"
    elif "pend" in st: return "⏳ Pending"
    return status

# --- Default FF Packages ---
DEFAULT_FF = {
    "ff_25d":    {"name": "25 Diamond", "price": 21, "g2bulk_code": "25", "bay2game_code": "FREEFIRE_BD_25", "stock_out": False, "api_cost_usd": 0.15, "category": "id_topup"},
    "ff_50d":    {"name": "50 Diamond", "price": 35, "g2bulk_code": "50", "bay2game_code": "FREEFIRE_BD_50", "stock_out": False, "api_cost_usd": 0.27, "category": "id_topup"},
    "ff_115d":   {"name": "115 Diamond", "price": 78, "g2bulk_code": "115", "bay2game_code": "FREEFIRE_BD_115", "stock_out": False, "api_cost_usd": 0.59, "category": "id_topup"},
    "ff_240d":   {"name": "240 Diamond", "price": 157, "g2bulk_code": "240", "bay2game_code": "FREEFIRE_BD_240", "stock_out": False, "api_cost_usd": 1.19, "category": "id_topup"},
    "ff_505d":   {"name": "505 Diamond", "price": 330, "g2bulk_code": "505", "bay2game_code": "COMBO_505", "stock_out": False, "api_cost_usd": 2.63, "category": "id_topup", "combo": ["ff_240d", "ff_240d", "ff_25d"]},
    "ff_610d":   {"name": "610 Diamond", "price": 398, "g2bulk_code": "610", "bay2game_code": "FREEFIRE_BD_610", "stock_out": False, "api_cost_usd": 3.01, "category": "id_topup"},
    "ff_1090d":  {"name": "1090 Diamond", "price": 715, "g2bulk_code": "1090", "bay2game_code": "COMBO_1090", "stock_out": False, "api_cost_usd": 5.39, "category": "id_topup", "combo": ["ff_610d", "ff_240d", "ff_240d"]},
    "ff_1240d":  {"name": "1240 Diamond", "price": 795, "g2bulk_code": "1240", "bay2game_code": "FREEFIRE_BD_1240", "stock_out": False, "api_cost_usd": 6.02, "category": "id_topup"},
    "ff_2530d":  {"name": "2530 Diamond", "price": 1600, "g2bulk_code": "2530", "bay2game_code": "FREEFIRE_BD_2530", "stock_out": False, "api_cost_usd": 12.08, "category": "id_topup"},
    "ff_weekly": {"name": "Weekly Membership", "price": 155, "g2bulk_code": "Weekly Membership", "bay2game_code": "FREEFIRE_BD_Weekly_Membership", "stock_out": False, "api_cost_usd": 1.20, "category": "weekly_monthly"},
    "ff_monthly":{"name": "Monthly Membership", "price": 769, "g2bulk_code": "Monthly Membership","bay2game_code": "FREEFIRE_BD_Monthly_Membership", "stock_out": False, "api_cost_usd": 5.94, "category": "weekly_monthly"},
    "ff_weekly2x": {"name": "Weekly 2x", "price": 310, "g2bulk_code": "Weekly 2x", "bay2game_code": "COMBO_WEEKLY_2X", "stock_out": False, "api_cost_usd": 2.40, "category": "weekly_monthly", "combo": ["ff_weekly", "ff_weekly"]},
    "ff_monthly2x": {"name": "Monthly 2x", "price": 1538, "g2bulk_code": "Monthly 2x", "bay2game_code": "COMBO_MONTHLY_2X", "stock_out": False, "api_cost_usd": 11.88, "category": "weekly_monthly", "combo": ["ff_monthly", "ff_monthly"]},
    "ff_weekly2x_monthly": {"name": "Weekly 2x & Monthly", "price": 924, "g2bulk_code": "Weekly 2x+Monthly", "bay2game_code": "COMBO_WEEKLY2X_MONTHLY", "stock_out": False, "api_cost_usd": 7.14, "category": "weekly_monthly", "combo": ["ff_weekly", "ff_weekly", "ff_monthly"]},
    "ff_weekly4x_monthly": {"name": "Weekly 4x & Monthly", "price": 1389, "g2bulk_code": "Weekly 4x+Monthly", "bay2game_code": "COMBO_WEEKLY4X_MONTHLY", "stock_out": False, "api_cost_usd": 10.74, "category": "weekly_monthly", "combo": ["ff_weekly", "ff_weekly", "ff_weekly", "ff_weekly", "ff_monthly"]},
}

def load_pkgs(path, default):
    if os.path.exists(path):
        try:
            with open(path) as f:
                d = json.load(f)
            for k, default_vals in default.items():
                if k not in d:
                    d[k] = dict(default_vals)
                else:
                    for sub_k, sub_v in default_vals.items():
                        d[k].setdefault(sub_k, sub_v)
            return d
        except: 
            pass
    return {k: dict(v) for k, v in default.items()}

def save_pkgs(path, pkgs):
    with open(path, "w") as f: 
        json.dump(pkgs, f, indent=2)

FF_PKG = load_pkgs(FF_FILE, DEFAULT_FF)

# --- Database Setup ---
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT, balance REAL DEFAULT 0, joined_at TEXT, banned INTEGER DEFAULT 0)")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game TEXT DEFAULT 'Free Fire',
        package TEXT, player_id TEXT, player_name TEXT, price REAL, status TEXT, order_ref TEXT, 
        date TEXT, serial_no TEXT, fail_reason TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, method TEXT,
        trx_id TEXT, status TEXT, date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending_payments (
        user_id INTEGER PRIMARY KEY, amount REAL, invoice_id TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending_manual_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, method TEXT, 
        trx_id TEXT, status TEXT, date TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN joined_at TEXT")
    except:
        pass
    
    try:
        c.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
    except:
        pass

    for col in [("game", "TEXT DEFAULT 'Free Fire'"), ("order_ref", "TEXT"), ("serial_no", "TEXT"), ("fail_reason", "TEXT")]:
        try: 
            c.execute(f"ALTER TABLE orders ADD COLUMN {col[0]} {col[1]}")
        except: 
            pass
        
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('zinipay_api', ?)", (DEFAULT_ZINIPAY_KEY,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('oxapay_api', ?)", (DEFAULT_OXAPAY_KEY,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('g2bulk_api', ?)", (DEFAULT_G2BULK_KEY,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bay2game_api', ?)", (DEFAULT_BAY2GAME_KEY,))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active_provider', 'bay2game')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_status', 'ON')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('dollar_rate', '125.0')")
    
    # Support & Channel Settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_admin', 'sazzat_20')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_channel', 'freefiretopup_bd')")
    
    conn.commit()
    conn.close()

# --- Settings Getters & Setters ---
def get_setting(key, default_value):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else default_value

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_dollar_rate(): return float(get_setting('dollar_rate', 125.0))
def set_dollar_rate(rate): set_setting('dollar_rate', rate)
def get_zinipay_api_key(): return get_setting('zinipay_api', DEFAULT_ZINIPAY_KEY)
def set_zinipay_api_key(key): set_setting('zinipay_api', key)
def get_oxapay_api_key(): return get_setting('oxapay_api', DEFAULT_OXAPAY_KEY)
def set_oxapay_api_key(key): set_setting('oxapay_api', key)
def get_g2bulk_api_key(): return get_setting('g2bulk_api', DEFAULT_G2BULK_KEY)
def set_g2bulk_api_key(key): set_setting('g2bulk_api', key)
def get_bay2game_api_key(): return get_setting('bay2game_api', DEFAULT_BAY2GAME_KEY)
def set_bay2game_api_key(key): set_setting('bay2game_api', key)
def get_active_provider(): return get_setting('active_provider', 'bay2game')
def set_active_provider(provider): set_setting('active_provider', provider)
def get_bot_status(): return get_setting('bot_status', 'ON')
def set_bot_status(status): set_setting('bot_status', status)

# Support & Channel Settings
def get_support_admin(): return get_setting('support_admin', 'sazzat_20')
def set_support_admin(username): set_setting('support_admin', username)
def get_support_channel(): return get_setting('support_channel', 'freefiretopup_bd')
def set_support_channel(username): set_setting('support_channel', username)

# --- User & DB Helpers ---
def get_balance(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def update_balance(uid, amount, name="Unknown"):
    conn = get_db()
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO users (user_id, name, balance, joined_at) VALUES (?,?,0,?)", (uid, name, now_str))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    conn.commit()
    conn.close()

def is_user_banned(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r and r[0] == 1

def ban_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

def unban_user(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET banned = 0 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

def get_total_orders():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(id) FROM orders")
    count = c.fetchone()[0]
    conn.close()
    return count + 1

def log_order(uid, game, package, player_id, player_name, price, status, order_ref="", serial_no="", fail_reason=""):
    date_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO orders (user_id, game, package, player_id, player_name, price, status, order_ref, date, serial_no, fail_reason) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              (uid, game, package, player_id, player_name, price, status, order_ref, date_str, serial_no, fail_reason))
    order_db_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_db_id

def update_order_status(serial_no, status, fail_reason="", order_ref=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE orders SET status=?, fail_reason=?, order_ref=? WHERE serial_no=?", (status, fail_reason, order_ref, serial_no))
    conn.commit()
    conn.close()

def get_order_by_serial(serial_no):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE serial_no=?", (serial_no,))
    row = c.fetchone()
    conn.close()
    return row

def get_user_name(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else f"User_{uid}"

def log_deposit(uid, amount, method, trx, status):
    date_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO deposits (user_id, amount, method, trx_id, status, date) 
                 VALUES (?,?,?,?,?,?)""", (uid, amount, method, trx, status, date_str))
    conn.commit()
    conn.close()

def save_pending_payment(uid, amount, invoice_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pending_payments (user_id, amount, invoice_id, created_at) VALUES (?,?,?,?)",
              (uid, amount, invoice_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_pending_payment(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT amount, invoice_id FROM pending_payments WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r if r else None

def delete_pending_payment(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM pending_payments WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

def save_pending_manual(uid, amount, method, trx_id):
    date_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO pending_manual_payments (user_id, amount, method, trx_id, status, date) 
                 VALUES (?,?,?,?,?,?)""", (uid, amount, method, trx_id, "Pending", date_str))
    last_id = c.lastrowid
    conn.commit()
    conn.close()
    return last_id

def get_pending_manual_payments():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, method, trx_id, date FROM pending_manual_payments WHERE status='Pending' ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def update_manual_payment_status(payment_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE pending_manual_payments SET status=? WHERE id=?", (status, payment_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, name, balance, banned FROM users ORDER BY user_id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# ============================================================
# API HELPERS
# ============================================================

def _as_float(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").strip()
        return float(value)
    except (TypeError, ValueError):
        return None

def _find_balance(payload):
    balance_keys = (
        "balance", "available_balance", "availableBalance",
        "wallet_balance", "walletBalance", "credit", "credits", "funds",
    )
    if isinstance(payload, dict):
        for key in balance_keys:
            if key in payload:
                balance = _as_float(payload[key])
                if balance is not None:
                    return balance
        for value in payload.values():
            balance = _find_balance(value)
            if balance is not None:
                return balance
    elif isinstance(payload, list):
        for value in payload:
            balance = _find_balance(value)
            if balance is not None:
                return balance
    return None

# ============================================================
# BAY2GAME API
# ============================================================

def check_bay2game_balance():
    try:
        api_key = get_bay2game_api_key()
        if not api_key: return 999999
        params = {'api_key': api_key}
        response = requests.get(f"{BAY2GAME_BASE_URL}/profile", params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            balance = _find_balance(data)
            if balance is not None: return balance
        return 999999
    except:
        return 999999

def create_bay2game_order(product_code, player_id, reference):
    try:
        api_key = get_bay2game_api_key()
        if not api_key:
            return False, None, "API key not configured"
            
        payload = {
            'api_key': api_key,
            'product_code': product_code,
            'game_user_id': player_id,
            'reference': reference
        }
        response = requests.post(f"{BAY2GAME_BASE_URL}/create_order", json=payload, timeout=15)
        
        if response.status_code in [200, 201, 202]:
            try:
                data = response.json()
                if data.get("success") is True or data.get("status") in ["success", "ok", "created"]:
                    order_data = data.get('data', {}) if isinstance(data.get('data'), dict) else {}
                    order_id = order_data.get('order_id') or order_data.get('orderId') or order_data.get('reference') or data.get('order_id')
                    if order_id:
                        return True, str(order_id), "Success"
                    return True, reference, "Success"
                else:
                    return False, None, data.get('message', 'Unknown error')
            except:
                if response.status_code in [200, 201, 202]:
                    return True, reference, "Success"
                return False, None, "Invalid response"
        else:
            return False, None, f"HTTP {response.status_code}"
    except Exception as e:
        return False, None, str(e)

def check_bay2game_order_status(reference):
    try:
        api_key = get_bay2game_api_key()
        if not api_key:
            return 'error', "API key not configured"
        params = {'api_key': api_key, 'reference': reference}
        response = requests.get(f"{BAY2GAME_BASE_URL}/check_order", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            order_data = data.get('data') if isinstance(data.get('data'), dict) else {}
            
            raw_status = (
                order_data.get('status') or 
                order_data.get('order_status') or 
                data.get('status') or 
                data.get('order_status') or 
                ''
            )
            status = str(raw_status).upper()
            
            if status in ['COMPLETED', 'SUCCESS', 'DONE', 'DELIVERED']:
                return 'completed', None
            elif status in ['PENDING', 'PROCESSING', 'LOOKING', 'QUEUED', 'WAITING']:
                return 'pending', None
            elif status in ['FAILED', 'CANCELED', 'CANCELLED', 'REFUNDED']:
                msg = order_data.get('message') or data.get('message') or 'Order failed'
                return 'failed', msg
            
            if data.get('success') is True and status in ['OK', 'TRUE']:
                return 'completed', None
                
            return 'pending', None
        return 'error', f"HTTP {response.status_code}"
    except Exception as e:
        return 'error', str(e)

# ============================================================
# G2BULK API
# ============================================================

def check_g2bulk_balance():
    try:
        api_key = get_g2bulk_api_key()
        if not api_key: return 999999
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.get(f"{G2BULK_BASE_URL}/getMe", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            balance = _find_balance(data)
            if balance is not None: return balance
        return 999999
    except:
        return 999999

def create_g2bulk_order(product_code, player_id):
    try:
        api_key = get_g2bulk_api_key()
        if not api_key:
            return False, None, "API key not configured"
            
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(uuid.uuid4())
        }
        payload = {"catalogue_name": product_code, "player_id": player_id}
        response = requests.post(f"{G2BULK_BASE_URL}/games/freefire_bd/order", json=payload, headers=headers, timeout=15)
        
        if response.status_code in [200, 201]:
            try:
                data = response.json()
                if data.get("success") or data.get("status") in ["success", "ok", "created"]:
                    order_id = data.get("order_id") or data.get("order", {}).get("order_id")
                    if order_id:
                        return True, str(order_id), "Success"
                    return True, f"ORD-{int(time.time())}", "Success"
                else:
                    return False, None, data.get("message", "Unknown error")
            except:
                if response.status_code == 201:
                    return True, f"ORD-{int(time.time())}", "Success"
                return False, None, "Invalid response"
        else:
            return False, None, f"HTTP {response.status_code}"
    except Exception as e:
        return False, None, str(e)

def check_g2bulk_order_status(order_id):
    try:
        api_key = get_g2bulk_api_key()
        if not api_key:
            return 'error', "API key not configured"
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        response = requests.post(f"{G2BULK_BASE_URL}/games/order/status", json={"order_id": str(order_id)}, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            order_data = data.get("data") if isinstance(data.get("data"), dict) else {}
            
            raw_status = (
                data.get("status") or 
                order_data.get("status") or 
                ""
            )
            status = str(raw_status).upper()
            
            if status in ["COMPLETED", "SUCCESS", "DONE", "DELIVERED"]:
                return 'completed', None
            elif status in ["FAILED", "REFUNDED", "CANCELED", "CANCELLED"]:
                msg = data.get('message') or order_data.get('message') or 'Order failed'
                return 'failed', msg
            elif status in ["PENDING", "PROCESSING", "LOOKING", "QUEUED"]:
                return 'pending', None
                
            return 'pending', None
        return 'error', f"HTTP {response.status_code}"
    except Exception as e:
        return 'error', str(e)

# ============================================================
# OXAPAY API
# ============================================================

def create_oxapay_invoice(uid, amount_usd, name="Customer"):
    try:
        api_key = get_oxapay_api_key().strip()
        if not api_key:
            return None, None, "OxaPay API key not configured."
        
        url = 'https://api.oxapay.com/v1/payment/invoice'
        payload = {
            "amount": float(amount_usd),
            "currency": "USD",
            "lifetime": 30,
            "fee_paid_by_payer": 1,
            "under_paid_coverage": 2.5,
            "to_currency": "USDT",
            "auto_withdrawal": False,
            "return_url": ZINIPAY_REDIRECT_URL,
            "order_id": f"ORD-OXA-{uid}-{int(time.time())}",
            "description": f"Add balance for User {uid} - {name}",
            "sandbox": False
        }
        headers = {'merchant_api_key': api_key, 'Content-Type': 'application/json'}
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code in [200, 201]:
            try:
                res_json = response.json()
                is_success = (
                    res_json.get("status") == "success" or 
                    res_json.get("success") is True or
                    res_json.get("code") == 200 or
                    "success" in str(res_json).lower()
                )
                if is_success:
                    data = res_json.get("data", {})
                    pay_url = data.get("pay_url") or data.get("payment_url") or res_json.get("pay_url")
                    track_id = data.get("track_id") or data.get("invoice_id") or res_json.get("track_id")
                    if pay_url and track_id:
                        return str(pay_url), str(track_id), "Success"
                    if pay_url:
                        track_id = f"INV-{uid}-{int(time.time())}"
                        return str(pay_url), str(track_id), "Success"
                error_msg = res_json.get("message") or "Unknown error"
                return None, None, error_msg
            except:
                track_id = f"INV-{uid}-{int(time.time())}"
                pay_url = f"https://pay.oxapay.com/invoice/{track_id}"
                return pay_url, track_id, "Success"
        return None, None, f"HTTP {response.status_code}"
    except Exception as e:
        return None, None, str(e)

def verify_oxapay_payment(track_id):
    try:
        api_key = get_oxapay_api_key().strip()
        if not api_key: return None
        
        endpoints = [
            f'https://api.oxapay.com/v1/payment/{track_id}',
            f'https://api.oxapay.com/payment/{track_id}',
            f'https://api.oxapay.com/v1/invoice/{track_id}'
        ]
        headers = {'merchant_api_key': api_key, 'Content-Type': 'application/json'}
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, headers=headers, timeout=15)
                if response.status_code == 200:
                    res_json = response.json()
                    if res_json.get("status") == "success" or res_json.get("success") is True:
                        return res_json.get("data", {})
            except:
                continue
        return None
    except:
        return None

def poll_oxapay_payment(uid, track_id, amount_usd, amount_bdt, chat_id, message_id):
    def _run():
        is_completed = False
        for _ in range(60):
            time.sleep(15)
            try:
                pending = get_pending_payment(uid)
                if not pending: break

                data = verify_oxapay_payment(track_id)
                if data:
                    status = str(data.get("status") or data.get("state") or "").lower()
                    is_paid = data.get("paid") is True or data.get("is_paid") is True
                    
                    if is_paid or status in ["paid", "completed", "success", "finished", "done"]:
                        if pending and pending[1] == track_id:
                            update_balance(uid, amount_bdt)
                            log_deposit(uid, amount_bdt, f"OxaPay Crypto (${amount_usd})", track_id, "Complete")
                            delete_pending_payment(uid)
                            
                            try: bot.delete_message(chat_id, message_id)
                            except: pass

                            success_msg = (
                                f"✅ Crypto Payment Successful!\n"
                                f"💵 Paid: ${f_num(amount_usd)} USDT\n"
                                f"💰 {f_num(amount_bdt)} TK Added to your wallet.\n\n"
                                f"💵 New Balance: {f_num(get_balance(uid))} TK"
                            )
                            bot.send_message(chat_id, success_msg, reply_markup=main_menu())
                            
                            admin_notify = (
                                f"✅ OxaPay Crypto Payment Successful\n\n"
                                f"👤 User ID: {uid}\n"
                                f"💵 Paid USD: ${f_num(amount_usd)}\n"
                                f"💰 BDT Added: {f_num(amount_bdt)} TK\n"
                                f"🆔 Track ID: {track_id}\n"
                                f"📅 Time: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}"
                            )
                            try: bot.send_message(PAYMENT_CHANNEL_ID, admin_notify)
                            except: pass
                            is_completed = True
                            break
                            
                    if status in ["expired", "refunded", "canceled", "cancelled", "failed", "error"]:
                        delete_pending_payment(uid)
                        try: bot.delete_message(chat_id, message_id)
                        except: pass
                        bot.send_message(chat_id, f"❌ Crypto Payment {status.title()}.", reply_markup=main_menu())
                        is_completed = True
                        break
            except Exception as e:
                logger.error(f"OxaPay polling error: {e}")
                
        if not is_completed:
            pending = get_pending_payment(uid)
            if pending and pending[1] == track_id:
                delete_pending_payment(uid)
                try: bot.delete_message(chat_id, message_id)
                except: pass
                try: bot.send_message(chat_id, "❌ Payment Timeout or Canceled.", reply_markup=main_menu())
                except: pass

    threading.Thread(target=_run, daemon=True).start()

# ============================================================
# ZINIPAY API
# ============================================================

def create_zinipay_invoice(uid, amount, name="Customer"):
    try:
        api_key = get_zinipay_api_key()
        if not api_key: return None, None, "ZiniPay API key not configured"
            
        payload = {
            "cus_name": str(name)[:45],
            "cus_email": f"user{uid}@example.com",
            "amount": float(amount),
            "metadata": {"order_id": f"ORD-{uid}-{int(time.time())}", "customer_id": str(uid)},
            "redirect_url": ZINIPAY_REDIRECT_URL,
            "cancel_url": ZINIPAY_REDIRECT_URL
        }
        
        response = requests.post(f"{ZINIPAY_BASE_URL}/v1/payment/create", json=payload,
            headers={"zini-api-key": api_key, "Content-Type": "application/json"}, timeout=15)
        data = response.json()
        
        if data.get("status") is True and data.get("payment_url"):
            return data["payment_url"], data["payment_url"].split('/')[-1], "Success"
        return None, None, data.get("message", "Error")
    except Exception as e:
        return None, None, str(e)

def verify_zinipay_payment(invoice_id):
    try:
        api_key = get_zinipay_api_key()
        if not api_key: return None
        response = requests.post(f"{ZINIPAY_BASE_URL}/v1/payment/verify", json={"invoice_id": invoice_id},
            headers={"zini-api-key": api_key, "Content-Type": "application/json"}, timeout=15)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def poll_zinipay_payment(uid, invoice_id, amount, chat_id, message_id):
    def _run():
        is_completed = False
        for _ in range(60):
            time.sleep(3)
            try:
                pending = get_pending_payment(uid)
                if not pending: break

                data = verify_zinipay_payment(invoice_id)
                if data:
                    status = str(data.get("status", "")).upper()
                    if status == "COMPLETED":
                        if pending and pending[1] == invoice_id:
                            update_balance(uid, amount)
                            log_deposit(uid, amount, "ZiniPay Auto", invoice_id, "Complete")
                            delete_pending_payment(uid)
                            
                            try: bot.delete_message(chat_id, message_id)
                            except: pass

                            bot.send_message(chat_id, f"✅ Payment Successful!\n💰 {f_num(amount)} TK Added to your wallet.\n\n💵 New Balance: {f_num(get_balance(uid))} TK", reply_markup=main_menu())
                            
                            admin_notify = (f"✅ Auto Payment Successful (ZiniPay)\n\n"
                                            f"👤 User ID: {uid}\n"
                                            f"💰 Amount: {f_num(amount)} TK\n"
                                            f"🆔 Invoice: {invoice_id}\n"
                                            f"📅 Time: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}")
                            try: bot.send_message(PAYMENT_CHANNEL_ID, admin_notify)
                            except: pass
                        is_completed = True
                        break
                    elif status in ["FAILED", "CANCELED"]:
                        delete_pending_payment(uid)
                        try: bot.delete_message(chat_id, message_id)
                        except: pass
                        bot.send_message(chat_id, "❌ Payment Failed or Canceled.", reply_markup=main_menu())
                        is_completed = True
                        break
            except:
                pass
                
        if not is_completed:
            pending = get_pending_payment(uid)
            if pending and pending[1] == invoice_id:
                delete_pending_payment(uid)
                try: bot.delete_message(chat_id, message_id)
                except: pass
                try: bot.send_message(chat_id, "❌ Payment Timeout or Canceled.", reply_markup=main_menu())
                except: pass

    threading.Thread(target=_run, daemon=True).start()

# ============================================================
# COMBINED API FUNCTIONS
# ============================================================

def check_api_balance(provider=None):
    if provider is None: provider = get_active_provider()
    if provider == "bay2game": return check_bay2game_balance()
    return check_g2bulk_balance()

def create_api_order(provider, product_code, player_id, reference):
    if provider == "bay2game": return create_bay2game_order(product_code, player_id, reference)
    return create_g2bulk_order(product_code, player_id)

def check_api_order_status(provider, ref_or_id):
    if provider == "bay2game": return check_bay2game_order_status(ref_or_id)
    return check_g2bulk_order_status(ref_or_id)

# --- Order Formatting ---
def get_admin_order_msg(order_no, serial, t_name, uid, game, p_name, p_id, pkg, price, date_str, status, reason=""):
    reason_str = f" ({reason})" if reason else ""
    st_formatted = format_status(status)
    return (f"Topup Number: {order_no}\n\n"
           f"📋 Serial NO: {serial}\n"
           f"👤 User: {t_name}\n"
           f"🆔 User ID: {uid}\n"
           f"🎮 Game: {game}\n"
           f"👤 Player Name: {p_name}\n"
           f"🆔 Player ID: {p_id}\n"
           f"💎 Package: {pkg}\n"
           f"💰 Price: {f_num(price)} TK\n"
           f"📅 Time: {date_str}\n"
           f"📌 Status: {st_formatted}{reason_str}\n\n"
           f"──────────────────")

def get_user_order_msg(serial, game, p_name, p_id, pkg, price, date_str, status, reason=""):
    st_formatted = format_status(status)
    reason_str = ""
    if ("cancel" in str(status).lower() or "fail" in str(status).lower()) and reason:
        reason_str = f" ({reason})"
    return (f"📋 Serial NO: {serial}\n\n"
           f"🎮 Game: {game}\n"
           f"👤 Player Name: {p_name}\n"
           f"🆔 Player ID: {p_id}\n"
           f"💎 Package: {pkg}\n"
           f"💰 Price: {f_num(price)} TK\n"
           f"📅 Time: {date_str}\n"
           f"📌 Status: {st_formatted}{reason_str}")

# --- Order Polling ---
def poll_order(provider, ref_or_id, chat_id, user_pending_msg_id, serial, pkg_name, price, uid, order_no, t_name, p_name, p_id, date_str):
    def _run():
        time.sleep(3)
        for attempt in range(120):
            time.sleep(5)
            try:
                status, error = check_api_order_status(provider, ref_or_id)
                
                if status == 'completed':
                    update_order_status(serial, "Complete", order_ref=str(ref_or_id))
                    user_msg = get_user_order_msg(serial, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Complete")
                    admin_msg = get_admin_order_msg(order_no, serial, t_name, uid, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Complete")
                    
                    if user_pending_msg_id:
                        try:
                            bot.delete_message(chat_id, user_pending_msg_id)
                        except Exception as e:
                            logger.error(f"Error deleting pending msg: {e}")
                    
                    try:
                        bot.send_message(chat_id, f"🎉 Topup Successful!\n\n{user_msg}", reply_markup=main_menu())
                    except Exception as e:
                        logger.error(f"Error sending complete msg: {e}")
                    
                    try:
                        bot.send_message(ADMIN_ID, admin_msg)
                    except Exception as e:
                        logger.error(f"Error sending admin msg: {e}")
                    return
                    
                elif status == 'pending':
                    continue
                    
                elif status == 'failed':
                    update_order_status(serial, "Canceled", error or "Order failed", order_ref=str(ref_or_id))
                    update_balance(uid, price)
                    
                    user_msg = get_user_order_msg(serial, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Canceled", error)
                    admin_msg = get_admin_order_msg(order_no, serial, t_name, uid, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Canceled", error)
                    
                    if user_pending_msg_id:
                        try:
                            bot.delete_message(chat_id, user_pending_msg_id)
                        except:
                            pass
                    
                    try:
                        bot.send_message(chat_id, f"❌ Order Failed! {f_num(price)} TK Refunded.\n\n{user_msg}", reply_markup=main_menu())
                    except:
                        pass
                    
                    try:
                        bot.send_message(ADMIN_ID, admin_msg)
                    except:
                        pass
                    return
                    
                elif status == 'error':
                    if attempt < 15:
                        continue
                    else:
                        update_order_status(serial, "Looking", f"API Error: {error}", order_ref=str(ref_or_id))
                        return
                    
            except Exception as e:
                logger.error(f"Polling error: {e}")
                if attempt >= 15:
                    update_order_status(serial, "Looking", f"Polling Error: {str(e)}")
                    return
                
    threading.Thread(target=_run, daemon=True).start()

# --- Place Order Function ---
def place_order(m, pid, player_id, p_name):
    if not m or not m.text:
        return
    if m.text in ["❌ Cancel Order", "🔙 Main Menu"]:
        return bot.send_message(m.chat.id, "❌ Order Canceled.", reply_markup=main_menu())
    if m.text == "🔙 Topup Menu":
        return bot.send_message(m.chat.id, "📌 Select Topup Type:", reply_markup=topup_menu())
    if m.text != "✅ Confirm Order":
        return
    
    pkg = FF_PKG[pid]
    uid = m.from_user.id
    t_name = m.from_user.first_name or f"User_{uid}"
    price = pkg["price"]
    
    is_combo = "combo" in pkg and pkg["combo"]
    
    if get_balance(uid) < price:
        return bot.send_message(
            m.chat.id,
            f"❌ Insufficient Balance! Need {f_num(price - get_balance(uid))} TK more.",
            reply_markup=main_menu()
        )
    
    update_balance(uid, -price)
    
    if is_combo:
        process_combo_order(uid, pkg["combo"], player_id, p_name, pkg["name"], price)
        return
    
    active_provider = get_active_provider()
    serial = generate_serial()
    order_no = get_total_orders()
    date_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    
    api_balance = check_api_balance(active_provider)
    total_usd_cost = pkg.get("api_cost_usd", 0)
    
    if api_balance < total_usd_cost:
        log_order(uid, "Free Fire", pkg["name"], player_id, p_name, price, "Looking", "", serial, f"API Balance: ${api_balance} < ${total_usd_cost}")
        
        user_msg = get_user_order_msg(serial, "Free Fire", p_name, player_id, pkg["name"], price, date_str, "Looking")
        admin_msg = get_admin_order_msg(order_no, serial, t_name, uid, "Free Fire", p_name, player_id, pkg["name"], price, date_str, "Looking", f"API Balance: ${api_balance} < ${total_usd_cost}")
        
        bot.send_message(m.chat.id, f"⏳ Order placed in Looking status.\n\n{user_msg}", reply_markup=main_menu())
        try:
            bot.send_message(ADMIN_ID, f"⏳ Order Waiting for API Balance\n\n{admin_msg}")
        except:
            pass
        return
    
    code = pkg.get("bay2game_code" if active_provider == "bay2game" else "g2bulk_code", pkg.get("api_name"))
    ref_id = f"ORD-{serial[1:]}-{int(time.time())}"
    
    success, order_ref, err_msg = create_api_order(active_provider, code, player_id, ref_id)
    
    if success:
        log_order(uid, "Free Fire", pkg["name"], player_id, p_name, price, "Pending", str(order_ref), serial)
        
        user_msg = get_user_order_msg(serial, "Free Fire", p_name, player_id, pkg["name"], price, date_str, "Pending")
        admin_msg = get_admin_order_msg(order_no, serial, t_name, uid, "Free Fire", p_name, player_id, pkg["name"], price, date_str, "Pending")
        
        try:
            u_p_msg = bot.send_message(m.chat.id, f"⏳ Order Processing...\n\n{user_msg}", reply_markup=main_menu())
        except:
            u_p_msg = None
        
        try:
            bot.send_message(ADMIN_ID, admin_msg)
        except:
            pass
        
        poll_order(active_provider, order_ref, m.chat.id, u_p_msg.message_id if u_p_msg else None, serial, pkg["name"], price, uid, order_no, t_name, p_name, player_id, date_str)
    else:
        update_balance(uid, price)
        log_order(uid, "Free Fire", pkg["name"], player_id, p_name, price, "Canceled", "", serial, err_msg)
        
        user_msg = get_user_order_msg(serial, "Free Fire", p_name, player_id, pkg["name"], price, date_str, "Canceled", err_msg)
        bot.send_message(m.chat.id, f"❌ Order Failed! {f_num(price)} TK Refunded.\n\n{user_msg}", reply_markup=main_menu())

# --- Combo Order Processing ---
def process_combo_order(uid, combo_packages, player_id, player_name, pkg_name, total_price):
    t_name = get_user_name(uid)
    serial = generate_serial()
    order_no = get_total_orders()
    date_str = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    active_provider = get_active_provider()
    
    total_usd_cost = sum(FF_PKG[k].get("api_cost_usd", 0) for k in combo_packages if k in FF_PKG)
    api_balance = check_api_balance(active_provider)
    
    if api_balance >= total_usd_cost:
        log_order(uid, "Free Fire", pkg_name, player_id, player_name, total_price, "Processing", "", serial, "")
        for idx, combo_pkg_key in enumerate(combo_packages):
            if combo_pkg_key in FF_PKG:
                combo_pkg = FF_PKG[combo_pkg_key]
                sub_serial = f"{serial}-{idx+1}"
                log_order(uid, "Free Fire", combo_pkg["name"], player_id, player_name, combo_pkg["price"], "Processing", "", sub_serial, f"Part of {pkg_name} combo")
        process_combo_orders_now(uid, combo_packages, player_id, player_name, pkg_name, total_price, serial, order_no, date_str, t_name)
        return True
    else:
        log_order(uid, "Free Fire", pkg_name, player_id, player_name, total_price, "Looking", "", serial, f"API Balance: ${f_num(api_balance)} < ${f_num(total_usd_cost)}")
        for idx, combo_pkg_key in enumerate(combo_packages):
            if combo_pkg_key in FF_PKG:
                combo_pkg = FF_PKG[combo_pkg_key]
                sub_serial = f"{serial}-{idx+1}"
                log_order(uid, "Free Fire", combo_pkg["name"], player_id, player_name, combo_pkg["price"], "Looking", "", sub_serial, f"Part of {pkg_name} combo")
        
        user_msg = get_user_order_msg(serial, "Free Fire", player_name, player_id, pkg_name, total_price, date_str, "Looking")
        admin_msg = get_admin_order_msg(order_no, serial, t_name, uid, "Free Fire", player_name, player_id, f"{pkg_name} (Combo)", total_price, date_str, "Looking", f"API Balance: ${f_num(api_balance)} < ${f_num(total_usd_cost)}")
        bot.send_message(uid, f"⏳ Order placed in Looking status.\n\n{user_msg}", reply_markup=main_menu())
        try:
            bot.send_message(ADMIN_ID, f"⏳ Combo Order Waiting for API Balance\n\n{admin_msg}")
        except:
            pass
        return True

def process_combo_orders_now(uid, combo_packages, player_id, player_name, pkg_name, total_price, serial, order_no, date_str, t_name):
    active_provider = get_active_provider()
    order_refs = []
    all_success = True
    failed_orders = []
    
    for idx, combo_pkg_key in enumerate(combo_packages):
        if combo_pkg_key not in FF_PKG:
            continue
            
        combo_pkg = FF_PKG[combo_pkg_key]
        sub_serial = f"{serial}-{idx+1}"
        
        code = combo_pkg.get("bay2game_code" if active_provider == "bay2game" else "g2bulk_code", combo_pkg.get("api_name"))
        ref_id = f"ORD-{serial[1:]}-{int(time.time())}-{idx}"
        
        success, order_ref, err_msg = create_api_order(active_provider, code, player_id, ref_id)
        
        if success:
            order_refs.append(order_ref)
            update_order_status(sub_serial, "Pending", order_ref=order_ref)
        else:
            all_success = False
            failed_orders.append(f"{combo_pkg['name']}: {err_msg}")
            update_order_status(sub_serial, "Canceled", fail_reason=err_msg)
    
    if all_success and order_refs:
        update_order_status(serial, "Pending", order_ref=",".join(order_refs))
        user_msg = get_user_order_msg(serial, "Free Fire", player_name, player_id, pkg_name, total_price, date_str, "Pending")
        bot.send_message(uid, f"⏳ Order Processing...\n\n{user_msg}", reply_markup=main_menu())
        
        for idx, ref in enumerate(order_refs):
            sub_serial = f"{serial}-{idx+1}"
            sub_pkg_name = combo_packages[idx]
            sub_pkg = FF_PKG[sub_pkg_name]
            poll_order(active_provider, ref, uid, None, sub_serial, sub_pkg["name"], sub_pkg["price"], uid, order_no, t_name, player_name, player_id, date_str)
    else:
        update_order_status(serial, "Canceled", fail_reason="Some orders failed")
        update_balance(uid, total_price)
        error_msg = "\n".join(failed_orders) if failed_orders else "Unknown error"
        bot.send_message(uid, f"❌ Combo Order Failed!\n💰 {f_num(total_price)} TK Refunded.\n\nError: {error_msg}", reply_markup=main_menu())

# --- Background Retry Thread ---
def retry_looking_orders():
    while True:
        time.sleep(20)
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM orders WHERE status='Looking'")
            looking_orders = c.fetchall()
            conn.close()
            
            if not looking_orders:
                continue

            active_provider = get_active_provider()
            now = datetime.now()

            for row in looking_orders:
                db_id, uid, game, pkg_name, p_id, p_name, price, status, order_ref, date_str, serial, reason = row
                
                if "-" in str(serial):
                    continue

                t_name = get_user_name(uid)
                
                try:
                    order_time = datetime.strptime(date_str, "%d-%m-%Y %I:%M %p")
                    elapsed_seconds = (now - order_time).total_seconds()
                except:
                    elapsed_seconds = 0
                
                if elapsed_seconds >= 600:
                    fail_reason = "API Timeout (10m)"
                    update_order_status(serial, "Canceled", fail_reason)
                    update_balance(uid, price)
                    
                    user_msg = get_user_order_msg(serial, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Canceled", fail_reason)
                    admin_msg = get_admin_order_msg(db_id, serial, t_name, uid, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Canceled", fail_reason)
                    
                    try:
                        bot.send_message(uid, f"❌ Order Auto-Canceled (Timeout)!\n💰 {f_num(price)} TK Refunded.\n\n{user_msg}", reply_markup=main_menu())
                    except:
                        pass
                    try:
                        bot.send_message(ADMIN_ID, f"⚠️ Auto-Canceled (10m Timeout).\n\n{admin_msg}")
                    except:
                        pass
                    continue
                
                pkg_info = None
                is_combo = False
                combo_packages = []
                
                for k, v in FF_PKG.items():
                    if v['name'] == pkg_name:
                        pkg_info = v
                        if "combo" in v and v["combo"]:
                            is_combo = True
                            combo_packages = v["combo"]
                        break
                
                if not pkg_info:
                    continue
                
                api_balance = check_api_balance(active_provider)
                
                if not is_combo:
                    total_usd_cost = pkg_info.get("api_cost_usd", 0)
                    if api_balance >= total_usd_cost:
                        update_order_status(serial, "Processing")
                        
                        code = pkg_info.get("bay2game_code" if active_provider == "bay2game" else "g2bulk_code", pkg_info.get("api_name"))
                        ref_id = f"ORD-{serial[1:]}-{int(time.time())}"
                        
                        success, new_ref_id, err_msg = create_api_order(active_provider, code, p_id, ref_id)
                        
                        if success:
                            update_order_status(serial, "Pending", "", str(new_ref_id))
                            user_msg = get_user_order_msg(serial, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Pending")
                            admin_msg = get_admin_order_msg(db_id, serial, t_name, uid, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Pending")
                            
                            try:
                                u_p_msg = bot.send_message(uid, f"⏳ API Balance Found! Order Processing...\n\n{user_msg}", reply_markup=main_menu())
                            except:
                                u_p_msg = None
                            try:
                                bot.send_message(ADMIN_ID, admin_msg)
                            except:
                                pass
                            
                            poll_order(active_provider, new_ref_id, uid, u_p_msg.message_id if u_p_msg else None, serial, pkg_name, price, uid, db_id, t_name, p_name, p_id, date_str)
                        else:
                            update_order_status(serial, "Canceled", err_msg)
                            update_balance(uid, price)
                            user_msg = get_user_order_msg(serial, "Free Fire", p_name, p_id, pkg_name, price, date_str, "Canceled", err_msg)
                            try:
                                bot.send_message(uid, f"❌ Order Failed: {f_num(price)} TK Refunded.\n\n{user_msg}", reply_markup=main_menu())
                            except:
                                pass

        except Exception as e:
            logger.error(f"Retry Thread Error: {e}")

threading.Thread(target=retry_looking_orders, daemon=True).start()

# ============================================================
# KEYBOARDS
# ============================================================

def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("💎 Topup", "💰 Balance")
    m.row("➕ Add Balance", "📜 History")
    m.row("👤 My Account", "📞 Support")
    return m

def topup_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add("💎 ID Code Topup", "📅 Weekly & Monthly")
    m.add("🔙 Main Menu")
    return m

def id_code_topup_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = []
    order = ["ff_25d", "ff_50d", "ff_115d", "ff_240d", "ff_505d", "ff_610d", "ff_1090d", "ff_1240d", "ff_2530d"]
    for key in order:
        if key in FF_PKG:
            v = FF_PKG[key]
            icon = "🚫" if v.get("stock_out") else "💎"
            buttons.append(types.KeyboardButton(f"{icon} {v['name']} | {f_num(v['price'])} TK"))
    m.add(*buttons)
    m.add("🔙 Topup Menu")
    return m

def weekly_monthly_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = []
    order = ["ff_weekly", "ff_monthly", "ff_weekly2x", "ff_monthly2x", "ff_weekly2x_monthly", "ff_weekly4x_monthly"]
    for key in order:
        if key in FF_PKG:
            v = FF_PKG[key]
            icon = "🚫" if v.get("stock_out") else "💎"
            buttons.append(types.KeyboardButton(f"{icon} {v['name']} | {f_num(v['price'])} TK"))
    m.add(*buttons)
    m.add("🔙 Topup Menu")
    return m

def confirm_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add("✅ Confirm Order", "❌ Cancel Order")
    return m

def payment_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add("💳 Auto payment (BDT)", "🪙 Crypto Auto (OxaPay)")
    m.add("📝 Manual Payment", "🔙 Main Menu")
    return m

def manual_payment_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add("💵 Bkash", "💵 Nagad")
    m.add("🔙 Back to Methods")
    return m

def history_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add("📦 Order History", "💵 Add Money History")
    m.add("🔙 Main Menu")
    return m

def support_keyboard():
    m = types.InlineKeyboardMarkup(row_width=1)
    channel = get_support_channel()
    admin = get_support_admin()
    m.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel}"))
    m.add(types.InlineKeyboardButton("👨‍💻 Support Admin", url=f"https://t.me/{admin}"))
    return m

def admin_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    status_text = "🟢 Bot Status: ON" if get_bot_status() == "ON" else "🔴 Bot Status: OFF"
    m.add(status_text)
    m.add("⚙️ FF Price Change", "📦 Stock Out Manage")
    m.add("💵 Set Dollar Rate", "💵 Profit Calculator")
    m.add("📊 Stats", "📋 Pending Payments")
    m.add("📈 Sales Report", "💰 Add User Balance")
    m.add("🔍 Check Order (Serial)", "👤 User Details")
    m.add("🔑 API Settings", "💾 Backup DB")
    m.add("📥 Restore DB", "🔙 Main Menu")
    m.add("🚫 User Ban", "✅ User Unban")
    m.add("📢 Send Notice", "💰 Remove Balance")
    m.add("🔢 Ban/Unban by ID")
    m.add("🔧 Support Settings")
    return m

def support_settings_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add("📢 Change Channel", "👨‍💻 Change Admin")
    m.add("🔙 Admin Menu")
    return m

def admin_remove_balance(m):
    if not m or not m.text:
        return
    if m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    
    text = m.text.strip()
    
    if text.isdigit():
        target_uid = int(text)
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, f"💵 Enter amount to remove from User ID <code>{target_uid}</code>:", parse_mode="HTML"),
            admin_remove_balance_amount, target_uid
        )
    else:
        bot.send_message(ADMIN_ID, "❌ Invalid ID. Please send a valid Telegram ID.", reply_markup=admin_menu())

def admin_remove_balance_amount(m, target_uid):
    if not m or not m.text:
        return
    if m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    try:
        amount = float(m.text.strip())
        if amount <= 0:
            return bot.send_message(ADMIN_ID, "❌ Amount must be greater than 0. Try again:")
        current_balance = get_balance(target_uid)
        if amount > current_balance:
            return bot.send_message(ADMIN_ID, f"❌ User only has {f_num(current_balance)} TK. Cannot remove {f_num(amount)} TK.\nEnter new amount:", reply_markup=admin_menu())
        
        update_balance(target_uid, -amount, f"User_{target_uid}")
        bot.send_message(ADMIN_ID, f"✅ Successfully removed {f_num(amount)} TK from User ID <code>{target_uid}</code>.\nNew Balance: {f_num(get_balance(target_uid))} TK", parse_mode="HTML")
        try:
            bot.send_message(target_uid, f"⚠️ Admin removed {f_num(amount)} TK from your balance!\n💰 New Balance: {f_num(get_balance(target_uid))} TK")
        except:
            bot.send_message(ADMIN_ID, "⚠️ User did not start the bot yet, but balance updated.")
    except ValueError:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, "❌ Invalid amount. Try again:"), admin_remove_balance_amount, target_uid)

# ============================================================
# SALES REPORT MENU
# ============================================================

def sales_report_menu():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(
        types.InlineKeyboardButton("📅 Today", callback_data="sales_today"),
        types.InlineKeyboardButton("🗓️ Last 7 Days", callback_data="sales_7days"),
        types.InlineKeyboardButton("📆 Last 30 Days", callback_data="sales_30days"),
        types.InlineKeyboardButton("📊 All Time", callback_data="sales_all")
    )
    return m

def api_settings_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    active = get_active_provider().upper()
    m.add(f"🔄 Active API: [{active}] (Click to Switch)")
    m.add("🟢 Change ZiniPay API", "🪙 Change OxaPay API")
    m.add("🔵 Change G2Bulk API", "🔴 Change Bay2Game API")
    m.add("🔙 Admin Menu")
    return m

def build_stock_markup():
    mk = types.InlineKeyboardMarkup(row_width=1)
    for k, v in FF_PKG.items():
        icon = "❌" if v.get("stock_out") else "✅"
        mk.add(types.InlineKeyboardButton(f"{icon} {v['name']}", callback_data=f"sff_{k}"))
    return mk

def build_price_change_markup():
    mk = types.InlineKeyboardMarkup(row_width=1)
    for k, v in FF_PKG.items():
        mk.add(types.InlineKeyboardButton(f"✏️ {v['name']} - {f_num(v['price'])} TK", callback_data=f"editprice_{k}"))
    return mk

def provider_switch_keyboard():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("🔵 G2Bulk", callback_data="set_prov_g2bulk"),
           types.InlineKeyboardButton("🔴 Bay2Game", callback_data="set_prov_bay2game"))
    return mk

def get_user_list_keyboard(users, action):
    mk = types.InlineKeyboardMarkup(row_width=2)
    count = 0
    for user_id, name, balance, banned in users:
        if count >= 20:
            break
        status_icon = "🔴" if banned else "🟢"
        display_name = name[:15] if name else f"User_{user_id}"
        callback_data = f"{action}_{user_id}"
        mk.add(types.InlineKeyboardButton(f"{status_icon} {display_name}", callback_data=callback_data))
        count += 1
    mk.add(types.InlineKeyboardButton("🔙 Admin Menu", callback_data="back_admin"))
    return mk

def get_user_list_keyboard_remove(users):
    mk = types.InlineKeyboardMarkup(row_width=2)
    count = 0
    for user_id, name, balance, banned in users:
        if count >= 20:
            break
        display_name = name[:15] if name else f"User_{user_id}"
        callback_data = f"remove_{user_id}"
        mk.add(types.InlineKeyboardButton(f"💰 {display_name} ({f_num(balance)} TK)", callback_data=callback_data))
        count += 1
    mk.add(types.InlineKeyboardButton("🔙 Admin Menu", callback_data="back_admin"))
    return mk

# ============================================================
# MY ACCOUNT HELPER
# ============================================================

def show_my_account(m):
    uid = m.from_user.id
    username = m.from_user.username
    username_str = f"{username}" if username else m.from_user.first_name or f"User_{uid}"
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT balance, joined_at FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    balance = r[0] if r else 0
    joined_at = r[1] if (r and r[1]) else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("SELECT COUNT(id), SUM(price) FROM orders WHERE user_id=? AND status='Complete'", (uid,))
    orders_data = c.fetchone()
    total_orders = orders_data[0] if orders_data and orders_data[0] else 0
    total_spent = orders_data[1] if orders_data and orders_data[1] else 0
    
    conn.close()
    
    account_msg = (
        f"🆔 Telegram ID: {uid}\n"
        f"📝 Username: {username_str}\n"
        f"💰 Balance: {f_num(balance)} TK\n"
        f"📊 Status: ✅ Active\n"
        f"🛍️ Total Orders: {total_orders}\n"
        f"💸 Total Spent: {f_num(total_spent)} TK\n"
        f"📅 Joined: {joined_at}"
    )
    bot.send_message(m.chat.id, account_msg, reply_markup=main_menu())

# ============================================================
# CALLBACK HANDLERS
# ============================================================

@bot.callback_query_handler(func=lambda c: c.data.startswith("sales_"))
def cb_sales_report(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    action = call.data
    if action == "sales_today":
        counts, total = get_sales_by_timeframe(days=0)
        title = "Today's Sales Report"
    elif action == "sales_7days":
        counts, total = get_sales_by_timeframe(days=7)
        title = "Last 7 Days Sales Report"
    elif action == "sales_30days":
        counts, total = get_sales_by_timeframe(days=30)
        title = "Last 30 Days Sales Report"
    else:
        counts, total = get_sales_by_timeframe(days=None)
        title = "All Time Sales Report"
        
    msg = format_sales_report(title, counts, total)
    try:
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=sales_report_menu())
    except:
        pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cancel_pay_"))
def cb_cancel_payment(call):
    uid = call.from_user.id
    delete_pending_payment(uid)
    bot.answer_callback_query(call.id, "❌ Payment Canceled")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    bot.send_message(call.message.chat.id, "❌ পেমেন্ট রিকোয়েস্ট বাতিল করা হয়েছে।", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_prov_"))
def cb_switch_provider(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    prov = call.data.replace("set_prov_", "")
    set_active_provider(prov)
    bot.answer_callback_query(call.id, f"✅ Active API switched to {prov.upper()}!")
    try:
        bot.edit_message_text(f"⚙️ Active TopUp API Provider changed to: {prov.upper()}",
                               call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("sff_"))
def cb_ff_stock(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    key = call.data[4:]
    if key in FF_PKG:
        FF_PKG[key]["stock_out"] = not FF_PKG[key].get("stock_out", False)
        save_pkgs(FF_FILE, FF_PKG)
        state = "❌ Stock Out" if FF_PKG[key]["stock_out"] else "✅ Available"
        bot.answer_callback_query(call.id, f"{FF_PKG[key]['name']}: {state}")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=build_stock_markup())
        except:
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("editprice_"))
def cb_edit_price(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    key = call.data[10:]
    if key in FF_PKG:
        try:
            msg = bot.send_message(call.message.chat.id, f"✏️ Enter new price for {FF_PKG[key]['name']}:\n\n(Just type the new price in Taka. Example: 22)\n(Or to also change USD api cost type: 22 0.16)")
            bot.register_next_step_handler(msg, process_interactive_price_change, key)
        except:
            pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("approve_") or c.data.startswith("reject_"))
def handle_admin_payment_approval(call):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "❌ You are not an admin!")
        
    parts = call.data.split("_")
    action, payment_id = parts[0], int(parts[1])
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, amount, method, trx_id FROM pending_manual_payments WHERE id=? AND status='Pending'", (payment_id,))
    row = c.fetchone()
    
    if not row:
        bot.answer_callback_query(call.id, "❌ Not found or already processed.")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass
        conn.close()
        return
    
    uid, amount, method, trx_id = row
    current_text = call.message.text if call.message.text else "Payment Request Details:"
    
    if action == "approve":
        update_balance(uid, amount)
        log_deposit(uid, amount, method, trx_id, "Complete")
        update_manual_payment_status(payment_id, "Approved")
        bot.send_message(uid, f"✅ Payment Approved!\n💰 {f_num(amount)} TK Added.\nBalance: {f_num(get_balance(uid))} TK", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "✅ Approved!")
        current_text += "\n\n✅ Status: Approved"
    else:
        update_manual_payment_status(payment_id, "Rejected")
        bot.send_message(uid, "❌ Payment Rejected by Admin.", reply_markup=main_menu())
        bot.answer_callback_query(call.id, "❌ Rejected!")
        current_text += "\n\n❌ Status: Rejected"
        
    try:
        bot.edit_message_text(current_text, call.message.chat.id, call.message.message_id, reply_markup=None)
    except:
        pass
    conn.close()

# --- Ban/Unban/Notice/Remove Balance Callbacks ---

@bot.callback_query_handler(func=lambda c: c.data.startswith("ban_") or c.data.startswith("unban_"))
def cb_ban_unban_user(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    
    action, user_id = call.data.split("_")
    user_id = int(user_id)
    
    if action == "ban":
        ban_user(user_id)
        bot.answer_callback_query(call.id, f"✅ User {user_id} Banned!")
        bot.send_message(ADMIN_ID, f"🚫 User {user_id} has been banned.")
        try:
            bot.send_message(user_id, "🚫 You have been banned from using this bot.")
        except:
            pass
    else:
        unban_user(user_id)
        bot.answer_callback_query(call.id, f"✅ User {user_id} Unbanned!")
        bot.send_message(ADMIN_ID, f"✅ User {user_id} has been unbanned.")
        try:
            bot.send_message(user_id, "✅ You have been unbanned from using this bot.")
        except:
            pass
    
    users = get_all_users()
    if action == "ban":
        keyboard = get_user_list_keyboard(users, "ban")
    else:
        keyboard = get_user_list_keyboard(users, "unban")
    
    try:
        bot.edit_message_text("👥 Select a user to manage:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_"))
def cb_remove_balance(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    
    user_id = int(call.data.split("_")[1])
    bot.send_message(ADMIN_ID, f"💵 Enter amount to remove from User ID <code>{user_id}</code>:", parse_mode="HTML")
    bot.register_next_step_handler_by_chat_id(ADMIN_ID, admin_remove_balance_amount, user_id)
    bot.answer_callback_query(call.id, "Enter amount to remove")

@bot.callback_query_handler(func=lambda c: c.data == "back_admin")
def cb_back_admin(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied")
        return
    try:
        bot.edit_message_text("📊 Admin Panel:", call.message.chat.id, call.message.message_id, reply_markup=admin_menu())
    except:
        bot.send_message(call.message.chat.id, "📊 Admin Panel:", reply_markup=admin_menu())
    bot.answer_callback_query(call.id)

# ============================================================
# MESSAGE HANDLERS
# ============================================================

@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    user_first_name = m.from_user.first_name if m.from_user.first_name else f"User_{uid}"
    
    if is_user_banned(uid):
        m_kb = types.InlineKeyboardMarkup(row_width=2)
        channel = get_support_channel()
        admin = get_support_admin()
        m_kb.add(
            types.InlineKeyboardButton("📢 Channel", url=f"https://t.me/{channel}"),
            types.InlineKeyboardButton("👨‍💻 Support Admin", url=f"https://t.me/{admin}")
        )
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.\n\nContact admin for more information.", reply_markup=m_kb)
    
    update_balance(uid, 0, user_first_name)
    if uid != ADMIN_ID and get_bot_status() == "OFF":
        m_kb = types.InlineKeyboardMarkup(row_width=2)
        channel = get_support_channel()
        admin = get_support_admin()
        m_kb.add(
            types.InlineKeyboardButton("📢 Channel", url=f"https://t.me/{channel}"),
            types.InlineKeyboardButton("👨‍💻 Support Admin", url=f"https://t.me/{admin}")
        )
        return bot.send_message(m.chat.id, "🚫 বট অস্থায়ী সময়ের জন্য বন্ধ রয়েছে!\n\nআরো বিস্তারিত জানতে টেলিগ্রাম চ্যানেলে জয়েন হন বা এডমিন কে মেসেজ দিন।", reply_markup=m_kb)
        
    bot.send_message(m.chat.id, "👋 Welcome! Select an option below.", reply_markup=main_menu())

@bot.message_handler(commands=["admin"])
def admin_cmd(m):
    if m.from_user.id == ADMIN_ID:
        bot.send_message(m.chat.id, "📊 Admin Panel:", reply_markup=admin_menu())

# ============================================================
# PAYMENT FUNCTIONS
# ============================================================

def process_zinipay_payment(m):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    try:
        amount = float(m.text.strip())
        if amount < 10:
            return bot.send_message(m.chat.id, "❌ Min 10 TK required.", reply_markup=main_menu())
    except:
        return bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ Valid amount:"), process_zinipay_payment)
    
    uid = m.from_user.id
    
    if is_user_banned(uid):
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.", reply_markup=main_menu())
    
    msg = bot.send_message(m.chat.id, "⏳ Loading Gateway...")
    url, inv, err = create_zinipay_invoice(uid, amount, m.from_user.first_name or "User")
    if url:
        save_pending_payment(uid, amount, inv)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 Pay Now", url=url),
            types.InlineKeyboardButton("❌ Cancel Payment", callback_data=f"cancel_pay_{inv}")
        )
        try:
            bot.delete_message(m.chat.id, msg.message_id)
        except:
            pass
        
        link_msg = bot.send_message(
            m.chat.id,
            f"📢 Auto Payment Request\n\n💰 Amount: {f_num(amount)} TK\n\n👇 নিচের লিংকে ক্লিক করে পেমেন্ট সম্পন্ন করুন।",
            reply_markup=markup
        )
        poll_zinipay_payment(uid, inv, amount, m.chat.id, link_msg.message_id)
    else:
        bot.send_message(m.chat.id, f"❌ Gateway Error: {err}", reply_markup=main_menu())

def process_oxapay_payment_bdt(m):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    try:
        amount_bdt = float(m.text.strip())
        if amount_bdt < 50:
            return bot.send_message(m.chat.id, "❌ Minimum 50 BDT required for crypto payment.", reply_markup=main_menu())
    except:
        return bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ Enter valid BDT amount:"), process_oxapay_payment_bdt)
    
    uid = m.from_user.id
    
    if is_user_banned(uid):
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.", reply_markup=main_menu())
    
    rate = get_dollar_rate()
    amount_usd = round(amount_bdt / rate, 2)
    
    if amount_usd < 0.5:
        return bot.send_message(m.chat.id, f"❌ Minimum 0.5 USD required.\n\n{amount_bdt} BDT = ${amount_usd} USD at rate {rate} TK\nPlease add more BDT.", reply_markup=main_menu())
    
    msg = bot.send_message(m.chat.id, "⏳ Creating Crypto Invoice...")
    url, track_id, err = create_oxapay_invoice(uid, amount_usd, m.from_user.first_name or "User")
    
    if url and track_id:
        save_pending_payment(uid, amount_bdt, track_id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 Pay with OxaPay (Crypto)", url=url),
            types.InlineKeyboardButton("❌ Cancel Payment", callback_data=f"cancel_pay_{track_id}")
        )
        try:
            bot.delete_message(m.chat.id, msg.message_id)
        except:
            pass
        
        link_msg = bot.send_message(
            m.chat.id,
            f"📢 <b>OxaPay Crypto Auto Payment</b>\n\n"
            f"💰 BDT Amount: <b>{f_num(amount_bdt)} TK</b>\n"
            f"💵 USD Required: <b>${amount_usd} USDT</b>\n"
            f"📈 Rate: 1 USD = {rate} TK\n\n"
            f"👇 নিচের লিংকে ক্লিক করে আপনার ওয়ালেট বা এক্সচেঞ্জ থেকে ${amount_usd} USDT পেমেন্ট করুন।",
            parse_mode="HTML",
            reply_markup=markup
        )
        poll_oxapay_payment(uid, track_id, amount_usd, amount_bdt, m.chat.id, link_msg.message_id)
    else:
        error_msg = err if err else "Unknown error"
        bot.send_message(m.chat.id, f"❌ Crypto Gateway Error: {error_msg}", reply_markup=main_menu())

def process_manual_payment_step1(m, method):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    if m.text == "🔙 Back to Methods":
        return bot.send_message(m.chat.id, "💳 Select Payment Method:", reply_markup=payment_menu())
    try:
        amount = float(m.text.strip())
        if amount < 10:
            return bot.send_message(m.chat.id, "❌ Minimum 10 TK required.", reply_markup=main_menu())
    except:
        return bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ Send valid amount:"), process_manual_payment_step1, method)
    
    uid = m.from_user.id
    
    if is_user_banned(uid):
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.", reply_markup=main_menu())
    
    bot.register_next_step_handler(
        bot.send_message(m.chat.id, f"📌 {method} Personal: 01778153826\n\nউপরে দেওয়া নাম্বারে {f_num(amount)} TK সেন্ড মানি করে Trx ID দিন:"),
        process_manual_payment_step2, method, amount
    )

def process_manual_payment_step2(m, method, amount):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    if m.text == "🔙 Back to Methods":
        return bot.send_message(m.chat.id, "💳 Select Payment Method:", reply_markup=payment_menu())
    trx_id = m.text.strip()
    uid = m.from_user.id
    
    if is_user_banned(uid):
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.", reply_markup=main_menu())
    
    payment_id = save_pending_manual(uid, amount, method, trx_id)
    bot.send_message(m.chat.id, f"✅ Payment Request Submitted!\n💰 Amount: {f_num(amount)} TK\n💳 Method: {method}\n🆔 TrxID: {trx_id}\n⏳ Admin will verify soon.", reply_markup=main_menu())
    admin_msg = f"📋 New Payment Request\n\n👤 User: {m.from_user.first_name}\n🆔 User ID: {uid}\n💰 Amount: {f_num(amount)} TK\n💳 Method: {method}\n🆔 TrxID: {trx_id}\n📅 Time: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}"
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Complete", callback_data=f"approve_{payment_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data=f"reject_{payment_id}")
    )
    try:
        bot.send_message(PAYMENT_CHANNEL_ID, admin_msg, reply_markup=markup)
    except:
        pass

def show_pending_payments(m):
    payments = get_pending_manual_payments()
    if not payments:
        return bot.send_message(ADMIN_ID, "📭 No pending payments.")
    msg = "📋 Pending Payments:\n\n"
    for pid, uid, amount, method, trx_id, date in payments:
        msg += f"🆔 #{pid} | 👤 {get_user_name(uid)} ({uid})\n💰 {f_num(amount)} TK | 💳 {method}\n🆔 {trx_id}\n📅 {date}\n" + "─"*20 + "\n"
    bot.send_message(ADMIN_ID, msg)

def show_history(m, table):
    uid = m.from_user.id
    
    if is_user_banned(uid):
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.", reply_markup=main_menu())
    
    t_name = m.from_user.first_name or f"User_{uid}"
    conn = get_db()
    c = conn.cursor()
    if table == "orders":
        c.execute("SELECT serial_no, date, package, player_id, player_name, price, status, fail_reason FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
        rows = c.fetchall()
        if rows:
            msg = "📦 Your Last 10 Orders:\n\n"
            for row in rows:
                serial, date, pkg, pid, pname, price, status, reason = row
                reason_str = f" ({reason})" if status.lower() in ["canceled", "cancel", "failed"] and reason else ""
                st_formatted = format_status(status)
                msg += (f"📋 Serial NO: {serial}\n📅 Date: {date}\n💎 Package: {pkg}\n🆔 Player ID: {pid}\n"
                        f"👤 Player Name: {pname}\n💰 Price: {f_num(price)} TK\n📌 Status: {st_formatted}{reason_str}\n\n──────────────────\n\n")
            bot.send_message(uid, msg, reply_markup=main_menu())
        else:
            bot.send_message(uid, "📭 No orders found.", reply_markup=main_menu())
    else:
        c.execute("SELECT amount, method, trx_id, status, date FROM deposits WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
        rows = c.fetchall()
        if rows:
            msg = "💵 Add Money History:\n\n"
            for row in rows:
                amount, method, trx, status, date = row
                emoji = "✅" if status.lower() in ["complete", "approved"] else "⏳" if status.lower() == "pending" else "❌"
                msg += (f"👤 User: {t_name}\n🆔 ID: {uid}\n{emoji} {method}: {f_num(amount)} TK\n"
                        f"🆔 TrxID: {trx}\n📅 {date}\n\n──────────────────\n\n")
            bot.send_message(uid, msg, reply_markup=main_menu())
        else:
            bot.send_message(uid, "📭 No deposit history found.", reply_markup=main_menu())
    conn.close()

def ff_get_uid(m, pid):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    if m.text == "🔙 Topup Menu":
        return bot.send_message(m.chat.id, "📌 Select Topup Type:", reply_markup=topup_menu())
    
    uid = m.from_user.id
    
    if is_user_banned(uid):
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.", reply_markup=main_menu())
    
    player_id, p_name = m.text.strip(), "Player"
    bot.send_message(m.chat.id, "🔍 Checking Player Name...")
    
    try:
        g2bulk_headers = {"X-API-Key": get_g2bulk_api_key(), "Content-Type": "application/json"}
        r = requests.post(f"{G2BULK_BASE_URL}/games/checkPlayerId", json={"game": "freefire_bd", "user_id": player_id}, headers=g2bulk_headers, timeout=10).json()
        if r.get("name"):
            p_name = r["name"]
    except:
        pass
    
    pkg = FF_PKG[pid]
    try:
        msg = bot.send_message(
            m.chat.id,
            f"📋 Order Details:\n\n🎮 Game: Free Fire\n👤 Name: {p_name}\n🆔 UID: {player_id}\n💎 Package: {pkg['name']}\n💰 Price: {f_num(pkg['price'])} TK\n\nConfirm Order:",
            reply_markup=confirm_menu()
        )
        bot.register_next_step_handler(msg, place_order, pid, player_id, p_name)
    except:
        pass

def admin_check_serial(m):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    order = get_order_by_serial(m.text.strip())
    if order:
        db_id, uid, game, pkg_name, p_id, p_name, price, status, order_ref, date_str, s_no, reason = order
        bot.send_message(
            m.chat.id,
            f"🔍 Check Result:\n\n{get_admin_order_msg(db_id, s_no, get_user_name(uid), uid, game, p_name, p_id, pkg_name, price, date_str, status, reason)}"
        )
    else:
        bot.send_message(m.chat.id, "❌ Order not found!")

def get_user_bio(m):
    if not m or not m.text:
        return
    if m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    try:
        target_uid = int(m.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, balance, banned FROM users WHERE user_id=?", (target_uid,))
        u_info = c.fetchone()
        if not u_info:
            conn.close()
            return bot.send_message(m.chat.id, "❌ User not found in database.", reply_markup=admin_menu())
            
        name, balance, banned = u_info
        status_text = "🚫 Banned" if banned else "✅ Active"
        c.execute("SELECT COUNT(id), SUM(price) FROM orders WHERE user_id=? AND status='Complete'", (target_uid,))
        orders_info = c.fetchone()
        total_orders = orders_info[0] or 0
        total_spent = orders_info[1] or 0
        
        c.execute("SELECT SUM(amount) FROM deposits WHERE user_id=? AND status IN ('Complete', 'Approved')", (target_uid,))
        deposits_info = c.fetchone()
        total_deposited = deposits_info[0] or 0
        conn.close()
        
        bio_msg = (f"👤 <b>User Bio-Data:</b>\n\n"
                   f"📛 <b>Name:</b> {name}\n"
                   f"🆔 <b>TG ID:</b> <code>{target_uid}</code>\n"
                   f"📊 <b>Status:</b> {status_text}\n"
                   f"💰 <b>Current Balance:</b> {f_num(balance)} TK\n"
                   f"──────────────────\n"
                   f"📦 <b>Total Packages Bought:</b> {total_orders} Pcs\n"
                   f"💸 <b>Total Money Spent:</b> {f_num(total_spent)} TK\n"
                   f"📥 <b>Total Money Added:</b> {f_num(total_deposited)} TK\n")
        bot.send_message(m.chat.id, bio_msg, parse_mode="HTML", reply_markup=admin_menu())
    except ValueError:
        bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ Invalid ID. Try again:"), get_user_bio)

def admin_add_bal_uid(m):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    try:
        target_uid = int(m.text.strip())
        bot.register_next_step_handler(bot.send_message(m.chat.id, f"💵 Enter amount to add for User ID <code>{target_uid}</code>:", parse_mode="HTML"), admin_add_bal_amount, target_uid)
    except ValueError:
        bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ Invalid ID. Try again:"), admin_add_bal_uid)

def admin_add_bal_amount(m, target_uid):
    if not m or not m.text:
        return
    if m.text == "🔙 Main Menu":
        return start(m)
    try:
        amount = float(m.text.strip())
        update_balance(target_uid, amount, f"User_{target_uid}")
        bot.send_message(m.chat.id, f"✅ Successfully added {f_num(amount)} TK to User ID <code>{target_uid}</code>.\nNew Balance: {f_num(get_balance(target_uid))} TK", parse_mode="HTML")
        try:
            bot.send_message(target_uid, f"🎁 Admin added {f_num(amount)} TK to your balance!\n💰 New Balance: {f_num(get_balance(target_uid))} TK")
        except:
            bot.send_message(m.chat.id, "⚠️ User did not start the bot yet, but balance saved.")
    except ValueError:
        bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ Invalid amount. Try again:"), admin_add_bal_amount, target_uid)

def admin_ban_unban_by_id(m):
    if not m or not m.text:
        return
    if m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    
    try:
        target_uid = int(m.text.strip())
        
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, name, banned FROM users WHERE user_id=?", (target_uid,))
        user = c.fetchone()
        conn.close()
        
        if not user:
            return bot.send_message(ADMIN_ID, f"❌ User ID <code>{target_uid}</code> not found in database.", parse_mode="HTML", reply_markup=admin_menu())
        
        user_id, name, banned = user
        status_text = "🔴 Banned" if banned else "🟢 Active"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        if banned:
            markup.add(types.InlineKeyboardButton("✅ Unban User", callback_data=f"unban_{user_id}"))
        else:
            markup.add(types.InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{user_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Admin Menu", callback_data="back_admin"))
        
        bot.send_message(
            ADMIN_ID,
            f"👤 <b>User Found:</b>\n\n"
            f"📛 Name: {name}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📊 Status: {status_text}\n\n"
            f"What would you like to do?",
            parse_mode="HTML",
            reply_markup=markup
        )
        
    except ValueError:
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, "❌ Invalid ID. Please enter a valid Telegram ID (numbers only):"),
            admin_ban_unban_by_id
        )

def admin_send_notice(m):
    if not m or not m.text:
        return
    if m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    
    notice_text = m.text
    users = get_all_users()
    
    sent_count = 0
    failed_count = 0
    
    bot.send_message(ADMIN_ID, f"📢 Sending notice to {len(users)} users...")
    
    for user_id, name, balance, banned in users:
        try:
            if banned:
                continue
            bot.send_message(
                user_id,
                f"📢 <b>Admin Notice</b>\n\n{notice_text}\n\n- Admin",
                parse_mode="HTML"
            )
            sent_count += 1
            time.sleep(0.1)
        except Exception as e:
            failed_count += 1
    
    bot.send_message(
        ADMIN_ID,
        f"✅ Notice sent!\n\n📤 Sent: {sent_count} users\n❌ Failed: {failed_count} users",
        reply_markup=admin_menu()
    )

def update_dollar_rate(m):
    if not m or not m.text:
        return
    if m.text in ["🔙 Admin Menu", "🔙 Main Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    try:
        rate = float(m.text.strip())
        if rate <= 0:
            raise ValueError
        set_dollar_rate(rate)
        success_msg = f"✅ <b>Dollar rate updated to:</b> {rate} TK\n\n" + generate_profit_report_msg(rate)
        bot.send_message(ADMIN_ID, success_msg, parse_mode="HTML", reply_markup=admin_menu())
    except ValueError:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, "❌ Invalid rate. Try again:"), update_dollar_rate)

def change_zinipay_api(m):
    if not m or not m.text:
        return
    if m.text.lower() in ["cancel", "🔙 admin menu"]:
        return bot.send_message(ADMIN_ID, "❌ Cancelled.", reply_markup=admin_menu())
    set_zinipay_api_key(m.text.strip())
    bot.send_message(ADMIN_ID, "✅ ZiniPay API Key updated!", reply_markup=admin_menu())

def change_oxapay_api(m):
    if not m or not m.text:
        return
    if m.text.lower() in ["cancel", "🔙 admin menu"]:
        return bot.send_message(ADMIN_ID, "❌ Cancelled.", reply_markup=admin_menu())
    set_oxapay_api_key(m.text.strip())
    bot.send_message(ADMIN_ID, "✅ OxaPay API Key updated!", reply_markup=admin_menu())

def change_g2bulk_api(m):
    if not m or not m.text:
        return
    if m.text.lower() in ["cancel", "🔙 admin menu"]:
        return bot.send_message(ADMIN_ID, "❌ Cancelled.", reply_markup=admin_menu())
    set_g2bulk_api_key(m.text.strip())
    bot.send_message(ADMIN_ID, "✅ G2Bulk API Key updated!", reply_markup=admin_menu())

def change_bay2game_api(m):
    if not m or not m.text:
        return
    if m.text.lower() in ["cancel", "🔙 admin menu"]:
        return bot.send_message(ADMIN_ID, "❌ Cancelled.", reply_markup=admin_menu())
    set_bay2game_api_key(m.text.strip())
    bot.send_message(ADMIN_ID, "✅ Bay2Game API Key updated!", reply_markup=admin_menu())

def change_support_channel(m):
    if not m or not m.text:
        return
    if m.text.lower() in ["cancel", "🔙 admin menu"]:
        return bot.send_message(ADMIN_ID, "❌ Cancelled.", reply_markup=admin_menu())
    username = m.text.strip().replace("@", "")
    set_support_channel(username)
    bot.send_message(ADMIN_ID, f"✅ Support Channel updated to: @{username}", reply_markup=admin_menu())

def change_support_admin(m):
    if not m or not m.text:
        return
    if m.text.lower() in ["cancel", "🔙 admin menu"]:
        return bot.send_message(ADMIN_ID, "❌ Cancelled.", reply_markup=admin_menu())
    username = m.text.strip().replace("@", "")
    set_support_admin(username)
    bot.send_message(ADMIN_ID, f"✅ Support Admin updated to: @{username}", reply_markup=admin_menu())

def process_interactive_price_change(m, key):
    if not m or not m.text:
        return
    if m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    parts = m.text.strip().split()
    try:
        price = float(parts[0])
        FF_PKG[key]["price"] = price
        if len(parts) >= 2:
            FF_PKG[key]["api_cost_usd"] = float(parts[1])
        save_pkgs(FF_FILE, FF_PKG)
        msg = f"✅ {FF_PKG[key]['name']} updated!\n💰 New Sell Price: {f_num(price)} TK"
        if len(parts) >= 2:
            msg += f"\n💲 New API Cost: $ {FF_PKG[key]['api_cost_usd']}"
        bot.send_message(m.chat.id, msg, reply_markup=admin_menu())
    except:
        bot.send_message(m.chat.id, "❌ Invalid format. Enter numbers only.", reply_markup=admin_menu())

def process_db_restore(m):
    if m.text and m.text in ["🔙 Main Menu", "🔙 Admin Menu"]:
        return bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    if not m.document:
        return bot.register_next_step_handler(bot.send_message(m.chat.id, "❌ ফাইল পাওয়া যায়নি! ব্যাকআপ `users.db` ফাইলটি আপলোড করুন:"), process_db_restore)
    try:
        file_info = bot.get_file(m.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(DB_PATH, 'wb') as new_db:
            new_db.write(downloaded_file)
        init_db()
        bot.send_message(ADMIN_ID, "✅ Database Restored Successfully!", reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Restore Failed: {str(e)}", reply_markup=admin_menu())

# ============================================================
# REPORT FUNCTIONS
# ============================================================

def get_sales_by_timeframe(days=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT package, price, date FROM orders WHERE status='Complete'")
    rows = c.fetchall()
    conn.close()

    now = datetime.now()
    today_str = now.strftime("%d-%m-%Y")
    pkg_counts = {}
    total_money = 0
    
    for pkg_name, price, date_str in rows:
        try:
            order_time = datetime.strptime(date_str, "%d-%m-%Y %I:%M %p")
        except:
            continue
        
        is_match = False
        if days is None:
            is_match = True
        elif days == 0 and order_time.strftime("%d-%m-%Y") == today_str:
            is_match = True
        elif days and order_time >= now - timedelta(days=days):
            is_match = True
                
        if is_match:
            pkg_counts[pkg_name] = pkg_counts.get(pkg_name, 0) + 1
            total_money += price
            
    return pkg_counts, total_money

def format_sales_report(title, pkg_counts, total_money):
    report = f"📈 <b>{title}</b>\n\n💰 <b>Total Sales: {f_num(total_money)} TK</b>\n──────────────────\n"
    if not pkg_counts:
        report += "📭 No sales found for this timeframe."
    else:
        for pkg_name, count in pkg_counts.items():
            report += f"💎 {pkg_name}: {count} Pcs\n"
    return report + "──────────────────"

def generate_profit_report_msg(rate):
    msg = f"💵 <b>Current Dollar Rate:</b> {rate} TK\n\n<b>📦 Package Profits:</b>\n──────────────────\n"
    for k, v in FF_PKG.items():
        cost_tk = v.get("api_cost_usd", 0) * rate
        sell_tk = v["price"]
        profit = sell_tk - cost_tk
        msg += f"💎 <b>{v['name']}</b>:\n   Sell: {f_num(sell_tk)} TK | Cost: {f_num(cost_tk)} TK | <b>Profit: {f_num(profit)} TK</b>\n\n"
    return msg + "──────────────────\n"

# ============================================================
# MAIN MESSAGE HANDLER
# ============================================================

@bot.message_handler(func=lambda m: True)
def handle(m):
    uid = m.from_user.id
    text = m.text
    
    if not text:
        return
    
    if uid != ADMIN_ID and is_user_banned(uid):
        m_kb = types.InlineKeyboardMarkup(row_width=2)
        channel = get_support_channel()
        admin = get_support_admin()
        m_kb.add(
            types.InlineKeyboardButton("📢 Channel", url=f"https://t.me/{channel}"),
            types.InlineKeyboardButton("👨‍💻 Support Admin", url=f"https://t.me/{admin}")
        )
        return bot.send_message(m.chat.id, "🚫 You are banned from using this bot.\n\nContact admin for more information.", reply_markup=m_kb)
    
    if uid != ADMIN_ID and get_bot_status() == "OFF":
        m_kb = types.InlineKeyboardMarkup(row_width=2)
        channel = get_support_channel()
        admin = get_support_admin()
        m_kb.add(
            types.InlineKeyboardButton("📢 Channel", url=f"https://t.me/{channel}"),
            types.InlineKeyboardButton("👨‍💻 Support Admin", url=f"https://t.me/{admin}")
        )
        return bot.send_message(m.chat.id, "🚫 বট অস্থায়ী সময়ের জন্য বন্ধ রয়েছে!\n\nআরো বিস্তারিত জানতে টেলিগ্রাম চ্যানেলে জয়েন হন বা এডমিন কে মেসেজ দিন।", reply_markup=m_kb)
    
    if text in ["🔙 Main Menu", "Main Menu"]:
        bot.send_message(m.chat.id, "🏠 Main Menu:", reply_markup=main_menu())
    elif text in ["💎 Topup", "Topup"]:
        bot.send_message(m.chat.id, "📌 Select Topup Type:", reply_markup=topup_menu())
    elif text == "🔙 Topup Menu":
        bot.send_message(m.chat.id, "📌 Select Topup Type:", reply_markup=topup_menu())
    elif text == "💎 ID Code Topup":
        bot.send_message(m.chat.id, "🔥 Select Free Fire Package:", reply_markup=id_code_topup_menu())
    elif text == "📅 Weekly & Monthly":
        bot.send_message(m.chat.id, "📅 Select Weekly/Monthly Package:", reply_markup=weekly_monthly_menu())
    elif text in ["💰 Balance", "Balance"]:
        bot.send_message(m.chat.id, f"💰 Balance: {f_num(get_balance(uid))} TK")
    elif text in ["👤 My Account", "My Account"]:
        show_my_account(m)
    elif text in ["➕ Add Balance", "Add Balance"]:
        bot.send_message(m.chat.id, "💳 Select Payment Method:", reply_markup=payment_menu())
    elif text == "🔙 Back to Methods":
        bot.send_message(m.chat.id, "💳 Select Payment Method:", reply_markup=payment_menu())
    elif text == "📝 Manual Payment":
        bot.send_message(m.chat.id, "📝 Select Manual Payment Method:", reply_markup=manual_payment_menu())
    elif text in ["💳 Auto payment (BDT)", "💳 Auto payment"]:
        bot.register_next_step_handler(bot.send_message(m.chat.id, "💵 Enter Amount to add in BDT (TK)\n(Min: 10 TK)", reply_markup=types.ReplyKeyboardRemove()), process_zinipay_payment)
    elif text in ["🪙 Crypto Auto (OxaPay)", "🪙 Crypto Auto"]:
        bot.register_next_step_handler(bot.send_message(
            m.chat.id,
            f"🪙 <b>OxaPay Crypto Auto Deposit</b>\n\n💵 Current Rate: 1 USD = {get_dollar_rate()} TK\n\nকত টাকা (BDT) এড করতে চান তা টাইপ করুন:\n(Example: 500 or 1000 or 2500)",
            parse_mode="HTML",
            reply_markup=types.ReplyKeyboardRemove()
        ), process_oxapay_payment_bdt)
    elif text in ["💵 Bkash", "💵 Nagad"]:
        method = text.replace("💵 ", "")
        bot.register_next_step_handler(bot.send_message(m.chat.id, f"💵 {method} এ কত টাকা এড করতে চান?\n(Min: 10 TK)", reply_markup=types.ReplyKeyboardRemove()), process_manual_payment_step1, method)
    elif text in ["📜 History", "History"]:
        bot.send_message(m.chat.id, "📜 Select History Type:", reply_markup=history_menu())
    elif text == "📦 Order History":
        show_history(m, "orders")
    elif text == "💵 Add Money History":
        show_history(m, "deposits")
    elif text in ["📞 Support", "Support"]:
        bot.send_message(m.chat.id, "👨‍💻 Contact Admin for help:", reply_markup=support_keyboard())
    elif text.startswith("💎") and "|" in text:
        parts = text.split("|")
        if len(parts) == 2:
            pkg_name = parts[0].replace("💎", "").strip()
            pkg_key = None
            for k, v in FF_PKG.items():
                if v['name'] == pkg_name and not v.get("stock_out"):
                    pkg_key = k
                    break
            if pkg_key:
                bot.register_next_step_handler(
                    bot.send_message(m.chat.id, f"🎯 Send Player UID for {FF_PKG[pkg_key]['name']}:"),
                    ff_get_uid, pkg_key
                )
            else:
                bot.send_message(m.chat.id, "❌ Package not found or out of stock.", reply_markup=topup_menu())
    elif text.startswith("🚫 "):
        bot.send_message(m.chat.id, "⚠️ This package is Stock Out. Select another.")
    elif text == "🔙 Admin Menu" and uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "📊 Admin Panel:", reply_markup=admin_menu())
    elif (text.startswith("🟢 Bot Status:") or text.startswith("🔴 Bot Status:")) and uid == ADMIN_ID:
        curr = get_bot_status()
        new_status = "OFF" if curr == "ON" else "ON"
        set_bot_status(new_status)
        st_text = "🟢 Bot is now ONLINE!" if new_status == "ON" else "🔴 Bot is now OFF (Maintenance Mode)!"
        bot.send_message(ADMIN_ID, f"✅ {st_text}", reply_markup=admin_menu())
    elif text == "💵 Set Dollar Rate" and uid == ADMIN_ID:
        rate = get_dollar_rate()
        msg = f"💵 <b>Current Dollar Rate:</b> {rate} TK\n\n✏️ Enter new dollar rate (1 USD = ? BDT):\n(Example: 125 or 128.5)"
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, msg, parse_mode="HTML"), update_dollar_rate)
    elif text == "📊 Stats" and uid == ADMIN_ID:
        conn = get_db()
        c = conn.cursor()
        users_list = c.execute("SELECT user_id, name, balance, banned FROM users").fetchall()
        tu = len(users_list)
        pending = c.execute("SELECT COUNT(*) FROM pending_manual_payments WHERE status='Pending'").fetchone()[0]
        banned_count = c.execute("SELECT COUNT(*) FROM users WHERE banned=1").fetchone()[0]
        conn.close()
        
        users_str = ""
        for u_id, name, bal, banned in users_list:
            status_icon = "🔴" if banned else "🟢"
            safe_name = str(name).replace("<", "&lt;").replace(">", "&gt;")
            users_str += f"{status_icon} {safe_name} (<code>{u_id}</code>) - 💰 {f_num(bal)} TK\n"
        
        stats_msg = (f"📊 <b>Admin Stats:</b>\n\n👥 Total Users: {tu}\n🚫 Banned Users: {banned_count}\n⏳ Pending Manual Payments: {pending}\n\n📋 <b>All Users List:</b>\n──────────────────\n{users_str}")
        bot.send_message(ADMIN_ID, stats_msg, parse_mode="HTML")
    elif text == "📈 Sales Report" and uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "📊 Select a timeframe for Sales Report:", reply_markup=sales_report_menu())
    elif text == "📋 Pending Payments" and uid == ADMIN_ID:
        show_pending_payments(m)
    elif text == "⚙️ FF Price Change" and uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "👇 Select a package to change its price:", reply_markup=build_price_change_markup())
    elif text == "📦 Stock Out Manage" and uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "📦 Stock Out Management\n✅ = Available | ❌ = Stock Out\nClick to toggle:", reply_markup=build_stock_markup())
    elif text == "🔍 Check Order (Serial)" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, "📋 Enter Serial No (e.g., #A7K9M2P1):"), admin_check_serial)
    elif text == "💰 Add User Balance" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, "👤 Enter User's Telegram ID:"), admin_add_bal_uid)
    elif text == "💰 Remove Balance" and uid == ADMIN_ID:
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, "👤 Enter User's Telegram ID to remove balance:\n\n(Example: 8766653823)"),
            admin_remove_balance
        )
    elif text == "👤 User Details" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, "👤 Enter User's Telegram ID:"), get_user_bio)
    elif text == "💵 Profit Calculator" and uid == ADMIN_ID:
        rate = get_dollar_rate()
        msg = generate_profit_report_msg(rate) + "✏️ <i>Send new dollar rate to update, or click '🔙 Admin Menu' to cancel.</i>"
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, msg, parse_mode="HTML"), update_dollar_rate)
    elif text == "💾 Backup DB" and uid == ADMIN_ID:
        if os.path.exists(DB_PATH):
            try:
                with open(DB_PATH, "rb") as doc:
                    bot.send_document(ADMIN_ID, doc, caption=f"📦 Database Backup File\n📅 Date: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}")
            except:
                pass
    elif text == "📥 Restore DB" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, "📥 Database Restore\n\nফাইল আপলোড করুন: "), process_db_restore)
    elif text == "🔑 API Settings" and uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "⚙️ API Settings & Provider Switcher:", reply_markup=api_settings_menu())
    elif text.startswith("🔄 Active API:") and uid == ADMIN_ID:
        curr = get_active_provider().upper()
        bot.send_message(ADMIN_ID, f"🌐 Current Active API Provider: {curr}\n\nChoose API provider to process topup orders:", reply_markup=provider_switch_keyboard())
    elif text == "🟢 Change ZiniPay API" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, f"Current ZiniPay API:\n{get_zinipay_api_key()}\n\n✏️ Send new API Key:"), change_zinipay_api)
    elif text == "🪙 Change OxaPay API" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, f"Current OxaPay API:\n{get_oxapay_api_key()}\n\n✏️ Send new API Key:"), change_oxapay_api)
    elif text == "🔵 Change G2Bulk API" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, f"Current G2Bulk API:\n{get_g2bulk_api_key()}\n\n✏️ Send new API Key:"), change_g2bulk_api)
    elif text == "🔴 Change Bay2Game API" and uid == ADMIN_ID:
        bot.register_next_step_handler(bot.send_message(ADMIN_ID, f"Current Bay2Game API:\n{get_bay2game_api_key()}\n\n✏️ Send new API Key:"), change_bay2game_api)
    elif text == "🚫 User Ban" and uid == ADMIN_ID:
        users = get_all_users()
        bot.send_message(ADMIN_ID, "👥 Select a user to ban:\n(🔴 = Banned, 🟢 = Active)", reply_markup=get_user_list_keyboard(users, "ban"))
    elif text == "✅ User Unban" and uid == ADMIN_ID:
        users = get_all_users()
        bot.send_message(ADMIN_ID, "👥 Select a user to unban:\n(🔴 = Banned, 🟢 = Active)", reply_markup=get_user_list_keyboard(users, "unban"))
    elif text == "📢 Send Notice" and uid == ADMIN_ID:
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, "📢 Enter notice message to send to all users:\n\n(This will be sent to all users who started the bot)"),
            admin_send_notice
        )
    elif text == "🔢 Ban/Unban by ID" and uid == ADMIN_ID:
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, "🔢 Enter the Telegram ID of the user you want to ban/unban:\n\n(Example: 8766653823)"),
            admin_ban_unban_by_id
        )
    elif text == "🔧 Support Settings" and uid == ADMIN_ID:
        channel = get_support_channel()
        admin = get_support_admin()
        bot.send_message(
            ADMIN_ID,
            f"🔧 <b>Support Settings</b>\n\n"
            f"📢 Current Channel: @{channel}\n"
            f"👨‍💻 Current Admin: @{admin}\n\n"
            f"Select an option below to change:",
            parse_mode="HTML",
            reply_markup=support_settings_menu()
        )
    elif text == "📢 Change Channel" and uid == ADMIN_ID:
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, "📢 Enter new channel username:\n\n(Example: freefiretopup_bd)\n\nOr type 'cancel' to cancel:"),
            change_support_channel
        )
    elif text == "👨‍💻 Change Admin" and uid == ADMIN_ID:
        bot.register_next_step_handler(
            bot.send_message(ADMIN_ID, "👨‍💻 Enter new admin username:\n\n(Example: sazzat_20)\n\nOr type 'cancel' to cancel:"),
            change_support_admin
        )

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    init_db()
    print("🚀 Bot Started Successfully...")
    print(f"✅ Active Provider: {get_active_provider()}")
    print(f"✅ Bay2Game API Key: {'configured' if get_bay2game_api_key() else 'not configured'}")
    print(f"✅ G2Bulk API Key: {'configured' if get_g2bulk_api_key() else 'not configured'}")
    print(f"✅ ZiniPay API Key: {'configured' if get_zinipay_api_key() else 'not configured'}")
    print(f"✅ OxaPay API Key: {'configured' if get_oxapay_api_key() else 'not configured'}")
    print(f"✅ Support Channel: @{get_support_channel()}")
    print(f"✅ Support Admin: @{get_support_admin()}")
    
    balance = check_api_balance()
    print(f"💰 Active API Balance: ${balance}")
    
    bot.infinity_polling()
