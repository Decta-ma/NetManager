"""
ماژول مدیریت پایگاه داده - SQLite
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "traffic.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """ساخت جداول اولیه در صورت عدم وجود"""
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            mac_address TEXT,
            ip_address  TEXT,
            department  TEXT,
            is_admin    INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            start_time  TEXT    NOT NULL,
            end_time    TEXT,
            ip_address  TEXT,
            mac_address TEXT,
            ssid        TEXT,
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS traffic_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            user_id     INTEGER NOT NULL REFERENCES users(id),
            timestamp   TEXT    NOT NULL DEFAULT (datetime('now')),
            bytes_sent      INTEGER DEFAULT 0,
            bytes_received  INTEGER DEFAULT 0,
            interval_sec    INTEGER DEFAULT 60
        );

        CREATE TABLE IF NOT EXISTS daily_summary (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            date        TEXT    NOT NULL,
            total_sent      INTEGER DEFAULT 0,
            total_received  INTEGER DEFAULT 0,
            total_bytes     INTEGER DEFAULT 0,
            session_count   INTEGER DEFAULT 0,
            UNIQUE(user_id, date)
        );
    """)

    conn.commit()
    conn.close()
    print(f"[DB] دیتابیس آماده شد: {DB_PATH}")


def ensure_user(username: str, mac: str = None, ip: str = None,
                department: str = None, is_admin: bool = False) -> int:
    """ثبت یا بازیابی کاربر و بازگشت user_id"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    if row:
        user_id = row["id"]
        cur.execute(
            "UPDATE users SET mac_address=?, ip_address=?, department=? WHERE id=?",
            (mac, ip, department, user_id)
        )
    else:
        cur.execute(
            """INSERT INTO users (username, mac_address, ip_address, department, is_admin)
               VALUES (?, ?, ?, ?, ?)""",
            (username, mac, ip, department, int(is_admin))
        )
        user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def start_session(user_id: int, ip: str, mac: str, ssid: str) -> int:
    """شروع یک session جدید"""
    conn = get_connection()
    cur = conn.cursor()
    # بستن session‌های قبلی که باز مانده
    cur.execute(
        "UPDATE sessions SET is_active=0, end_time=? WHERE user_id=? AND is_active=1",
        (datetime.now().isoformat(), user_id)
    )
    cur.execute(
        """INSERT INTO sessions (user_id, start_time, ip_address, mac_address, ssid)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, datetime.now().isoformat(), ip, mac, ssid)
    )
    session_id = cur.lastrowid
    conn.commit()
    conn.close()
    return session_id


def end_session(session_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET is_active=0, end_time=? WHERE id=?",
        (datetime.now().isoformat(), session_id)
    )
    conn.commit()
    conn.close()


def log_traffic(session_id: int, user_id: int, sent: int, received: int, interval: int = 60):
    """ذخیره یک رکورد ترافیک"""
    conn = get_connection()
    conn.execute(
        """INSERT INTO traffic_logs (session_id, user_id, bytes_sent, bytes_received, interval_sec)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, user_id, sent, received, interval)
    )
    # آپدیت خلاصه روزانه
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        """INSERT INTO daily_summary (user_id, date, total_sent, total_received, total_bytes, session_count)
           VALUES (?, ?, ?, ?, ?, 1)
           ON CONFLICT(user_id, date) DO UPDATE SET
               total_sent      = total_sent + excluded.total_sent,
               total_received  = total_received + excluded.total_received,
               total_bytes     = total_bytes + excluded.total_sent + excluded.total_received
        """,
        (user_id, today, sent, received, sent + received)
    )
    conn.commit()
    conn.close()
