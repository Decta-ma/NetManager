#!/usr/bin/env python3
"""
NetMonitor — سامانه پایش مصرف ترافیک شبکه شرکت

اجرا در پس‌زمینه (لینوکس):
  nohup python main.py monitor -u ali -d IT &

گزارش مدیریتی:
  python main.py report all
  python main.py report user <نام>
  python main.py report today
  python main.py report top
  python main.py report trend
"""

import argparse
import os
import sys
import signal
import time

from agents.monitor import NetworkMonitor
from reports.report import report_all_users, report_user, report_top, report_daily_trend, report_today


def cmd_monitor(args):
    monitor = NetworkMonitor(
        username=args.username,
        interval=args.interval,
        department=args.department,
        allowed_ssid=args.ssid,
    )
    monitor.start()

    def _exit(sig, frame):
        monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _exit)
    signal.signal(signal.SIGTERM, _exit)

    # بلاک کردن پروسه — بدون خروجی ترمینال
    while monitor.is_running():
        time.sleep(5)


def cmd_report(args):
    sub  = args.sub
    days = getattr(args, "days", 30)

    if sub == "all":
        report_all_users(days)
    elif sub == "today":
        report_today()
    elif sub == "user":
        if not args.username:
            print("خطا: نام کاربر را مشخص کنید.")
            sys.exit(1)
        report_user(args.username, days)
    elif sub == "top":
        report_top(getattr(args, "n", 10), days)
    elif sub == "trend":
        report_daily_trend(days)
    else:
        print(f"زیرفرمان نامعتبر: {sub}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="netmonitor")
    sub = parser.add_subparsers(dest="command", required=True)

    # ─── monitor ───
    mon = sub.add_parser("monitor", help="شروع پایش ترافیک در پس‌زمینه")
    mon.add_argument("-u", "--username",   default=None)
    mon.add_argument("-d", "--department", default=None)
    mon.add_argument("-i", "--interval",   type=int, default=60)
    mon.add_argument("-s", "--ssid",       default="mana")

    # ─── report ───
    rep = sub.add_parser("report", help="گزارش‌گیری مدیریتی")
    rep.add_argument("sub", choices=["all", "today", "user", "top", "trend"])
    rep.add_argument("username", nargs="?", default=None)
    rep.add_argument("--days", type=int, default=30)
    rep.add_argument("--n",    type=int, default=10)

    args = parser.parse_args()

    if args.command == "monitor":
        cmd_monitor(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
