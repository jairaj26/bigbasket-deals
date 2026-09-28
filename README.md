# 🛒 BigBasket Deal Sniper & Explorer

A fast, lightweight, 100% client-side tool to find flash sales, clearance prices, and steep discounts (&ge;50% OFF) across BigBasket on both Desktop and Mobile.

---

## 💡 Why In-Browser?

BigBasket uses Akamai Bot Manager which aggressively blocks external automated scripts and backend servers (403 Forbidden). 

This tool runs **directly inside your own authenticated browser session** on [bigbasket.com](https://www.bigbasket.com). It leverages your real browser cookies, TLS fingerprint, and active location/pincode—meaning **zero bot blocks, zero 403 errors, and 100% live inventory accurate to your dark store**.

---

## ⚡ Choose Your Setup Method

Choose the method that best fits your setup:

| Feature | 🐒 Tampermonkey (Userscript) | 🔖 Browser Bookmarklet |
| :--- | :--- | :--- |
| **Best For** | Desktop (Edge / Chrome) & Android (Kiwi / Firefox) | Any browser, Mobile Safari & Chrome |
| **Extensions Required?** | Yes (Tampermonkey extension) | **No extensions needed** |
| **Auto-load on BigBasket?** | ✅ Yes, automatically | 👆 Manual click on bookmark |
| **12:00 AM Midnight Auto-Sniper?**| ✅ Supported | ❌ Requires manual click |
| **Auto-Updates?** | ✅ Yes, background updates | ✅ Yes (Mobile CDN version) |

---

## 🐒 Method 1: Tampermonkey Userscript (Recommended)

The userscript automatically loads every time you visit [bigbasket.com](https://www.bigbasket.com) and enables the **12:00 AM Midnight Auto-Sniper**.

### Step 1: Install Tampermonkey
- **Microsoft Edge**: [Install Tampermonkey from Edge Add-ons](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/iikmkjmpaadaobahmlepeloendndfphd)
- **Google Chrome**: [Install Tampermonkey from Chrome Web Store](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)
- **Android**: Install [Firefox for Android](https://play.google.com/store/apps/details?id=org.mozilla.firefox) or [Kiwi Browser](https://play.google.com/store/apps/details?id=com.kiwibrowser.browser), then add the Tampermonkey extension.

### Step 2: Enable "Developer Mode" (Edge & Chrome only)
Modern Chromium browsers (Manifest V3) require this 1-time toggle to allow userscripts to run:
1. In Edge, go to: `edge://extensions` (or `chrome://extensions` in Chrome).
2. Toggle **Developer mode** to **ON** on the left sidebar.

### Step 3: 1-Click Install the Script
Click this direct link:
👉 **[Install BigBasket Deal Sniper Userscript](https://raw.githubusercontent.com/jairaj26/bigbasket-deals/main/bb_deal_finder.user.js)**

Tampermonkey will automatically open an install screen. Click the green **"Install"** button. Done!

---

### ⏰ Optional: Automated Hourly Deal Sniper (Runs Every Hour)

BigBasket refreshes inventories and drops flash sales throughout the day. You can schedule Windows to automatically launch Edge, pin the window on top of current apps (without altering your window size), run **Fetch All (20)**, and chime when deals are ready:

#### 🕒 Hourly Automated Schedule
* **Runs Every 1 Hour Continuously** while your PC is on.
* Automatically wakes Edge pinned on top, starts the scan, and presents fresh deals throughout the day.

#### 📌 Pin-On-Top Window Management
Edge launches and automatically pins **on top of all open desktop apps (such as PotPlayer, video players, games)**:
* **Preserves your original window size and position**: Does not resize or move your browser.
* Ensures the deal scanner stays visible while your background videos keep playing.

#### ⚡ Instant Grid View + Live Background Loading
* **Opens Immediately After Batch 1**: You don't have to wait for all 20 categories. The full Deals Explorer grid opens as soon as the first 7 priority categories finish!
* **Live Background Stream**: Batches 2 and 3 continue loading in the background, smoothly inserting new deals, updating category filters, and adjusting brand counts in real time.
* **Persistent Out of Stock Filter**: Out of stock items are displayed by default. If you uncheck "Show Out of Stock", your preference is saved and remembered for all future fetches.

#### 🛡️ Anti-429 Rate-Limit Protection (3 Prioritized Batches)
BigBasket restricts rapid sequential queries across categories. Deal Sniper eliminates 429 errors using smart prioritized batching and humanized pacing:
1. **2.0–2.5s Delay with Jitter**: Paces requests realistically per category and rotates unique `x-tracker` tokens so token buckets replenish continuously.
2. **Batch 1 (High-Priority Essentials - First 7)**: Foodgrains/Masala, Dairy, Edible Oils, Beverages, Chocolates, Snacks, Bakery. *(Grid opens immediately here!)*
3. **10-Second Anti-429 Pause**: Live countdown pause allowing BigBasket rate counters to cool down.
4. **Batch 2 (Personal Care & Biscuits - Next 7)**: Dry Fruits, Skin care, Hair care, Bath, Baby care, Detergents, Biscuits & Cookies.
5. **10-Second Anti-429 Pause**: Second cooldown pause.
6. **Batch 3 (Gourmet & Remaining - Last 6)**: Gourmet & World Food, Diapers & Wipes, Beauty & Hygiene, Cleaning & Household, Kitchen, Fruits & Veggies.
7. **Adaptive Exponential Backoff**: If a 429 ever occurs, the script pauses with a live countdown (4s, 7s, 10s) and retries up to 3 times before background recovery.
8. **Maximum 7 Selectable**: The manual category picker is capped at **7 categories max per fetch** to prevent accidental rate limits.

#### 🌐 VPN Clock Drift Detection (HTTPS Atomic Time)
When VPNs are active, standard Windows NTP time sync (UDP port 123) is blocked, causing PC clocks to slowly slip by 3–4 minutes per week. Deal Sniper includes an **HTTPS Port 443 atomic time sync** (unaffected by VPNs) to ensure automated scans trigger at the exact atomic second.

```powershell
# 1. Register hourly schedule in Windows Task Scheduler (runs silently every 1 hour)
python bb_sniper.py --install-task

# 2. Test launch pinned on top immediately over current apps
python bb_sniper.py --now

# 3. Check status & upcoming trigger times
python bb_sniper.py --status-task

# 4. Check PC clock drift against atomic internet time (HTTPS - VPN proof)
python bb_sniper.py --check-clock

# 5. Sync Windows system clock to atomic internet time
python bb_sniper.py --sync-clock

# 6. Live terminal countdown daemon with auto drift compensation
python bb_sniper.py --watch

# 7. Remove scheduled task anytime
python bb_sniper.py --remove-task
```

When any scheduled slot arrives:
1. Windows wakes Edge pinned on top of open apps at `https://www.bigbasket.com/?bb_auto=all`.
2. A Windows toast notification confirms: *"BigBasket Deal Sniper Activated"*.
3. The script automatically runs **Fetch All (20)** across all categories in 3 prioritized batches.
4. If any 429 occurs, it smoothly defers and recovers missing pages in the background.
5. The Deals Explorer grid pops open with your deals, accompanied by an audio chime alert!

---

## 🔖 Method 2: Browser Bookmarklet (Zero Extensions)

Works on any desktop or mobile browser without installing any browser extensions.

### 💻 A. Desktop (PC / Mac)
1. Open the **[1-Click Install Webpage](https://jairaj26.github.io/bigbasket-deals/)**.
2. Drag the green **`🛒 BB Deals`** button to your Bookmarks Bar (`Ctrl/Cmd + Shift + B`).
3. Whenever you are on [bigbasket.com](https://www.bigbasket.com), click your **`BB Deals`** bookmark!

### 📱 B. Mobile (Android & iOS)
Most mobile browsers (Chrome, Safari, Edge, Samsung Internet) do not support bookmark drag-and-drop. Setup takes 30 seconds:

#### 1. Copy this Mobile Script:
```javascript
javascript:(function(){if(window.__BB_SNIPER__){const p=document.getElementById('bb-pop');if(p)p.style.display=p.style.display==='none'?'flex':'none';return;}const s=document.createElement('script');s.src='https://jairaj26.github.io/bigbasket-deals/bb_deal_finder.min.js?t='+Date.now();s.onerror=function(){const f=document.createElement('script');f.src='https://cdn.jsdelivr.net/gh/jairaj26/bigbasket-deals@main/bb_deal_finder.min.js?t='+Date.now();document.body.appendChild(f);};document.body.appendChild(s);})();
```
*(Or copy it with a single tap from the **[1-Click Installer Webpage](https://jairaj26.github.io/bigbasket-deals/)**).*

#### 2. Save as Bookmark in Mobile Browser:
- **Chrome / Brave / Edge (Android & iOS):**
  1. Bookmark any webpage (tap `⋮` menu &rarr; tap ⭐).
  2. Tap **Edit Bookmark** at the bottom (or Bookmarks &rarr; `⋮` &rarr; **Edit**).
  3. Change Name to: `BB Deals`.
  4. In the URL field: Erase everything and **paste** the copied script.
  5. Tap **Save**.

- **Safari (iPhone / iPad):**
  1. Bookmark this page (tap Share &rarr; **Add Bookmark**).
  2. Open Bookmarks (book icon) &rarr; tap **Edit** &rarr; tap the bookmark.
  3. Rename it to `BB Deals`.
  4. Erase the URL and **paste** the copied script. Tap **Done**.

#### 3. Run on BigBasket:
1. Open [bigbasket.com](https://www.bigbasket.com).
2. Tap the browser address bar, type **`BB Deals`**, and tap the bookmark suggestion.
3. The green **BB Deals** button will instantly appear!

### 🔧 C. Desktop Standalone Bookmark (Offline / No CDN)
1. Create a new bookmark on your desktop browser.
2. Copy the full standalone code from [`bookmarklet.txt`](bookmarklet.txt).
3. Paste it into the bookmark's **URL / Address** field and save.

---

## 🚀 How to Use Deal Sniper

1. Open [bigbasket.com](https://www.bigbasket.com) in your browser.
2. Click your **`BB Deals`** bookmark (or if using Tampermonkey, the green button is already there).
3. Tap the green **BB Deals** button at the bottom-right of the page to open the control panel:
   - **Targeted Scan**: Pick up to 2 specific categories and tap **Fetch Selected**.
   - **Full Catalog Scan**: Tap **Fetch All (20)** to scan the entire store with automatic 429 rate-limit recovery.
4. The Deals Explorer grid opens automatically with your deals sorted by highest discount!
5. Use real-time filters:
   - **Search**: Filter by product name.
   - **Sort**: Discount (High to Low), Price (Low to High), or Price (High to Low).
   - **Brand Filter**: Multi-select dropdown with live product counts.
   - **Show Out of Stock**: Toggle unavailable products on/off.

---

## ✨ Features

- **⚡ Fast Category Sniping & Fetch All:** Select specific categories for instant results or hit **Fetch All (20)** to scan the entire catalog with automatic 429 rate-limit recovery.
- **⏰ 12:00 AM Midnight Auto-Sniper:** Automated Windows Task Scheduler launcher that automatically opens Microsoft Edge at midnight, runs the scan, opens the deals grid, and rings an audio chime.
- **📱 Responsive 3-Column Mobile Grid:** Designed specifically for mobile screens with a 3-items-per-row card layout, compact badges, and high product density.
- **🚫 Hide Out of Stock by Default:** Out-of-stock items are hidden automatically so you only browse available products. Easily toggle them back on with one tap.
- **📊 3 Smart Sort Modes:**
  1. **Discount: High to Low** (Default — highest percentage cuts first)
  2. **Price: Low to High** (Cheapest items first)
  3. **Price: High to Low** (Premium deals first)
- **⚖️ Unit Pricing Intelligence:** Automatically standardizes package weights & volumes (`Rs./100g`, `Rs./kg`, `Rs./100ml`, `Rs./L`, `Rs./pc`) so you instantly spot true value.
- **🔍 Instant Filter & Search:** Real-time search by product name and multi-select brand filtering.
- **🔗 Direct Product Links:** Click any product card to view it directly on BigBasket.

---

## 🛠️ Development & Building

The source code is located in `bb_deal_finder.js`. To rebuild all distribution bundles (`bb_deal_finder.user.js`, `bb_deal_finder.min.js`, `bookmarklet.txt`, and `index.html`):

```bash
node build.js
```

This runs a syntax check, strips comments and whitespace, regenerates the minified bookmarklet, updates the self-contained userscript, and syncs `index.html`.
