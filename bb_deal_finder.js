/**
 * BigBasket Deal Sniper (FAB Edition)
 * Works as a standalone script or bookmarklet (e.g. loaded via jsDelivr CDN)
 *
 * Features:
 * - Mobile & Desktop friendly Floating Action Button (FAB) + Popover.
 * - Categorized deal scanner with pagination & discount threshold filtering.
 * - Dynamic "Fetch" button (disabled until at least 1 category is selected).
 * - Automatic uncheck upon fetch completion.
 * - Live progress bar & status updates during network fetching.
 * - Dedicated "Open Deals in New Tab" dashboard button that appears after fetching.
 * - Fullscreen Deals Dashboard with search, category filtering, sorting, CSV export & link copying.
 */

(function () {
    'use strict';

    // Prevent multiple duplicate scripts running simultaneously
    if (window.__BB_DEAL_SNIPER_INITIALIZED__) {
        const popover = document.getElementById('bb-fab-popover');
        if (popover) {
            popover.classList.toggle('bb-show');
        }
        return;
    }
    window.__BB_DEAL_SNIPER_INITIALIZED__ = true;

    // --- Configuration ---
    const CONFIG = {
        delayMin: 800,
        delayMax: 1800,
        minDiscount: 70,
        maxPages: 6,
        getHeaders: () => ({
            "accept": "*/*",
            "content-type": "application/json",
            "x-channel": "BB-WEB",
            "x-entry-context": "bb-b2c",
            "x-entry-context-id": "100",
            "x-tracker": typeof crypto !== 'undefined' && crypto.randomUUID 
                ? crypto.randomUUID() 
                : ('bb-' + Math.random().toString(36).substring(2, 11) + '-' + Date.now())
        })
    };

    // 🎯 Explicitly Curated Categories with Mapped API Endpoint Types
    const FIXED_CATEGORIES = [
        { name: "Atta, Rice, Dal & More", slug: "2517587cs-attaricedalsmo", type: "sis" },
        { name: "Oil, Ghee & Masala", slug: "2517588cs-oilgheemasalas", type: "sis" },
        { name: "Dry Fruits & Cereals", slug: "2517573cs-dryfruitsseeds", type: "sis" },
        { name: "Dairy", slug: "2515888cs-viewallfallbac", type: "sis" },
        { name: "Bakery & Batters", slug: "2504814cs-viewallbakebat", type: "sis" },
        { name: "Hot & Cold Beverages", slug: "2513246cs-beverages", type: "sis" },
        { name: "Bath, Body & Oral Care", slug: "2517577cs-bathbodyoralca", type: "sis" },
        { name: "Hair Care", slug: "2505250cs-viewallhair", type: "sis" },
        { name: "Beauty & Cosmetics", slug: "2516515cs-beautycosmviewall", type: "sis" },
        { name: "Sauces & Spreads", slug: "2510268s-rl-breakfastsaucesspr", type: "sis" },
        { name: "Cleaners & Repellents", slug: "2517576cs-cleanersrepell", type: "sis" },
        { name: "Stationery & Books", slug: "2517600cs-stationerybook", type: "sis" },
        { name: "Sweets & Chocolates", slug: "2505617cs-viewallswecho", type: "sis" },
        { name: "Namkeen & Chips", slug: "2505649cs-viewanamkeen", type: "sis" },
        { name: "Biscuits & Cookies", slug: "2505722cs-viewallbisc", type: "sis" },
        { name: "Instant & Frozen Foods", slug: "l1-instant-frozen-foods", type: "sis" },
        { name: "Gourmet & World Food", slug: "gourmet-world-food", type: "pc" }
    ];

    // State Variables
    let allProducts = [];
    let isFetching = false;

    // --- Helpers ---
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

    const fetchJSON = async (url) => {
        try {
            const res = await fetch(url, { headers: CONFIG.getHeaders() });
            if (!res.ok) return null;
            const text = await res.text();
            return text ? JSON.parse(text) : null;
        } catch (err) {
            console.warn("[BB Sniper] Fetch failed:", err);
            return null;
        }
    };

    const processProduct = (p, catSlug, catName) => {
        const mrp = parseFloat(p.pricing?.discount?.mrp || p.pricing?.mrp || 0);
        const sp = parseFloat(p.pricing?.discount?.prim_price?.sp || p.pricing?.offer_price || 0);
        const disc = mrp > 0 && sp > 0 ? ((mrp - sp) / mrp) * 100 : 0;
        const savings = Math.max(0, mrp - sp);
        const isAvail = p.availability?.avail_status === '001';

        if (isAvail && mrp > 0 && sp > 0) {
            const productUrl = p.absolute_url 
                ? (p.absolute_url.startsWith('http') ? p.absolute_url : 'https://www.bigbasket.com' + p.absolute_url)
                : `https://www.bigbasket.com/pd/${p.id}`;

            return {
                id: p.id || Math.random().toString(36).substring(7),
                name: (p.desc || p.p_desc || 'Product') + (p.w ? ` (${p.w})` : ''),
                brand: p.brand?.name || p.p_brand || 'BigBasket',
                mrp: parseFloat(mrp.toFixed(2)),
                sp: parseFloat(sp.toFixed(2)),
                savings: parseFloat(savings.toFixed(2)),
                disc: parseFloat(disc.toFixed(1)),
                img: p.images?.[0]?.s || p.images?.[0]?.m || p.images?.[0]?.l || 'https://www.bigbasket.com/static/images/default.jpg',
                cat: catName,
                slug: catSlug,
                url: productUrl
            };
        }
        return null;
    };

    // --- Category Scanner ---
    const scanCategory = async (catSlug, onProgress) => {
        const cat = FIXED_CATEGORIES.find(c => c.slug === catSlug);
        if (!cat) return [];

        let page = 1;
        let more = true;
        let items = [];

        while (more && page <= CONFIG.maxPages) {
            if (onProgress) onProgress(`Scanning ${cat.name} (P${page})...`);

            const url = `https://www.bigbasket.com/listing-svc/v2/products?type=${cat.type}&slug=${cat.slug}&page=${page}&sort=dphtl`;
            const data = await fetchJSON(url);

            const randomDelay = Math.floor(Math.random() * (CONFIG.delayMax - CONFIG.delayMin + 1)) + CONFIG.delayMin;
            await sleep(randomDelay);

            const prods = data?.tabs?.[0]?.product_info?.products;
            if (!prods || !prods.length) {
                more = false;
                break;
            }

            let maxDiscInPage = 0;

            prods.forEach(p => {
                const parentItem = processProduct(p, cat.slug, cat.name);
                if (parentItem) {
                    items.push(parentItem);
                    if (parentItem.disc > maxDiscInPage) maxDiscInPage = parentItem.disc;
                }

                if (p.children && Array.isArray(p.children)) {
                    p.children.forEach(child => {
                        const childItem = processProduct(child, cat.slug, cat.name);
                        if (childItem) {
                            items.push(childItem);
                            if (childItem.disc > maxDiscInPage) maxDiscInPage = childItem.disc;
                        }
                    });
                }
            });

            // If the highest discount on this sorted page is less than minimum discount threshold, stop scanning further pages
            if (maxDiscInPage < CONFIG.minDiscount) {
                console.log(`[BB Sniper] Dropping ${cat.name} at P${page} (Max deal was ${maxDiscInPage.toFixed(0)}% < ${CONFIG.minDiscount}%)`);
                more = false;
            } else {
                page++;
            }
        }

        return items;
    };

    // --- Inject Styles ---
    const injectStyles = () => {
        if (document.getElementById('bb-fab-styles')) return;
        const style = document.createElement('style');
        style.id = 'bb-fab-styles';
        style.textContent = `
            /* FAB & Container */
            #bb-fab-container {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 2147483647;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                -webkit-font-smoothing: antialiased;
            }

            #bb-fab-btn {
                background: linear-gradient(135deg, #43a047, #2e7d32);
                color: #ffffff;
                border: none;
                padding: 12px 18px;
                border-radius: 50px;
                font-size: 14px;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 8px 24px rgba(46, 125, 50, 0.4);
                display: flex;
                align-items: center;
                gap: 8px;
                transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s;
                user-select: none;
            }

            #bb-fab-btn:hover {
                transform: translateY(-2px) scale(1.02);
                box-shadow: 0 12px 28px rgba(46, 125, 50, 0.5);
            }

            #bb-fab-btn:active {
                transform: scale(0.96);
            }

            .bb-fab-badge {
                background: #ffeb3b;
                color: #1b5e20;
                font-size: 11px;
                font-weight: 800;
                padding: 2px 7px;
                border-radius: 12px;
                display: none;
            }

            /* Popover Card (Desktop & Mobile) */
            #bb-fab-popover {
                position: absolute;
                bottom: 60px;
                right: 0;
                width: 340px;
                max-width: calc(100vw - 32px);
                max-height: calc(85vh - 70px);
                background: #ffffff;
                border-radius: 16px;
                box-shadow: 0 16px 40px rgba(0, 0, 0, 0.2), 0 0 0 1px rgba(0, 0, 0, 0.08);
                display: none;
                flex-direction: column;
                overflow: hidden;
                box-sizing: border-box;
                animation: bb-popover-in 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            }

            #bb-fab-popover.bb-show {
                display: flex;
            }

            @keyframes bb-popover-in {
                from { opacity: 0; transform: translateY(10px) scale(0.96); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @media (max-width: 480px) {
                #bb-fab-container {
                    bottom: 16px;
                    right: 16px;
                }
                #bb-fab-popover {
                    position: fixed;
                    bottom: 74px;
                    right: 16px;
                    left: 16px;
                    width: auto;
                    max-width: none;
                    max-height: 75vh;
                }
            }

            /* Popover Header */
            .bb-pop-header {
                background: #2e7d32;
                color: #ffffff;
                padding: 12px 16px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .bb-pop-header-title {
                font-size: 14px;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 6px;
            }

            .bb-pop-close {
                background: rgba(255, 255, 255, 0.2);
                border: none;
                color: #ffffff;
                width: 26px;
                height: 26px;
                border-radius: 50%;
                font-size: 16px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.15s;
            }

            .bb-pop-close:hover {
                background: rgba(255, 255, 255, 0.35);
            }

            /* Category Quick Actions Toolbar */
            .bb-cat-bar {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 8px 14px;
                background: #f8fafc;
                border-bottom: 1px solid #e2e8f0;
                font-size: 12px;
                color: #475569;
                font-weight: 600;
            }

            .bb-cat-links {
                display: flex;
                gap: 8px;
            }

            .bb-link-btn {
                background: none;
                border: none;
                color: #2e7d32;
                font-size: 11.5px;
                font-weight: 700;
                cursor: pointer;
                padding: 2px 4px;
                border-radius: 4px;
            }

            .bb-link-btn:hover {
                background: #e2e8f0;
            }

            /* Categories Scroll List */
            .bb-cat-list {
                padding: 8px 14px;
                overflow-y: auto;
                max-height: 240px;
                display: flex;
                flex-direction: column;
                gap: 4px;
                box-sizing: border-box;
                background: #ffffff;
            }

            .bb-cat-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 6px 4px;
                border-radius: 6px;
                cursor: pointer;
                user-select: none;
                font-size: 12.5px;
                color: #334155;
                transition: background 0.1s;
            }

            .bb-cat-item:hover {
                background: #f1f5f9;
            }

            .bb-cat-item input[type="checkbox"] {
                width: 16px;
                height: 16px;
                accent-color: #2e7d32;
                cursor: pointer;
                margin: 0;
            }

            /* Live Progress & Status Bar */
            .bb-status-box {
                padding: 8px 14px;
                background: #f8fafc;
                border-top: 1px solid #e2e8f0;
                font-size: 11.5px;
                color: #475569;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }

            .bb-status-text {
                font-weight: 600;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .bb-progress {
                height: 4px;
                background: #e2e8f0;
                border-radius: 2px;
                overflow: hidden;
                display: none;
            }

            .bb-progress-bar {
                height: 100%;
                width: 100%;
                background: #2e7d32;
                animation: bb-anim-prog 1.2s infinite ease-in-out;
                transform-origin: 0% 50%;
            }

            @keyframes bb-anim-prog {
                0% { transform: translateX(0) scaleX(0); }
                50% { transform: translateX(0) scaleX(0.5); }
                100% { transform: translateX(100%) scaleX(0.5); }
            }

            /* Bottom Action Buttons */
            .bb-actions-box {
                padding: 12px 14px;
                background: #ffffff;
                border-top: 1px solid #e2e8f0;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }

            .bb-btn-row {
                display: flex;
                gap: 8px;
            }

            .bb-btn {
                flex: 1;
                padding: 9px 12px;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 5px;
                transition: background 0.15s, opacity 0.15s, transform 0.1s;
                font-family: inherit;
            }

            .bb-btn:active {
                transform: scale(0.98);
            }

            .bb-btn:disabled {
                opacity: 0.45;
                cursor: not-allowed;
                transform: none !important;
            }

            .bb-btn-fetch {
                background: #2e7d32;
                color: #ffffff;
            }
            .bb-btn-fetch:hover:not(:disabled) {
                background: #1b5e20;
            }

            .bb-btn-all {
                background: #d32f2f;
                color: #ffffff;
            }
            .bb-btn-all:hover:not(:disabled) {
                background: #b71c1c;
            }

            .bb-btn-open-tab {
                background: linear-gradient(135deg, #1976d2, #1565c0);
                color: #ffffff;
                width: 100%;
                padding: 10px 12px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                box-shadow: 0 4px 12px rgba(25, 118, 210, 0.3);
                display: none; /* Initially hidden until items are fetched */
                border: none;
                cursor: pointer;
                align-items: center;
                justify-content: center;
                gap: 6px;
                transition: background 0.15s;
            }
            .bb-btn-open-tab:hover:not(:disabled) {
                background: linear-gradient(135deg, #1565c0, #0d47a1);
            }
        `;
        document.head.appendChild(style);
    };

    // --- Build FAB & Popover DOM ---
    const buildFABUI = () => {
        injectStyles();

        let container = document.getElementById('bb-fab-container');
        if (container) return;

        container = document.createElement('div');
        container.id = 'bb-fab-container';

        container.innerHTML = `
            <!-- Popover Dialog -->
            <div id="bb-fab-popover">
                <div class="bb-pop-header">
                    <div class="bb-pop-header-title">
                        <span>🛒</span>
                        <span>BB Deal Sniper</span>
                    </div>
                    <button class="bb-pop-close" id="bb-pop-close" title="Close">&times;</button>
                </div>

                <div class="bb-cat-bar">
                    <span id="bb-cat-selected-count">Select Categories</span>
                    <div class="bb-cat-links">
                        <button class="bb-link-btn" id="bb-sel-all">All</button>
                        <span style="color:#cbd5e1">|</span>
                        <button class="bb-link-btn" id="bb-sel-none">None</button>
                    </div>
                </div>

                <div class="bb-cat-list" id="bb-cat-list"></div>

                <div class="bb-status-box">
                    <div class="bb-status-text" id="bb-status-text">Ready to scan (≥${CONFIG.minDiscount}% OFF deals)</div>
                    <div class="bb-progress" id="bb-progress">
                        <div class="bb-progress-bar"></div>
                    </div>
                </div>

                <div class="bb-actions-box">
                    <div class="bb-btn-row">
                        <!-- Fetch is disabled until at least 1 category is selected -->
                        <button id="bb-fetch-btn" class="bb-btn bb-btn-fetch" disabled>⚡ Fetch</button>
                        <button id="bb-fetch-all-btn" class="bb-btn bb-btn-all">🚀 Fetch All</button>
                    </div>
                    <!-- Option to open in new tab (appears once items are fetched) -->
                    <button id="bb-open-tab-btn" class="bb-btn-open-tab">
                        🖥️ Open Deals in New Tab
                    </button>
                </div>
            </div>

            <!-- Floating Action Button -->
            <button id="bb-fab-btn" title="Open BB Deal Finder">
                <span>🛒 BB Deals</span>
                <span id="bb-fab-badge" class="bb-fab-badge">0</span>
            </button>
        `;

        document.body.appendChild(container);

        // Populate Categories
        const catList = document.getElementById('bb-cat-list');
        FIXED_CATEGORIES.forEach(c => {
            const item = document.createElement('label');
            item.className = 'bb-cat-item';
            item.innerHTML = `
                <input type="checkbox" value="${c.slug}" class="bb-cat-cb">
                <span>${c.name}</span>
            `;
            catList.appendChild(item);
        });

        // Setup Event Listeners
        const popover = document.getElementById('bb-fab-popover');
        const fabBtn = document.getElementById('bb-fab-btn');
        const closeBtn = document.getElementById('bb-pop-close');
        const fetchBtn = document.getElementById('bb-fetch-btn');
        const fetchAllBtn = document.getElementById('bb-fetch-all-btn');
        const openTabBtn = document.getElementById('bb-open-tab-btn');
        const selAllBtn = document.getElementById('bb-sel-all');
        const selNoneBtn = document.getElementById('bb-sel-none');

        // Toggle Popover
        fabBtn.onclick = (e) => {
            e.stopPropagation();
            popover.classList.toggle('bb-show');
        };

        closeBtn.onclick = () => {
            popover.classList.remove('bb-show');
        };

        // Update "Fetch" button state according to selected checkboxes
        const updateSelectionState = () => {
            const checkedBoxes = document.querySelectorAll('.bb-cat-cb:checked');
            const count = checkedBoxes.length;
            const countLabel = document.getElementById('bb-cat-selected-count');

            if (countLabel) {
                countLabel.innerText = count > 0 ? `${count} Selected` : 'Select Categories';
            }

            if (!isFetching) {
                fetchBtn.disabled = count === 0;
                fetchBtn.innerText = count > 0 ? `⚡ Fetch (${count})` : '⚡ Fetch';
            }
        };

        catList.addEventListener('change', (e) => {
            if (e.target.classList.contains('bb-cat-cb')) {
                updateSelectionState();
            }
        });

        selAllBtn.onclick = () => {
            if (isFetching) return;
            document.querySelectorAll('.bb-cat-cb').forEach(cb => { cb.checked = true; });
            updateSelectionState();
        };

        selNoneBtn.onclick = () => {
            if (isFetching) return;
            document.querySelectorAll('.bb-cat-cb').forEach(cb => { cb.checked = false; });
            updateSelectionState();
        };

        fetchBtn.onclick = () => handleFetch(false);
        fetchAllBtn.onclick = () => handleFetch(true);
        openTabBtn.onclick = openDashboardTab;

        // Auto-show popover initially on injection
        popover.classList.add('bb-show');
    };

    // --- State UI Update Helpers ---
    const setBusyState = (busy, statusMessage = '') => {
        isFetching = busy;
        const fetchBtn = document.getElementById('bb-fetch-btn');
        const fetchAllBtn = document.getElementById('bb-fetch-all-btn');
        const openTabBtn = document.getElementById('bb-open-tab-btn');
        const selAllBtn = document.getElementById('bb-sel-all');
        const selNoneBtn = document.getElementById('bb-sel-none');
        const checkboxes = document.querySelectorAll('.bb-cat-cb');
        const progressBar = document.getElementById('bb-progress');
        const statusText = document.getElementById('bb-status-text');

        if (statusText && statusMessage) {
            statusText.innerText = statusMessage;
        }

        if (progressBar) {
            progressBar.style.display = busy ? 'block' : 'none';
        }

        if (fetchBtn) fetchBtn.disabled = busy || document.querySelectorAll('.bb-cat-cb:checked').length === 0;
        if (fetchAllBtn) fetchAllBtn.disabled = busy;
        if (openTabBtn) openTabBtn.disabled = busy;
        if (selAllBtn) selAllBtn.disabled = busy;
        if (selNoneBtn) selNoneBtn.disabled = busy;
        checkboxes.forEach(cb => { cb.disabled = busy; });
    };

    // --- Execute Fetch ---
    const handleFetch = async (fetchAll = false) => {
        if (isFetching) return;

        let slugsToFetch = [];
        if (fetchAll) {
            slugsToFetch = FIXED_CATEGORIES.map(c => c.slug);
        } else {
            const checked = Array.from(document.querySelectorAll('.bb-cat-cb:checked'));
            slugsToFetch = checked.map(cb => cb.value);
            if (slugsToFetch.length === 0) return;
        }

        setBusyState(true, `Starting fetch for ${slugsToFetch.length} categories...`);

        // Clear previous batch products
        allProducts = [];

        for (let i = 0; i < slugsToFetch.length; i++) {
            const slug = slugsToFetch[i];
            const items = await scanCategory(slug, (msg) => {
                setBusyState(true, `[${i + 1}/${slugsToFetch.length}] ${msg}`);
            });

            if (items && items.length) {
                allProducts.push(...items);
            }
        }

        // 🎯 Once fetched, uncheck all checkboxes
        document.querySelectorAll('.bb-cat-cb').forEach(cb => {
            cb.checked = false;
        });

        // Update counts and reset busy state
        setBusyState(false, `✅ Done! Found ${allProducts.length} deals.`);

        const countLabel = document.getElementById('bb-cat-selected-count');
        if (countLabel) countLabel.innerText = 'Select Categories';

        const fetchBtn = document.getElementById('bb-fetch-btn');
        if (fetchBtn) {
            fetchBtn.disabled = true; // Disabled because no items are checked now
            fetchBtn.innerText = '⚡ Fetch';
        }

        // 🎯 Show the "Open Deals in New Tab" button once items are fetched
        const openTabBtn = document.getElementById('bb-open-tab-btn');
        if (openTabBtn) {
            if (allProducts.length > 0) {
                openTabBtn.style.display = 'flex';
                openTabBtn.innerText = `🖥️ View ${allProducts.length} Deals in New Tab ↗`;
            } else {
                openTabBtn.style.display = 'none';
            }
        }

        // Update Floating Button Badge
        const fabBadge = document.getElementById('bb-fab-badge');
        if (fabBadge) {
            fabBadge.innerText = allProducts.length;
            fabBadge.style.display = allProducts.length > 0 ? 'inline-block' : 'none';
        }
    };

    // --- Dashboard in New Tab ---
    const openDashboardTab = () => {
        if (!allProducts || allProducts.length === 0) {
            alert("No products fetched yet! Please fetch some categories first.");
            return;
        }

        const win = window.open('', '_blank');
        if (!win) {
            alert("Popup blocked! Please allow popups for BigBasket to open the dashboard tab.");
            return;
        }

        const jsonData = JSON.stringify(allProducts);

        const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛒 BigBasket Deals Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2e7d32;
            --primary-dark: #1b5e20;
            --primary-light: #e8f5e9;
            --accent-red: #e53935;
            --bg: #f8fafc;
            --surface: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --radius: 12px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -1px rgba(0,0,0,0.04);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text-main);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1440px;
            margin: 0 auto;
        }

        header {
            background: var(--surface);
            padding: 18px 22px;
            border-radius: var(--radius);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border);
            margin-bottom: 20px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }

        .brand-title {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .brand-title h1 {
            font-size: 20px;
            font-weight: 800;
            color: var(--primary-dark);
            letter-spacing: -0.5px;
        }

        .pill-count {
            background: var(--primary-light);
            color: var(--primary);
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 20px;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-action {
            background: var(--surface);
            border: 1px solid var(--border);
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-main);
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s;
            font-family: inherit;
        }

        .btn-action:hover {
            background: #f1f5f9;
            border-color: #cbd5e1;
        }

        .controls-grid {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 10px;
        }

        @media (max-width: 900px) {
            .controls-grid {
                grid-template-columns: 1fr 1fr;
            }
        }

        @media (max-width: 600px) {
            .controls-grid {
                grid-template-columns: 1fr;
            }
            body { padding: 12px; }
        }

        .search-wrapper { position: relative; }

        .search-wrapper input {
            width: 100%;
            padding: 10px 14px 10px 36px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 13.5px;
            font-family: inherit;
            outline: none;
            background: #ffffff;
            transition: border-color 0.15s;
        }

        .search-wrapper input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(46, 125, 50, 0.12);
        }

        .search-icon {
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 13px;
        }

        select {
            width: 100%;
            padding: 9px 12px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 13px;
            font-family: inherit;
            font-weight: 500;
            background: #ffffff;
            color: var(--text-main);
            outline: none;
            cursor: pointer;
        }

        select:focus {
            border-color: var(--primary);
        }

        .stats-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12.5px;
            color: var(--text-muted);
            padding: 0 4px;
            margin-bottom: 14px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 16px;
        }

        .card {
            background: var(--surface);
            border-radius: var(--radius);
            border: 1px solid var(--border);
            padding: 14px;
            display: flex;
            flex-direction: column;
            position: relative;
            box-shadow: var(--shadow-sm);
            transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s;
        }

        .card:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-lg);
            border-color: #cbd5e1;
        }

        .badge-discount {
            position: absolute;
            top: 10px;
            left: 10px;
            background: var(--accent-red);
            color: #ffffff;
            font-size: 11.5px;
            font-weight: 800;
            padding: 3px 7px;
            border-radius: 6px;
            box-shadow: 0 2px 6px rgba(229, 57, 53, 0.3);
            z-index: 2;
        }

        .badge-savings {
            position: absolute;
            top: 10px;
            right: 10px;
            background: var(--primary-light);
            color: var(--primary-dark);
            font-size: 11px;
            font-weight: 700;
            padding: 3px 7px;
            border-radius: 6px;
            z-index: 2;
        }

        .img-container {
            width: 100%;
            height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 10px;
            background: #fafafa;
            border-radius: 8px;
            overflow: hidden;
        }

        .img-container img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            transition: transform 0.2s;
        }

        .card:hover .img-container img {
            transform: scale(1.04);
        }

        .card-meta {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 4px;
        }

        .brand {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }

        .cat-tag {
            font-size: 10px;
            background: #f1f5f9;
            color: #475569;
            padding: 2px 6px;
            border-radius: 4px;
            max-width: 120px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-main);
            line-height: 1.4;
            margin-bottom: 10px;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            min-height: 36px;
        }

        .price-row {
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin-top: auto;
            margin-bottom: 10px;
        }

        .sp {
            font-size: 17px;
            font-weight: 800;
            color: var(--text-main);
        }

        .mrp {
            font-size: 12.5px;
            color: var(--text-muted);
            text-decoration: line-through;
            font-weight: 500;
        }

        .btn-buy {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            width: 100%;
            padding: 8px;
            background: var(--primary);
            color: #ffffff;
            text-decoration: none;
            border-radius: 8px;
            font-size: 12.5px;
            font-weight: 700;
            transition: background 0.15s;
        }

        .btn-buy:hover {
            background: var(--primary-dark);
        }

        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 60px 20px;
            background: var(--surface);
            border-radius: var(--radius);
            border: 1px dashed var(--border);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-top">
                <div class="brand-title">
                    <h1>🛒 BigBasket Deals Dashboard</h1>
                    <span class="pill-count" id="total-badge">0 Deals</span>
                </div>
                <div class="header-actions">
                    <button class="btn-action" id="btn-export">📥 Export CSV</button>
                    <button class="btn-action" id="btn-copy-links">🔗 Copy Links</button>
                </div>
            </div>

            <div class="controls-grid">
                <div class="search-wrapper">
                    <span class="search-icon">🔍</span>
                    <input type="text" id="search" placeholder="Search brand or product...">
                </div>

                <select id="filter-cat">
                    <option value="all">All Categories</option>
                </select>

                <select id="filter-disc">
                    <option value="0">All Discounts</option>
                    <option value="50">≥ 50% OFF</option>
                    <option value="60">≥ 60% OFF</option>
                    <option value="70">≥ 70% OFF</option>
                    <option value="80">≥ 80% OFF</option>
                </select>

                <select id="sort">
                    <option value="disc_desc">Sort: Discount % (High to Low)</option>
                    <option value="save_desc">Sort: Savings ₹ (High to Low)</option>
                    <option value="price_asc">Sort: Price (Low to High)</option>
                    <option value="price_desc">Sort: Price (High to Low)</option>
                </select>
            </div>
        </header>

        <div class="stats-bar">
            <span id="stats-showing">Showing 0 products</span>
        </div>

        <main class="grid" id="grid"></main>
    </div>

    <script>
        const products = ${jsonData};

        const catSelect = document.getElementById('filter-cat');
        const categories = [...new Set(products.map(p => p.cat))].sort();
        categories.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            catSelect.appendChild(opt);
        });

        document.getElementById('total-badge').innerText = \`\${products.length} Deals\`;

        const render = () => {
            const query = document.getElementById('search').value.toLowerCase().trim();
            const selectedCat = document.getElementById('filter-cat').value;
            const minDisc = parseFloat(document.getElementById('filter-disc').value) || 0;
            const sortMode = document.getElementById('sort').value;

            let filtered = products.filter(p => {
                const matchesQuery = !query || p.name.toLowerCase().includes(query) || p.brand.toLowerCase().includes(query);
                const matchesCat = selectedCat === 'all' || p.cat === selectedCat;
                const matchesDisc = p.disc >= minDisc;
                return matchesQuery && matchesCat && matchesDisc;
            });

            if (sortMode === 'disc_desc') filtered.sort((a, b) => b.disc - a.disc);
            else if (sortMode === 'save_desc') filtered.sort((a, b) => b.savings - a.savings);
            else if (sortMode === 'price_asc') filtered.sort((a, b) => a.sp - b.sp);
            else if (sortMode === 'price_desc') filtered.sort((a, b) => b.sp - a.sp);

            const grid = document.getElementById('grid');
            if (filtered.length === 0) {
                grid.innerHTML = \`
                    <div class="empty-state">
                        <h3 style="margin-bottom:6px; color:#334155;">No matching deals found</h3>
                        <p style="color:#64748b; font-size:13.5px;">Try changing your search keyword or discount filter.</p>
                    </div>
                \`;
            } else {
                grid.innerHTML = filtered.map(p => \`
                    <div class="card">
                        <span class="badge-discount">\${p.disc}% OFF</span>
                        <span class="badge-savings">Save ₹\${p.savings}</span>
                        <div class="img-container">
                            <img src="\${p.img}" alt="\${p.name}" loading="lazy" onerror="this.src='https://www.bigbasket.com/static/images/default.jpg'">
                        </div>
                        <div class="card-meta">
                            <span class="brand">\${p.brand}</span>
                            <span class="cat-tag" title="\${p.cat}">\${p.cat}</span>
                        </div>
                        <div class="title" title="\${p.name}">\${p.name}</div>
                        <div class="price-row">
                            <span class="sp">₹\${p.sp}</span>
                            <span class="mrp">₹\${p.mrp}</span>
                        </div>
                        <a href="\${p.url}" target="_blank" rel="noopener noreferrer" class="btn-buy">
                            View on BigBasket ↗
                        </a>
                    </div>
                \`).join('');
            }

            document.getElementById('stats-showing').innerText = \`Showing \${filtered.length} of \${products.length} products\`;
        };

        // Export to CSV
        document.getElementById('btn-export').onclick = () => {
            if (!products.length) return alert('No products to export.');
            const headers = ["ID", "Name", "Brand", "Category", "MRP", "Offer Price", "Discount %", "Savings ₹", "URL"];
            const rows = products.map(p => [
                p.id,
                \`"\${(p.name || '').replace(/"/g, '""')}"\`,
                \`"\${(p.brand || '').replace(/"/g, '""')}"\`,
                \`"\${(p.cat || '').replace(/"/g, '""')}"\`,
                p.mrp,
                p.sp,
                p.disc,
                p.savings,
                \`"\${p.url}"\`
            ]);

            const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\\n");
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "bigbasket_deals_" + new Date().toISOString().slice(0, 10) + ".csv");
            document.body.appendChild(link);
            link.click();
            link.remove();
        };

        // Copy Links
        document.getElementById('btn-copy-links').onclick = () => {
            const urls = products.map(p => \`\${p.name} (₹\${p.sp} - \${p.disc}% OFF): \${p.url}\`).join('\\n');
            navigator.clipboard.writeText(urls).then(() => {
                alert('Copied ' + products.length + ' deal links to clipboard!');
            }).catch(() => {
                alert('Failed to copy links. Please allow clipboard permissions.');
            });
        };

        document.getElementById('search').addEventListener('input', render);
        document.getElementById('filter-cat').addEventListener('change', render);
        document.getElementById('filter-disc').addEventListener('change', render);
        document.getElementById('sort').addEventListener('change', render);

        render();
    </script>
</body>
</html>`;

        win.document.open();
        win.document.write(html);
        win.document.close();
    };

    // Initialize FAB
    buildFABUI();
    console.log("🛒 BigBasket Deal Sniper (FAB) Loaded Successfully!");
})();
