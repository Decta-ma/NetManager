"""
عامل پایش شبکه — بدون خروجی ترمینال، فقط لاگ فایل + دیتابیس
"""

import time
import socket
import uuid
import getpass
import threading
import psutil
from datetime import datetime
from pathlib import Path
from sys import platform

import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from db.database import init_db, ensure_user, start_session, end_session, log_traffic

LOG_PATH = Path(__file__).parents[1] / "monitor.log"


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def get_mac_address() -> str:
    mac = uuid.getnode()
    return ':'.join(f'{(mac >> (8*i)) & 0xff:02x}' for i in reversed(range(6)))


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_network_interface() -> str:
    try:
        local_ip = get_local_ip()
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.address == local_ip:
                    return iface
    except Exception:
        pass
    return None


def get_ssid() -> str:
    import subprocess
    try:
        if platform == "win32":
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, encoding="utf-8", errors="ignore"
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("SSID") and "BSSID" not in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        return parts[1].strip()
        elif platform.startswith("linux"):
            # اول iwgetid امتحان کن، بعد nmcli
            result = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True)
            ssid = result.stdout.strip()
            if ssid:
                return ssid
            # fallback به nmcli (Ubuntu و distro های مدرن)
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if line.startswith("yes:"):
                    return line.split(":", 1)[1].strip()
            return "UNKNOWN"
        elif platform == "darwin":
            result = subprocess.run(
                ["/System/Library/PrivateFrameworks/Apple80211.framework"
                 "/Versions/Current/Resources/airport", "-I"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if " SSID:" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "UNKNOWN"


class NetworkMonitor:
    def __init__(self, username: str = None, interval: int = 60,
                 department: str = None, allowed_ssid: str = None):
        init_db()
        self.username     = username or getpass.getuser()
        self.interval     = interval
        self.department   = department
        self.allowed_ssid = allowed_ssid
        self.ip           = get_local_ip()
        self.mac          = get_mac_address()
        self.ssid         = get_ssid()
        self.iface        = get_network_interface()

        self.user_id    = ensure_user(self.username, self.mac, self.ip, department)
        self.session_id = None
        self._running   = False
        self._thread    = None
        self._prev_sent = 0
        self._prev_recv = 0

    def _on_correct_network(self) -> bool:
        if self.allowed_ssid is None:
            return True
        return get_ssid() == self.allowed_ssid

    def _snapshot(self):
        try:
            per_iface = psutil.net_io_counters(pernic=True)
            iface = self.iface or "Wi-Fi"
            if iface in per_iface:
                c = per_iface[iface]
                return c.bytes_sent, c.bytes_recv
        except Exception:
            pass
        c = psutil.net_io_counters()
        return c.bytes_sent, c.bytes_recv

    @staticmethod
    def _fmt(b: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    def _loop(self):
        self._prev_sent, self._prev_recv = self._snapshot()
        _log(f"START | user={self.username} | ssid={self.allowed_ssid} | ip={self.ip} | iface={self.iface}")

        while self._running:
            time.sleep(self.interval)
            if not self._running:
                break

            if not self._on_correct_network():
                self._prev_sent, self._prev_recv = self._snapshot()
                continue

            curr_sent, curr_recv = self._snapshot()
            delta_sent = max(0, curr_sent - self._prev_sent)
            delta_recv = max(0, curr_recv - self._prev_recv)
            self._prev_sent, self._prev_recv = curr_sent, curr_recv

            log_traffic(self.session_id, self.user_id, delta_sent, delta_recv, self.interval)

    def start(self):
        if self._running:
            return
        self.ip  = get_local_ip()
        self.ssid = get_ssid()
        self.session_id = start_session(self.user_id, self.ip, self.mac, self.ssid)
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=False)
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        if self.session_id:
            end_session(self.session_id)
        _log(f"STOP | user={self.username} | session={self.session_id}")

    def is_running(self) -> bool:
        return self._running
