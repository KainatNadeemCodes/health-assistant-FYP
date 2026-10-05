import sqlite3
import os

# Make sure we are looking at the right database file
db_path = "health_assistant.db"

if not os.path.exists(db_path):
    print("ERROR: health_assistant.db not found in this folder.")
    print("Make sure you are running this from inside the Backend folder.")
else:
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    print("=" * 50)
    print("DATABASE SUMMARY")
    print("=" * 50)

    cur.execute("SELECT COUNT(*) FROM users")
    print(f"Total Users       : {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM consultations")
    print(f"Total Consultations: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM feedback")
    print(f"Total Feedback     : {cur.fetchone()[0]}")

    print()
    print("=" * 50)
    print("REGISTERED USERS")
    print("=" * 50)
    cur.execute("SELECT id, username, email, role, created_at FROM users")
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  ID: {row[0]} | Name: {row[1]} | Email: {row[2]} | Role: {row[3]} | Joined: {row[4]}")
    else:
        print("  No users registered yet.")

    print()
    print("=" * 50)
    print("RECENT CONSULTATIONS (last 5)")
    print("=" * 50)
    cur.execute("""
        SELECT id, user_id, prediction, triage_level, specialist, timestamp
        FROM consultations
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    rows = cur.fetchall()
    if rows:
        for row in rows:
            user = f"User {row[1]}" if row[1] else "Guest"
            print(f"  ID: {row[0]} | {user} | {row[2]} | {row[3]} | {row[4]} | {row[5]}")
    else:
        print("  No consultations yet.")

    print()
    print("=" * 50)
    print("FEEDBACK")
    print("=" * 50)
    cur.execute("SELECT id, consult_id, rating, comments, created_at FROM feedback")
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  ID: {row[0]} | Consult: {row[1]} | Rating: {row[2]}/5 | Comment: {row[3]} | Date: {row[4]}")
    else:
        print("  No feedback submitted yet.")

    print()
    print("=" * 50)
    conn.close()