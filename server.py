# -*- coding: utf-8 -*-
"""
NF TWEAKS - HIGH-TECH CLIENT PORTAL & WEB SERVER
Multi-Page Web Architecture + One-Time PIN Generation + Automated Order/Key Engine + Owner Approval
"""
import os
import sys
import json
import time
import string
import random
import hashlib
import mimetypes
import socket
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
PINS_DB_PATH = os.path.join(BASE_DIR, "pins_db.json")
USERS_DB_PATH = os.path.join(BASE_DIR, "users_db.json")
ORDERS_DB_PATH = os.path.join(BASE_DIR, "orders_db.json")
PAYMENT_SETTINGS_PATH = os.path.join(BASE_DIR, "payment_settings.json")
KEYS_DB_PATH = os.path.join(BASE_DIR, "keys_db.json")
VALID_KEYS_PATH = os.path.join(BASE_DIR, "valid_keys.json")

# Discord Live Stats Cache (60 seconds)
DISCORD_STATS_CACHE = {
    "timestamp": 0,
    "data": {
        "approximate_member_count": 68,
        "approximate_presence_count": 31,
        "guild_name": "NF Pack",
        "invite_url": "https://discord.gg/kZDX8cfTp"
    }
}

def get_discord_stats():
    now = time.time()
    if now - DISCORD_STATS_CACHE["timestamp"] < 60:
        return DISCORD_STATS_CACHE["data"]
    try:
        req = urllib.request.Request(
            "https://discord.com/api/v9/invites/kZDX8cfTp?with_counts=true",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = json.loads(res.read().decode("utf-8"))
            mem = raw.get("approximate_member_count") or 68
            online = raw.get("approximate_presence_count") or 31
            guild = raw.get("guild", {}).get("name", "NF Pack")
            res_data = {
                "approximate_member_count": mem,
                "approximate_presence_count": online,
                "guild_name": guild,
                "invite_url": "https://discord.gg/kZDX8cfTp"
            }
            DISCORD_STATS_CACHE["timestamp"] = now
            DISCORD_STATS_CACHE["data"] = res_data
            return res_data
    except Exception as e:
        print(f"[DISCORD STATS FETCH NOTICE] {e}")
        return DISCORD_STATS_CACHE["data"]

# In-memory sessions: token -> { "username": ..., "role": ..., "discord_tag": ..., "login_time": ... }
SESSIONS = {}

# Candidate paths for the downloadable executable
CANDIDATE_EXES = [
    os.path.join(BASE_DIR, "NF_Tweaks_FPS_Booster.exe"),
    os.path.join(r"C:\Users\proog\Desktop", "NF_Tweaks_FPS_Booster.exe"),
    os.path.join(PARENT_DIR, "dist", "NF_Tweaks_FPS_Booster.exe"),
    os.path.join(PARENT_DIR, "NF_Tweaks_FPS_Booster.exe")
]

def get_exe_path():
    for p in CANDIDATE_EXES:
        if os.path.exists(p):
            return p
    return None

def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            print(f"[JSON LOAD ERROR] {path}: {e}")
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[JSON SAVE ERROR] {path}: {e}")
        return False

def hash_pw(password):
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()

def ensure_owner_seeded():
    users = load_json(USERS_DB_PATH, {})
    found_key = None
    for k in users.keys():
        if k.lower() == "ogdovmesi":
            found_key = k
            break
    if not found_key:
        users["ogdovmesi"] = {
            "username": "ogdovmesi",
            "password_hash": hash_pw("goblinstyx12"),
            "role": "owner",
            "discord_tag": "ogdovmesi",
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        }
        save_json(USERS_DB_PATH, users)
    else:
        # Guarantee role is owner
        if users[found_key].get("role") != "owner":
            users[found_key]["role"] = "owner"
            save_json(USERS_DB_PATH, users)

ensure_owner_seeded()

def generate_unique_key():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    keys_db = load_json(KEYS_DB_PATH, {})
    for _ in range(100):
        parts = ["".join(random.choice(chars) for _ in range(5)) for _ in range(5)]
        key = "-".join(parts)
        if key not in keys_db:
            return key
    return "-".join("".join(random.choice(chars) for _ in range(5)) for _ in range(5))

class NFPortalRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def _send_json(self, status_code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-NF-Token")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-NF-Token")
        self.end_headers()

    def _get_auth_user(self, query=None):
        # 1. From Authorization header
        auth_header = self.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif self.headers.get("X-NF-Token"):
            token = self.headers.get("X-NF-Token").strip()
        elif query and "token" in query:
            token = query.get("token", [""])[0].strip()

        if token and token in SESSIONS:
            sess = SESSIONS[token]
            users = load_json(USERS_DB_PATH, {})
            u = users.get(sess["username"])
            if u:
                return {
                    "username": u["username"],
                    "role": u.get("role", "customer"),
                    "discord_tag": u.get("discord_tag", ""),
                    "token": token
                }
        return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. API: Server Status
        if path == "/api/status":
            keys_db = load_json(KEYS_DB_PATH, {})
            pins_db = load_json(PINS_DB_PATH, {})
            orders_db = load_json(ORDERS_DB_PATH, {})
            exe_p = get_exe_path()
            exe_size_mb = round(os.path.getsize(exe_p) / (1024 * 1024), 2) if exe_p else 0
            pending_orders = sum(1 for o in orders_db.values() if o.get("status") == "pending_approval")
            return self._send_json(200, {
                "status": "online",
                "app_name": "NF Tweaks FPS Booster Portal",
                "version": "2.4.0 Final",
                "total_keys": len(keys_db),
                "total_pins": len(pins_db),
                "pending_orders": pending_orders,
                "exe_ready": bool(exe_p),
                "exe_size_mb": exe_size_mb
            })

        # 1.1 API: Payment Settings for Customers
        elif path == "/api/payment-settings":
            settings = load_json(PAYMENT_SETTINGS_PATH, {
                "discord_invite": "discord.gg/kZDX8cfTp",
                "note": "Ödemeler yalnızca resmi Discord sunucumuzda ticket üzerinden Sunucu Sahibi (ogdovmesi) ile teyit edilerek alınır."
            })
            return self._send_json(200, {
                "status": "success",
                "settings": settings
            })

        # 1.2 API: Discord Live Server Stats
        elif path == "/api/discord-stats":
            stats = get_discord_stats()
            return self._send_json(200, {
                "status": "success",
                "stats": stats
            })

        # 2. API: Current Auth User Profile
        elif path == "/api/auth/me":
            user = self._get_auth_user(query)
            if not user:
                return self._send_json(401, {"status": "unauthorized", "authenticated": False})
            return self._send_json(200, {
                "status": "success",
                "authenticated": True,
                "user": user
            })

        # 3. API: Customer's Orders
        elif path == "/api/orders/my-orders":
            user = self._get_auth_user(query)
            if not user:
                return self._send_json(401, {"status": "error", "message": "Lütfen önce giriş yapın."})

            orders_db = load_json(ORDERS_DB_PATH, {})
            my_orders = []
            for oid, o in sorted(orders_db.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
                if o.get("username") == user["username"]:
                    # Create safe copy
                    item = dict(o)
                    # If not yet approved by owner, mask the key so customer cannot use it
                    if item.get("status") != "approved":
                        raw_k = item.get("key", "")
                        prefix = raw_k.split("-")[0] if "-" in raw_k else "NF"
                        item["key_masked"] = f"{prefix}-••••-••••-••••-••••"
                        item["key"] = item["key_masked"]
                    else:
                        item["key_masked"] = item.get("key")
                    my_orders.append(item)

            return self._send_json(200, {
                "status": "success",
                "orders": my_orders
            })

        # 4. API: Admin Orders List (Owner / Admin only)
        elif path == "/api/admin/orders":
            user = self._get_auth_user(query)
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim! Sadece Sunucu Sahibi veya Admin görebilir."})

            orders_db = load_json(ORDERS_DB_PATH, {})
            order_list = []
            for oid, o in sorted(orders_db.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
                order_list.append(o)

            return self._send_json(200, {
                "status": "success",
                "orders": order_list
            })

        # 5. API: Admin Users List (Owner / Admin only)
        elif path == "/api/admin/users":
            user = self._get_auth_user(query)
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim! Sadece Sunucu Sahibi veya Admin görebilir."})

            users_db = load_json(USERS_DB_PATH, {})
            orders_db = load_json(ORDERS_DB_PATH, {})
            user_list = []
            for uname, u in users_db.items():
                orders_count = sum(1 for o in orders_db.values() if o.get("username") == uname)
                user_list.append({
                    "username": uname,
                    "role": u.get("role", "customer"),
                    "discord_tag": u.get("discord_tag", ""),
                    "created_at": u.get("created_at", ""),
                    "orders_count": orders_count,
                    "is_owner": u.get("role") == "owner"
                })

            return self._send_json(200, {
                "status": "success",
                "users": user_list,
                "current_user_role": user.get("role")
            })

        # 6. API: Admin Stats (Owner / Admin only)
        elif path == "/api/admin/stats":
            user = self._get_auth_user(query)
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim!"})

            orders_db = load_json(ORDERS_DB_PATH, {})
            keys_db = load_json(KEYS_DB_PATH, {})
            pins_db = load_json(PINS_DB_PATH, {})
            users_db = load_json(USERS_DB_PATH, {})

            pending = sum(1 for o in orders_db.values() if o.get("status") == "pending_approval")
            approved = sum(1 for o in orders_db.values() if o.get("status") == "approved")
            total_rev = sum(o.get("price", 0) for o in orders_db.values() if o.get("status") == "approved")
            used_pins = sum(1 for p in pins_db.values() if p.get("used", False))

            return self._send_json(200, {
                "status": "success",
                "stats": {
                    "pending_orders": pending,
                    "approved_orders": approved,
                    "total_revenue": total_rev,
                    "total_users": len(users_db),
                    "total_keys": len(keys_db),
                    "total_pins": len(pins_db),
                    "used_pins": used_pins
                }
            })

        # 6.1 API: Admin PINs List
        elif path == "/api/admin/pins":
            user = self._get_auth_user(query)
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim!"})

            pins_db = load_json(PINS_DB_PATH, {})
            pin_list = []
            for pin, p in sorted(pins_db.items(), key=lambda x: str(x[1].get("created_at", "")), reverse=True):
                p_copy = dict(p)
                p_copy["pin"] = pin
                pin_list.append(p_copy)

            return self._send_json(200, {
                "status": "success",
                "pins": pin_list,
                "total_pins": len(pin_list)
            })

        # 6.2 API: Admin Keys List
        elif path == "/api/admin/keys":
            user = self._get_auth_user(query)
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim!"})

            keys_db = load_json(KEYS_DB_PATH, {})
            key_list = []
            for k, val in sorted(keys_db.items(), key=lambda x: str(x[1].get("created_at", "")), reverse=True):
                item = dict(val)
                item["key"] = k
                key_list.append(item)

            return self._send_json(200, {
                "status": "success",
                "keys": key_list,
                "total_keys": len(key_list)
            })

        # 7. API: Download Executable with Key + PIN (Enforces 1-time PIN rule)
        elif path == "/api/download-tweak":
            key = (query.get("key", [""])[0]).strip().upper()
            pin = (query.get("pin", [""])[0]).strip()

            if not pin:
                return self._send_json(400, {
                    "status": "error",
                    "message": "Güvenlik PIN'i zorunludur."
                })

            pins_db = load_json(PINS_DB_PATH, {})
            pin_data = pins_db.get(pin)

            if not pin_data:
                return self._send_json(404, {
                    "status": "error",
                    "message": "Geçersiz veya bulunamayan Güvenlik PIN'i!"
                })

            # Check if matching key or admin manual pin
            if pin_data.get("key") != "ADMIN_MANUAL_PIN" and pin_data.get("key", "").upper() != key:
                return self._send_json(403, {
                    "status": "error",
                    "message": "Bu PIN girilen lisans anahtarıyla eşleşmiyor!"
                })

            # Check if PIN has ALREADY been used
            if pin_data.get("used", False) or pin_data.get("download_count", 0) >= 1:
                return self._send_json(403, {
                    "status": "error",
                    "error_code": "PIN_ALREADY_USED",
                    "message": f"ERİŞİM REDDEDİLDİ: Bu Güvenlik PIN'i ({pin}) daha önce kullanılmıştır ve tek seferlik hakkı dolmuştur! Güvenlik nedeniyle aynı PIN ile 2. kez indirme yapılamaz."
                })

            exe_path = get_exe_path()
            if not exe_path or not os.path.exists(exe_path):
                return self._send_json(500, {
                    "status": "error",
                    "message": "Sunucuda NF_Tweaks_FPS_Booster.exe dosyası bulunamadı."
                })

            # Burn the PIN immediately (Set used=True, download_count=1)
            pin_data["used"] = True
            pin_data["download_count"] = 1
            pin_data["downloaded_at"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            pin_data["client_ip"] = self.client_address[0]
            pins_db[pin] = pin_data
            save_json(PINS_DB_PATH, pins_db)

            # Serve the binary
            file_size = os.path.getsize(exe_path)
            filename = os.path.basename(exe_path)

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(file_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()

            with open(exe_path, "rb") as f:
                while chunk := f.read(65536):
                    try:
                        self.wfile.write(chunk)
                    except:
                        break
            return

        # Fallback to standard static files
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except:
            req_data = {}

        # ==========================================
        # AUTH APIS: REGISTER & LOGIN
        # ==========================================
        if path == "/api/auth/register":
            username = (req_data.get("username") or "").strip()
            password = (req_data.get("password") or "").strip()
            discord_tag = (req_data.get("discord_tag") or "").strip()

            if not username or len(username) < 3:
                return self._send_json(400, {"status": "error", "message": "Kullanıcı adı en az 3 karakter olmalıdır."})
            if not password or len(password) < 4:
                return self._send_json(400, {"status": "error", "message": "Şifre en az 4 karakter olmalıdır."})

            users = load_json(USERS_DB_PATH, {})
            # Case-insensitive check
            for u in users.keys():
                if u.lower() == username.lower():
                    return self._send_json(409, {"status": "error", "message": "Bu kullanıcı adı zaten alınmış!"})

            # Create user
            users[username] = {
                "username": username,
                "password_hash": hash_pw(password),
                "role": "customer",
                "discord_tag": discord_tag,
                "created_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            }
            save_json(USERS_DB_PATH, users)

            # Generate session token
            token = hashlib.sha256(f"{username}-{time.time()}-{random.random()}".encode()).hexdigest()
            SESSIONS[token] = {
                "username": username,
                "role": "customer",
                "discord_tag": discord_tag,
                "login_time": time.time()
            }

            return self._send_json(200, {
                "status": "success",
                "message": "Hesabınız başarıyla oluşturuldu!",
                "token": token,
                "user": {
                    "username": username,
                    "role": "customer",
                    "discord_tag": discord_tag
                }
            })

        elif path == "/api/auth/login":
            username = (req_data.get("username") or "").strip()
            password = (req_data.get("password") or "").strip()

            if not username or not password:
                return self._send_json(400, {"status": "error", "message": "Kullanıcı adı ve şifre zorunludur."})

            ensure_owner_seeded()
            users = load_json(USERS_DB_PATH, {})

            matched_user = None
            for uname, udata in users.items():
                if uname.lower() == username.lower():
                    matched_user = udata
                    break

            if not matched_user:
                return self._send_json(401, {"status": "error", "message": "Kullanıcı adı veya şifre hatalı!"})

            if matched_user.get("password_hash") != hash_pw(password):
                return self._send_json(401, {"status": "error", "message": "Kullanıcı adı veya şifre hatalı!"})

            token = hashlib.sha256(f"{matched_user['username']}-{time.time()}-{random.random()}".encode()).hexdigest()
            SESSIONS[token] = {
                "username": matched_user["username"],
                "role": matched_user.get("role", "customer"),
                "discord_tag": matched_user.get("discord_tag", ""),
                "login_time": time.time()
            }

            return self._send_json(200, {
                "status": "success",
                "message": f"Hoş geldiniz, {matched_user['username']}!",
                "token": token,
                "user": {
                    "username": matched_user["username"],
                    "role": matched_user.get("role", "customer"),
                    "discord_tag": matched_user.get("discord_tag", "")
                }
            })

        elif path == "/api/auth/logout":
            token = None
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
            if token and token in SESSIONS:
                del SESSIONS[token]
            return self._send_json(200, {"status": "success", "message": "Başarıyla çıkış yapıldı."})

        elif path == "/api/auth/change-password":
            user = self._get_auth_user()
            if not user:
                return self._send_json(401, {"status": "error", "message": "Lütfen önce giriş yapın."})

            old_pw = (req_data.get("old_password") or "").strip()
            new_pw = (req_data.get("new_password") or "").strip()

            if not old_pw or not new_pw:
                return self._send_json(400, {"status": "error", "message": "Mevcut şifre ve yeni şifre zorunludur."})

            if len(new_pw) < 4:
                return self._send_json(400, {"status": "error", "message": "Yeni şifre en az 4 karakter olmalıdır."})

            users = load_json(USERS_DB_PATH, {})
            uname = user["username"]
            matched_key = None
            for k in users.keys():
                if k.lower() == uname.lower():
                    matched_key = k
                    break

            if not matched_key:
                return self._send_json(404, {"status": "error", "message": "Kullanıcı bulunamadı."})

            if users[matched_key].get("password_hash") != hash_pw(old_pw):
                return self._send_json(401, {"status": "error", "message": "Mevcut şifreniz hatalı!"})

            users[matched_key]["password_hash"] = hash_pw(new_pw)
            save_json(USERS_DB_PATH, users)

            return self._send_json(200, {
                "status": "success",
                "message": "Şifreniz başarıyla değiştirildi! Yeni şifreniz sisteme kaydedildi."
            })

        elif path == "/api/admin/payment-settings":
            user = self._get_auth_user()
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim! Sadece Owner veya Admin değiştirebilir."})

            settings = load_json(PAYMENT_SETTINGS_PATH, {})
            settings["bank_name"] = (req_data.get("bank_name") or "").strip()
            settings["iban"] = (req_data.get("iban") or "").strip()
            settings["account_holder"] = (req_data.get("account_holder") or "").strip()
            settings["papara_no"] = (req_data.get("papara_no") or "").strip()
            settings["crypto_wallet"] = (req_data.get("crypto_wallet") or "").strip()
            settings["discord_invite"] = (req_data.get("discord_invite") or "discord.gg/kZDX8cfTp").strip()
            settings["note"] = (req_data.get("note") or "").strip()
            save_json(PAYMENT_SETTINGS_PATH, settings)

            return self._send_json(200, {
                "status": "success",
                "message": "Ödeme ve banka hesap bilgileri başarıyla güncellendi!",
                "settings": settings
            })

        # ==========================================
        # ORDERS API: CUSTOMER CREATES ORDER
        # ==========================================
        elif path == "/api/orders/create":
            user = self._get_auth_user()
            if not user:
                return self._send_json(401, {"status": "error", "message": "Sipariş oluşturmak için lütfen önce giriş yapın."})

            plan = req_data.get("plan", "lifetime").lower()
            payment_method = req_data.get("payment_method", "Banka Havalesi / EFT / Papara")
            note = (req_data.get("note") or "").strip()
            discord_tag = (req_data.get("discord_tag") or user.get("discord_tag", "")).strip()

            # Map plans to pricing & labels (Prices requested: Lifetime 1.5k, Monthly 1k, Weekly 600 TL)
            if plan in ("weekly", "1week", "haftalik"):
                plan_key = "1week"
                plan_label = "1 Haftalık Espor Lisansı"
                duration_days = 7
                price = 600
            elif plan in ("monthly", "1month", "aylik"):
                plan_key = "1month"
                plan_label = "1 Aylık Pro Lisans"
                duration_days = 30
                price = 1000
            else:
                plan_key = "lifetime"
                plan_label = "Sınırsız Lifetime VIP"
                duration_days = -1
                price = 1500

            # Generate real registered tweak key
            new_key = generate_unique_key()
            order_id = f"ORD-{random.randint(10000, 99999)}"

            # Save in orders_db.json
            orders_db = load_json(ORDERS_DB_PATH, {})
            order_data = {
                "id": order_id,
                "username": user["username"],
                "discord_tag": discord_tag,
                "plan": plan_key,
                "plan_label": plan_label,
                "duration_days": duration_days,
                "price": price,
                "currency": "₺",
                "key": new_key,
                "status": "pending_approval",  # REQUIRES OWNER APPROVAL
                "payment_method": payment_method,
                "note": note,
                "created_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "approved_at": None,
                "approved_by": None
            }
            orders_db[order_id] = order_data
            save_json(ORDERS_DB_PATH, orders_db)

            # Register key in admin_keys_db.json as pending_approval
            keys_db = load_json(KEYS_DB_PATH, {})
            keys_db[new_key] = {
                "plan": plan_key,
                "plan_label": plan_label,
                "duration_days": duration_days,
                "created_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "status": "pending_approval",
                "customer": user["username"],
                "order_id": order_id,
                "activated_at": None,
                "expires_at": None
            }
            save_json(KEYS_DB_PATH, keys_db)

            # Note: valid_keys.json is NOT modified yet. Key becomes valid ONLY upon owner approval!

            # Return response to customer with MASKED key
            prefix = new_key.split("-")[0]
            masked_key = f"{prefix}-••••-••••-••••-••••"

            return self._send_json(200, {
                "status": "success",
                "order_id": order_id,
                "plan_label": plan_label,
                "price": price,
                "currency": "₺",
                "key_masked": masked_key,
                "order_status": "pending_approval",
                "message": "Siparişiniz başarıyla alındı! Lisans kodunuz üretildi ancak ödeme onayı için Sunucu Sahibi (OGDovmesi) onayı beklenmektedir. Onaylandıktan hemen sonra kodunuz teslim edilecektir."
            })

        # ==========================================
        # ADMIN / OWNER APPROVAL & MANAGEMENT APIS
        # ==========================================
        elif path == "/api/admin/orders/approve":
            user = self._get_auth_user()
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim! Sadece Sunucu Sahibi veya Admin onaylayabilir."})

            order_id = req_data.get("order_id")
            if not order_id:
                return self._send_json(400, {"status": "error", "message": "Sipariş ID gereklidir."})

            orders_db = load_json(ORDERS_DB_PATH, {})
            order = orders_db.get(order_id)
            if not order:
                return self._send_json(404, {"status": "error", "message": "Sipariş bulunamadı."})

            key = order.get("key")
            if not key:
                return self._send_json(400, {"status": "error", "message": "Siparişe bağlı lisans anahtarı bulunamadı."})

            # Update order
            order["status"] = "approved"
            order["approved_at"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            order["approved_by"] = user["username"]
            orders_db[order_id] = order
            save_json(ORDERS_DB_PATH, orders_db)

            # Activate in admin_keys_db.json
            keys_db = load_json(KEYS_DB_PATH, {})
            if key in keys_db:
                keys_db[key]["status"] = "unused"
                keys_db[key]["approved_at"] = order["approved_at"]
                keys_db[key]["approved_by"] = user["username"]
            else:
                keys_db[key] = {
                    "plan": order.get("plan", "lifetime"),
                    "plan_label": order.get("plan_label", "Lifetime (Sınırsız)"),
                    "duration_days": order.get("duration_days", -1),
                    "created_at": order.get("created_at"),
                    "status": "unused",
                    "customer": order.get("username"),
                    "order_id": order_id,
                    "approved_at": order["approved_at"],
                    "approved_by": user["username"]
                }
            save_json(KEYS_DB_PATH, keys_db)

            # Add SHA-256 hash to valid_keys.json so Tweak application accepts it!
            key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            valid_hashes = load_json(VALID_KEYS_PATH, [])
            if not isinstance(valid_hashes, list):
                valid_hashes = []
            if key_hash not in valid_hashes:
                valid_hashes.append(key_hash)
                save_json(VALID_KEYS_PATH, valid_hashes)

            return self._send_json(200, {
                "status": "success",
                "message": f"Sipariş {order_id} başarıyla ONAYLANDI! Lisans anahtarı ({key}) tweak uygulamasına ve indirme sistemine kaydedildi.",
                "order": order
            })

        elif path == "/api/admin/orders/reject":
            user = self._get_auth_user()
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim!"})

            order_id = req_data.get("order_id")
            orders_db = load_json(ORDERS_DB_PATH, {})
            order = orders_db.get(order_id)
            if not order:
                return self._send_json(404, {"status": "error", "message": "Sipariş bulunamadı."})

            key = order.get("key")
            order["status"] = "rejected"
            order["rejected_at"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            order["rejected_by"] = user["username"]
            orders_db[order_id] = order
            save_json(ORDERS_DB_PATH, orders_db)

            # Revoke in admin_keys_db.json
            keys_db = load_json(KEYS_DB_PATH, {})
            if key in keys_db:
                keys_db[key]["status"] = "revoked"
                save_json(KEYS_DB_PATH, keys_db)

            # Remove hash from valid_keys.json if present
            key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            valid_hashes = load_json(VALID_KEYS_PATH, [])
            if isinstance(valid_hashes, list) and key_hash in valid_hashes:
                valid_hashes.remove(key_hash)
                save_json(VALID_KEYS_PATH, valid_hashes)

            return self._send_json(200, {
                "status": "success",
                "message": f"Sipariş {order_id} reddedildi ve anahtar iptal edildi."
            })

        elif path == "/api/admin/users/set-role":
            user = self._get_auth_user()
            # STRICT REQUIREMENT: Only the owner (OGDovmesi) can grant/revoke admin rights!
            if not user or user.get("role") != "owner":
                return self._send_json(403, {
                    "status": "error",
                    "message": "Yetkisiz işlem! Yalnızca Sunucu Sahibi (OGDovmesi) admin yetkisi verebilir veya kaldırabilir."
                })

            target_username = req_data.get("username")
            new_role = req_data.get("role", "customer").lower()

            if not target_username:
                return self._send_json(400, {"status": "error", "message": "Kullanıcı adı gereklidir."})

            if target_username.lower() == "ogdovmesi":
                return self._send_json(400, {"status": "error", "message": "Sunucu Sahibinin (Owner) yetkisi değiştirilemez!"})

            if new_role not in ("admin", "customer"):
                return self._send_json(400, {"status": "error", "message": "Geçersiz rol. Sadece 'admin' veya 'customer' atanabilir."})

            users = load_json(USERS_DB_PATH, {})
            if target_username not in users:
                return self._send_json(404, {"status": "error", "message": "Kullanıcı bulunamadı."})

            users[target_username]["role"] = new_role
            save_json(USERS_DB_PATH, users)

            # Update live session if active
            for tok, sess in SESSIONS.items():
                if sess.get("username") == target_username:
                    sess["role"] = new_role

            return self._send_json(200, {
                "status": "success",
                "message": f"'{target_username}' kullanıcısının yetkisi başarıyla '{new_role.upper()}' olarak güncellendi."
            })

        elif path == "/api/admin/create-key":
            user = self._get_auth_user()
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz erişim!"})

            plan = req_data.get("plan", "lifetime")
            if plan in ("weekly", "1week"):
                plan_key = "1week"
                plan_label = "1 Haftalık (7 Gün)"
                days = 7
            elif plan in ("monthly", "1month"):
                plan_key = "1month"
                plan_label = "1 Aylık (30 Gün)"
                days = 30
            else:
                plan_key = "lifetime"
                plan_label = "Lifetime (Sınırsız)"
                days = -1

            key = generate_unique_key()
            now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            keys_db = load_json(KEYS_DB_PATH, {})
            keys_db[key] = {
                "plan": plan_key,
                "plan_label": plan_label,
                "duration_days": days,
                "created_at": now,
                "status": "unused",
                "customer": req_data.get("note", f"Admin Üretimi ({user['username']})"),
                "approved_by": user["username"],
                "approved_at": now
            }
            save_json(KEYS_DB_PATH, keys_db)

            key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            valid_hashes = load_json(VALID_KEYS_PATH, [])
            if not isinstance(valid_hashes, list): valid_hashes = []
            if key_hash not in valid_hashes:
                valid_hashes.append(key_hash)
                save_json(VALID_KEYS_PATH, valid_hashes)

            return self._send_json(200, {
                "status": "success",
                "key": key,
                "plan_label": plan_label,
                "message": f"Manuel lisans anahtarı üretildi ve sisteme kaydedildi: {key}"
            })

        # 16. API: Admin Manual PIN Generator
        elif path == "/api/admin/create-pin":
            user = self._get_auth_user()
            if not user or user.get("role") not in ("owner", "admin"):
                return self._send_json(403, {"status": "error", "message": "Yetkisiz işlem!"})

            pins_db = load_json(PINS_DB_PATH, {})
            custom_pin = (str(req_data.get("pin") or "")).strip()
            note = (req_data.get("note") or f"Admin Üretimi ({user['username']})").strip()

            if custom_pin:
                if len(custom_pin) < 4 or len(custom_pin) > 10:
                    return self._send_json(400, {"status": "error", "message": "PIN 4-10 hane arasında olmalıdır."})
                pin = custom_pin
            else:
                for _ in range(50):
                    cand = str(random.randint(100000, 999999))
                    if cand not in pins_db:
                        pin = cand
                        break
                else:
                    pin = str(random.randint(100000, 999999))

            now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            pins_db[pin] = {
                "key": "ADMIN_MANUAL_PIN",
                "created_at": now,
                "used": False,
                "download_count": 0,
                "downloaded_at": None,
                "max_allowed": 1,
                "note": note,
                "created_by": user["username"]
            }
            save_json(PINS_DB_PATH, pins_db)
            return self._send_json(200, {
                "status": "success",
                "pin": pin,
                "message": f"Tek seferlik indirme PIN'i ({pin}) başarıyla oluşturuldu!"
            })

        # ==========================================
        # KEY & PIN VERIFICATION APIS
        # ==========================================
        elif path == "/api/verify-key":
            key = (req_data.get("key") or "").strip().upper()
            if not key:
                return self._send_json(400, {"status": "error", "message": "Lisans anahtarı boş olamaz."})

            k_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            valid_hashes = set(load_json(VALID_KEYS_PATH, []))
            keys_db = load_json(KEYS_DB_PATH, {})

            if k_hash not in valid_hashes and key not in keys_db:
                return self._send_json(404, {
                    "status": "error",
                    "message": "Geçersiz veya veritabanında bulunamayan lisans anahtarı!"
                })

            info = keys_db.get(key, {})
            # Check if pending approval
            if info.get("status") == "pending_approval":
                return self._send_json(403, {
                    "status": "error",
                    "error_code": "PENDING_APPROVAL",
                    "message": "Bu lisans anahtarı için ödeme onayı bekleniyor! Sunucu Sahibi (OGDovmesi) onayladıktan sonra PIN oluşturabilir ve indirebilirsiniz."
                })

            plan_label = info.get("plan_label", "Ömür Boyu (Lifetime)")
            days = info.get("duration_days", -1)

            pins_db = load_json(PINS_DB_PATH, {})
            existing_pins = [p for p, data in pins_db.items() if data.get("key", "").upper() == key]

            return self._send_json(200, {
                "status": "success",
                "valid": True,
                "key": key,
                "plan": info.get("plan", "lifetime"),
                "plan_label": plan_label,
                "duration_days": days,
                "existing_pins_count": len(existing_pins),
                "message": f"Lisans anahtarı başarıyla doğrulandı! Paket: {plan_label}"
            })

        elif path == "/api/create-pin":
            key = (req_data.get("key") or "").strip().upper()
            custom_pin = (str(req_data.get("pin") or "")).strip()

            if not key:
                return self._send_json(400, {"status": "error", "message": "Lisans anahtarı gereklidir."})

            k_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            valid_hashes = set(load_json(VALID_KEYS_PATH, []))
            keys_db = load_json(KEYS_DB_PATH, {})

            if k_hash not in valid_hashes and key not in keys_db:
                return self._send_json(403, {"status": "error", "message": "Yetkisiz veya geçersiz lisans anahtarı!"})

            info = keys_db.get(key, {})
            if info.get("status") == "pending_approval":
                return self._send_json(403, {
                    "status": "error",
                    "message": "Bu lisans anahtarı henüz Sunucu Sahibi tarafından onaylanmamıştır."
                })

            pins_db = load_json(PINS_DB_PATH, {})

            # If custom PIN provided
            if custom_pin:
                if len(custom_pin) < 4 or len(custom_pin) > 10:
                    return self._send_json(400, {"status": "error", "message": "Güvenlik PIN'i 4 ile 10 hane arasında olmalıdır."})
                pin = custom_pin
            else:
                for _ in range(50):
                    cand = str(random.randint(100000, 999999))
                    if cand not in pins_db:
                        pin = cand
                        break
                else:
                    pin = str(random.randint(100000, 999999))

            # ENFORCE 1-TIME PIN RULE: If PIN exists in pins_db
            if pin in pins_db:
                existing_pin = pins_db[pin]
                if existing_pin.get("used", False) or existing_pin.get("download_count", 0) >= 1:
                    return self._send_json(409, {
                        "status": "error",
                        "error_code": "PIN_ALREADY_EXISTS_AND_USED",
                        "message": f"Bu PIN ({pin}) daha önce oluşturulmuş ve tek seferlik indirme hakkı dolmuştur! Lütfen farklı bir PIN belirleyin."
                    })
                if existing_pin.get("key", "").upper() != key:
                    return self._send_json(409, {
                        "status": "error",
                        "error_code": "PIN_TAKEN",
                        "message": "Bu PIN başka bir lisans anahtarı tarafından rezerve edilmiş. Lütfen farklı bir PIN seçin."
                    })

            # Save fresh PIN
            pins_db[pin] = {
                "key": key,
                "created_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "used": False,
                "download_count": 0,
                "downloaded_at": None,
                "max_allowed": 1
            }
            save_json(PINS_DB_PATH, pins_db)

            return self._send_json(200, {
                "status": "success",
                "pin": pin,
                "key": key,
                "max_downloads": 1,
                "remaining_downloads": 1,
                "message": f"Tek seferlik Güvenlik PIN'i ({pin}) başarıyla oluşturuldu! Bu PIN ile en fazla 1 kez indirme yapılabilir."
            })

        elif path == "/api/check-pin":
            pin = (str(req_data.get("pin") or "")).strip()
            if not pin:
                return self._send_json(400, {"status": "error", "message": "PIN girilmedi."})

            pins_db = load_json(PINS_DB_PATH, {})
            pin_data = pins_db.get(pin)

            if not pin_data:
                return self._send_json(404, {
                    "status": "not_found",
                    "message": "Bu PIN veritabanında bulunamadı."
                })

            is_used = bool(pin_data.get("used", False) or pin_data.get("download_count", 0) >= 1)
            return self._send_json(200, {
                "status": "success",
                "pin": pin,
                "used": is_used,
                "download_count": pin_data.get("download_count", 0),
                "created_at": pin_data.get("created_at"),
                "downloaded_at": pin_data.get("downloaded_at"),
                "remaining_downloads": 0 if is_used else 1,
                "message": "PIN kullanılmış ve hakkı dolmuş." if is_used else "PIN aktif ve 1 kez indirilebilir."
            })

        return self._send_json(404, {"status": "error", "message": "API endpoint bulunamadı."})

def run_server(port=8080):
    httpd = ThreadingHTTPServer(("0.0.0.0", port), NFPortalRequestHandler)

    print(f"============================================================")
    print(f"🚀 NF TWEAKS WEB PORTAL & SUNUCU BAŞLATILDI")
    print(f"🌐 Adres: http://127.0.0.1:{port} veya http://localhost:{port}")
    print(f"📁 Dizin: {BASE_DIR}")
    print(f"📦 İndirilecek Dosya: {get_exe_path()}")
    print(f"👑 Varsayılan Owner: OGDovmesi (Şifre: admin)")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nSunucu kapatıldı.")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except:
            pass
    run_server(port)
