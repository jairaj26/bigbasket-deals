# 🛒 BigBasket Telegram Deal Sniper

A 100% silent, headless background automation that monitors BigBasket for steep discount deals (&ge;70% OFF) and alerts directly to your personal Telegram bot.

---

## ✨ Features

- **🤖 Zero Desktop Disruption**: Runs completely in the background via Playwright and Microsoft Edge positioned off-screen. No browser windows or command prompts will ever interrupt your work or media playback.
- **🛡️ Akamai Bot-Proof**: Bypasses Akamai Bot Manager (Status 200) by utilizing a genuine browser runtime environment with your authentic dark-store session.
- **📱 Clean 3-Line Combined Messages**: Each deal card is formatted in a compact 3-line layout:
  ```text
  🛒 Fortune Sunlite Refined Sunflower Oil (1L)
  💰 ₹85  (MRP: ₹175) || 51% OFF 
  🔗 [Open on BigBasket](https://www.bigbasket.com/pd/...)
  ```
  Deals are grouped into combined messages separated by `\n\n` within Telegram's message limits.
- **🧠 15-Day Cooloff & Deduplication**:
  - **Day 1**: Newly discovered deals are sent immediately.
  - **Day 2**: If an item stays at the **same discount** for the second day, it is **hidden from sending for 15 days** to prevent notification fatigue.
  - **Discount Changes**: If a price drops further or the discount changes, the deal is **alerted immediately**.
  - **No Duplicate Alerts**: Identical deals are never repeated on subsequent scans within the same day.
- **⏰ Automated 4x Daily Schedule**: Pre-configured for Windows Task Scheduler to scan at peak restock and clearance times (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM). Automatically catches up if the PC was powered off during a scheduled slot.

---

## 🚀 Quick Setup

### 1. Configure Credentials (`.env`)
Create or edit `.env` in the project root:

```env
# 1. Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN="your_bot_token_here"

# 2. Your Telegram Chat ID from @userinfobot
TELEGRAM_CHAT_ID=your_chat_id_here

# Minimum discount % to alert (e.g. 70% OFF)
MIN_DISCOUNT=70

# Delivery pincode
PINCODE=560045
```

> **How to get Telegram credentials in 60 seconds:**
> 1. In Telegram, search for `@BotFather` &rarr; send `/newbot` &rarr; copy the **HTTP API token**.
> 2. Search for `@userinfobot` &rarr; click `/start` &rarr; copy your numeric **Id**.
> 3. Send a message (e.g. `/start`) to your new bot once so Telegram allows it to message you.

### 2. Verify Telegram Connection
```powershell
python bb_telegram_sniper.py --test-telegram
```
Your bot will immediately send a test deal card to confirm delivery.

### 3. Run a Live Background Scan
```powershell
python bb_telegram_sniper.py --now
```
Scans your assigned essential categories, applies discount and 15-day cooloff filters, and delivers deals directly to Telegram.

---

## ⏰ Windows Task Scheduler Automation

Register the background job so it runs automatically 4 times a day without requiring any terminal to stay open:

```powershell
# Register the 4x daily silent schedule (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)
python bb_telegram_sniper.py --install-task

# Check status and upcoming run times
python bb_telegram_sniper.py --status-task

# Remove the scheduled task anytime
python bb_telegram_sniper.py --remove-task

# Reset deals history tracking database
python bb_telegram_sniper.py --reset-history
```

---

## 📂 Project Structure

```text
BigBasket/
├── bb_telegram_sniper.py   # Core headless background scanner & Telegram dispatcher
├── .env                    # Secret credentials (Bot token, Chat ID, min discount)
├── .env.example            # Sample configuration template
├── .gitignore              # Ignores sensitive credentials & history caches
└── README.md               # Documentation
```
