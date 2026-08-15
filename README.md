# 🛒 BigBasket Deal Finder

A lightweight, high-performance bookmarklet and category scanner to find the best flash deals (≥70% OFF) across BigBasket categories on both Desktop and Mobile.

---

## ⚡ Quick Bookmarklet Setup

### 1. Create a New Bookmark
- In Chrome / Edge / Brave / Safari / Firefox, press `Ctrl + Shift + O` (or `Cmd + Shift + O` on Mac) to open Bookmark Manager.
- Add a new bookmark named **🛒 BB Deals**.

### 2. Set the Bookmark URL
Copy and paste the following snippet into the **URL** field:

```javascript
javascript:(function(){const s=document.createElement('script');s.src='https://cdn.jsdelivr.net/gh/JairamS/BigBasket@main/bb_deal_finder.js?t='+Date.now();document.body.appendChild(s);})();
```

> **Note:** The `?t=...` cache-buster parameter ensures you always fetch the latest version of the script.

### 3. Run on BigBasket
1. Visit [bigbasket.com](https://www.bigbasket.com).
2. Click your **🛒 BB Deals** bookmark.
3. The floating action button (FAB) will appear at the bottom right. Select your desired categories, hit **⚡ Fetch**, and click **🖥️ View Deals in New Tab** to explore deals!

---

## ✨ Features
- **Mobile & Desktop Ready:** Sleek Floating Action Button (FAB) that expands into a category menu.
- **Smart Category Scanning:** Scans curated categories with automatic pagination and discount threshold cutoffs.
- **Dynamic Button Control:** "Fetch" button enables dynamically when at least 1 category is selected.
- **Auto-Uncheck on Complete:** Automatically resets category checkboxes after fetching.
- **Full Deals Dashboard:** Opens fetched items in an interactive new tab with:
  - Real-time search across product titles and brands
  - Category filters & discount filters
  - Sorting by discount %, savings (₹), and price
  - One-click **CSV Export** & **Link Copying**
