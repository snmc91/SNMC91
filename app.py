from flask import Flask, render_template, request, redirect, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash
import os, json

app = Flask(__name__)
app.secret_key = "mysecretkey"

# ---- CONFIG ----
ADMIN_USER = "admin"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
UPLOAD_BASE = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_BASE, exist_ok=True)

# ---- HELPERS ----
def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---- USER ACTIONS ----
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

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        users = load_users()
        if u and p and u not in users and u != ADMIN_USER:
            users[u] = {
                "password": generate_password_hash(p),
                "links": []
            }
            save_users(users)
            os.makedirs(os.path.join(UPLOAD_BASE, u), exist_ok=True)
            return redirect("/")
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
    return render_template("dashboard.html", files=files, links=links, user=u)

@app.route("/download/<username>/<name>")
def download(username, name):
    if "user" not in session or session["user"] != username:
        return redirect("/")
    return send_from_directory(os.path.join(UPLOAD_BASE, username), name, as_attachment=True)

# ---- ADMIN PANEL ----
@app.route("/admin")
def admin_panel():
    if "user" not in session or session["user"] != ADMIN_USER:
        return redirect("/")
    users = load_users()
    return render_template("admin.html", users=users)

@app.route("/admin/update_user", methods=["POST"])
def admin_update_user():
    global ADMIN_USER
    if "user" not in session or session["user"] != ADMIN_USER:
        return redirect("/")

    old_username = request.form.get("old_username")
    new_username = request.form.get("new_username")
    new_password = request.form.get("new_password")

    users = load_users()
    if old_username in users:
        target = old_username

        # Change username (avoid duplicates)
        if new_username and new_username != old_username and new_username not in users:
            users[new_username] = users.pop(old_username)

            old_dir = os.path.join(UPLOAD_BASE, old_username)
            new_dir = os.path.join(UPLOAD_BASE, new_username)
            if os.path.exists(old_dir):
                os.rename(old_dir, new_dir)

            if old_username == ADMIN_USER:
                ADMIN_USER = new_username
                session["user"] = new_username

            target = new_username

        # Change password
        if new_password:
            users[target]["password"] = generate_password_hash(new_password)

        save_users(users)

    return redirect("/admin")

@app.route("/admin/user/<username>")
def admin_view_user(username):
    if "user" not in session or session["user"] != ADMIN_USER:
        return redirect("/")
    users = load_users()
    user_dir = os.path.join(UPLOAD_BASE, username)
    files = os.listdir(user_dir) if os.path.exists(user_dir) else []
    links = users.get(username, {}).get("links", [])
    return render_template("admin_user.html", username=username, files=files, links=links)

@app.route("/admin/reset_user/<username>", methods=["POST"])
def admin_reset_user(username):
    if "user" not in session or session["user"] != ADMIN_USER:
        return redirect("/")
    users = load_users()
    if username in users:
        users[username]["links"] = []
        save_users(users)
    user_dir = os.path.join(UPLOAD_BASE, username)
    if os.path.exists(user_dir):
        for f in os.listdir(user_dir):
            try:
                os.remove(os.path.join(user_dir, f))
            except:
                pass
    return redirect(f"/admin/user/{username}")

@app.route("/admin/delete_user/<username>", methods=["POST"])
def admin_delete_user(username):
    if "user" not in session or session["user"] != ADMIN_USER:
        return redirect("/")
    if username == ADMIN_USER:
        return redirect("/admin")

    users = load_users()
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

# ---- RENDER PORT FIX ----
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
