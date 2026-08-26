# 🛒 BigBasket Deal Finder

A lightweight, high-performance bookmarklet and category scanner to find flash deals across BigBasket categories on both Desktop and Mobile.

---

## ⚡ Bookmarklet Setup (100% CSP-Safe)

BigBasket enforces strict Content Security Policies (`script-src-elem`) that block scripts loaded from external CDNs like jsDelivr.

To use the bookmarklet without CSP errors, paste the direct inline JavaScript code below into your bookmark.

### 1. Create a New Bookmark
- In Chrome / Edge / Brave / Safari / Firefox, press `Ctrl + Shift + O` (or `Cmd + Shift + O` on Mac) to open Bookmark Manager.
- Add a new bookmark named **🛒 BB Deals**.

### 2. Set the Bookmark URL
Copy and paste the entire code from **[`bookmarklet.txt`](./bookmarklet.txt)** into the **URL** field of the bookmark.

---

## 🚀 How to Run
1. Go to [bigbasket.com](https://www.bigbasket.com).
2. Click your **🛒 BB Deals** bookmark.
3. The floating action button (FAB) will appear at the bottom-right.
4. Select your categories → click **⚡ Fetch** → click **🖥️ View Items in New Tab** to explore the deals!

---

## ✨ Features
- **Guaranteed Page 1 for All Categories:** Page 1 items are always captured for every selected category.
- **Smart 50% Pagination:** Automatically fetches Page 2+ only if all items on the current page have $\ge 50\%$ OFF.
- **Mobile & Desktop FAB:** Sleek floating button that expands into a categories drawer.
- **Full Deals Dashboard:**
  - Real-time search across product titles and brands
  - Category filters & discount tier filters (All, $\ge 30\%$, $\ge 50\%$, $\ge 60\%$, $\ge 70\%$, $\ge 80\%$)
  - Sorting by discount %, savings (₹), and price
  - One-click **CSV Export** & **Link Copying**
