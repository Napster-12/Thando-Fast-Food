import os
import random
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("THANDO_DB", os.path.join(BASE_DIR, "thando.db"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "thando-admin")

STORE = {
    "name": "THANDO FAST FOOD",
    "short_name": "Thando",
    "tagline": "Good food, good mood.",
    "phone": "076 868 2209",
    "phone_link": "+27768682209",
    "address": "10 Intaka Place, Ntuzuma",
    "hours": "Open daily, 11:00 – 23:00",
    "open_hour": 11,
    "close_hour": 23,
}

# Menu sections, in the order they appear on the menu board.
CATEGORIES = [
    {"name": "Kota", "icon": "basket2-fill", "blurb": "Create your own kota."},
    {"name": "Amagwinya", "icon": "brightness-high-fill", "blurb": "Fresh vetkoek, plain or loaded (umkhuba)."},
    {"name": "Isinkwa Combo", "icon": "grid-3x3-gap-fill", "blurb": "Bread on its own or with fries and toppings."},
    {"name": "Hotdogs", "icon": "fire", "blurb": "Hot, saucy and filling."},
    {"name": "Fries", "icon": "bag-fill", "blurb": "Hot chips in three sizes."},
    {"name": "Something Meaty", "icon": "star-fill", "blurb": "On their own, or as fillings for your kota."},
]


def _items(category, rows):
    return [{"id": i, "name": n, "price": p, "category": category, "desc": d} for i, n, p, d in rows]


MENU = (
    _items("Amagwinya", [
        ("igwinya", "Igwinya only", 5.00, ""),
        ("igwinya-polony", "Igwinya & polony", 6.50, ""),
        ("igwinya-cheese", "Igwinya & cheese", 8.00, ""),
        ("igwinya-polony-cheese", "Igwinya, polony & cheese", 10.00, ""),
        ("umkhuba-yababa", "Igwinya & half yababa", 10.00, "Umkhuba"),
        ("umkhuba-fries", "Igwinya & fries", 10.00, "Umkhuba"),
        ("umkhuba-yababa-fries", "Igwinya, half yababa & fries", 15.00, "Umkhuba"),
    ])
    + _items("Isinkwa Combo", [
        ("white-bread", "White bread", 20.00, ""),
        ("brown-bread", "Brown bread", 19.00, ""),
        ("bread-slice", "Slice of bread", 2.00, ""),
        ("four-slice", "4 slices of bread", 5.00, ""),
        ("four-slice-fries", "4 slices with fries", 10.00, ""),
        ("four-slice-yababa-fries", "4 slices with yababa & fries", 20.00, ""),
        ("four-slice-russian-fries", "4 slices with half cheese russian & fries", 25.00, ""),
    ])
    + _items("Hotdogs", [
        ("hotdog", "Hotdog", 20.00, ""),
        ("hotdog-onions", "Hotdog with onions", 22.00, ""),
        ("hotdog-shatini", "Hotdog with shatini", 23.00, ""),
        ("hotdog-russian", "Hotdog with cheese russian", 25.00, ""),
        ("hotdog-chips", "Hotdog & chips", 35.00, ""),
    ])
    + _items("Fries", [
        ("chips-small", "Small chips", 15.00, ""),
        ("chips-medium", "Medium chips", 20.00, ""),
        ("chips-large", "Large chips", 30.00, ""),
    ])
    + _items("Something Meaty", [
        ("polony", "Polony", 1.50, ""),
        ("cheese", "Cheese", 4.00, ""),
        ("yababa", "Yababa", 18.00, ""),
        ("sausage", "Sausage", 6.00, ""),
        ("cheese-russian", "Cheese russian", 20.00, ""),
        ("chicken-feet", "Chicken feet", 2.00, ""),
    ])
)
MENU_BY_ID = {item["id"]: item for item in MENU}

# Create-your-own kota: pick one bread base, then add any fillings.
KOTA_BASES = [i for i in MENU if i["category"] == "Isinkwa Combo" and i["id"] != "bread-slice"]
KOTA_FILLINGS = [i for i in MENU if i["category"] == "Something Meaty"]
KOTA_MAX_EACH = 5

for cat in CATEGORIES:
    prices = [i["price"] for i in MENU if i["category"] == cat["name"]]
    cat["from_price"] = min(prices) if prices else min(b["price"] for b in KOTA_BASES)

ORDER_STATUSES = ["Received", "Preparing", "Ready", "Collected", "Cancelled"]
BOOKING_STATUSES = ["Pending", "Confirmed", "Cancelled"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    notes TEXT,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Received',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    item_name TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_phone TEXT,
    booking_date TEXT NOT NULL,
    booking_time TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    special_requests TEXT,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    barcode TEXT UNIQUE NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    low_stock_at INTEGER NOT NULL DEFAULT 5,
    price REAL NOT NULL DEFAULT 0
);
"""


# ---------- Database ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        db.execute(
            "INSERT INTO products (name, description, barcode, stock, low_stock_at, price) VALUES (?, ?, ?, ?, ?, ?)",
            ("Chicken Spice", "Ground chicken spice mix", "123456789", 20, 5, 25.00),
        )
    db.commit()
    db.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(row):
    return dict(row) if row else None


# ---------- Auth ----------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify(error="Not logged in"), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    return {"store": STORE, "is_admin": session.get("is_admin", False)}


# ---------- Public pages ----------

@app.route("/")
def home():
    return render_template("home.html", menu=MENU, categories=CATEGORIES)


@app.route("/menu")
def menu():
    return render_template("menu.html", menu=MENU, categories=CATEGORIES,
                           kota_bases=KOTA_BASES, kota_fillings=KOTA_FILLINGS, kota_max=KOTA_MAX_EACH)


@app.route("/reservation")
def reservation():
    return render_template("reservation.html", today=date.today().isoformat())


@app.route("/chat")
def chat():
    return render_template("chat.html", menu=MENU)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            next_url = request.args.get("next", "")
            # Only allow local redirects
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("admin")
            return redirect(next_url)
        flash("Wrong password, try again.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------- Staff pages ----------

@app.route("/admin")
@login_required
def admin():
    db = get_db()
    orders = [row_to_dict(r) for r in db.execute("SELECT * FROM orders ORDER BY id DESC")]
    items = db.execute("SELECT * FROM order_items").fetchall()
    for order in orders:
        order["items"] = [dict(i) for i in items if i["order_id"] == order["id"]]
    bookings = db.execute(
        "SELECT * FROM bookings ORDER BY booking_date DESC, booking_time DESC").fetchall()
    return render_template("admin.html", orders=orders, bookings=bookings,
                           order_statuses=ORDER_STATUSES, booking_statuses=BOOKING_STATUSES)


@app.route("/management")
@login_required
def management():
    return render_template("management.html")


# ---------- API: orders ----------

def make_order_code(db):
    while True:
        code = f"TF-{random.randint(10000, 99999)}"
        if not db.execute("SELECT 1 FROM orders WHERE code = ?", (code,)).fetchone():
            return code


def build_kota(spec):
    """Turn {"base": id, "fillings": {id: qty}} into (name, price), or None if invalid."""
    if not isinstance(spec, dict):
        return None
    base = MENU_BY_ID.get(spec.get("base"))
    if base not in KOTA_BASES:
        return None
    price = base["price"]
    parts = []
    fillings = spec.get("fillings") or {}
    if not isinstance(fillings, dict):
        return None
    for item in KOTA_FILLINGS:
        try:
            n = int(fillings.get(item["id"], 0))
        except (TypeError, ValueError):
            return None
        if not 0 <= n <= KOTA_MAX_EACH:
            return None
        if n:
            price += item["price"] * n
            parts.append(f"{n}× {item['name']}" if n > 1 else item["name"])
    name = f"Kota: {base['name']}" + (f" + {', '.join(parts)}" if parts else "")
    return name, round(price, 2)


@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    name = (data.get("customer_name") or "").strip()
    phone = (data.get("customer_phone") or "").strip()
    notes = (data.get("notes") or "").strip()[:500]
    if not name or not phone:
        return jsonify(error="Name and phone number are required."), 400

    lines = []  # (display name, unit price, quantity)
    for entry in data.get("items") or []:
        try:
            qty = int(entry.get("quantity", 0))
        except (TypeError, ValueError):
            continue
        if not 0 < qty <= 50:
            continue
        if "kota" in entry:
            kota = build_kota(entry["kota"])
            if kota:
                lines.append((*kota, qty))
        elif entry.get("id") in MENU_BY_ID:
            item = MENU_BY_ID[entry["id"]]
            lines.append((item["name"], item["price"], qty))
    if not lines:
        return jsonify(error="Your cart is empty."), 400

    # Prices always come from the server-side menu, never from the client.
    total = round(sum(price * qty for _, price, qty in lines), 2)
    db = get_db()
    code = make_order_code(db)
    cur = db.execute(
        "INSERT INTO orders (code, customer_name, customer_phone, notes, total, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (code, name, phone, notes, total, now_iso()),
    )
    db.executemany(
        "INSERT INTO order_items (order_id, item_name, unit_price, quantity) VALUES (?, ?, ?, ?)",
        [(cur.lastrowid, name, price, qty) for name, price, qty in lines],
    )
    db.commit()
    return jsonify(code=code, total=total, status="Received"), 201


@app.get("/api/orders/<code>")
def track_order(code):
    row = get_db().execute(
        "SELECT code, status, total, created_at FROM orders WHERE code = ?", (code.upper(),)
    ).fetchone()
    if not row:
        return jsonify(error="Order not found."), 404
    return jsonify(dict(row))


@app.post("/api/orders/<int:order_id>/status")
@login_required
def update_order_status(order_id):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in ORDER_STATUSES:
        return jsonify(error="Invalid status."), 400
    db = get_db()
    if db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id)).rowcount == 0:
        abort(404)
    db.commit()
    return jsonify(ok=True, status=status)


# ---------- API: bookings ----------

@app.post("/api/bookings")
def create_booking():
    data = request.get_json(silent=True) or {}
    name = (data.get("customer_name") or "").strip()
    email = (data.get("customer_email") or "").strip()
    phone = (data.get("customer_phone") or "").strip()
    booking_date = data.get("booking_date") or ""
    booking_time = data.get("booking_time") or ""
    requests_text = (data.get("special_requests") or "").strip()[:500]

    if not name or not email or not booking_date or not booking_time:
        return jsonify(error="Please fill in all required fields."), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify(error="Please enter a valid email address."), 400
    try:
        party_size = int(data.get("party_size", 0))
        day = date.fromisoformat(booking_date)
        hour, minute = (int(p) for p in booking_time.split(":"))
    except (TypeError, ValueError):
        return jsonify(error="Invalid date, time or party size."), 400
    if not 1 <= party_size <= 8:
        return jsonify(error="Online bookings are for 1–8 people. For bigger groups, please call us."), 400
    if day < date.today():
        return jsonify(error="Please choose a date from today onwards."), 400
    # Last seating is one hour before closing.
    minutes = hour * 60 + minute
    if not STORE["open_hour"] * 60 <= minutes <= (STORE["close_hour"] - 1) * 60:
        return jsonify(error="Please choose a time between 11:00 and 22:00."), 400

    db = get_db()
    cur = db.execute(
        """INSERT INTO bookings (customer_name, customer_email, customer_phone, booking_date,
           booking_time, party_size, special_requests, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, email, phone, booking_date, booking_time, party_size, requests_text, now_iso()),
    )
    db.commit()
    return jsonify(id=cur.lastrowid, status="Pending"), 201


@app.post("/api/bookings/<int:booking_id>/status")
@login_required
def update_booking_status(booking_id):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in BOOKING_STATUSES:
        return jsonify(error="Invalid status."), 400
    db = get_db()
    if db.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id)).rowcount == 0:
        abort(404)
    db.commit()
    return jsonify(ok=True, status=status)


# ---------- API: inventory ----------

def product_from_payload(data):
    name = (data.get("name") or "").strip()
    barcode = (data.get("barcode") or "").strip()
    if not name or not barcode:
        raise ValueError("Name and barcode are required.")
    try:
        stock = int(data.get("stock", 0))
        low = int(data.get("low_stock_at", 5))
        price = float(data.get("price", 0))
    except (TypeError, ValueError):
        raise ValueError("Stock, low-stock level and price must be numbers.")
    if stock < 0 or low < 0 or price < 0:
        raise ValueError("Numbers can't be negative.")
    return (name, (data.get("description") or "").strip(), barcode, stock, low, round(price, 2))


@app.get("/api/products")
@login_required
def list_products():
    rows = get_db().execute("SELECT * FROM products ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/products")
@login_required
def create_product():
    try:
        values = product_from_payload(request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO products (name, description, barcode, stock, low_stock_at, price) VALUES (?, ?, ?, ?, ?, ?)",
            values)
    except sqlite3.IntegrityError:
        return jsonify(error="A product with that barcode already exists."), 409
    db.commit()
    return jsonify(row_to_dict(db.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone())), 201


@app.put("/api/products/<int:product_id>")
@login_required
def update_product(product_id):
    try:
        values = product_from_payload(request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    db = get_db()
    try:
        updated = db.execute(
            """UPDATE products SET name = ?, description = ?, barcode = ?, stock = ?,
               low_stock_at = ?, price = ? WHERE id = ?""", (*values, product_id)).rowcount
    except sqlite3.IntegrityError:
        return jsonify(error="A product with that barcode already exists."), 409
    if not updated:
        abort(404)
    db.commit()
    return jsonify(row_to_dict(db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()))


@app.delete("/api/products/<int:product_id>")
@login_required
def delete_product(product_id):
    db = get_db()
    if db.execute("DELETE FROM products WHERE id = ?", (product_id,)).rowcount == 0:
        abort(404)
    db.commit()
    return jsonify(ok=True)


@app.get("/api/products/barcode/<barcode>")
@login_required
def product_by_barcode(barcode):
    row = get_db().execute("SELECT * FROM products WHERE barcode = ?", (barcode.strip(),)).fetchone()
    if not row:
        return jsonify(error="No product with that barcode."), 404
    return jsonify(dict(row))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
