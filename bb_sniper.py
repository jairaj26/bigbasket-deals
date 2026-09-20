"""
BigBasket Midnight Deal Sniper Launcher & Scheduler
===================================================
Automatically launches Microsoft Edge at 12:00:15 AM to scan BigBasket deals
using your authenticated browser session and Tampermonkey/bookmarklet.

Usage:
  python bb_sniper.py --install-task    # Register Windows Task Scheduler (Daily 12:00:15 AM)
  python bb_sniper.py --remove-task     # Remove Windows Task Scheduler job
  python bb_sniper.py --status-task     # Check Task Scheduler status & next run time
  python bb_sniper.py --now             # Test immediately (launch Edge + notification)
  python bb_sniper.py --watch           # Run as live terminal countdown daemon
"""

import sys
import os
import time
import argparse
import subprocess
import webbrowser
from datetime import datetime, timedelta

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

TASK_NAME = "BigBasketMidnightSniper"
TARGET_URL = "https://www.bigbasket.com/?bb_auto=all"
SCHEDULE_TIME = "00:00:15"  # 12:00:15 AM (gives 15s buffer for midnight price refresh)


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


def launch_edge(url: str = TARGET_URL):
    """Launch Microsoft Edge with the target auto-run URL."""
    edge_exe = get_edge_path()
    print(f"[*] Launching BigBasket Deal Sniper in Microsoft Edge...")
    print(f"[*] URL: {url}")

    show_notification(
        "BigBasket Deal Sniper Activated",
        "Launching Edge at 12 AM to scan all 20 categories for flash deals!"
    )

    if edge_exe:
        try:
            subprocess.Popen([edge_exe, url])
            print(f"[OK] Launched Edge executable: {edge_exe}")
            return True
        except Exception as e:
            print(f"[!] Failed to launch via msedge.exe: {e}")

    # Fallback 1: Windows 'microsoft-edge:' URI scheme
    try:
        os.system(f'start microsoft-edge:"{url}"')
        print("[OK] Launched via microsoft-edge URI protocol.")
        return True
    except Exception as e:
        print(f"[!] Protocol launch failed: {e}")

    # Fallback 2: Python webbrowser
    try:
        webbrowser.open(url)
        print("[OK] Launched via default browser handler.")
        return True
    except Exception as e:
        print(f"[!] Webbrowser launch failed: {e}")

    return False


def install_task():
    """Register daily midnight task in Windows Task Scheduler."""
    script_path = os.path.abspath(__file__)

    # Use pythonw.exe so execution runs silently with NO console popup window
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable

    action_cmd = f'"{pythonw_path}" "{script_path}" --run-now'

    cmd = [
        "schtasks", "/create",
        "/tn", TASK_NAME,
        "/tr", action_cmd,
        "/sc", "daily",
        "/st", SCHEDULE_TIME,
        "/f"
    ]

    print(f"[*] Registering scheduled task: {TASK_NAME}")
    print(f"[*] Schedule: Daily at {SCHEDULE_TIME} (12:00:15 AM)")
    print(f"[*] Action: {action_cmd}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"\n[OK] SUCCESS: Scheduled task '{TASK_NAME}' registered successfully!")
            print(f"    Edge will automatically open every night at 12:00:15 AM.")
            print(f"    You can test it anytime with: python bb_sniper.py --now")
            print(f"    Check status with: python bb_sniper.py --status-task")
            print(f"    Remove anytime with: python bb_sniper.py --remove-task\n")
        else:
            print(f"[X] Error creating task:\n{res.stderr.strip() or res.stdout.strip()}")
            if "Access is denied" in (res.stderr + res.stdout):
                print("[!] Tip: Open PowerShell / Command Prompt as Administrator and run the command again.")
    except Exception as e:
        print(f"[!] Execution failed: {e}")


def remove_task():
    """Remove scheduled task from Windows Task Scheduler."""
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"[OK] SUCCESS: Scheduled task '{TASK_NAME}' removed.")
        else:
            print(f"[!] Result: {res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        print(f"[!] Error deleting task: {e}")


def status_task():
    """Check status and next run time of the scheduled task."""
    cmd = ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST", "/v"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"[OK] Task '{TASK_NAME}' is currently REGISTERED.\n")
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if any(line_str.startswith(k) for k in [
                    "TaskName:", "Status:", "Next Run Time:", "Last Run Time:", "Last Result:", "Schedule Type:", "Start Time:"
                ]):
                    print(f"  {line_str}")
        else:
            print(f"[!] Task '{TASK_NAME}' is NOT registered.")
            print("    Run 'python bb_sniper.py --install-task' to enable daily midnight sniping.")
    except Exception as e:
        print(f"[!] Error querying task: {e}")


def watch_mode():
    """Run an interactive console countdown timer until 12:00:15 AM."""
    print("=" * 60)
    print("  BigBasket Midnight Sniper - Live Terminal Watcher")
    print("=" * 60)
    print(f"[*] Target launch time: Every day at {SCHEDULE_TIME}")
    print("[*] Press Ctrl+C at any time to exit.\n")

    while True:
        now = datetime.now()
        target_today = now.replace(hour=0, minute=0, second=15, microsecond=0)

        if now < target_today:
            next_run = target_today
        else:
            next_run = target_today + timedelta(days=1)

        diff = next_run - now
        total_seconds = int(diff.total_seconds())

        if total_seconds <= 1:
            print(f"\n[!] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - IT'S 12:00 AM! Launching BigBasket Sniper...")
            launch_edge()
            time.sleep(10)  # avoid double triggering within the same second
            continue

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        sys.stdout.write(f"\r[*] Next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')} | Countdown: {hours:02d}h {minutes:02d}m {seconds:02d}s ")
        sys.stdout.write(" ")
        sys.stdout.flush()
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        description="BigBasket Midnight Deal Sniper Launcher & Scheduler (Microsoft Edge)"
    )
    parser.add_argument("--now", "--run-now", action="store_true", help="Launch BigBasket in Edge immediately and test notification")
    parser.add_argument("--install-task", action="store_true", help="Register Windows Task Scheduler job for 12:00:15 AM daily")
    parser.add_argument("--remove-task", action="store_true", help="Remove Windows Task Scheduler job")
    parser.add_argument("--status-task", action="store_true", help="View scheduled task status and next run time")
    parser.add_argument("--watch", action="store_true", help="Run in terminal watch mode with live countdown")

    args = parser.parse_args()

    if args.now:
        launch_edge()
    elif args.install_task:
        install_task()
    elif args.remove_task:
        remove_task()
    elif args.status_task:
        status_task()
    elif args.watch:
        watch_mode()
    else:
        print("BigBasket Midnight Deal Sniper")
        print("-" * 40)
        print("Available options:")
        print("  1) python bb_sniper.py --now           -> Test launch in Edge immediately")
        print("  2) python bb_sniper.py --install-task  -> Register daily 12:00 AM Windows task")
        print("  3) python bb_sniper.py --status-task   -> Check task status")
        print("  4) python bb_sniper.py --remove-task   -> Remove scheduled task")
        print("  5) python bb_sniper.py --watch         -> Live countdown in console")
        print("-" * 40)
        parser.print_help()


if __name__ == "__main__":
    main()
