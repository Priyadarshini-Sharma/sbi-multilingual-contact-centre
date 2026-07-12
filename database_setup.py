"""
database_setup.py
------------------
Initializes sbi_contact_centre.db (SQLite) with three tables:
  - Customers
  - Agents
  - CallLogs

Run standalone to (re)create the DB and seed it with synthetic data:
    python database_setup.py
"""

import sqlite3
import random
from pathlib import Path

DB_PATH = Path(__file__).parent / "sbi_contact_centre.db"

# ---- Synthetic seed data -----------------------------------------------

INDIAN_LANGUAGES = [
    "Hindi", "English", "Bengali", "Marathi", "Tamil", "Telugu",
    "Gujarati", "Kannada", "Malayalam", "Punjabi", "Odia",
    "Konkani", "Dogri", "Nepali",
]

FIRST_NAMES = [
    "Rohan", "Priya", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya",
    "Rahul", "Meera", "Aditya", "Divya", "Karthik", "Neha", "Suresh",
    "Pooja", "Manoj", "Ritu", "Sanjay", "Deepika", "Amitabh",
]

SPECIALTIES = ["Fraud", "Loans", "General", "Deceased Claims", "YONO Tech", "Video Advisory"]


def get_connection():
    return sqlite3.connect(DB_PATH)


def create_schema(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS CallLogs")
    cur.execute("DROP TABLE IF EXISTS Customers")
    cur.execute("DROP TABLE IF EXISTS Agents")

    cur.execute("""
        CREATE TABLE Customers (
            customer_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number      TEXT UNIQUE NOT NULL,
            name              TEXT NOT NULL,
            age               INTEGER NOT NULL,
            native_language   TEXT NOT NULL,
            balance           REAL NOT NULL,
            nominee_status    TEXT NOT NULL,   -- 'Registered' / 'Not Registered'
            voiceprint_enrolled INTEGER NOT NULL  -- boolean 0/1: Service 2, Passive Voice Biometrics
        )
    """)

    cur.execute("""
        CREATE TABLE Agents (
            agent_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            languages      TEXT NOT NULL,   -- comma-separated
            specialties    TEXT NOT NULL,   -- comma-separated, e.g. "Fraud,YONO Tech"
            workload_score REAL NOT NULL,   -- 0.0 - 1.0
            csat_score     REAL NOT NULL    -- 0.0 - 5.0
        )
    """)

    cur.execute("""
        CREATE TABLE CallLogs (
            call_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id       INTEGER NOT NULL,
            agent_id          INTEGER,        -- nullable: may be self-service
            intent            TEXT NOT NULL,
            initial_sentiment REAL NOT NULL,  -- -1.0 to 1.0
            final_sentiment   REAL NOT NULL,  -- -1.0 to 1.0
            duration_seconds  INTEGER NOT NULL,
            fcr_status        INTEGER NOT NULL, -- boolean 0/1
            FOREIGN KEY (customer_id) REFERENCES Customers(customer_id),
            FOREIGN KEY (agent_id) REFERENCES Agents(agent_id)
        )
    """)
    conn.commit()


def seed_customers(conn, n=150):
    cur = conn.cursor()
    used_numbers = set()
    for i in range(n):
        name = random.choice(FIRST_NAMES)
        age = random.randint(18, 85)
        lang = random.choice(INDIAN_LANGUAGES)
        balance = round(random.uniform(500, 500000), 2)
        nominee = random.choice(["Registered", "Not Registered"])
        voiceprint_enrolled = 1 if random.random() < 0.6 else 0

        # generate a unique 10-digit mobile number
        while True:
            phone = "9" + "".join(str(random.randint(0, 9)) for _ in range(9))
            if phone not in used_numbers:
                used_numbers.add(phone)
                break

        cur.execute(
            """INSERT INTO Customers
               (phone_number, name, age, native_language, balance, nominee_status, voiceprint_enrolled)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (phone, name, age, lang, balance, nominee, voiceprint_enrolled),
        )
    conn.commit()


def seed_agents(conn):
    """8 agents covering original specialties (Fraud, Loans, General) plus
    the 3 new specialties from the mentor's brief (Deceased Claims, YONO Tech,
    Video Advisory). Existing agents keep their original skills and gain a
    second specialty where the brief specifically suggested it (Rohan ->
    YONO Tech, Priya -> Deceased Claims), rather than losing Fraud/Loans
    coverage. 3 new agents added for baseline coverage of the new specialties.
    """
    agents = [
        # name,      languages,               specialties,                  workload, csat
        ("Rohan",    "Marathi,Hindi,English", "Fraud,YONO Tech",            0.35, 4.6),
        ("Priya",    "Tamil,English",         "Loans,Deceased Claims",      0.20, 4.8),
        ("Sneha",    "Bengali,Hindi,English", "General",                    0.55, 4.2),
        ("Karthik",  "Telugu,Kannada,English","Fraud",                      0.60, 4.4),
        ("Divya",    "Gujarati,Hindi,English","Loans,Video Advisory",       0.10, 4.9),
        ("Ananya",   "Hindi,English,Punjabi", "Deceased Claims,General",    0.25, 4.7),
        ("Vikram",   "English,Hindi,Malayalam","YONO Tech,Fraud",           0.40, 4.5),
        ("Meera",    "English,Hindi,Odia",    "Video Advisory,Loans",       0.30, 4.8),
    ]
    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO Agents (name, languages, specialties, workload_score, csat_score)
           VALUES (?, ?, ?, ?, ?)""",
        agents,
    )
    conn.commit()


def main():
    conn = get_connection()
    create_schema(conn)
    seed_customers(conn, n=20)
    seed_agents(conn)

    cur = conn.cursor()
    n_customers = cur.execute("SELECT COUNT(*) FROM Customers").fetchone()[0]
    n_agents = cur.execute("SELECT COUNT(*) FROM Agents").fetchone()[0]
    print(f"Database initialized at: {DB_PATH}")
    print(f"  Customers seeded: {n_customers}")
    print(f"  Agents seeded:    {n_agents}")

    print("\nSample agents:")
    for row in cur.execute("SELECT agent_id, name, languages, specialties, workload_score FROM Agents"):
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    main()