
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-before-deployment"

DB = "ecopoints.db"

REWARDS = {
    "Mobile Phone": 50,
    "Laptop": 100,
    "Battery": 20,
    "Keyboard": 30,
    "Mouse": 15,
    "Monitor": 60,
    "Other": 10
}

BADGES = [
    {"name": "Green Beginner", "points": 100, "icon": "🌱"},
    {"name": "Eco Explorer", "points": 300, "icon": "🌿"},
    {"name": "Planet Protector", "points": 700, "icon": "🌍"},
    {"name": "Eco Legend", "points": 1500, "icon": "🏆"}
]


def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            points INTEGER DEFAULT 0
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            location TEXT NOT NULL,
            points INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    admin = con.execute(
        "SELECT id FROM users WHERE email=?",
        ("admin@ecopoints.com",)
    ).fetchone()

    if not admin:
        con.execute("""
            INSERT INTO users(name,email,password)
            VALUES(?,?,?)
        """, (
            "Eco Admin",
            "admin@ecopoints.com",
            generate_password_hash("Admin@123")
        ))

    con.commit()
    con.close()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("email") != "admin@ecopoints.com":
            flash("Admin access required.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    con = get_db()
    total_items = con.execute("""
        SELECT COALESCE(SUM(quantity),0)
        FROM requests WHERE status='Collected'
    """).fetchone()[0]

    total_users = con.execute("""
        SELECT COUNT(*) FROM users
        WHERE email != 'admin@ecopoints.com'
    """).fetchone()[0]

    con.close()

    return render_template(
        "index.html",
        total_items=total_items,
        total_users=total_users
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or len(password) < 8:
            flash("Enter your name and a password of at least 8 characters.")
            return redirect(url_for("register"))

        con = get_db()
        try:
            con.execute("""
                INSERT INTO users(name,email,password)
                VALUES(?,?,?)
            """, (name, email, generate_password_hash(password)))
            con.commit()
            flash("Welcome to EcoPoints! Your account is ready.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("This email is already registered.")
        finally:
            con.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        con = get_db()
        user = con.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()
        con.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["email"] = user["email"]

            if email == "admin@ecopoints.com":
                return redirect(url_for("admin"))

            return redirect(url_for("dashboard"))

        flash("Incorrect email or password.")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    if session["email"] == "admin@ecopoints.com":
        return redirect(url_for("admin"))

    con = get_db()

    user = con.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    requests = con.execute("""
        SELECT * FROM requests
        WHERE user_id=? ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    collected_items = con.execute("""
        SELECT COALESCE(SUM(quantity),0)
        FROM requests
        WHERE user_id=? AND status='Collected'
    """, (session["user_id"],)).fetchone()[0]

    con.close()

    points = user["points"]

    earned_badges = [
        badge for badge in BADGES
        if points >= badge["points"]
    ]

    next_badge = next(
        (badge for badge in BADGES if points < badge["points"]),
        None
    )

    if next_badge:
        previous = 0
        for badge in BADGES:
            if badge["points"] < next_badge["points"]:
                previous = badge["points"]

        progress = min(
            100,
            int((points - previous) /
                (next_badge["points"] - previous) * 100)
        )
        points_needed = next_badge["points"] - points
    else:
        progress = 100
        points_needed = 0

    challenge_goal = 3
    challenge_progress = min(collected_items, challenge_goal)

    return render_template(
        "dashboard.html",
        user=user,
        requests=requests,
        collected_items=collected_items,
        badges=earned_badges,
        next_badge=next_badge,
        progress=progress,
        points_needed=points_needed,
        challenge_goal=challenge_goal,
        challenge_progress=challenge_progress
    )


@app.route("/submit", methods=["GET", "POST"])
@login_required
def submit():
    if session["email"] == "admin@ecopoints.com":
        return redirect(url_for("admin"))

    if request.method == "POST":
        item = request.form["item"]
        location = request.form["location"].strip()

        try:
            quantity = int(request.form["quantity"])
        except ValueError:
            flash("Enter a valid quantity.")
            return redirect(url_for("submit"))

        if item not in REWARDS or not location or not 1 <= quantity <= 100:
            flash("Please enter valid details.")
            return redirect(url_for("submit"))

        points = REWARDS[item] * quantity

        con = get_db()
        con.execute("""
            INSERT INTO requests
            (user_id,item,quantity,location,points,status)
            VALUES(?,?,?,?,?,'Pending')
        """, (
            session["user_id"],
            item,
            quantity,
            location,
            points
        ))
        con.commit()
        con.close()

        flash("Request submitted! Points will be credited after collection.")
        return redirect(url_for("dashboard"))

    return render_template("submit.html", rewards=REWARDS)


@app.route("/admin")
@login_required
@admin_required
def admin():
    con = get_db()

    requests = con.execute("""
        SELECT requests.*, users.name, users.email
        FROM requests
        JOIN users ON requests.user_id=users.id
        ORDER BY requests.id DESC
    """).fetchall()

    stats = {
        "users": con.execute("""
            SELECT COUNT(*) FROM users
            WHERE email != 'admin@ecopoints.com'
        """).fetchone()[0],

        "requests": con.execute(
            "SELECT COUNT(*) FROM requests"
        ).fetchone()[0],

        "pending": con.execute("""
            SELECT COUNT(*) FROM requests WHERE status='Pending'
        """).fetchone()[0],

        "collected": con.execute("""
            SELECT COUNT(*) FROM requests WHERE status='Collected'
        """).fetchone()[0]
    }

    con.close()

    return render_template(
        "admin.html",
        requests=requests,
        stats=stats
    )


@app.route("/update/<int:request_id>/<action>", methods=["POST"])
@login_required
@admin_required
def update_request(request_id, action):
    if action not in ["Collected", "Rejected"]:
        flash("Invalid action.")
        return redirect(url_for("admin"))

    con = get_db()

    row = con.execute(
        "SELECT * FROM requests WHERE id=?",
        (request_id,)
    ).fetchone()

    if row and row["status"] == "Pending":
        con.execute(
            "UPDATE requests SET status=? WHERE id=?",
            (action, request_id)
        )

        if action == "Collected":
            con.execute("""
                UPDATE users SET points=points+?
                WHERE id=?
            """, (row["points"], row["user_id"]))

        con.commit()

    con.close()
    flash("Collection status updated.")
    return redirect(url_for("admin"))


@app.route("/leaderboard")
def leaderboard():
    con = get_db()

    users = con.execute("""
        SELECT name, points FROM users
        WHERE email != 'admin@ecopoints.com'
        ORDER BY points DESC LIMIT 10
    """).fetchall()

    con.close()
    return render_template("leaderboard.html", users=users)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
