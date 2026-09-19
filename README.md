# 🛒 BigBasket Deal Sniper & Explorer

A fast, lightweight, 100% client-side browser bookmarklet to find flash sales and steep discounts across BigBasket on both Desktop and Mobile.

---

## 💡 Why a Bookmarklet?

BigBasket uses Akamai Bot Manager which aggressively blocks external automated scripts and servers (403 Forbidden). 

This tool runs **directly inside your own authenticated browser session** on [bigbasket.com](https://www.bigbasket.com). It shares your real browser cookies, TLS fingerprint, and active location/pincode—meaning **zero bot blocks, zero 403 errors, and 100% live inventory accurate to your dark store**.

---

## ✨ Features

- **⚡ Fast Category Sniping:** Select up to 2 categories at a time for fast, targeted scanning without throttling.
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

## ⚡ 1-Click Install

### 💻 Method 1: Desktop (PC / Mac)
1. Open the **[1-Click Install Page](https://jairaj26.github.io/bigbasket-deals/)** in your browser.
2. Drag the green **`🛒 BB Deals`** button to your Bookmarks / Favorites bar (`Ctrl/Cmd + Shift + B`).
3. *(Pro-tip: If you use Chrome, Edge, or Safari, bookmarks auto-sync to your mobile phone when signed into your account!)*

### 📱 Method 2: Mobile (Direct Import)
1. Open **`https://jairaj26.github.io/bigbasket-deals/`** on your phone.
2. Tap **`📥 Download Mobile Bookmark (.html)`**.
3. Open your mobile browser's **Bookmarks** $\rightarrow$ tap **Import** $\rightarrow$ select the downloaded file!

### 🔧 Method 3: Manual Bookmark Creation
1. Create a new bookmark in your browser with any name (e.g. `BB Deals`).
2. Copy the entire code from [`bookmarklet.txt`](bookmarklet.txt).
3. Paste it into the bookmark's **URL / Address** field and save.

### 🐒 Method 4: Userscript (Tampermonkey / Violentmonkey)
- Install [`bb_deal_finder.user.js`](bb_deal_finder.user.js) to have the tool auto-load every time you visit [bigbasket.com](https://www.bigbasket.com).

---

## 🚀 How to Use

1. Go to [bigbasket.com](https://www.bigbasket.com) in your browser.
2. Tap / click your **`BB Deals`** bookmark.
3. The green **BB Deals** button appears at the bottom-right of the page. Tap it to open the category picker.
4. Select up to **2 categories** (e.g., *Snacks & Branded Foods*, *Detergents & Dishwash*).
5. Tap **Fetch Selected**.
6. The Deals Explorer grid opens automatically with your deals sorted by highest discount!

---

## 🛠️ Development & Building

The source code is located in `bb_deal_finder.js`. To rebuild the minified bookmarklet and update `index.html`:

```bash
node build.js
```

This runs a syntax check, strips comments and whitespace, regenerates `bookmarklet.txt` and `bb_deal_finder.min.js`, and syncs `index.html`.
