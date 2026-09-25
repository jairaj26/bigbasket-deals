"""
BigBasket Deal Sniper Launcher & Multi-Schedule Automation
==========================================================
Automatically launches Microsoft Edge in a right-hand sidebar layout
at 4 daily times: 12:00 AM, 4:00 PM, 7:00 PM, and 11:30 PM.

Includes:
- Right-sidebar docking (430px wide, keeps PotPlayer/video unobstructed on the left)
- HTTPS Atomic Internet Time drift detection & sync (fixes VPN UDP clock drift)
- Multi-trigger Windows Task Scheduler registration with battery support

Usage:
  python bb_sniper.py --now             # Test launch in right sidebar immediately
  python bb_sniper.py --install-task    # Register 4 daily schedules in Windows Task Scheduler
  python bb_sniper.py --status-task     # Check scheduled task status and next run times
  python bb_sniper.py --remove-task     # Remove scheduled tasks
  python bb_sniper.py --check-clock     # Check PC clock drift against atomic internet time
  python bb_sniper.py --sync-clock      # Sync Windows clock with atomic internet time (HTTPS)
  python bb_sniper.py --watch           # Run terminal daemon with real-time countdown
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

# 4 Daily Scan Times with a 15-second buffer for BigBasket database price updates
SCHEDULE_TIMES = [
    ("00:00:15", "12:00 AM (Midnight Reset & Flash Deals)"),
    ("16:00:15", "04:00 PM (Afternoon Stock Refresh)"),
    ("19:00:15", "07:00 PM (Evening Flash Deals)"),
    ("23:30:15", "11:30 PM (Pre-Midnight Clearance)"),
]

DEFAULT_SIDEBAR_WIDTH = 430


# ==============================================================================
# 1. Screen & Window Management (Sidebar Placement & Z-Order)
# ==============================================================================

def get_sidebar_geometry(desired_width: int = DEFAULT_SIDEBAR_WIDTH):
    """
    Detect screen work area (excluding Windows taskbar) and calculate
    coordinates for a right-aligned vertical sidebar window.
    """
    if HAS_WIN32 and os.name == "nt":
        rect = ctypes.wintypes.RECT()
        # SPI_GETWORKAREA = 48
        if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            screen_w = rect.right - rect.left
            screen_h = rect.bottom - rect.top
            w = min(desired_width, screen_w)
            x = rect.right - w
            y = rect.top
            h = screen_h
            return x, y, w, h
    # Safe fallback if API unavailable (standard 1366x768 display)
    return 936, 0, desired_width, 728


def snap_edge_to_sidebar(timeout_seconds: float = 6.0):
    """
    Locates the Edge window, snaps it to the right-side vertical sidebar,
    and brings it above PotPlayer/other windows without locking focus permanently.
    """
    if not (HAS_WIN32 and os.name == "nt"):
        return False

    user32 = ctypes.windll.user32
    x, y, w, h = get_sidebar_geometry()

    SW_RESTORE = 9
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_SHOWWINDOW = 0x0040
    SWP_RELEASE_FLAGS = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE

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
            # 2. Position as right sidebar and bring above other windows
            user32.SetWindowPos(target_hwnd, HWND_TOPMOST, x, y, w, h, SWP_SHOWWINDOW)
            user32.SetForegroundWindow(target_hwnd)
            # 3. Release topmost lock so PotPlayer / other apps can be clicked anytime
            time.sleep(0.2)
            user32.SetWindowPos(target_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_RELEASE_FLAGS)
            print(f"[OK] Positioned '{title[:35]}' as right sidebar ({x}, {y}, {w}, {h})")
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


def launch_edge(url: str = TARGET_URL, sidebar: bool = True):
    """Launch Microsoft Edge in right-side sidebar mode."""
    edge_exe = get_edge_path()
    x, y, w, h = get_sidebar_geometry()

    print(f"[*] Launching BigBasket Deal Sniper in Microsoft Edge...")
    print(f"[*] Sidebar Mode : Right Edge (x={x}, y={y}, w={w}, h={h})")
    print(f"[*] URL          : {url}")

    show_notification(
        "BigBasket Deal Sniper Activated",
        "Scanning deals in right sidebar. PotPlayer/apps stay visible on the left!"
    )

    if edge_exe:
        try:
            # Launch in new window positioned at the right sidebar
            cmd = [
                edge_exe,
                "--new-window",
                f"--window-position={x},{y}",
                f"--window-size={w},{h}",
                url
            ]
            subprocess.Popen(cmd)
            print(f"[OK] Launched Edge executable: {edge_exe}")

            # Start background thread to snap and raise window over PotPlayer
            if sidebar and HAS_WIN32:
                threading.Thread(target=snap_edge_to_sidebar, args=(6.0,), daemon=True).start()
            return True
        except Exception as e:
            print(f"[!] Failed to launch via msedge.exe: {e}")

    # Fallback 1: Windows 'microsoft-edge:' URI scheme
    try:
        os.system(f'start microsoft-edge:"{url}"')
        print("[OK] Launched via microsoft-edge URI protocol.")
        if sidebar and HAS_WIN32:
            threading.Thread(target=snap_edge_to_sidebar, args=(6.0,), daemon=True).start()
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
# 4. Windows Task Scheduler (4 Daily Triggers & Battery Support)
# ==============================================================================

def install_task():
    """Register the 4 daily scan triggers in Windows Task Scheduler."""
    script_path = os.path.abspath(__file__)

    # Use pythonw.exe so execution runs silently with NO console popup window
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable

    action_arg = f'"{script_path}" --run-now'

    # Clean up legacy task if present
    subprocess.run(["schtasks", "/delete", "/tn", LEGACY_TASK_NAME, "/f"], capture_output=True, check=False)

    triggers_ps = ",\n        ".join([
        f'$(New-ScheduledTaskTrigger -Daily -At "{t_slot}")'
        for t_slot, _ in SCHEDULE_TIMES
    ])

    ps_script = f"""
    $action = New-ScheduledTaskAction -Execute '{pythonw_path}' -Argument '{action_arg}'
    $triggers = @(
        {triggers_ps}
    )
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $triggers -Settings $settings -Force
    """

    print(f"[*] Registering scheduled task: {TASK_NAME}")
    print("[*] 4 Daily Trigger Times configured:")
    for t_slot, desc in SCHEDULE_TIMES:
        print(f"    - {t_slot} : {desc}")

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            print(f"\n[OK] SUCCESS: Scheduled task '{TASK_NAME}' registered successfully!")
            print("    Edge will automatically open docked as a right sidebar at:")
            for t_slot, desc in SCHEDULE_TIMES:
                print(f"      * {desc}")
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
            print("  Configured Daily Scan Slots:")
            for t_slot, desc in SCHEDULE_TIMES:
                print(f"    * {t_slot} -> {desc}")
            print()
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if any(line_str.startswith(k) for k in [
                    "TaskName:", "Status:", "Next Run Time:", "Last Run Time:", "Last Result:", "Schedule Type:"
                ]):
                    print(f"  {line_str}")
        else:
            print(f"[!] Task '{TASK_NAME}' is NOT registered.")
            print("    Run 'python bb_sniper.py --install-task' to enable automated daily sniping.")
    except Exception as e:
        print(f"[!] Error querying task: {e}")


# ==============================================================================
# 5. Live Terminal Watcher Mode (Atomic Internet Time Compensated)
# ==============================================================================

def get_next_run(drift_seconds: float = 0.0):
    """Calculate the next upcoming scan slot, adjusting for clock drift."""
    # Effective atomic time now
    effective_now = datetime.now() - timedelta(seconds=drift_seconds)
    today = effective_now.date()

    candidates = []
    for t_str, desc in SCHEDULE_TIMES:
        h, m, s = map(int, t_str.split(":"))
        candidate_dt = datetime(today.year, today.month, today.day, h, m, s)
        if candidate_dt > effective_now:
            candidates.append((candidate_dt, desc))

    if not candidates:
        # Wrap around to tomorrow's first slot
        first_h, first_m, first_s = map(int, SCHEDULE_TIMES[0][0].split(":"))
        tomorrow = today + timedelta(days=1)
        next_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day, first_h, first_m, first_s)
        return next_dt, SCHEDULE_TIMES[0][1], drift_seconds

    candidates.sort(key=lambda x: x[0])
    return candidates[0][0], candidates[0][1], drift_seconds


def watch_mode():
    """Run an interactive console countdown timer with atomic drift compensation."""
    print("=" * 65)
    print("  BigBasket Deal Sniper - Live Terminal Watcher")
    print("=" * 65)
    print("[*] 4 Daily Scan Times:")
    for t_str, desc in SCHEDULE_TIMES:
        print(f"    - {t_str} : {desc}")

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
            print(f"\n[!] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - TRIGGER TIME REACHED ({desc})!")
            launch_edge()
            time.sleep(12)  # Avoid double-triggering within the same window
            continue

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        sys.stdout.write(
            f"\r[*] Next: {next_dt.strftime('%I:%M:%S %p')} ({desc[:25]}) | "
            f"Countdown: {hours:02d}h {minutes:02d}m {seconds:02d}s "
        )
        sys.stdout.flush()
        time.sleep(1)


# ==============================================================================
# 6. Main CLI Interface
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BigBasket Deal Sniper Launcher & Scheduler (Microsoft Edge Sidebar)"
    )
    parser.add_argument("--now", "--run-now", action="store_true", help="Launch BigBasket in right sidebar immediately")
    parser.add_argument("--install-task", action="store_true", help="Register Windows Task Scheduler job for 4 daily times")
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
        print("  BigBasket Deal Sniper Launcher")
        print("=" * 60)
        print("Available options:")
        print("  1) python bb_sniper.py --now           -> Test launch in right sidebar immediately")
        print("  2) python bb_sniper.py --install-task  -> Register 4 daily schedules in Windows Task Scheduler")
        print("  3) python bb_sniper.py --status-task   -> Check task status & upcoming trigger times")
        print("  4) python bb_sniper.py --check-clock   -> Check PC clock drift vs atomic internet time")
        print("  5) python bb_sniper.py --sync-clock    -> Sync Windows system clock via HTTPS")
        print("  6) python bb_sniper.py --watch         -> Live terminal countdown with auto drift adjustment")
        print("  7) python bb_sniper.py --remove-task   -> Remove scheduled task")
        print("-" * 60)
        parser.print_help()


if __name__ == "__main__":
    main()
