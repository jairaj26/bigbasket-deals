# 🛒 BigBasket Deal Finder

A fast, lightweight, 100% self-contained browser bookmarklet to find flash deals across BigBasket categories on both Desktop and Mobile.

---

## ⚡ Easy 1-Click Install

### 💻 Desktop (Mac / PC)
1. Open the **[1-Click Installer Page](https://jairaj26.github.io/bigbasket-deals/)** in your browser.
2. Drag the green **`🛒 BB Deals`** button directly to your Bookmarks / Favorites bar (`Ctrl/Cmd + Shift + B`).
3. *(Optional)* Bookmarks automatically sync to your mobile Chrome / Safari (via iCloud) / Edge when logged in!

### 📱 Mobile-Only (No PC/Mac)
1. Open **`https://jairaj26.github.io/bigbasket-deals/`** on your phone.
2. Tap **`📥 Download Mobile Bookmark (.html)`**.
3. Open your mobile browser's Bookmarks $\rightarrow$ tap **Import** $\rightarrow$ select the downloaded file!

---

## 🚀 How to Run
1. Go to [bigbasket.com](https://www.bigbasket.com).
2. Click your **BB Deals** bookmark.
3. The floating action button (FAB) will appear at the bottom-right.
4. Select your categories $\rightarrow$ click **Fetch** $\rightarrow$ the in-page Deals Explorer opens automatically!

---

## ✨ Features
- **Guaranteed Page 1 for All Categories:** Page 1 items are always captured for every category.
- **Smart 50% Pagination:** Automatically continues to Page 2+ only if all items on the current page have $\ge 50\%$ OFF.
- **Permanent Canonical Categories:** Uses permanent `type: 'pc'` BigBasket categories that never expire across all cities.
- **In-Page Deals Explorer:** Responsive full-screen grid directly on the page with real-time search, category filters, and discount tier filters.

---

# 🤖 Automated Python Deal Finder & Telegram Bot

An automated Python service that continuously snipes $\ge 70\%$ OFF deals across BigBasket for your selected pincode and pushes clean, actionable deal alerts directly to Telegram.

## 🌟 Highlights
- **📍 Dynamic Pincode Targeting:** Enter any 6-digit Indian delivery pincode; the bot resolves your localized dark store inventory and prices.
- **💬 Interactive Telegram Bot:** Simply message the bot your pincode, and it will scan and reply with all 70%+ deals immediately.
- **⚡ Clean Deal Format:** Clean message list showing Product Name, Brand, Selling Price, MRP, Discount % and a direct `[Click here to view]` link.
- **🧠 Smart Deduplication:** Powered by a local SQLite tracker so you never receive duplicate notifications for deals already alerted.
- **☁️ Zero-Server GitHub Actions:** Automatically scans on a recurring cron schedule (e.g. every 2 hours) on GitHub Actions without needing your PC on.

---

## 🚀 Quick Start (Local)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
Copy the example environment file and add your credentials:
```bash
cp .env.example .env
```
Edit `.env`:
- `TELEGRAM_BOT_TOKEN`: Get this from [@BotFather](https://t.me/BotFather) on Telegram.
- `TELEGRAM_CHAT_ID`: Your chat ID from [@userinfobot](https://t.me/userinfobot) (or channel `@your_channel`).
- `PINCODE`: Your 6-digit delivery pincode (e.g. `560001`).

### 3. Usage Modes

#### A. Interactive Telegram Bot (Asks for your Pincode)
```bash
python bot.py
# or
python main.py --bot
```
1. Open your Telegram bot and send `/start`.
2. The bot asks: *"Please enter your 6-digit Pincode"*.
3. Type `560001` (or your area code).
4. The bot scans BigBasket and replies with a formatted list of all deals $\ge 70\%$ OFF!

#### B. Dry Run (Inspect deals in console without sending to Telegram)
```bash
python main.py --dry-run --pincode 560001 --min-discount 70
```

#### C. Notification Push (Fetch, Deduplicate & Push to Telegram)
```bash
python main.py --notify --pincode 560001 --min-discount 70
```

---

## ☁️ Setting Up Free GitHub Actions (Automated Cloud Cron)

You can run this automation in the cloud for free without keeping your PC powered on:

1. Push this repository to GitHub.
2. Navigate to your repository $\rightarrow$ **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Add the following **Repository secrets**:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token.
   - `TELEGRAM_CHAT_ID`: Your Telegram Chat/Channel ID.
   - `PINCODE`: Your 6-digit delivery pincode (e.g. `560001`).
4. That's it! The workflow in [`.github/workflows/bb_deals.yml`](.github/workflows/bb_deals.yml) automatically runs at BigBasket's 3 key deal refresh windows:
   - **🌙 Midnight Drop (12:05 AM IST)**: Daily deal reset, bank offers, and campaign rollouts.
   - **☀️ Morning Refresh (7:35 AM IST)**: Morning grocery slots and fresh stock updates.
   - **🌆 Evening Clearance (6:05 PM IST)**: Evening flash drops and clearance additions.
   
   *(You can also trigger a scan on-demand anytime from the GitHub Actions tab or by typing `/deals` to your Telegram bot).*

