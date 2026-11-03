# 🛒 BigBasket Deal Sniper & Telegram Bot

A dual-mode toolkit to discover steep discounts (≥50% to ≥70% OFF) and clearance deals across BigBasket.

1. **🤖 Headless Telegram Bot** (Primary Background Automation): Silently monitors deals 4x daily in the background and delivers compact alerts directly to your Telegram bot.
2. **📱 Browser Bookmarklet** (On-Demand Manual Scanner): A lightweight, zero-install bookmarklet for Mobile (Chrome, Safari, iOS, Android) and PC/Mac to scan and browse deals interactively on BigBasket.

---

## 🤖 Mode 1: Automated Telegram Bot Sniper

A 100% silent background automation that runs via Playwright and Microsoft Edge positioned off-screen.

### ✨ Features
- **Zero Desktop Disruption**: Runs completely headless/off-screen. No browser windows or popups will ever interrupt your screen or media playback.
- **Akamai Bot-Proof**: Bypasses Akamai Bot Manager (Status 200) by utilizing a genuine browser session with your authentic dark-store session headers.
- **Clean 3-Line Combined Alerts**: Formatted in a compact 3-line card layout, combined into single messages:
  ```text
  🛒 Fortune Sunlite Refined Sunflower Oil (1L)
  💰 ₹85  (MRP: ₹175) || 51% OFF 
  🔗 [Open on BigBasket](https://www.bigbasket.com/pd/...)
  ```
- **15-Day Cooloff & Smart Deduplication**:
  - **Day 1**: Newly discovered deals are sent immediately.
  - **Day 2**: If an item stays at the **same discount** for the second day, it is **hidden from sending for 15 days** to prevent notification spam.
  - **Discount Changes**: If a price drops further or the discount changes, the deal is **alerted immediately**.
- **Automated 4x Daily Schedule**: Pre-configured for Windows Task Scheduler to scan at peak restock slots (**12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM**).

### Quick Setup

1. **Configure Credentials (`.env`)**:
   ```env
   # Telegram Bot Token from @BotFather
   TELEGRAM_BOT_TOKEN="your_bot_token_here"

   # Your Telegram Chat ID from @userinfobot
   TELEGRAM_CHAT_ID=your_chat_id_here

   # Minimum discount % to alert (e.g. 70% OFF)
   MIN_DISCOUNT=70

   # Delivery pincode
   PINCODE=560045
   ```

2. **Verify Telegram Connection**:
   ```powershell
   python bb_telegram_sniper.py --test-telegram
   ```

3. **Run a Live Background Scan**:
   ```powershell
   python bb_telegram_sniper.py --now
   ```

4. **Register 4x Daily Scheduled Task**:
   ```powershell
   # Register Windows Task Scheduler job (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)
   python bb_telegram_sniper.py --install-task

   # Check schedule status and upcoming run times
   python bb_telegram_sniper.py --status-task

   # Remove schedule anytime
   python bb_telegram_sniper.py --remove-task
   ```

---

## 📱 Mode 2: On-Demand Browser Bookmarklet (Mobile & PC)

A client-side bookmarklet that runs directly inside your active BigBasket tab without any third-party apps or browser extensions.

### 🌐 1-Click Installer
Open the web installer: **[https://jairaj26.github.io/bigbasket-deals/](https://jairaj26.github.io/bigbasket-deals/)**

### 📱 Mobile Setup (iPhone Safari & Android Chrome)
1. Open the [installer page](https://jairaj26.github.io/bigbasket-deals/) and tap **"📋 Copy Mobile Script"**.
2. **Bookmark the page** in your mobile browser.
3. Open your bookmarks, **edit the bookmark you just saved**:
   - Name: `BB Deals`
   - URL: Clear and **paste** the copied script.
   - Tap **Save**.
4. **To Run**: Open [bigbasket.com](https://www.bigbasket.com), type `BB Deals` in your address bar, and tap the bookmark suggestion.

### 💻 Desktop Setup (PC & Mac)
- **Drag & Drop**: Visit [jairaj26.github.io/bigbasket-deals](https://jairaj26.github.io/bigbasket-deals/) and drag the green **"🛒 BB Deals"** button onto your browser's Bookmarks Bar (`Ctrl + Shift + B` / `Cmd + Shift + B`).
- **Manual**: Copy the contents of `bookmarklet.txt` and create a new browser bookmark with that code as the URL.

### ⚡ Bookmarklet Features
- **Multi-Category Selection**: Select up to 3 categories at once to fetch deals on demand.
- **Dynamic Price per Unit**: Automatically calculates and displays `Rs./100g`, `Rs./kg`, `Rs./L`, or `Rs./pc`.
- **Out of Stock Toggle**: Instantly show or hide out-of-stock items.
- **Brand & Category Filtering**: Filter loaded deals by brand or category, and sort by highest discount or price.
- **Safe Akamai Rate Pacing**: Built-in adaptive backoff and jittered pacing to ensure safe scanning.

---

## 🛠️ Building & Updating Bookmarklets

When modifying [`bb_deal_finder.js`](file:///d:/Projects/BigBasket/bb_deal_finder.js):
```powershell
node build.js
```
This automatically validates syntax, minifies the code into `bb_deal_finder.min.js`, regenerates `bookmarklet.txt` and `mobile_bookmarklet.txt`, and syncs `index.html`.

---

## 📂 Repository Structure

```text
BigBasket/
├── bb_telegram_sniper.py    # Headless background scanner & Telegram bot dispatcher
├── .env                     # Credentials & configuration (ignored by git)
├── .env.example             # Template for configuration
├── bb_deal_finder.js        # Readable source code for browser bookmarklet
├── bb_deal_finder.min.js    # Minified bookmarklet script served via GitHub Pages
├── bookmarklet.txt          # Desktop standalone bookmarklet (javascript: URL)
├── mobile_bookmarklet.txt   # Mobile dynamic loader bookmarklet
├── build.js                 # Compiler & syntax checker for bookmarklet
├── index.html               # 1-Click web installer hosted on GitHub Pages
├── .gitignore               # Ignores local databases & .env
└── README.md                # Project documentation
```
