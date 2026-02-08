import sqlite3

DB_NAME = "secrets.db"


def init_db():
    """Creates the database table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create a table to store:
    # id (auto-number), issuer (e.g. Google), name (e.g. alice@gmail.com), secret (the key)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS accounts
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       issuer
                       TEXT,
                       name
                       TEXT,
                       secret
                       TEXT
                       UNIQUE
                   )
                   ''')

    conn.commit()
    conn.close()


def add_account(issuer, name, secret):
    """Saves a new account to the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("INSERT INTO accounts (issuer, name, secret) VALUES (?, ?, ?)",
                       (issuer, name, secret))

        conn.commit()
        print(f"[DB] Saved: {issuer} ({name})")
        return True
    except sqlite3.IntegrityError:
        print("[DB] Error: This secret already exists.")
        return False
    finally:
        conn.close()


def get_all_accounts():
    """Returns a list of all saved accounts."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT issuer, name, secret FROM accounts")
    rows = cursor.fetchall()

    conn.close()

    # Convert list of tuples to list of dictionaries
    accounts = []
    for row in rows:
        accounts.append({
            "issuer": row[0],
            "name": row[1],
            "secret": row[2]
        })
    return accounts


# Initialize the DB immediately when this script is imported
init_db()