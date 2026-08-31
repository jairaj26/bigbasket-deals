/**
 * BigBasket Deal Sniper (Reliable Fetch & Anti-Throttling Edition)
 * - Retries on rate-limiting / failed requests
 * - Respectful pacing between category requests to prevent Akamai throttling
 * - Composite deduplication to prevent cross-category item drops
 * - Live category item counters in status bar
 */
(function () {
    'use strict';

    if (window.__BB_SNIPER__) {
        const p = document.getElementById('bb-pop');
        if (p) p.style.display = p.style.display === 'none' ? 'flex' : 'none';
        return;
    }
    window.__BB_SNIPER__ = true;

    const CFG = {
        minD: 50,
        maxP: 6,
        dMin: 400,
        dMax: 800,
        hdrs: () => ({
            "accept": "*/*",
            "content-type": "application/json",
            "x-channel": "BB-WEB",
            "x-entry-context": "bb-b2c",
            "x-entry-context-id": "100",
            "x-tracker": typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : ('bb-' + Date.now())
        })
    };

    // Clean Master Categories & Top High-Deal Sub-Aisles
    const CATS = [
        "Baby Care|baby-care|pc",
        "Diapers & Wipes|diapers-wipes|pc",
        "Snacks & Branded Foods|snacks-branded-foods|pc",
        "Biscuits & Cookies|biscuits-cookies|pc",
        "Chocolates & Candies|chocolates-candies|pc",
        "Foodgrains, Oil & Masala|foodgrains-oil-masala|pc",
        "Edible Oils & Ghee|edible-oils-ghee|pc",
        "Dry Fruits|dry-fruits|pc",
        "Bakery, Cakes & Dairy|bakery-cakes-dairy|pc",
        "Dairy|dairy|pc",
        "Beverages (Tea/Coffee)|beverages|pc",
        "Beauty & Hygiene|beauty-hygiene|pc",
        "Skin Care|skin-care|pc",
        "Hair Care|hair-care|pc",
        "Bath & Hand Wash|bath-hand-wash|pc",
        "Cleaning & Household|cleaning-household|pc",
        "Detergents & Dishwash|detergents-dishwash|pc",
        "Gourmet & World Food|gourmet-world-food|pc",
        "Kitchen & Home Needs|kitchen-garden-pets|pc",
        "Fruits & Vegetables|fruits-vegetables|pc"
    ].map(s => {
        const [n, slug, t] = s.split('|');
        return { name: n, slug, type: t || 'pc' };
    });

    let prods = [];
    let isFetching = false;

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    // Resilient fetch with automatic retry on rate limiting
    const fetchJSON = async (url, retries = 2) => {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const res = await fetch(url, { headers: CFG.hdrs() });
                if (res.ok) {
                    const data = await res.json();
                    if (data) return data;
                } else if (res.status === 429 || res.status === 503) {
                    await sleep(600 * (attempt + 1));
                    continue;
                }
            } catch (err) {
                if (attempt === retries) return null;
                await sleep(500 * (attempt + 1));
            }
        }
        return null;
    };

    const getItems = (d) => {
        if (!d) return [];
        if (d.tabs && Array.isArray(d.tabs)) {
            for (const t of d.tabs) {
                if (t?.product_info?.products?.length) return t.product_info.products;
            }
        }
        return d.product_info?.products || (Array.isArray(d.products) ? d.products : []);
    };

    const parseProduct = (p, catName) => {
        if (!p) return null;
        const mrp = parseFloat(p.pricing?.discount?.mrp || p.pricing?.mrp || p.mrp || 0);
        let sp = parseFloat(p.pricing?.discount?.prim_price?.sp || p.pricing?.offer_price || p.pricing?.sp || p.sp || 0);
        if (sp <= 0 && mrp > 0) sp = mrp;
        const disc = mrp > 0 && sp > 0 ? ((mrp - sp) / mrp) * 100 : 0;
        const sav = Math.max(0, mrp - sp);

        // Detect Flash Sale & Liquidation deals
        const isFlash = (p.pricing?.offer?.campaign_type === 'HO-Liquidation' ||
            p.pricing?.offer?.offer_entry_text === 'Flash Sale!' ||
            p.pricing?.offer?.campaign_type_slug === 'HO-Liquidation' ||
            p.sku_deck_type === 'discounts_deck');

        if (mrp > 0 || sp > 0) {
            const url = p.absolute_url ? (p.absolute_url.startsWith('http') ? p.absolute_url : 'https://www.bigbasket.com' + p.absolute_url) : `https://www.bigbasket.com/pd/${p.id || ''}`;
            return {
                id: String(p.id || Math.random().toString(36).substring(7)),
                name: (p.desc || p.p_desc || p.name || 'Product') + (p.w ? ` (${p.w})` : ''),
                brand: p.brand?.name || p.p_brand || 'BigBasket',
                mrp: parseFloat(mrp.toFixed(2)),
                sp: parseFloat(sp.toFixed(2)),
                sav: parseFloat(sav.toFixed(2)),
                disc: parseFloat(disc.toFixed(1)),
                isFlash: !!isFlash,
                img: p.images?.[0]?.s || p.images?.[0]?.m || 'https://www.bigbasket.com/static/images/default.jpg',
                cat: catName,
                url
            };
        }
        return null;
    };

    const handlePage = (data, catName) => {
        const list = getItems(data);
        let pageItems = [];
        list.forEach(p => {
            const item = parseProduct(p, catName);
            if (item) pageItems.push(item);
            if (p.children && Array.isArray(p.children)) {
                p.children.forEach(c => {
                    const ci = parseProduct(c, catName);
                    if (ci) pageItems.push(ci);
                });
            }
        });
        return pageItems;
    };

    const scanCategory = async (cat, onProg) => {
        let res = [];
        let curType = cat.type;

        if (onProg) onProg(`Scanning ${cat.name}...`);

        const makeUrl = (type, slug, page) => `https://www.bigbasket.com/listing-svc/v2/products?type=${type}&slug=${slug}&page=${page}&sort=dphtl`;

        // 1. Fetch Page 1
        let data1 = await fetchJSON(makeUrl(curType, cat.slug, 1));
        let p1Items = handlePage(data1, cat.name);

        // Fallback endpoint if Page 1 is empty
        if (!p1Items.length) {
            const fallbacks = ['ps', 'sis', 'cl'].filter(t => t !== curType);
            for (const alt of fallbacks) {
                const altData = await fetchJSON(makeUrl(alt, cat.slug, 1));
                const items = handlePage(altData, cat.name);
                if (items.length) {
                    p1Items = items;
                    curType = alt;
                    break;
                }
            }
        }

        res.push(...p1Items);

        // 2. Fetch Page 2 with pacing delay
        await sleep(Math.floor(Math.random() * (CFG.dMax - CFG.dMin + 1)) + CFG.dMin);
        let data2 = await fetchJSON(makeUrl(curType, cat.slug, 2));
        let p2Items = handlePage(data2, cat.name);
        res.push(...p2Items);

        // 3. Continue to Page 3+ only if Page 2 ended with high discount >= minD%
        let page = 3;
        let more = p2Items.length > 0 && p2Items[p2Items.length - 1]?.disc >= CFG.minD;

        while (more && page <= CFG.maxP) {
            if (onProg) onProg(`Scanning ${cat.name} (P${page})...`);
            await sleep(Math.floor(Math.random() * (CFG.dMax - CFG.dMin + 1)) + CFG.dMin);
            const data = await fetchJSON(makeUrl(curType, cat.slug, page));
            const items = handlePage(data, cat.name);
            if (items.length) {
                res.push(...items);
                more = items[items.length - 1]?.disc >= CFG.minD;
                page++;
            } else {
                more = false;
            }
        }

        return res;
    };

    const injectCSS = () => {
        if (document.getElementById('bb-css')) return;
        const s = document.createElement('style');
        s.id = 'bb-css';
        s.textContent = `
            #bb-wrap{position:fixed;bottom:20px;right:20px;z-index:2147483640;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;}
            #bb-fab{background:#2e7d32;color:#fff;border:none;padding:12px 18px;border-radius:50px;font-size:14px;font-weight:700;cursor:pointer;box-shadow:0 8px 24px rgba(46,125,50,0.4);display:flex;align-items:center;gap:6px;}
            #bb-pop{position:absolute;bottom:60px;right:0;width:320px;max-width:calc(100vw - 32px);max-height:80vh;background:#fff;border-radius:16px;box-shadow:0 16px 40px rgba(0,0,0,0.2),0 0 0 1px rgba(0,0,0,0.08);display:flex;flex-direction:column;overflow:hidden;}
            @media(max-width:480px){#bb-pop{position:fixed;bottom:74px;right:16px;left:16px;width:auto;}}
            .bb-hd{background:#2e7d32;color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;font-size:14px;font-weight:700;}
            .bb-hd button{background:rgba(255,255,255,0.2);border:none;color:#fff;width:24px;height:24px;border-radius:50%;cursor:pointer;}
            .bb-tb{display:flex;justify-content:space-between;padding:8px 14px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px;font-weight:600;color:#475569;}
            .bb-tb button{background:none;border:none;color:#2e7d32;font-weight:700;cursor:pointer;font-size:11.5px;}
            .bb-list{padding:8px 14px;overflow-y:auto;max-height:220px;display:flex;flex-direction:column;gap:3px;}
            .bb-item{display:flex;align-items:center;gap:10px;padding:4px 0;font-size:12.5px;color:#334155;cursor:pointer;}
            .bb-item input{accent-color:#2e7d32;width:15px;height:15px;}
            .bb-st{padding:8px 14px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11.5px;color:#475569;font-weight:600;}
            .bb-acts{padding:12px 14px;background:#fff;border-top:1px solid #e2e8f0;display:flex;flex-direction:column;gap:8px;}
            .bb-row{display:flex;gap:8px;}
            .bb-btn{flex:1;padding:9px 12px;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;}
            .bb-btn:disabled{opacity:0.45;cursor:not-allowed;}
            .bb-btn-f{background:#2e7d32;color:#fff;}
            #bb-btn-a{background:#d32f2f;color:#fff;}
            .bb-btn-m{background:#1976d2;color:#fff;width:100%;padding:10px;display:none;box-shadow:0 4px 12px rgba(25,118,210,0.3);}
            
            #bb-modal{position:fixed;top:0;left:0;width:100%;height:100%;background:#f8fafc;z-index:2147483646;display:none;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:#0f172a;}
            .bb-m-top{background:#fff;padding:14px 20px;border-bottom:1px solid #e2e8f0;display:flex;flex-direction:column;gap:10px;position:sticky;top:0;z-index:10;}
            .bb-m-th{display:flex;justify-content:space-between;align-items:center;}
            .bb-m-th h2{font-size:18px;color:#1b5e20;margin:0;}
            .bb-m-cls{background:#e2e8f0;border:none;color:#334155;padding:6px 12px;border-radius:6px;font-weight:700;cursor:pointer;}
            .bb-m-ctrl{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;}
            @media(max-width:600px){.bb-m-ctrl{grid-template-columns:1fr;}}
            .bb-m-ctrl input,.bb-m-ctrl select{padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;}
            .bb-m-body{flex:1;overflow-y:auto;padding:20px;}
            .bb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;}
            .bb-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px;display:flex;flex-direction:column;position:relative;}
            .bb-card:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(0,0,0,0.06);}
            .bb-bdg{position:absolute;top:10px;left:10px;background:#e53935;color:#fff;font-size:11px;font-weight:800;padding:3px 7px;border-radius:6px;}
            .bb-bdg.flash{background:#d97706;}
            .bb-bdg.low{background:#4b5563;}
            .bb-sav{position:absolute;top:10px;right:10px;background:#e8f5e9;color:#1b5e20;font-size:11px;font-weight:700;padding:3px 7px;border-radius:6px;}
            #bb-img{width:100%;height:130px;display:flex;align-items:center;justify-content:center;background:#fafafa;border-radius:8px;margin-bottom:8px;}
            .bb-img img{max-width:100%;max-height:100%;object-fit:contain;}
            .bb-meta{display:flex;justify-content:space-between;font-size:10.5px;color:#64748b;font-weight:700;text-transform:uppercase;margin-bottom:4px;}
            .bb-ttl{font-size:12.5px;font-weight:600;color:#0f172a;line-height:1.4;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:35px;}
            .bb-prc{display:flex;align-items:baseline;gap:8px;margin-top:auto;margin-bottom:8px;}
            .bb-sp{font-size:16px;font-weight:800;color:#0f172a;}
            #bb-mrp{font-size:12px;color:#94a3b8;text-decoration:line-through;}
            .bb-buy{display:block;text-align:center;padding:8px;background:#2e7d32;color:#fff;text-decoration:none;border-radius:8px;font-size:12px;font-weight:700;}
            .bb-buy:hover{background:#1b5e20;}
        `;
        document.head.appendChild(s);
    };

    const buildUI = () => {
        injectCSS();
        if (document.getElementById('bb-wrap')) return;

        const w = document.createElement('div');
        w.id = 'bb-wrap';
        w.innerHTML = `
            <div id="bb-pop">
                <div class="bb-hd">
                    <span>BB Deal Sniper</span>
                    <button id="bb-cls">X</button>
                </div>
                <div class="bb-tb">
                    <span id="bb-lbl">Select Categories</span>
                    <div>
                        <button id="bb-all">All</button> | <button id="bb-none">None</button>
                    </div>
                </div>
                <div class="bb-list" id="bb-list"></div>
                <div class="bb-st" id="bb-st">Ready to scan categories</div>
                <div class="bb-acts">
                    <div class="bb-row">
                        <button id="bb-f" class="bb-btn bb-btn-f" disabled>Fetch</button>
                        <button id="bb-a" class="bb-btn bb-btn-a">Fetch All</button>
                    </div>
                    <button id="bb-m-btn" class="bb-btn bb-btn-m">View Deals Grid ></button>
                </div>
            </div>
            <button id="bb-fab">BB Deals</button>
        `;
        document.body.appendChild(w);

        const m = document.createElement('div');
        m.id = 'bb-modal';
        m.innerHTML = `
            <div class="bb-m-top">
                <div class="bb-m-th">
                    <h2>BigBasket Deals Explorer</h2>
                    <button class="bb-m-cls" id="bb-m-cls">Close</button>
                </div>
                <div class="bb-m-ctrl">
                    <input type="text" id="bb-q" placeholder="Search brand or product...">
                    <select id="bb-fc"><option value="all">All Categories</option></select>
                    <select id="bb-fd">
                        <option value="0">All Discounts (Show All)</option>
                        <option value="flash">Flash / Clearance Only</option>
                        <option value="30">>= 30% OFF</option>
                        <option value="50">>= 50% OFF</option>
                        <option value="60">>= 60% OFF</option>
                        <option value="70">>= 70% OFF</option>
                        <option value="80">>= 80% OFF</option>
                    </select>
                </div>
            </div>
            <div class="bb-m-body">
                <div id="bb-stat" style="font-size:12.5px;color:#64748b;margin-bottom:14px;font-weight:600;"></div>
                <div class="bb-grid" id="bb-grid"></div>
            </div>
        `;
        document.body.appendChild(m);

        const list = document.getElementById('bb-list');
        CATS.forEach(c => {
            const el = document.createElement('label');
            el.className = 'bb-item';
            el.innerHTML = `<input type="checkbox" value="${c.slug}" class="bb-cb"> <span>${c.name}</span>`;
            list.appendChild(el);
        });

        const pop = document.getElementById('bb-pop');
        const fBtn = document.getElementById('bb-f');
        const aBtn = document.getElementById('bb-a');
        const mBtn = document.getElementById('bb-m-btn');
        const lbl = document.getElementById('bb-lbl');
        const st = document.getElementById('bb-st');

        document.getElementById('bb-fab').onclick = () => {
            pop.style.display = pop.style.display === 'none' ? 'flex' : 'none';
        };
        document.getElementById('bb-cls').onclick = () => { pop.style.display = 'none'; };

        const updateState = () => {
            const cnt = document.querySelectorAll('.bb-cb:checked').length;
            lbl.innerText = cnt > 0 ? `${cnt} Selected` : 'Select Categories';
            if (!isFetching) {
                fBtn.disabled = cnt === 0;
                fBtn.innerText = cnt > 0 ? `Fetch (${cnt})` : 'Fetch';
            }
        };

        list.addEventListener('change', updateState);
        document.getElementById('bb-all').onclick = () => {
            if (isFetching) return;
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.checked = true; });
            updateState();
        };
        document.getElementById('bb-none').onclick = () => {
            if (isFetching) return;
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.checked = false; });
            updateState();
        };

        const setBusy = (busy, msg = '') => {
            isFetching = busy;
            if (msg) st.innerText = msg;
            fBtn.disabled = busy || document.querySelectorAll('.bb-cb:checked').length === 0;
            aBtn.disabled = busy;
            mBtn.disabled = busy;
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.disabled = busy; });
        };

        const runFetch = async (all = false) => {
            if (isFetching) return;
            const slugs = all ? CATS.map(c => c.slug) : Array.from(document.querySelectorAll('.bb-cb:checked')).map(cb => cb.value);
            if (!slugs.length) return;

            setBusy(true, `Starting scan for ${slugs.length} categories...`);
            prods = [];

            for (let i = 0; i < slugs.length; i++) {
                const c = CATS.find(x => x.slug === slugs[i]);
                if (c) {
                    const items = await scanCategory(c, (m) => setBusy(true, `[${i + 1}/${slugs.length}] ${m}`));
                    if (items.length) {
                        prods.push(...items);
                        setBusy(true, `[${i + 1}/${slugs.length}] ${c.name}: +${items.length} items`);
                    }
                    // Respectful pacing between categories
                    await sleep(350);
                }
            }

            // Deduplicate across (id + cat) so cross-category products aren't dropped
            const seen = new Set();
            prods = prods.filter(p => {
                const key = `${p.id}-${p.cat}`;
                return seen.has(key) ? false : seen.add(key);
            });

            document.querySelectorAll('.bb-cb').forEach(cb => { cb.checked = false; });
            const catsCount = new Set(prods.map(p => p.cat)).size;

            setBusy(false, `Done! Found ${prods.length} items across ${catsCount} categories.`);
            lbl.innerText = 'Select Categories';
            fBtn.disabled = true;
            fBtn.innerText = 'Fetch';

            if (prods.length > 0) {
                mBtn.style.display = 'flex';
                mBtn.innerText = `View ${prods.length} Deals Grid >`;
                openModal();
            }
        };

        fBtn.onclick = () => runFetch(false);
        aBtn.onclick = () => runFetch(true);

        const openModal = () => {
            if (!prods.length) return alert('No products fetched yet!');
            const fc = document.getElementById('bb-fc');
            fc.innerHTML = '<option value="all">All Categories</option>';
            [...new Set(prods.map(p => p.cat))].sort().forEach(c => {
                fc.innerHTML += `<option value="${c}">${c}</option>`;
            });

            m.style.display = 'flex';
            renderModal();
        };

        const renderModal = () => {
            const q = document.getElementById('bb-q').value.toLowerCase().trim();
            const c = document.getElementById('bb-fc').value;
            const filterVal = document.getElementById('bb-fd').value;

            let filtered = prods.filter(p => {
                const matchQ = !q || p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q);
                const matchC = c === 'all' || p.cat === c;
                let matchD = true;
                if (filterVal === 'flash') {
                    matchD = p.isFlash;
                } else {
                    matchD = p.disc >= (parseFloat(filterVal) || 0);
                }
                return matchQ && matchC && matchD;
            });

            filtered.sort((a, b) => b.disc - a.disc);

            document.getElementById('bb-stat').innerText = `Showing ${filtered.length} of ${prods.length} items across ${new Set(prods.map(p => p.cat)).size} categories`;
            document.getElementById('bb-grid').innerHTML = filtered.map(p => `
                <div class="bb-card">
                    <span class="bb-bdg ${p.isFlash ? 'flash' : (p.disc < 50 ? 'low' : '')}">${p.isFlash ? 'FLASH ' : ''}${p.disc}% OFF</span>
                    <span class="bb-sav">Save Rs.${p.sav}</span>
                    <div class="bb-img"><img src="${p.img}" loading="lazy" onerror="this.src='https://www.bigbasket.com/static/images/default.jpg'"></div>
                    <div class="bb-meta"><span>${p.brand}</span><span>${p.cat}</span></div>
                    <div class="bb-ttl" title="${p.name}">${p.name}</div>
                    <div class="bb-prc"><span class="bb-sp">Rs.${p.sp}</span><span class="bb-mrp">Rs.${p.mrp}</span></div>
                    <a href="${p.url}" target="_blank" class="bb-buy">View on BigBasket ></a>
                </div>
            `).join('');
        };

        mBtn.onclick = openModal;
        document.getElementById('bb-m-cls').onclick = () => { m.style.display = 'none'; };
        document.getElementById('bb-q').oninput = renderModal;
        document.getElementById('bb-fc').onchange = renderModal;
        document.getElementById('bb-fd').onchange = renderModal;
    };

    buildUI();
})();
