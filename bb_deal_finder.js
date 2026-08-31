/**
 * BigBasket Deal Sniper
 */
(function () {
    'use strict';

    if (window.__BB_SNIPER__) {
        const p = document.getElementById('bb-pop');
        if (p) p.style.display = p.style.display === 'none' ? 'flex' : 'none';
        return;
    }
    window.__BB_SNIPER__ = true;

    const SESSION_TRACKER = (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : ('bb-' + Date.now()));

    const CFG = {
        maxCats: 2,
        minD: 50,
        maxP: 4,
        dMin: 800,
        dMax: 1200,
        hdrs: () => ({
            "accept": "*/*",
            "content-type": "application/json",
            "x-channel": "BB-WEB",
            "x-entry-context": "bb-b2c",
            "x-entry-context-id": "100",
            "x-tracker": SESSION_TRACKER
        })
    };

    const CATS = [
        "Baby Care|baby-care",
        "Diapers & Wipes|diapers-wipes",
        "Snacks & Branded Foods|snacks-branded-foods",
        "Biscuits & Cookies|biscuits-cookies",
        "Chocolates & Candies|chocolates-candies",
        "Foodgrains, Oil & Masala|foodgrains-oil-masala",
        "Edible Oils & Ghee|edible-oils-ghee",
        "Dry Fruits|dry-fruits",
        "Bakery, Cakes & Dairy|bakery-cakes-dairy",
        "Dairy|dairy",
        "Beverages (Tea/Coffee)|beverages",
        "Beauty & Hygiene|beauty-hygiene",
        "Skin Care|skin-care",
        "Hair Care|hair-care",
        "Bath & Hand Wash|bath-hand-wash",
        "Cleaning & Household|cleaning-household",
        "Detergents & Dishwash|detergents-dishwash",
        "Gourmet & World Food|gourmet-world-food",
        "Kitchen & Home Needs|kitchen-garden-pets",
        "Fruits & Vegetables|fruits-vegetables"
    ].map(s => {
        const [n, slug] = s.split('|');
        return { name: n, slug, type: 'pc' };
    });

    let prods = [];
    let isFetching = false;

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    const fetchJSON = async (url) => {
        try {
            const res = await fetch(url, { headers: CFG.hdrs() });
            if (res.ok) return await res.json();
            if (res.status === 429) {
                await sleep(1500);
                const retryRes = await fetch(url, { headers: CFG.hdrs() });
                if (retryRes.ok) return await retryRes.json();
            }
        } catch { }
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
        const makeUrl = (page) => `https://www.bigbasket.com/listing-svc/v2/products?type=pc&slug=${cat.slug}&page=${page}&sort=dphtl`;

        if (onProg) onProg(`Scanning ${cat.name} (Page 1)...`);
        let data1 = await fetchJSON(makeUrl(1));
        let p1Items = handlePage(data1, cat.name);
        res.push(...p1Items);

        await sleep(Math.floor(Math.random() * (CFG.dMax - CFG.dMin + 1)) + CFG.dMin);

        if (onProg) onProg(`Scanning ${cat.name} (Page 2)...`);
        let data2 = await fetchJSON(makeUrl(2));
        let p2Items = handlePage(data2, cat.name);
        res.push(...p2Items);

        let page = 3;
        let more = p2Items.length > 0 && p2Items[p2Items.length - 1]?.disc >= CFG.minD;

        while (more && page <= CFG.maxP) {
            if (onProg) onProg(`Scanning ${cat.name} (Page ${page})...`);
            await sleep(Math.floor(Math.random() * (CFG.dMax - CFG.dMin + 1)) + CFG.dMin);
            const data = await fetchJSON(makeUrl(page));
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
            .bb-item.disabled{opacity:0.35;cursor:not-allowed;}
            .bb-st{padding:8px 14px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11.5px;color:#475569;font-weight:600;}
            .bb-acts{padding:12px 14px;background:#fff;border-top:1px solid #e2e8f0;display:flex;flex-direction:column;gap:8px;}
            .bb-btn{width:100%;padding:10px 14px;border:none;border-radius:8px;font-size:13.5px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;}
            .bb-btn:disabled{opacity:0.45;cursor:not-allowed;}
            .bb-btn-f{background:#2e7d32;color:#fff;}
            .bb-btn-m{background:#1976d2;color:#fff;display:none;box-shadow:0 4px 12px rgba(25,118,210,0.3);}
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
            .bb-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px;display:flex;flex-direction:column;position:relative;text-decoration:none;color:inherit;cursor:pointer;transition:transform 0.15s,box-shadow 0.15s,border-color 0.15s;}
            .bb-card:hover{transform:translateY(-3px);box-shadow:0 10px 24px rgba(0,0,0,0.08);border-color:#94a3b8;}
            .bb-bdg{position:absolute;top:10px;left:10px;background:#2e7d32;color:#fff;border-radius:6px;padding:4px 6px;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;text-align:center;min-width:34px;box-shadow:0 2px 6px rgba(46,125,50,0.25);}
            .bb-bdg-val{font-size:11.5px;font-weight:800;}
            .bb-bdg-txt{font-size:8.5px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;}
            .bb-sav{position:absolute;top:10px;right:10px;background:#e8f5e9;color:#1b5e20;font-size:11px;font-weight:700;padding:3px 7px;border-radius:6px;}
            #bb-img{width:100%;height:130px;display:flex;align-items:center;justify-content:center;background:#fafafa;border-radius:8px;margin-bottom:8px;}
            .bb-img img{max-width:100%;max-height:100%;object-fit:contain;}
            .bb-meta{display:flex;justify-content:space-between;font-size:10.5px;color:#64748b;font-weight:700;text-transform:uppercase;margin-bottom:4px;}
            .bb-ttl{font-size:12.5px;font-weight:600;color:#0f172a;line-height:1.4;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:35px;}
            .bb-prc{display:flex;align-items:baseline;gap:8px;margin-top:auto;}
            .bb-sp{font-size:16px;font-weight:800;color:#0f172a;}
            #bb-mrp{font-size:12px;color:#94a3b8;text-decoration:line-through;}
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
                    <span id="bb-lbl">Pick 1 or 2 Categories</span>
                    <div>
                        <button id="bb-none">Clear</button>
                    </div>
                </div>
                <div class="bb-list" id="bb-list"></div>
                <div class="bb-st" id="bb-st">Select up to 2 categories to scan</div>
                <div class="bb-acts">
                    <button id="bb-f" class="bb-btn bb-btn-f" disabled>Fetch Deals</button>
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
                    <select id="bb-st">
                        <option value="d">Sort: Highest Discount %</option>
                        <option value="pa">Sort: Price Low to High</option>
                        <option value="pd">Sort: Price High to Low</option>
                        <option value="s">Sort: Biggest Rupee Savings</option>
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
        const mBtn = document.getElementById('bb-m-btn');
        const lbl = document.getElementById('bb-lbl');

        document.getElementById('bb-fab').onclick = () => {
            pop.style.display = pop.style.display === 'none' ? 'flex' : 'none';
        };
        document.getElementById('bb-cls').onclick = () => { pop.style.display = 'none'; };

        const updateState = () => {
            const checked = document.querySelectorAll('.bb-cb:checked');
            const cnt = checked.length;

            lbl.innerText = cnt > 0 ? `${cnt}/${CFG.maxCats} Selected` : `Pick 1 or 2 Categories`;

            document.querySelectorAll('.bb-cb').forEach(cb => {
                if (!cb.checked) {
                    cb.disabled = cnt >= CFG.maxCats;
                    cb.parentElement.classList.toggle('disabled', cnt >= CFG.maxCats);
                } else {
                    cb.disabled = false;
                    cb.parentElement.classList.remove('disabled');
                }
            });

            if (!isFetching) {
                fBtn.disabled = cnt === 0;
                fBtn.innerText = cnt > 0 ? `Fetch (${cnt} ${cnt === 1 ? 'Category' : 'Categories'})` : 'Fetch Deals';
            }
        };

        list.addEventListener('change', updateState);

        document.getElementById('bb-none').onclick = () => {
            if (isFetching) return;
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.checked = false; });
            updateState();
        };

        const setBusy = (busy, msg = '') => {
            isFetching = busy;
            const statusEl = document.getElementById('bb-st');
            if (statusEl && msg) statusEl.innerText = msg;
            fBtn.disabled = busy || document.querySelectorAll('.bb-cb:checked').length === 0;
            mBtn.disabled = busy;
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.disabled = busy; });
        };

        const runFetch = async () => {
            if (isFetching) return;
            const slugs = Array.from(document.querySelectorAll('.bb-cb:checked')).map(cb => cb.value).slice(0, CFG.maxCats);
            if (!slugs.length) return;

            setBusy(true, `Starting paced scan for ${slugs.length} categories...`);
            prods = [];

            for (let i = 0; i < slugs.length; i++) {
                const c = CATS.find(x => x.slug === slugs[i]);
                if (c) {
                    const items = await scanCategory(c, (m) => setBusy(true, `[${i + 1}/${slugs.length}] ${m}`));
                    if (items.length) {
                        prods.push(...items);
                        setBusy(true, `[${i + 1}/${slugs.length}] ${c.name}: +${items.length} items`);
                    }
                    if (i < slugs.length - 1) {
                        await sleep(900);
                    }
                }
            }

            const seen = new Set();
            prods = prods.filter(p => {
                const key = `${p.id}-${p.cat}`;
                return seen.has(key) ? false : seen.add(key);
            });

            document.querySelectorAll('.bb-cb').forEach(cb => { cb.checked = false; });
            updateState();

            const catsCount = new Set(prods.map(p => p.cat)).size;
            setBusy(false, `Done! Found ${prods.length} items across ${catsCount} categories.`);

            fBtn.disabled = true;
            fBtn.innerText = 'Fetch Deals';

            if (prods.length > 0) {
                mBtn.style.display = 'flex';
                mBtn.innerText = `View ${prods.length} Deals Grid >`;
                openModal();
            }
        };

        fBtn.onclick = runFetch;

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
            const sortMode = document.getElementById('bb-st').value;

            let filtered = prods.filter(p => {
                const matchQ = !q || p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q);
                const matchC = c === 'all' || p.cat === c;
                return matchQ && matchC;
            });

            if (sortMode === 'pa') {
                filtered.sort((a, b) => a.sp - b.sp);
            } else if (sortMode === 'pd') {
                filtered.sort((a, b) => b.sp - a.sp);
            } else if (sortMode === 's') {
                filtered.sort((a, b) => b.sav - a.sav);
            } else {
                filtered.sort((a, b) => b.disc - a.disc);
            }

            document.getElementById('bb-stat').innerText = `Showing ${filtered.length} of ${prods.length} items across ${new Set(prods.map(p => p.cat)).size} categories`;
            document.getElementById('bb-grid').innerHTML = filtered.map(p => `
                <a href="${p.url}" target="_blank" class="bb-card">
                    <div class="bb-bdg">
                        <span class="bb-bdg-val">${p.disc}%</span>
                        <span class="bb-bdg-txt">OFF</span>
                    </div>
                    <span class="bb-sav">Save Rs.${p.sav}</span>
                    <div class="bb-img"><img src="${p.img}" loading="lazy" onerror="this.src='https://www.bigbasket.com/static/images/default.jpg'"></div>
                    <div class="bb-meta"><span>${p.brand}</span><span>${p.cat}</span></div>
                    <div class="bb-ttl" title="${p.name}">${p.name}</div>
                    <div class="bb-prc"><span class="bb-sp">Rs.${p.sp}</span><span class="bb-mrp">Rs.${p.mrp}</span></div>
                </a>
            `).join('');
        };

        mBtn.onclick = openModal;
        document.getElementById('bb-m-cls').onclick = () => { m.style.display = 'none'; };
        document.getElementById('bb-q').oninput = renderModal;
        document.getElementById('bb-fc').onchange = renderModal;
        document.getElementById('bb-st').onchange = renderModal;
    };

    buildUI();
})();
