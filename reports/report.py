"""
Reporting module for management
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from db.database import get_connection


def _fmt(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} PB"


def _bar(value: int, max_val: int, width: int = 20) -> str:
    if max_val == 0:
        return "░" * width
    filled = int((value / max_val) * width)
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────
#  Management Reports
# ─────────────────────────────────────────────
def report_all_users(days: int = 30):
    """Summary of all users' usage over the last N days"""
    conn = get_connection()

    rows = conn.execute("""
        SELECT u.username, u.department, u.ip_address,
               COALESCE(SUM(d.total_sent),     0) AS sent,
               COALESCE(SUM(d.total_received), 0) AS recv,
               COALESCE(SUM(d.total_bytes),    0) AS total,
               COUNT(DISTINCT d.date)              AS active_days
        FROM users u
        LEFT JOIN daily_summary d
               ON d.user_id = u.id
              AND d.date >= date('now', ? )
        GROUP BY u.id
        ORDER BY total DESC
    """, (f"-{days} days",)).fetchall()

    conn.close()

    if not rows:
        print("No data found.")
        return

    max_total = max(r["total"] for r in rows) or 1
    sep = "─" * 80

    print(f"\n{'═'*80}")
    print(f"  📊  Traffic Usage Report — Last {days} Days")
    print(f"{'═'*80}")
    print(f"  {'User':<18} {'Department':<12} {'Sent':>10} {'Received':>10} {'Total':>10}  Chart")
    print(sep)

    for r in rows:
        bar = _bar(r["total"], max_total)
        dept = r["department"] or "-"

        print(
            f"  {r['username']:<18} {dept:<12} "
            f"{_fmt(r['sent']):>10} {_fmt(r['recv']):>10} "
            f"{_fmt(r['total']):>10}  {bar}"
        )

    print(sep)

    total_all = sum(r["total"] for r in rows)

    print(f"  Total Network Usage: {_fmt(total_all)}")
    print(f"{'═'*80}\n")


def report_user(username: str, days: int = 30):
    """Detailed report for a specific user"""
    conn = get_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    ).fetchone()

    if not user:
        print(f"User '{username}' not found.")
        conn.close()
        return

    daily = conn.execute("""
        SELECT date, total_sent, total_received, total_bytes, session_count
        FROM daily_summary
        WHERE user_id=? AND date >= date('now', ?)
        ORDER BY date DESC
    """, (user["id"], f"-{days} days")).fetchall()

    sessions = conn.execute("""
        SELECT start_time, end_time, ip_address, ssid,
               ROUND((julianday(COALESCE(end_time, datetime('now'))) -
                      julianday(start_time)) * 24 * 60, 1) AS duration_min
        FROM sessions
        WHERE user_id=? AND start_time >= datetime('now', ?)
        ORDER BY start_time DESC
        LIMIT 10
    """, (user["id"], f"-{days} days")).fetchall()

    conn.close()

    print(f"\n{'═'*70}")
    print(f"  👤  User Report: {username}")
    print(f"{'═'*70}")
    print(
        f"  Department: {user['department'] or '-'}   |   "
        f"IP: {user['ip_address'] or '-'}   |   "
        f"MAC: {user['mac_address'] or '-'}"
    )
    print()

    if daily:
        print(f"  {'Date':<12} {'Sent':>10} {'Received':>10} {'Total':>10}  {'Session':>7}")
        print("  " + "─" * 55)

        for d in daily:
            print(
                f"  {d['date']:<12} {_fmt(d['total_sent']):>10} "
                f"{_fmt(d['total_received']):>10} {_fmt(d['total_bytes']):>10}  "
                f"{d['session_count']:>7}"
            )

        total = sum(d["total_bytes"] for d in daily)

        print("  " + "─" * 55)
        print(f"  {'Total':<12} {_fmt(total):>32}")

    else:
        print("  No data recorded for this period.")

    if sessions:
        print(f"\n  ─── Last 10 Sessions ───")

        for s in sessions:
            et = s["end_time"] or "Active"

            print(
                f"  {s['start_time'][:16]}  →  "
                f"{et[:16] if et != 'Active' else et}  "
                f"|  {s['duration_min']} minutes  |  {s['ssid'] or '-'}"
            )

    print(f"{'═'*70}\n")


def report_top(n: int = 10, days: int = 30):
    """Top users by traffic consumption"""
    conn = get_connection()

    rows = conn.execute("""
        SELECT u.username, u.department,
               COALESCE(SUM(d.total_bytes), 0) AS total
        FROM users u
        LEFT JOIN daily_summary d ON d.user_id=u.id
              AND d.date >= date('now', ?)
        GROUP BY u.id
        ORDER BY total DESC
        LIMIT ?
    """, (f"-{days} days", n)).fetchall()

    conn.close()

    print(f"\n  🏆  Top {n} Users by Usage — Last {days} Days\n")

    for i, r in enumerate(rows, 1):
        print(
            f"  {i:>2}. {r['username']:<20} "
            f"{_fmt(r['total']):>10}   ({r['department'] or '-'})"
        )

    print()


def report_daily_trend(days: int = 14):
    """Daily network traffic consumption trend"""
    conn = get_connection()

    rows = conn.execute("""
        SELECT date, SUM(total_bytes) AS total
        FROM daily_summary
        WHERE date >= date('now', ?)
        GROUP BY date
        ORDER BY date
    """, (f"-{days} days",)).fetchall()

    conn.close()

    if not rows:
        print("No data available to display the trend.")
        return

    max_val = max(r["total"] for r in rows) or 1

    print(f"\n  📈  Network Usage Trend — Last {days} Days\n")

    for r in rows:
        bar = _bar(r["total"], max_val, 30)
        print(f"  {r['date']}  {bar}  {_fmt(r['total'])}")

    print()


def report_today():
    """Today's usage report — all users"""
    conn = get_connection()

    today = __import__('datetime').date.today().isoformat()

    rows = conn.execute("""
        SELECT u.username, u.department,
               COALESCE(d.total_sent,     0) AS sent,
               COALESCE(d.total_received, 0) AS recv,
               COALESCE(d.total_bytes,    0) AS total,
               COALESCE(d.session_count,  0) AS sessions
        FROM users u
        LEFT JOIN daily_summary d ON d.user_id=u.id AND d.date=?
        WHERE d.total_bytes > 0
        ORDER BY total DESC
    """, (today,)).fetchall()

    conn.close()

    print(f"\n{'═'*70}")
    print(f"  📅  Today's Usage Report — {today}")
    print(f"{'═'*70}")

    if not rows:
        print("  No data has been recorded for today yet.")
        print(f"{'═'*70}\n")
        return

    max_total = max(r["total"] for r in rows) or 1

    print(f"  {'User':<18} {'Department':<12} {'Sent':>10} {'Received':>10} {'Total':>10}")
    print("  " + "─" * 60)

    for r in rows:
        bar = _bar(r["total"], max_total, 15)

        print(
            f"  {r['username']:<18} {r['department'] or '-':<12} "
            f"{_fmt(r['sent']):>10} {_fmt(r['recv']):>10} "
            f"{_fmt(r['total']):>10}  {bar}"
        )

    total_all = sum(r["total"] for r in rows)

    print("  " + "─" * 60)
    print(f"  Total Usage Today: {_fmt(total_all)}")
    print(f"{'═'*70}\n")