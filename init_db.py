def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # Drop existing RoomSchedule table to recreate it with the updated schema
        cursor.execute('DROP TABLE IF EXISTS RoomSchedule')
        conn.commit()

        # Create new RoomSchedule table with start_time and end_time
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS RoomSchedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                subject TEXT NOT NULL,
                section TEXT NOT NULL,
                room TEXT NOT NULL,
                manual_override TEXT DEFAULT NULL
            )
        ''')

        # Insert default admin user if the users table is empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           ('admin', generate_password_hash('admin123'), 'admin'))
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                           ('guest', generate_password_hash('guest123'), 'user'))

        conn.commit()
