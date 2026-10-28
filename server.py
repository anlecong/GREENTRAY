import ipaddress
import hashlib
import json
import os
import re
import secrets
import sqlite3
import socket
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import qrcode
import qrcode.image.svg


ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("GREENTRAY_DATABASE", ROOT / "greentray.db"))
SESSION_SECONDS = 60 * 60 * 24 * 14
DEPOSIT = 10_000
SERVER_PORT = int(os.environ.get("PORT", "8000"))
IS_PRODUCTION = os.environ.get("GREENTRAY_ENV") == "production" or os.environ.get("RENDER") == "true"
BOX_TYPES = (("Hộp", "HP"), ("Cốc", "COC"))
BOXES_PER_TYPE = 30


def connect_db():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 310_000)
    return f"{salt}${derived.hex()}"


def verify_password(password, encoded):
    try:
        salt, expected = encoded.split("$", 1)
        actual = password_hash(password, salt).split("$", 1)[1]
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def customer_page_url():
    configured_url = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    if configured_url:
        parsed_url = urlparse(configured_url)
        if (
            parsed_url.scheme not in ("http", "https")
            or not parsed_url.netloc
            or parsed_url.path not in ("", "/")
            or parsed_url.params
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.username
            or parsed_url.password
            or (IS_PRODUCTION and parsed_url.scheme != "https")
        ):
            raise RuntimeError("PUBLIC_BASE_URL phải là URL HTTPS công khai hợp lệ.")
        return f"{parsed_url.scheme}://{parsed_url.netloc}/"
    if IS_PRODUCTION:
        raise RuntimeError("Thiếu URL công khai HTTPS của dịch vụ.")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("192.0.2.1", 80))
        address = ipaddress.ip_address(probe.getsockname()[0])
    if not address.is_private or address.is_loopback or address.is_link_local:
        raise RuntimeError("Không tìm thấy địa chỉ Wi-Fi/LAN riêng tư trên máy chủ.")
    return f"http://{address}:{SERVER_PORT}/"


def initialize_database():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as db:
        db.executescript((ROOT / "database.sql").read_text(encoding="utf-8"))
        admin_exists = db.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone()
        if IS_PRODUCTION and admin_exists is None:
            admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
            admin_name = os.environ.get("ADMIN_NAME", "Quản trị viên").strip()
            admin_password = os.environ.get("ADMIN_INITIAL_PASSWORD", "")
            if (
                not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", admin_email)
                or not 2 <= len(admin_name) <= 80
                or not 12 <= len(admin_password) <= 128
            ):
                raise RuntimeError(
                    "Cần cấu hình ADMIN_EMAIL hợp lệ và ADMIN_INITIAL_PASSWORD dài từ 12 đến 128 ký tự."
                )
            db.executemany(
                "INSERT INTO users (id, email, name, role, password_hash) VALUES (?, ?, ?, ?, ?)",
                [(uuid.uuid4().hex, admin_email, admin_name, "admin", password_hash(admin_password))],
            )
        elif not IS_PRODUCTION and db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO users (id, email, name, role, password_hash) VALUES (?, ?, ?, ?, ?)",
                [
                    ("admin-demo", "admin@greentray.local", "Quản trị viên", "admin", password_hash("Admin123!")),
                    ("customer-demo", "minhanh@greentray.local", "Minh Anh", "customer", password_hash("Khach123!")),
                ],
            )
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('deposit_amount', ?)",
            (str(DEPOSIT),),
        )
        db.execute("UPDATE boxes SET box_type='Hộp' WHERE box_type IN ('Hộp cơm', 'Hộp lớn', 'Tô')")
        db.execute("UPDATE boxes SET box_type='Cốc' WHERE box_type IN ('Ly', 'Ly giữ nhiệt')")
        for box_type, prefix in BOX_TYPES:
            boxes = db.execute(
                "SELECT id,code FROM boxes WHERE box_type=? ORDER BY id",
                (box_type,),
            ).fetchall()
            for index, box in enumerate(boxes, start=1):
                code = f"{prefix}{index:03}"
                if box["code"] != code:
                    db.execute("UPDATE boxes SET code=? WHERE id=?", (code, box["id"]))
            db.executemany(
                "INSERT INTO boxes (code,box_type) VALUES (?,?)",
                [
                    (f"{prefix}{index:03}", box_type)
                    for index in range(len(boxes) + 1, BOXES_PER_TYPE + 1)
                ],
            )


def public_user(row):
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"], "points": row["points"]}


class GreenTrayHandler(BaseHTTPRequestHandler):
    server_version = "GreenTrayLocal/1.0"

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")

    def send_json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, status, text, content_type="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 16_384:
            raise ValueError("Dữ liệu gửi lên quá lớn.")
        if not length:
            return {}
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Dữ liệu gửi lên không hợp lệ.")
        return value

    def current_user(self, db, roles=("admin", "customer")):
        cookies = {}
        for part in self.headers.get("Cookie", "").split(";"):
            key, separator, value = part.strip().partition("=")
            if separator:
                cookies[key] = value
        for role in roles:
            token = cookies.get(f"gt_{role}_sid")
            if not token:
                continue
            token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
            row = db.execute(
                """SELECT users.* FROM auth_sessions
                   JOIN users ON users.id = auth_sessions.user_id
                   WHERE auth_sessions.token_hash = ? AND auth_sessions.expires_at > datetime('now')""",
                (token_hash,),
            ).fetchone()
            if row is not None and row["role"] == role:
                return row
        return None

    def require_role(self, db, roles):
        user = self.current_user(db, roles)
        if user is None:
            if self.current_user(db) is not None:
                self.send_json(403, {"error": "Tài khoản không có quyền thực hiện thao tác này."})
            else:
                self.send_json(401, {"error": "Vui lòng đăng nhập để tiếp tục."})
            return None
        return user

    @staticmethod
    def create_session(db, user):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        db.execute(
            "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, datetime('now', ?))",
            (token_hash, user["id"], f"+{SESSION_SECONDS} seconds"),
        )
        secure = "; Secure" if IS_PRODUCTION else ""
        cookie = f"gt_{user['role']}_sid={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_SECONDS}{secure}"
        return cookie

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self.serve_page("customer.html")
        if path == "/admin":
            return self.serve_page("index.html")
        if path in ("/health", "/api/health"):
            return self.send_json(200, {"ok": True, "database": DATABASE.name})

        with connect_db() as db:
            if path == "/api/auth/me":
                requested_role = urlparse(self.path).query.removeprefix("role=")
                user = self.current_user(db, (requested_role,)) if requested_role in ("admin", "customer") else self.current_user(db)
                return self.send_json(200, {"user": public_user(user) if user else None})
            if path == "/api/customer/state":
                user = self.require_role(db, ("customer",))
                if user is None:
                    return
                return self.send_json(200, self.customer_state(db, user))
            if path == "/api/admin/state":
                user = self.require_role(db, ("admin",))
                if user is None:
                    return
                return self.send_json(200, self.admin_state(db))
            if path in ("/api/page-url/customer", "/api/page-qr/customer.svg"):
                user = self.require_role(db, ("admin",))
                if user is None:
                    return
                try:
                    page_url = customer_page_url()
                except OSError as error:
                    return self.send_json(503, {"error": f"Không xác định được địa chỉ mạng nội bộ: {error}"})
                except RuntimeError as error:
                    return self.send_json(503, {"error": str(error)})
                if path == "/api/page-url/customer":
                    return self.send_json(200, {"url": page_url})
                qr = qrcode.QRCode(box_size=10, border=3)
                qr.add_data(page_url)
                qr.make(fit=True)
                image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
                return self.send_text(200, image.to_string().decode("utf-8"), "image/svg+xml; charset=utf-8")
        return self.send_json(404, {"error": "Không tìm thấy đường dẫn."})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            return self.send_json(400, {"error": str(error) or "Dữ liệu JSON không hợp lệ."})

        if path == "/api/auth/register":
            name = data.get("name")
            email = data.get("email")
            password = data.get("password")
            if not isinstance(name, str) or not isinstance(email, str) or not isinstance(password, str):
                return self.send_json(400, {"error": "Vui lòng nhập họ tên, email và mật khẩu."})
            name = " ".join(name.split())
            email = email.strip().lower()
            if not 2 <= len(name) <= 80:
                return self.send_json(400, {"error": "Họ tên cần có từ 2 đến 80 ký tự."})
            if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                return self.send_json(400, {"error": "Địa chỉ email chưa hợp lệ."})
            if not 8 <= len(password) <= 128:
                return self.send_json(400, {"error": "Mật khẩu cần có từ 8 đến 128 ký tự."})
            user_id = uuid.uuid4().hex
            encoded_password = password_hash(password)
            with connect_db() as db:
                try:
                    with db:
                        db.execute(
                            "INSERT INTO users (id,email,name,role,password_hash) VALUES (?,?,?,'customer',?)",
                            (user_id, email, name, encoded_password),
                        )
                        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                        cookie = self.create_session(db, user)
                except sqlite3.IntegrityError:
                    return self.send_json(409, {"error": "Email này đã được đăng ký. Hãy đăng nhập hoặc dùng email khác."})
                return self.send_json(201, {"user": public_user(user)}, {"Set-Cookie": cookie})

        if path == "/api/auth/login":
            email = str(data.get("email", "")).strip().lower()
            password = data.get("password", "")
            if not isinstance(password, str) or not email or len(email) > 254 or len(password) > 256:
                return self.send_json(400, {"error": "Nhập email và mật khẩu hợp lệ."})
            with connect_db() as db:
                user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if user is None or not verify_password(password, user["password_hash"]):
                    return self.send_json(401, {"error": "Email hoặc mật khẩu không chính xác."})
                with db:
                    cookie = self.create_session(db, user)
                return self.send_json(200, {"user": public_user(user)}, {"Set-Cookie": cookie})

        if path == "/api/auth/logout":
            role = data.get("role")
            roles = (role,) if role in ("admin", "customer") else ("admin", "customer")
            cookies = {}
            for part in self.headers.get("Cookie", "").split(";"):
                key, separator, value = part.strip().partition("=")
                if separator:
                    cookies[key] = value
            with connect_db() as db:
                for session_role in roles:
                    token = cookies.get(f"gt_{session_role}_sid")
                    if token:
                        db.execute("DELETE FROM auth_sessions WHERE token_hash = ?", (hashlib.sha256(token.encode("ascii")).hexdigest(),))
            secure = "; Secure" if IS_PRODUCTION else ""
            cleared = ", ".join(
                f"gt_{session_role}_sid=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"
                for session_role in roles
            )
            return self.send_json(200, {"ok": True}, {"Set-Cookie": cleared})

        with connect_db() as db:
            user = self.require_role(db, ("customer",))
            if user is None:
                return
            if path == "/api/rentals":
                box_id = data.get("box_id")
                if not isinstance(box_id, int):
                    return self.send_json(400, {"error": "Mã hộp không hợp lệ."})
                rental_id = uuid.uuid4().hex
                try:
                    with db:
                        box = db.execute("SELECT * FROM boxes WHERE id = ?", (box_id,)).fetchone()
                        if box is None or box["status"] != "available":
                            return self.send_json(409, {"error": "Hộp không còn sẵn sàng để nhận."})
                        deposit = int(db.execute("SELECT value FROM settings WHERE key='deposit_amount'").fetchone()[0])
                        db.execute("UPDATE boxes SET status='rented' WHERE id=? AND status='available'", (box_id,))
                        if db.execute("SELECT changes()").fetchone()[0] != 1:
                            return self.send_json(409, {"error": "Hộp vừa được người khác nhận."})
                        db.execute(
                            "INSERT INTO rentals (id,user_id,box_id,deposit,status) VALUES (?,?,?,?,'rented')",
                            (rental_id, user["id"], box_id, deposit),
                        )
                        db.execute(
                            "INSERT INTO transactions (id,user_id,rental_id,transaction_type,amount) VALUES (?,?,?,'rent',?)",
                            (uuid.uuid4().hex, user["id"], rental_id, deposit),
                        )
                    return self.send_json(201, {"ok": True, "rental_id": rental_id})
                except sqlite3.IntegrityError:
                    return self.send_json(409, {"error": "Hộp vừa được người khác nhận."})
            if path == "/api/rentals/return":
                return self.return_rental(db, user, data)
        return self.send_json(404, {"error": "Không tìm thấy đường dẫn."})

    def return_rental(self, db, user, data):
        rental_id = data.get("rental_id")
        condition = data.get("condition", "good")
        if not isinstance(rental_id, str) or not rental_id:
            return self.send_json(400, {"error": "Lượt mượn không hợp lệ."})
        if condition not in ("good", "cleaning"):
            return self.send_json(400, {"error": "Tình trạng hộp không hợp lệ."})
        with db:
            rental = db.execute(
                """SELECT rentals.*, boxes.id AS actual_box_id, boxes.code
                   FROM rentals JOIN boxes ON boxes.id=rentals.box_id
                   WHERE rentals.user_id=? AND rentals.status='rented' AND rentals.id=?""",
                (user["id"], rental_id),
            ).fetchone()
            if rental is None:
                return self.send_json(409, {"error": "Không tìm thấy lượt mượn đang mở của bạn."})
            updated = db.execute(
                "UPDATE rentals SET status='returned',condition=?,returned_at=CURRENT_TIMESTAMP WHERE id=? AND status='rented'",
                (condition, rental["id"]),
            ).rowcount
            if updated != 1:
                return self.send_json(409, {"error": "Lượt mượn đã được trả trước đó."})
            box_status = "available" if condition == "good" else "cleaning"
            db.execute("UPDATE boxes SET status=? WHERE id=?", (box_status, rental["actual_box_id"]))
            points = 10
            db.execute("UPDATE users SET points=points+? WHERE id=?", (points, user["id"]))
            db.execute(
                "INSERT INTO transactions (id,user_id,rental_id,transaction_type,amount,green_points) VALUES (?,?,?,'return',?,?)",
                (uuid.uuid4().hex, user["id"], rental["id"], rental["deposit"], points),
            )
        return self.send_json(200, {"ok": True, "box_code": rental["code"], "green_points": points})

    @staticmethod
    def customer_state(db, user):
        boxes = db.execute(
            """SELECT id,code,box_type,status FROM boxes
               ORDER BY CASE box_type WHEN 'Hộp' THEN 0 ELSE 1 END, code"""
        ).fetchall()
        rentals = db.execute(
            """SELECT rentals.id,rentals.deposit,rentals.status,rentals.condition,rentals.rented_at,
                      boxes.code,boxes.box_type
               FROM rentals JOIN boxes ON boxes.id=rentals.box_id
               WHERE rentals.user_id=? ORDER BY rentals.rented_at DESC""",
            (user["id"],),
        ).fetchall()
        transactions = db.execute(
            "SELECT transaction_type,amount,green_points,created_at FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
            (user["id"],),
        ).fetchall()
        deposit = int(db.execute("SELECT value FROM settings WHERE key='deposit_amount'").fetchone()[0])
        return {
            "user": public_user(user),
            "boxes": [dict(row) for row in boxes],
            "rentals": [dict(row) for row in rentals],
            "transactions": [dict(row) for row in transactions],
            "settings": {"deposit_amount": deposit},
        }

    @staticmethod
    def admin_state(db):
        boxes = db.execute(
            """SELECT id,code,box_type,status FROM boxes
               ORDER BY CASE box_type WHEN 'Hộp' THEN 0 ELSE 1 END, code"""
        ).fetchall()
        rentals = db.execute(
            """SELECT rentals.id,rentals.deposit,rentals.status,rentals.rented_at,rentals.returned_at,
                      users.name AS customer_name,users.email,boxes.code,boxes.box_type
               FROM rentals JOIN users ON users.id=rentals.user_id
               JOIN boxes ON boxes.id=rentals.box_id ORDER BY rentals.rented_at DESC LIMIT 100"""
        ).fetchall()
        counts = db.execute(
            "SELECT COUNT(*) AS total,SUM(status='available') AS available,SUM(status='rented') AS rented FROM boxes"
        ).fetchone()
        usage_count = db.execute(
            "SELECT COUNT(*) FROM transactions WHERE transaction_type='rent'"
        ).fetchone()[0]
        return_count = db.execute(
            "SELECT COUNT(*) FROM transactions WHERE transaction_type='return'"
        ).fetchone()[0]
        daily_usage = db.execute(
            """SELECT date(created_at) AS day, COUNT(*) AS count
               FROM transactions
               WHERE transaction_type='rent' AND date(created_at) >= date('now', '-6 days')
               GROUP BY date(created_at) ORDER BY day"""
        ).fetchall()
        usage_by_type = db.execute(
            """SELECT boxes.box_type AS label, COUNT(rentals.id) AS count
               FROM boxes LEFT JOIN rentals ON rentals.box_id=boxes.id
               GROUP BY boxes.box_type ORDER BY count DESC, label"""
        ).fetchall()
        deposit = int(db.execute("SELECT value FROM settings WHERE key='deposit_amount'").fetchone()[0])
        active_deposit = db.execute("SELECT COALESCE(SUM(deposit),0) FROM rentals WHERE status='rented'").fetchone()[0]
        return {
            "boxes": [dict(row) for row in boxes],
            "rentals": [dict(row) for row in rentals],
            "daily_usage": [dict(row) for row in daily_usage],
            "usage_by_type": [dict(row) for row in usage_by_type],
            "stats": {
                "total": counts["total"],
                "available": counts["available"] or 0,
                "rented": counts["rented"] or 0,
                "deposit": active_deposit,
                "usage_count": usage_count,
                "return_count": return_count,
                "return_rate": round(return_count / usage_count * 100, 1) if usage_count else 0,
                "plastic_saved_kg": ((return_count * 150 + 50) // 100) / 10,
            },
            "deposit_amount": deposit,
        }

    def serve_page(self, filename):
        try:
            body = (ROOT / filename).read_bytes()
        except OSError:
            return self.send_json(500, {"error": f"Thiếu tệp giao diện {filename}."})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    initialize_database()
    server = ThreadingHTTPServer(("0.0.0.0", SERVER_PORT), GreenTrayHandler)
    print(f"GreenTray is running on port {SERVER_PORT}")
    if IS_PRODUCTION:
        print(f"Open GreenTray: {customer_page_url()}")
    else:
        print(f"Open on this computer: http://127.0.0.1:{SERVER_PORT}/")
        try:
            print(f"Open on the same Wi-Fi: {customer_page_url()}")
        except (OSError, RuntimeError) as error:
            print(f"Could not determine LAN address: {error}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGreenTray stopped.")
    finally:
        server.server_close()
