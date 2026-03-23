from flask import Flask, render_template, request, redirect, g, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime, date

app = Flask(__name__)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.permanent_session_lifetime = 60 * 60 * 24 * 30  # 30 يوم
app.secret_key = 'secret123'
DB = "database.db"

# =====================
# NOW() IN HTML
# =====================
@app.context_processor
def inject_now():
    return {'now': datetime.now}

# =====================
# DB CONNECTION
# =====================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# =====================
# INIT DB ✅ (FIXED)
# =====================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # USERS
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )''')

    # CARS
    c.execute('''CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        marque TEXT,
        modele TEXT,
        prix INTEGER,
        plate TEXT,
        chassis TEXT,
        assurance TEXT,
        controle TEXT,
        oil_change TEXT
    )''')

    # CLIENTS
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT
    )''')

    # RENTALS
    c.execute('''CREATE TABLE IF NOT EXISTS rentals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        car_id INTEGER,
        start_date TEXT,
        end_date TEXT
    )''')

    # ✅ LOGS (الجديد)
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        car_id INTEGER,
        action TEXT,
        fuel TEXT,
        km TEXT,
        damage TEXT,
        note TEXT,
        date TEXT
    )''')

    conn.commit()
    conn.close()

# =====================
# CHECK LOGIN
# =====================
def check_login():
    return 'user_id' in session

# =====================
# REGISTER ✅
# =====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    db = get_db()

    if request.method == 'POST':
        username = request.form.get('username')
        raw_password = request.form.get('password')

        # تحقق من الحقول
        if not username or not raw_password:
            flash("❌ جميع الحقول مطلوبة", "warning")
            return redirect('/register')

        if len(raw_password) < 4:
            flash("❌ كلمة السر ضعيفة", "warning")
            return redirect('/register')

        password = generate_password_hash(raw_password)

        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            db.commit()
            flash("✅ تم إنشاء الحساب", "success")
            return redirect('/login')

        except sqlite3.IntegrityError:
            flash("❌ اسم المستخدم موجود بالفعل", "danger")
            return redirect('/register')

    return render_template('register.html')

# =====================
# LOGIN ✅
# =====================
@app.route('/login', methods=['GET','POST'])
def login():
    db = get_db()

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # تحقق من الحقول
        if not username or not password:
            flash("❌ جميع الحقول مطلوبة", "warning")
            return redirect('/login')

        user = db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user['password'], password):
            session.permanent = True
            session['user_id'] = user['id']
            flash("✅ مرحبا بك!", "success")
            return redirect('/dashboard')
        else:
            flash("❌ معلومات خاطئة", "danger")
            return redirect('/login')

    return render_template('login.html')

# =====================
# LOGOUT
# =====================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# =====================
# HOME
# =====================
@app.route('/')
def home():
    if not check_login():
        return redirect('/login')
    return render_template('index.html')

# =====================
# CARS
# =====================
@app.route('/cars', methods=['GET', 'POST'])
def cars_page():
    if not check_login():
        return redirect('/login')

    db = get_db()

    if request.method == 'POST':
        data = tuple(request.form.get(x) for x in [
            'marque','modele','prix','plate','chassis','assurance','controle','oil_change'
        ])

        if not all(data):
            return "❌ جميع الحقول مطلوبة"

        db.execute("""
            INSERT INTO cars (marque, modele, prix, plate, chassis, assurance, controle, oil_change)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        db.commit()

    cars = db.execute("SELECT * FROM cars ORDER BY id DESC").fetchall()
    return render_template('cars.html', cars=cars)

@app.route('/delete_car/<int:id>')
def delete_car(id):
    if not check_login():
        return redirect('/login')

    db = get_db()
    db.execute("DELETE FROM cars WHERE id=?", (id,))
    db.commit()
    return redirect('/cars')

# =====================
# CLIENTS
# =====================
@app.route('/clients', methods=['GET', 'POST'])
def clients_page():
    if not check_login():
        return redirect('/login')

    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')

        if not name or not phone:
            return "❌ البيانات ناقصة"

        db.execute("INSERT INTO clients (name, phone) VALUES (?, ?)", (name, phone))
        db.commit()

    clients = db.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    return render_template('clients.html', clients=clients)

@app.route('/delete_client/<int:id>')
def delete_client(id):
    if not check_login():
        return redirect('/login')

    db = get_db()
    db.execute("DELETE FROM clients WHERE id=?", (id,))
    db.commit()
    return redirect('/clients')

# =====================
# RENTALS
# =====================
@app.route('/rentals', methods=['GET','POST'])
def rentals_page():
    if not check_login():
        return redirect('/login')

    db = get_db()
    error = None

    if request.method == 'POST':
        try:
            car_id = int(request.form.get('car'))
            client_id = int(request.form.get('client'))
            start = request.form.get('start_date')
            end = request.form.get('end_date')

            d1 = datetime.strptime(start, "%Y-%m-%d")
            d2 = datetime.strptime(end, "%Y-%m-%d")

            if d2 <= d1:
                error = "❌ تاريخ غير صالح"
            else:
                conflict = db.execute("""
                    SELECT 1 FROM rentals
                    WHERE car_id=? AND (start_date <= ? AND end_date >= ?)
                """, (car_id, end, start)).fetchone()

                if conflict:
                    error = "❌ السيارة محجوزة"
                else:
                    today = str(date.today())
                    car = db.execute("""
                        SELECT assurance, controle, oil_change
                        FROM cars WHERE id=?
                    """, (car_id,)).fetchone()

                    if not car:
                        error = "❌ السيارة غير موجودة"
                    elif car["assurance"] < today or car["controle"] < today:
                        error = "❌ التأمين أو الفحص منتهي"
                    elif car["oil_change"] < today:
                        error = "❌ تحتاج تغيير زيت"
                    else:
                        db.execute("""
                            INSERT INTO rentals (client_id, car_id, start_date, end_date)
                            VALUES (?, ?, ?, ?)
                        """, (client_id, car_id, start, end))
                        db.commit()
                        return redirect('/rentals')

        except Exception as e:
            error = f"⚠️ {str(e)}"

    rentals = db.execute("""
        SELECT rentals.id, clients.name, cars.marque, cars.modele, cars.prix,
               rentals.start_date, rentals.end_date
        FROM rentals
        JOIN clients ON rentals.client_id = clients.id
        JOIN cars ON rentals.car_id = cars.id
        ORDER BY rentals.id DESC
    """).fetchall()

    clients = db.execute("SELECT * FROM clients").fetchall()

    today = str(date.today())
    cars = db.execute("""
        SELECT * FROM cars
        WHERE assurance >= ? AND controle >= ?
    """, (today, today)).fetchall()

    return render_template('rentals.html',
                           rentals=rentals,
                           clients=clients,
                           cars=cars,
                           error=error)

@app.route('/delete_rental/<int:id>')
def delete_rental(id):
    if not check_login():
        return redirect('/login')

    db = get_db()
    db.execute("DELETE FROM rentals WHERE id=?", (id,))
    db.commit()
    return redirect('/rentals')

# =====================
# DASHBOARD
# =====================
@app.route('/dashboard')
def dashboard():
    if not check_login():
        return redirect('/login')

    db = get_db()

    cars = db.execute("SELECT COUNT(*) FROM cars").fetchone()[0]
    clients = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    rentals = db.execute("SELECT COUNT(*) FROM rentals").fetchone()[0]

    today = str(date.today())

    expired_insurance = db.execute(
        "SELECT COUNT(*) FROM cars WHERE assurance < ?", (today,)
    ).fetchone()[0]

    expired_controle = db.execute(
        "SELECT COUNT(*) FROM cars WHERE controle < ?", (today,)
    ).fetchone()[0]

    oil_due = db.execute(
        "SELECT COUNT(*) FROM cars WHERE oil_change < ?", (today,)
    ).fetchone()[0]

    return render_template(
        'dashboard.html',
        cars=cars,
        clients=clients,
        rentals=rentals,
        expired_insurance=expired_insurance,
        expired_controle=expired_controle,
        oil_due=oil_due
    )

# =====================
# FIELD APP 📱
# =====================
@app.route('/field', methods=['GET','POST'])
def field_app():
    if not check_login():
        return redirect('/login')

    db = get_db()

    if request.method == 'POST':
        car_id = request.form.get('car')
        action = request.form.get('action')
        fuel = request.form.get('fuel')
        km = request.form.get('km')
        damage = request.form.get('damage')
        note = request.form.get('note')

        from datetime import datetime
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")

        db.execute("""
            INSERT INTO logs (car_id, action, fuel, km, damage, note, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (car_id, action, fuel, km, damage, note, date_now))

        db.commit()
        flash("✅ تسجلت العملية", "success")
        return redirect('/field')

    cars = db.execute("SELECT * FROM cars").fetchall()

    return render_template('field.html', cars=cars)

@app.route('/debug_cars')
def debug_cars():
    db = get_db()
    cars = db.execute("SELECT * FROM cars").fetchall()

    result = []
    for car in cars:
        result.append(dict(car))

    return str(result)
@app.route('/logs')
def logs():
    if not check_login():
        return redirect('/login')

    db = get_db()

    logs = db.execute("""
        SELECT logs.*, cars.marque, cars.modele
        FROM logs
        JOIN cars ON logs.car_id = cars.id
        ORDER BY logs.id DESC
    """).fetchall()

    return render_template('logs.html', logs=logs)


# =====================
# RUN
# =====================

if __name__ == '__main__':
    print("🚀 creating database...")
    init_db()   # ✅ مهم جدا هنا

    print("🚀 server starting...")
    app.run(host='0.0.0.0', port=5000, debug=True)
