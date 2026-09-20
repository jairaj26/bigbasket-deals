# 🛒 BigBasket Deal Sniper & Explorer

A fast, lightweight, 100% client-side browser bookmarklet to find flash sales and steep discounts across BigBasket on both Desktop and Mobile.

---

## 💡 Why a Bookmarklet?

BigBasket uses Akamai Bot Manager which aggressively blocks external automated scripts and servers (403 Forbidden). 

This tool runs **directly inside your own authenticated browser session** on [bigbasket.com](https://www.bigbasket.com). It shares your real browser cookies, TLS fingerprint, and active location/pincode—meaning **zero bot blocks, zero 403 errors, and 100% live inventory accurate to your dark store**.

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

## ⏰ 12:00 AM Midnight Auto-Sniper Setup (Edge + Windows)

BigBasket frequently updates discounts and releases flash deals at 12:00 AM (midnight). You can automate Edge to open and scan automatically:

### 1. Install Tampermonkey in Microsoft Edge
1. Add the [Tampermonkey Extension](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/iikmkjmpaadaobahmlepeloendndfphd) to Edge.
2. Click the Tampermonkey icon &rarr; **Create a new script**.
3. Paste the contents of [`bb_deal_finder.user.js`](bb_deal_finder.user.js) and save (`Ctrl+S`).

### 2. Enable Midnight Automation in Windows
Run the launcher in this repository to register with **Windows Task Scheduler**:

```bash
# Register daily 12:00:15 AM task (runs silently with pythonw, zero RAM)
python bb_sniper.py --install-task

# Check scheduled status & next run time
python bb_sniper.py --status-task

# Test launch in Edge right now
python bb_sniper.py --now

# Remove scheduled task anytime
python bb_sniper.py --remove-task
```

When midnight arrives:
1. Windows wakes Edge to `https://www.bigbasket.com/?bb_auto=all`.
2. A Windows toast notification confirms: *"BigBasket Deal Sniper Activated"*.
3. Tampermonkey automatically runs **Fetch All (20)** across all categories.
4. If BigBasket rate-limits any page (429), it automatically defers and recovers it smoothly in the background.
5. The Deals Explorer grid pops open with your deals, accompanied by an audio chime alert!

---

## ⚡ 1-Click Install

### 💻 Method 1: Desktop (PC / Mac)
1. Open the **[1-Click Install Page](https://jairaj26.github.io/bigbasket-deals/)** in your browser.
2. Drag the green **`🛒 BB Deals`** button to your Bookmarks / Favorites bar (`Ctrl/Cmd + Shift + B`).
3. *(Pro-tip: If you use Chrome, Edge, or Safari, bookmarks auto-sync to your mobile phone when signed into your account!)*

### 📱 Method 2: Mobile (Copy & Paste as Bookmark)

Most mobile browsers (Chrome, Safari, Edge, Samsung Internet, Brave) do not support importing bookmark files. Setting it up on your phone takes less than 30 seconds using the lightweight script below:

#### 1. Copy this Mobile Script:
```javascript
javascript:(function(){if(window.__BB_SNIPER__){const p=document.getElementById('bb-pop');if(p)p.style.display=p.style.display==='none'?'flex':'none';return;}const s=document.createElement('script');s.src='https://jairaj26.github.io/bigbasket-deals/bb_deal_finder.min.js?t='+Date.now();s.onerror=function(){const f=document.createElement('script');f.src='https://cdn.jsdelivr.net/gh/jairaj26/bigbasket-deals@main/bb_deal_finder.min.js?t='+Date.now();document.body.appendChild(f);};document.body.appendChild(s);})();
```

*(You can also copy it with a single tap from the **[1-Click Installer Webpage](https://jairaj26.github.io/bigbasket-deals/)**).*

#### 2. Save it as a Bookmark in your Mobile Browser:
- **Chrome / Brave / Edge (Android & iOS):**
  1. Bookmark any webpage (tap `⋮` menu &rarr; tap the **⭐ Star**).
  2. Tap **Edit Bookmark** at the bottom (or open Bookmarks &rarr; tap `⋮` next to the bookmark &rarr; **Edit**).
  3. Change the **Name** to: `BB Deals`.
  4. In the **URL / Address** field: Erase everything and **paste** the copied script.
  5. Tap **Save**.

- **Safari (iPhone / iPad):**
  1. Bookmark this page (tap the Share icon &rarr; **Add Bookmark**).
  2. Open Bookmarks (book icon) &rarr; tap **Edit** (bottom-right) &rarr; tap the bookmark you just created.
  3. Rename it to `BB Deals`.
  4. Erase the URL and **paste** the copied script. Tap **Done**.

#### 3. Run on BigBasket:
1. Open [bigbasket.com](https://www.bigbasket.com).
2. Tap the browser address bar, type **`BB Deals`**, and tap the bookmark suggestion (or open Bookmarks and tap **BB Deals**).
3. The green **BB Deals** button will instantly appear!

> 💡 **Auto-Updating:** Because this script loads directly from GitHub, your bookmark will always run the newest version automatically without needing manual updates!

### 🔧 Method 3: Desktop Standalone Bookmark (Offline / No CDN)
1. Create a new bookmark on your desktop browser.
2. Copy the full standalone code from [`bookmarklet.txt`](bookmarklet.txt).
3. Paste it into the bookmark's **URL / Address** field and save.

### 🐒 Method 4: Userscript (Tampermonkey / Violentmonkey)
- Install [`bb_deal_finder.user.js`](bb_deal_finder.user.js) to have the tool auto-load every time you visit [bigbasket.com](https://www.bigbasket.com).

---

## 🚀 How to Use Manually

1. Go to [bigbasket.com](https://www.bigbasket.com) in your browser.
2. Tap / click your **`BB Deals`** bookmark or open via Tampermonkey.
3. The green **BB Deals** button appears at the bottom-right of the page. Tap it to open the category picker.
4. Select up to **2 categories** and tap **Fetch Selected**, or tap **Fetch All (20)** to scan all categories.
5. The Deals Explorer grid opens automatically with your deals sorted by highest discount!

---

## 🛠️ Development & Building

The source code is located in `bb_deal_finder.js`. To rebuild the minified bookmarklet and update `index.html`:

```bash
node build.js
```

This runs a syntax check, strips comments and whitespace, regenerates `bookmarklet.txt` and `bb_deal_finder.min.js`, and syncs `index.html`.

