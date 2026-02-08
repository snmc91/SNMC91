from flask import Flask, render_template, request, redirect, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
import os, json, requests

app = Flask(__name__)
app.secret_key = "mysecretkey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
PENDING_FILE = os.path.join(BASE_DIR, "pending_users.json")
UPLOAD_BASE = os.path.join(BASE_DIR, "uploads")

# 🔐 Telegram config
BOT_TOKEN = "8237574970:AAGGmIA8pPjarNEQZFvNB5q6oqx7G_BPBhY"
ADMIN_CHAT_ID = "7701363302"

os.makedirs(UPLOAD_BASE, exist_ok=True)

# ---------- HELPERS ----------
def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_pending():
    if not os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, "w") as f:
            json.dump({}, f)
    with open(PENDING_FILE, "r") as f:
        return json.load(f)

def save_pending(data):
    with open(PENDING_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_admin_user(username):
    users = load_users()
    return users.get(username, {}).get("is_admin") is True

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": ADMIN_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print("Telegram error:", e)
# ---------- TELEGRAM INLINE BUTTONS ----------
TELEGRAM_WEBHOOK_SECRET = "snmc91_secret_key_123"  # koi random string rakh de

def send_telegram_approval(username):
   url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": 7701363302,
        "text": f"🆕 New account request:\nUsername: {username}",
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [
                    {"text": "✅ Approve", "callback_data": f"approve:{username}"},
                    {"text": "❌ Reject", "callback_data": f"reject:{username}"}
                ]
            ]
        })
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Telegram send error:", e)

def telegram_webhook():
    data = request.get_json(silent=True) or {}
    cb = data.get("callback_query")
    if not cb:
        return "ok"

    action, username = cb.get("data", "").split(":", 1)
    pending = load_pending()
    users = load_users()

    if action == "approve" and username in pending:
        users[username] = pending.pop(username)
        save_users(users)
        save_pending(pending)
        os.makedirs(os.path.join(UPLOAD_BASE, username), exist_ok=True)
        send_telegram(f"✅ Approved: {username}")

    if action == "reject" and username in pending:
        pending.pop(username)
        save_pending(pending)
        send_telegram(f"❌ Rejected: {username}")

    return "ok"
@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    cb = data.get("callback_query")
    if not cb:
        return "ok"

    payload = cb.get("data", "")
    if ":" not in payload:
        return "ok"

    action, username = payload.split(":", 1)
    pending = load_pending()
    users = load_users()

    if action == "approve" and username in pending:
        users[username] = pending.pop(username)
        save_users(users)
        save_pending(pending)
        os.makedirs(os.path.join(UPLOAD_BASE, username), exist_ok=True)
        send_telegram(f"✅ Approved: {username}")

    elif action == "reject" and username in pending:
        pending.pop(username)
        save_pending(pending)
        send_telegram(f"❌ Rejected: {username}")

    return "ok"
# ---------- USER ACTIONS ----------
@app.route("/delete_file/<username>/<name>", methods=["POST"])
def delete_file(username, name):
    if "user" not in session or session["user"] != username:
        return redirect("/")
    file_path = os.path.join(UPLOAD_BASE, username, name)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect("/dashboard")

@app.route("/delete_link/<int:index>", methods=["POST"])
def delete_link(index):
    if "user" not in session:
        return redirect("/")
    u = session["user"]
    users = load_users()
    try:
        users[u]["links"].pop(index)
        save_users(users)
    except:
        pass
    return redirect("/dashboard")

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        users = load_users()
        if u in users and check_password_hash(users[u]["password"], p):
            session["user"] = u
            return redirect("/dashboard")
    return render_template("login.html")

# 🔔 REGISTER → pending + Telegram notify
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        users = load_users()
        pending = load_pending()

        if not u or not p:
            return render_template("register.html", error="Username & password required")

        if u in users or u in pending:
            return render_template("register.html", error="Username already exists or pending approval")

        pending[u] = {
            "password": generate_password_hash(p),
            "links": [],
            "is_admin": False
        }
        save_pending(pending)

        # 👇 Ye line yahin rehni chahiye (same indentation)
        send_telegram_approval(u)

        return render_template("register.html", success="Request sent to admin. Wait for approval.")
    return render_template("register.html")
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect("/")
    u = session["user"]
    user_dir = os.path.join(UPLOAD_BASE, u)
    os.makedirs(user_dir, exist_ok=True)

    users = load_users()

    if request.method == "POST":
        if "file" in request.files:
            f = request.files["file"]
            if f.filename:
                f.save(os.path.join(user_dir, f.filename))
        if request.form.get("link"):
            users[u]["links"].append(request.form.get("link"))
            save_users(users)

    files = os.listdir(user_dir)
    links = users[u]["links"]
    return render_template("dashboard.html", files=files, links=links, user=u, is_admin=is_admin_user(u))

@app.route("/download/<username>/<name>")
def download(username, name):
    if "user" not in session or session["user"] != username:
        return redirect("/")
    return send_from_directory(os.path.join(UPLOAD_BASE, username), name, as_attachment=True)

# ---------- ADMIN PANEL ----------
@app.route("/admin")
def admin_panel():
    if "user" not in session or not is_admin_user(session["user"]):
        return redirect("/")
    users = load_users()
    return render_template("admin.html", users=users)
@app.route("/admin/update_user", methods=["POST"])
def admin_update_user():
    if "user" not in session or not is_admin_user(session["user"]):
        return redirect("/")

    old_username = request.form.get("old_username")
    new_username = request.form.get("new_username")
    new_password = request.form.get("new_password")

    users = load_users()
    if old_username in users:
        target = old_username

        # change username
        if new_username and new_username != old_username and new_username not in users:
            users[new_username] = users.pop(old_username)
            users[new_username]["is_admin"] = users[new_username].get("is_admin", False)

            old_dir = os.path.join(UPLOAD_BASE, old_username)
            new_dir = os.path.join(UPLOAD_BASE, new_username)
            if os.path.exists(old_dir):
                os.rename(old_dir, new_dir)

            if session.get("user") == old_username:
                session["user"] = new_username

            target = new_username

        # change password
        if new_password:
            users[target]["password"] = generate_password_hash(new_password)

        save_users(users)

    return redirect("/admin")
@app.route("/admin/pending")
def admin_pending():
    if "user" not in session or not is_admin_user(session["user"]):
        return redirect("/")
    pending = load_pending()
    return render_template("admin_pending.html", pending=pending)

@app.route("/admin/approve/<username>", methods=["POST"])
def admin_approve(username):
    if "user" not in session or not is_admin_user(session["user"]):
        return redirect("/")
    pending = load_pending()
    users = load_users()

    if username in pending:
        users[username] = pending.pop(username)
        save_users(users)
        save_pending(pending)
        os.makedirs(os.path.join(UPLOAD_BASE, username), exist_ok=True)
        send_telegram(f"✅ Approved: {username}")

    return redirect("/admin/pending")

@app.route("/admin/reject/<username>", methods=["POST"])
def admin_reject(username):
    if "user" not in session or not is_admin_user(session["user"]):
        return redirect("/")
    pending = load_pending()

    if username in pending:
        pending.pop(username)
        save_pending(pending)
        send_telegram(f"❌ Rejected: {username}")

    return redirect("/admin/pending")

@app.route("/admin/delete_user/<username>", methods=["POST"])
def admin_delete_user(username):
    if "user" not in session or not is_admin_user(session["user"]):
        return redirect("/")

    users = load_users()

    # admin ko delete na hone do
    if users.get(username, {}).get("is_admin") is True:
        return redirect("/admin")

    if username in users:
        users.pop(username, None)
        save_users(users)

    user_dir = os.path.join(UPLOAD_BASE, username)
    if os.path.exists(user_dir):
        for f in os.listdir(user_dir):
            try:
                os.remove(os.path.join(user_dir, f))
            except:
                pass
        try:
            os.rmdir(user_dir)
        except:
            pass

    return redirect("/admin")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# ---------- RENDER PORT FIX ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
