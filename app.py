from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pytz import timezone

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DB_NAME = 'room_schedule.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'user'))
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS RoomSchedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            subject TEXT NOT NULL,
            section TEXT NOT NULL,
            room TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            manual_override TEXT DEFAULT NULL
        )''')
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin",
                           generate_password_hash('admin123'), 'admin'))
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("guest",
                           generate_password_hash('guest123'), 'user'))
        conn.commit()

def get_current_day_time():
    ph_tz = timezone('Asia/Manila')
    now = datetime.now(ph_tz)
    return now.strftime('%A'), now.strftime('%H:%M')

def get_schedule():
    day, current_time = get_current_day_time()
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM RoomSchedule")
        rows = cursor.fetchall()
        schedule = []

        current_time_obj = datetime.strptime(current_time, '%H:%M')

        # Create a set to store rooms that are in use during the current day and time
        rooms_in_use = {}

        # Loop through each schedule and determine if the room is in use
        for row in rows:
            id = row[0]
            schedule_day = row[1]
            start_time = row[2]
            end_time = row[3]
            room = row[6]
            status = row[7]
            manual_override = row[8]

            try:
                start_time_obj = datetime.strptime(start_time, '%H:%M')
                end_time_obj = datetime.strptime(end_time, '%H:%M')
            except ValueError:
                continue

            # If today is the scheduled day and the current time falls within the schedule time, mark the room as in use
            if schedule_day == day:
                if room not in rooms_in_use:
                    rooms_in_use[room] = []

                rooms_in_use[room].append((start_time_obj, end_time_obj))

        # Now, loop through the rooms and assign the correct status based on usage
        for row in rows:
            id = row[0]
            schedule_day = row[1]
            start_time = row[2]
            end_time = row[3]
            room = row[6]
            status = row[7]
            manual_override = row[8]

            try:
                start_time_obj = datetime.strptime(start_time, '%H:%M')
                end_time_obj = datetime.strptime(end_time, '%H:%M')
            except ValueError:
                continue

            # Check if the room is in use today, and if the class overlaps with the current time
            room_in_use = False
            if schedule_day == day:
                for scheduled_start, scheduled_end in rooms_in_use.get(room, []):
                    if scheduled_start <= current_time_obj <= scheduled_end:
                        room_in_use = True
                        break

            # Now, determine the status of the room
            if room_in_use:
                status = "Occupied (Auto)" if manual_override is None else "Occupied (Manual)" if manual_override == "occupied" else "Available (Manual)"
            else:
                # If there's no class in use, use auto availability unless there's a manual override
                status = "Available (Auto)" if manual_override is None else "Available (Manual)"

            schedule.append({
                'id': id,
                'day': schedule_day,
                'start_time': start_time,
                'end_time': end_time,
                'subject': row[4],
                'section': row[5],
                'room': room,
                'status': status,
            })

        # Sort the schedule by availability (available rooms first)
        schedule.sort(key=lambda x: ('Available' in x['status'], x['status'] != 'Available (Auto)'), reverse=True)
        return schedule




@app.route('/')
def index():
    if 'username' in session:
        schedule_data = get_schedule()
        user_role = session.get('role')
        return render_template('index.html', schedule=schedule_data, role=user_role)
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[2], password):
                session['username'] = user[1]
                session['role'] = user[3]
                return redirect('/')
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'user')",
                               (username, hashed_pw))
                conn.commit()
                return redirect('/login')
            except sqlite3.IntegrityError:
                return "Username already exists", 400
    return render_template('register.html')

@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'username' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403
    if request.method == 'POST':
        day = request.form['day']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        subject = request.form['subject']
        section = request.form['section']
        room = request.form['room']
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO RoomSchedule (day, start_time, end_time, subject, section, room, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)''', (day, start_time, end_time, subject, section, room, "available"))
            conn.commit()
        return redirect('/')
    return render_template('add.html')

@app.route('/add-admin', methods=['GET', 'POST'])
def add_admin():
    if 'username' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'admin')",
                               (username, hashed_pw))
                conn.commit()
                return "New admin created successfully!"
            except sqlite3.IntegrityError:
                return "Username already exists", 400
    return render_template('add_admin.html')

@app.route('/override/<int:schedule_id>/<action>')
def override(schedule_id, action):
    if 'username' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403

    override_value = None if action == 'auto' else action

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT room, day FROM RoomSchedule WHERE id = ?", (schedule_id,))
        result = cursor.fetchone()

        if result:
            room, day = result
            cursor.execute("""
                UPDATE RoomSchedule 
                SET manual_override = ? 
                WHERE room = ? 
                AND day = ?
            """, (override_value, room, day))
            conn.commit()

    return redirect('/')


@app.route('/delete-schedule/<int:schedule_id>')
def delete_schedule(schedule_id):
    if 'username' not in session or session.get('role') != 'admin':
        return "Unauthorized", 403
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM RoomSchedule WHERE id = ?", (schedule_id,))
        conn.commit()
    return redirect('/')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, use_reloader=False)
