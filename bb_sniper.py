"""
BigBasket Deal Sniper Launcher & Daily Automation
=================================================
Automatically launches Microsoft Edge pinned on top of open desktop apps
4 times daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM) while the PC is on.

Includes:
- Pin-On-Top Window Management (keeps Edge pinned over PotPlayer/other apps, preserving original window size)
- Multi-Trigger Windows Task Scheduler registration with battery support (4 daily scans)
- HTTPS Atomic Internet Time drift detection & sync (fixes VPN UDP clock drift)

Usage:
  python bb_sniper.py --now             # Test launch in Edge pinned on top immediately
  python bb_sniper.py --install-task    # Register 4x daily schedule in Windows Task Scheduler
  python bb_sniper.py --status-task     # Check scheduled task status and next run times
  python bb_sniper.py --remove-task     # Remove scheduled tasks
  python bb_sniper.py --check-clock     # Check PC clock drift against atomic internet time
  python bb_sniper.py --sync-clock      # Sync Windows clock with atomic internet time (HTTPS)
  python bb_sniper.py --watch           # Run terminal daemon with real-time countdown to next slot
"""

import sys
import os
import time
import argparse
import subprocess
import threading
import urllib.request
import email.utils
from datetime import datetime, timedelta, timezone

# Windows Win32 API imports
try:
    import ctypes
    import ctypes.wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Safely handle Windows console encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

TASK_NAME = "BigBasketDealSniper"
LEGACY_TASK_NAME = "BigBasketMidnightSniper"
TARGET_URL = "https://www.bigbasket.com/?bb_auto=all"

# 4 daily scan slots: (hour, minute, label)
DAILY_SCHEDULE = [
    (0, 0, "12:00 AM (Midnight Deals)"),
    (16, 0, "4:00 PM (Afternoon Restock)"),
    (19, 0, "7:00 PM (Evening Flash Sales)"),
    (23, 30, "11:30 PM (Pre-Midnight Clearance)")
]


# ==============================================================================
# 1. Window Management (Pin-On-Top over other apps, preserving original size)
# ==============================================================================

def pin_edge_on_top(timeout_seconds: float = 8.0):
    """
    Locates the Edge window, brings it to foreground, and pins it ON TOP of all other open apps (HWND_TOPMOST)
    WITHOUT altering its position or size.
    """
    if not (HAS_WIN32 and os.name == "nt"):
        return False

    user32 = ctypes.windll.user32

    SW_RESTORE = 9
    HWND_TOPMOST = -1
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040
    FLAGS = SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW

    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        time.sleep(0.4)
        found_hwnds = []

        def enum_callback(hwnd, lParam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    cls_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cls_buff, 256)
                    cls_name = cls_buff.value
                    if "Chrome_WidgetWin_1" in cls_name and ("BigBasket" in title or "Edge" in title or "Personal" in title or "Work" in title):
                        found_hwnds.append((hwnd, title))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        if found_hwnds:
            target_hwnd, title = found_hwnds[0]
            # 1. Restore if minimized
            user32.ShowWindow(target_hwnd, SW_RESTORE)
            # 2. Pin ON TOP of all other apps (HWND_TOPMOST) keeping exact size and position
            user32.SetWindowPos(target_hwnd, HWND_TOPMOST, 0, 0, 0, 0, FLAGS)
            user32.SetForegroundWindow(target_hwnd)
            print(f"[OK] Pinned '{title[:35]}' on top of other apps (original size preserved).")
            return True

    return False


# ==============================================================================
# 2. Atomic Internet Time (HTTPS Drift Detection & Sync)
# ==============================================================================

def check_internet_time():
    """
    Fetch true atomic internet time via HTTPS (port 443) and calculate PC clock drift.
    Port 443 is never blocked by VPNs, unlike standard NTP (UDP 123).
    """
    endpoints = [
        "https://www.google.com",
        "https://www.cloudflare.com",
        "https://www.microsoft.com"
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0")
            t_before = time.time()
            with urllib.request.urlopen(req, timeout=4) as resp:
                t_after = time.time()
                date_hdr = resp.headers.get("Date")
                if not date_hdr:
                    continue
                net_dt = email.utils.parsedate_to_datetime(date_hdr)
                rtt = t_after - t_before
                # Compensate for network round-trip time
                net_timestamp = net_dt.timestamp() + (rtt / 2.0)
                local_timestamp = time.time()
                drift_seconds = local_timestamp - net_timestamp
                return {
                    "url": url,
                    "net_dt": datetime.fromtimestamp(net_timestamp, tz=timezone.utc),
                    "local_dt": datetime.fromtimestamp(local_timestamp, tz=timezone.utc),
                    "drift_seconds": drift_seconds,
                    "rtt_ms": rtt * 1000.0
                }
        except Exception:
            continue
    return None


def show_clock_status():
    """Display the clock status and drift compared to atomic internet time."""
    print("=" * 65)
    print("  Atomic Internet Time Check (HTTPS Port 443 - VPN Proof)")
    print("=" * 65)
    res = check_internet_time()
    if not res:
        print("[!] Could not connect to internet time servers.")
        return

    net_dt_local = res["net_dt"].astimezone()
    pc_dt_local = res["local_dt"].astimezone()
    drift = res["drift_seconds"]

    print(f"[*] Time Server Checked : {res['url']} (Latency: {res['rtt_ms']:.1f} ms)")
    print(f"[*] True Internet Time  : {net_dt_local.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    print(f"[*] Your PC Clock Time  : {pc_dt_local.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")

    if abs(drift) < 1.0:
        print(f"\n[OK] PERFECT: Your PC clock is accurate to within {drift:+.2f} seconds.")
    else:
        status = "SLOW (behind)" if drift < 0 else "FAST (ahead)"
        print(f"\n[!] NOTICE: Your PC clock is {abs(drift):.1f} seconds {status} real-world time.")
        print("    (This frequently happens when VPNs block standard UDP 123 NTP sync).")
        print("\n    To fix your Windows clock, run:")
        print("      python bb_sniper.py --sync-clock")
        print("    Or run Watcher Mode ('python bb_sniper.py --watch') which automatically")
        print("    compensates for this drift without modifying your Windows settings.")


def sync_system_clock():
    """Synchronize the Windows system clock to atomic internet time."""
    if not (HAS_WIN32 and os.name == "nt"):
        print("[!] Clock synchronization requires Windows.")
        return False

    print("[*] Contacting atomic internet time servers...")
    res = check_internet_time()
    if not res:
        print("[!] Failed to obtain internet time over HTTPS.")
        return False

    drift = res["drift_seconds"]
    net_dt = res["net_dt"]

    if abs(drift) < 1.0:
        print(f"[OK] Clock is already accurate (drift: {drift:+.2f}s). No adjustment needed.")
        return True

    class SYSTEMTIME(ctypes.Structure):
        _fields_ = [
            ("wYear", ctypes.c_ushort),
            ("wMonth", ctypes.c_ushort),
            ("wDayOfWeek", ctypes.c_ushort),
            ("wDay", ctypes.c_ushort),
            ("wHour", ctypes.c_ushort),
            ("wMinute", ctypes.c_ushort),
            ("wSecond", ctypes.c_ushort),
            ("wMilliseconds", ctypes.c_ushort),
        ]

    st = SYSTEMTIME()
    st.wYear = net_dt.year
    st.wMonth = net_dt.month
    st.wDayOfWeek = 0
    st.wDay = net_dt.day
    st.wHour = net_dt.hour
    st.wMinute = net_dt.minute
    st.wSecond = net_dt.second
    st.wMilliseconds = int(net_dt.microsecond / 1000)

    success = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
    if success:
        print(f"[OK] SUCCESS: Windows system clock adjusted by {drift:+.2f} seconds to true atomic time!")
        return True
    else:
        err = ctypes.GetLastError()
        print(f"[!] Windows prevented modifying the system time (Error code: {err}).")
        print("    Adjusting the hardware system clock requires Administrator permissions.")
        print("\n    To sync your clock with Administrator rights, open PowerShell and run:")
        print("      Start-Process python -ArgumentList 'bb_sniper.py --sync-clock' -Verb RunAs")
        print("\n    Alternatively, in Watcher Mode ('python bb_sniper.py --watch'),")
        print(f"    Deal Sniper compensates for your {abs(drift):.1f}s drift automatically without admin rights!")
        return False


# ==============================================================================
# 3. Microsoft Edge Launching & Notifications
# ==============================================================================

def get_edge_path():
    """Find the Microsoft Edge executable path on Windows."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def show_notification(title: str, message: str):
    """Trigger a native Windows 10/11 Toast Notification via PowerShell."""
    escaped_title = title.replace('"', '`"').replace("'", "''")
    escaped_msg = message.replace('"', '`"').replace("'", "''")

    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode('{escaped_title}')) > $null
    $textNodes.Item(1).AppendChild($template.CreateTextNode('{escaped_msg}')) > $null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("BigBasket Deal Sniper").Show($toast)
    """

    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            creationflags=flags
        )
    except Exception as e:
        print(f"[!] Notification error: {e}")


def launch_edge(url: str = TARGET_URL, pin_top: bool = True):
    """Launch Microsoft Edge and pin on top of all other apps without resizing."""
    edge_exe = get_edge_path()

    print(f"[*] Launching BigBasket Deal Sniper in Microsoft Edge...")
    print(f"[*] Window State : Pinned On Top (Original window size preserved)")
    print(f"[*] Schedule     : 4x Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)")
    print(f"[*] URL          : {url}")

    show_notification(
        "BigBasket Deal Sniper Activated",
        "Edge launched and pinned on top to scan BigBasket deals!"
    )

    if edge_exe:
        try:
            # Launch in new window without altering size or position
            cmd = [edge_exe, "--new-window", url]
            subprocess.Popen(cmd)
            print(f"[OK] Launched Edge executable: {edge_exe}")

            # Start background thread to pin the window on top of all open apps (e.g. PotPlayer)
            if pin_top and HAS_WIN32:
                threading.Thread(target=pin_edge_on_top, args=(8.0,), daemon=True).start()
            return True
        except Exception as e:
            print(f"[!] Failed to launch via msedge.exe: {e}")

    # Fallback 1: Windows 'microsoft-edge:' URI scheme
    try:
        os.system(f'start microsoft-edge:"{url}"')
        print("[OK] Launched via microsoft-edge URI protocol.")
        if pin_top and HAS_WIN32:
            threading.Thread(target=pin_edge_on_top, args=(8.0,), daemon=True).start()
        return True
    except Exception as e:
        print(f"[!] Protocol launch failed: {e}")

    # Fallback 2: Python webbrowser
    try:
        import webbrowser
        webbrowser.open(url)
        print("[OK] Launched via default browser handler.")
        return True
    except Exception as e:
        print(f"[!] Webbrowser launch failed: {e}")

    return False


# ==============================================================================
# 4. Windows Task Scheduler (Daily Triggers & Battery Support)
# ==============================================================================

def install_task():
    """Register the 4-times daily scan schedule in Windows Task Scheduler."""
    script_path = os.path.abspath(__file__)

    # Use pythonw.exe so execution runs silently with NO console popup window
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable

    # Clean up legacy tasks if present
    for tname in [TASK_NAME, LEGACY_TASK_NAME]:
        subprocess.run(["schtasks", "/delete", "/tn", tname, "/f"], capture_output=True, check=False)

    print(f"[*] Registering scheduled task: {TASK_NAME}")
    print("[*] Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM) while PC is on")
    print(f"[*] Executable: {pythonw_path}")

    # Use PowerShell Register-ScheduledTask to support multiple daily triggers & battery execution
    ps_script = f"""
    $ErrorActionPreference = 'Stop'
    $action = New-ScheduledTaskAction -Execute '{pythonw_path}' -Argument '"{script_path}" --run-now'
    $triggers = @(
        $(New-ScheduledTaskTrigger -Daily -At "00:00"),
        $(New-ScheduledTaskTrigger -Daily -At "16:00"),
        $(New-ScheduledTaskTrigger -Daily -At "19:00"),
        $(New-ScheduledTaskTrigger -Daily -At "23:30")
    )
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $triggers -Settings $settings -Force
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            print(f"\n[OK] SUCCESS: Scheduled task '{TASK_NAME}' registered successfully!")
            print("    Edge will automatically open pinned on top at:")
            print("      • 12:00 AM  (Midnight Deals)")
            print("      •  4:00 PM  (Afternoon Restock)")
            print("      •  7:00 PM  (Evening Flash Sales)")
            print("      • 11:30 PM  (Pre-Midnight Clearance)")
            print("\n    - Test immediately with : python bb_sniper.py --now")
            print("    - Check status with     : python bb_sniper.py --status-task")
            print("    - Check clock sync with : python bb_sniper.py --check-clock")
            print("    - Remove anytime with   : python bb_sniper.py --remove-task\n")
        else:
            print(f"[X] Error creating task:\n{res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        print(f"[!] Execution failed: {e}")


def remove_task():
    """Remove scheduled tasks from Windows Task Scheduler."""
    removed_any = False
    for tname in [TASK_NAME, LEGACY_TASK_NAME]:
        cmd = ["schtasks", "/delete", "/tn", tname, "/f"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"[OK] Scheduled task '{tname}' removed.")
            removed_any = True
    if not removed_any:
        print("[!] No active BigBasket scheduled task was found to remove.")


def status_task():
    """Check status and next run times of the scheduled task."""
    cmd = ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST", "/v"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"[OK] Task '{TASK_NAME}' is currently ACTIVE.\n")
            print("  Configured Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)\n")
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if any(line_str.startswith(k) for k in [
                    "TaskName:", "Status:", "Next Run Time:", "Last Run Time:", "Last Result:", "Schedule Type:", "Start Time:", "Repeat:"
                ]):
                    print(f"  {line_str}")
        else:
            print(f"[!] Task '{TASK_NAME}' is NOT registered.")
            print("    Run 'python bb_sniper.py --install-task' to enable automated deal sniping.")
    except Exception as e:
        print(f"[!] Error querying task: {e}")


# ==============================================================================
# 5. Live Terminal Watcher Mode (4x Daily Atomic Internet Time Compensated)
# ==============================================================================

def get_next_run(drift_seconds: float = 0.0):
    """Calculate the next upcoming scan slot from the 4 daily schedule targets, adjusting for clock drift."""
    effective_now = datetime.now() - timedelta(seconds=drift_seconds)

    candidates = []
    for day_offset in (0, 1):
        target_day = effective_now.date() + timedelta(days=day_offset)
        for hour, minute, label in DAILY_SCHEDULE:
            candidate_dt = datetime(
                target_day.year, target_day.month, target_day.day,
                hour, minute, 15
            )
            if candidate_dt > effective_now:
                candidates.append((candidate_dt, label))

    candidates.sort(key=lambda x: x[0])
    next_dt, label = candidates[0]
    desc = f"{label} at {next_dt.strftime('%I:%M %p')}"
    return next_dt, desc, drift_seconds


def watch_mode():
    """Run an interactive console countdown timer for daily scans with atomic drift compensation."""
    print("=" * 65)
    print("  BigBasket Deal Sniper - Daily Live Terminal Watcher")
    print("=" * 65)
    print("[*] Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)")

    print("\n[*] Checking atomic internet time to compensate for PC clock drift...")
    drift_seconds = 0.0
    time_info = check_internet_time()
    if time_info:
        drift_seconds = time_info["drift_seconds"]
        status = "slow" if drift_seconds < 0 else "fast"
        print(f"[OK] Clock drift calibrated: PC clock is {abs(drift_seconds):.1f}s {status}.")
        print("    Auto-compensation active: countdown is locked to atomic real-world time.")
    else:
        print("[!] Could not connect to internet time server. Using local PC clock.")

    print("\n[*] Press Ctrl+C at any time to exit.\n")

    last_drift_check = time.time()

    while True:
        # Re-check internet drift every 60 minutes
        if time.time() - last_drift_check > 3600:
            time_info = check_internet_time()
            if time_info:
                drift_seconds = time_info["drift_seconds"]
            last_drift_check = time.time()

        next_dt, desc, drift = get_next_run(drift_seconds)
        effective_now = datetime.now() - timedelta(seconds=drift_seconds)
        diff = next_dt - effective_now
        total_seconds = int(diff.total_seconds())

        if total_seconds <= 1:
            print(f"\n[!] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - TRIGGER REACHED ({desc})!")
            launch_edge()
            time.sleep(20)  # Avoid double-triggering within the same window
            continue

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        sys.stdout.write(
            f"\r[*] Next Run: {next_dt.strftime('%I:%M:%S %p')} ({desc}) | "
            f"Countdown: {hours:02d}h {minutes:02d}m {seconds:02d}s "
        )
        sys.stdout.flush()
        time.sleep(1)


# ==============================================================================
# 6. Main CLI Interface
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BigBasket Deal Sniper Launcher & Daily Scheduler (Microsoft Edge Pinned-On-Top)"
    )
    parser.add_argument("--now", "--run-now", action="store_true", help="Launch BigBasket and pin Edge on top immediately")
    parser.add_argument("--install-task", action="store_true", help="Register Windows Task Scheduler job (4 times daily: 12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)")
    parser.add_argument("--remove-task", action="store_true", help="Remove Windows Task Scheduler jobs")
    parser.add_argument("--status-task", action="store_true", help="View scheduled task status and next run times")
    parser.add_argument("--check-clock", action="store_true", help="Check PC clock drift against atomic internet time (HTTPS)")
    parser.add_argument("--sync-clock", action="store_true", help="Synchronize Windows system clock to atomic internet time")
    parser.add_argument("--watch", action="store_true", help="Run in terminal watch mode with live countdown and drift compensation")

    args = parser.parse_args()

    if args.now:
        launch_edge()
        time.sleep(2)
    elif args.install_task:
        install_task()
    elif args.remove_task:
        remove_task()
    elif args.status_task:
        status_task()
    elif args.check_clock:
        show_clock_status()
    elif args.sync_clock:
        sync_system_clock()
    elif args.watch:
        watch_mode()
    else:
        print("=" * 60)
        print("  BigBasket Deal Sniper Launcher (4x Daily Automation)")
        print("=" * 60)
        print("Available options:")
        print("  1) python bb_sniper.py --now           -> Test launch in Edge pinned on top immediately")
        print("  2) python bb_sniper.py --install-task  -> Register 4x daily schedule in Windows Task Scheduler")
        print("  3) python bb_sniper.py --status-task   -> Check task status & upcoming trigger times")
        print("  4) python bb_sniper.py --check-clock   -> Check PC clock drift vs atomic internet time")
        print("  5) python bb_sniper.py --sync-clock    -> Sync Windows system clock via HTTPS")
        print("  6) python bb_sniper.py --watch         -> Live terminal countdown with auto drift adjustment")
        print("  7) python bb_sniper.py --remove-task   -> Remove scheduled task")
        print("-" * 60)
        parser.print_help()


if __name__ == "__main__":
    main()
