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
        maxCats: 1,
        pagesPerCat: 2,
        dMin: 800,
        dMax: 1100,
        hdrs: () => ({
            "accept": "application/json",
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
    let abortScan = false;
    let selectedBrands = new Set();

    const sleep = (ms) => new Promise(r => setTimeout(r, ms));

    const fetchJSON = async (url) => {
        try {
            const res = await fetch(url, { headers: CFG.hdrs() });
            if (res.ok) return await res.json();
            if (res.status === 429) {
                await sleep(2500);
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

    const calcUnitPrice = (sp, wStr, name) => {
        if (!sp || sp <= 0) return '';
        const text = ((wStr || '') + ' ' + (name || '')).toLowerCase();

        const gMatch = text.match(/([\d.]+)\s*(?:g|gm|gms|gram|grams)\b/i);
        if (gMatch) {
            const g = parseFloat(gMatch[1]);
            if (g > 0) {
                const p100 = (sp / g) * 100;
                const formatted = p100 >= 10 ? Math.round(p100) : p100.toFixed(1);
                return `Rs.${formatted}/100g`;
            }
        }

        const kgMatch = text.match(/([\d.]+)\s*(?:kg|kgs|kilo|kilogram)\b/i);
        if (kgMatch) {
            const kg = parseFloat(kgMatch[1]);
            if (kg > 0) {
                const pkg = sp / kg;
                const formatted = pkg >= 10 ? Math.round(pkg) : pkg.toFixed(1);
                return `Rs.${formatted}/kg`;
            }
        }

        const mlMatch = text.match(/([\d.]+)\s*(?:ml|mls|millilitre|milliliter)\b/i);
        if (mlMatch) {
            const ml = parseFloat(mlMatch[1]);
            if (ml > 0) {
                const p100 = (sp / ml) * 100;
                const formatted = p100 >= 10 ? Math.round(p100) : p100.toFixed(1);
                return `Rs.${formatted}/100ml`;
            }
        }

        const lMatch = text.match(/([\d.]+)\s*(?:l|ltr|litre|liter|litres)\b/i);
        if (lMatch) {
            const l = parseFloat(lMatch[1]);
            if (l > 0) {
                const pl = sp / l;
                const formatted = pl >= 10 ? Math.round(pl) : pl.toFixed(1);
                return `Rs.${formatted}/L`;
            }
        }

        const pcMatch = text.match(/([\d.]+)\s*(?:pcs|pc|units|unit|count|sheets|wipes|diapers|tablets|capsules|caps)\b/i);
        if (pcMatch) {
            const pc = parseFloat(pcMatch[1]);
            if (pc > 1) {
                const ppc = sp / pc;
                const formatted = ppc >= 10 ? Math.round(ppc) : ppc.toFixed(1);
                return `Rs.${formatted}/pc`;
            }
        }

        return '';
    };

    const parseProduct = (p, catName) => {
        if (!p) return null;
        const mrp = parseFloat(p.pricing?.discount?.mrp || p.pricing?.mrp || p.mrp || 0);
        let sp = parseFloat(p.pricing?.discount?.prim_price?.sp || p.pricing?.offer_price || p.pricing?.sp || p.sp || 0);
        if (sp <= 0 && mrp > 0) sp = mrp;
        const disc = mrp > 0 && sp > 0 ? ((mrp - sp) / mrp) * 100 : 0;
        const sav = Math.max(0, mrp - sp);

        const isOutOfStock = Boolean(
            p.availability && (
                p.availability.is_available === false ||
                p.availability.avail_status === '002' ||
                p.availability.avail_status === '000' ||
                p.availability.button_state === 'OUT_OF_STOCK' ||
                p.availability.button_state === 'NOT_AVAILABLE' ||
                p.availability.button_state === 'COMING_SOON'
            )
        );

        if (mrp > 0 || sp > 0) {
            const url = p.absolute_url ? (p.absolute_url.startsWith('http') ? p.absolute_url : 'https://www.bigbasket.com' + p.absolute_url) : `https://www.bigbasket.com/pd/${p.id || ''}`;
            const weightStr = p.w || p.pack_desc || '';
            const unitPrice = calcUnitPrice(sp, weightStr, p.desc || p.p_desc || p.name || '');

            return {
                id: String(p.id || Math.random().toString(36).substring(7)),
                name: (p.desc || p.p_desc || p.name || 'Product') + (weightStr ? ` (${weightStr})` : ''),
                brand: p.brand?.name || p.p_brand || 'BigBasket',
                mrp: parseFloat(mrp.toFixed(2)),
                sp: parseFloat(sp.toFixed(2)),
                sav: parseFloat(sav.toFixed(2)),
                disc: parseFloat(disc.toFixed(1)),
                unitPrice,
                isOutOfStock,
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

        if (onProg) onProg(`Scanning ${cat.name} (P1)...`);
        let data1 = await fetchJSON(makeUrl(1));
        let p1Items = handlePage(data1, cat.name);
        res.push(...p1Items);

        if (abortScan) return res;

        await sleep(Math.floor(Math.random() * (CFG.dMax - CFG.dMin + 1)) + CFG.dMin);

        if (onProg) onProg(`Scanning ${cat.name} (P2)...`);
        let data2 = await fetchJSON(makeUrl(2));
        let p2Items = handlePage(data2, cat.name);
        res.push(...p2Items);

        return res;
    };

    const injectCSS = () => {
        if (document.getElementById('bb-css')) return;
        const s = document.createElement('style');
        s.id = 'bb-css';
        s.textContent = `
            #bb-wrap{position:fixed;bottom:20px;right:20px;z-index:2147483640;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;}
            #bb-fab{background:#2e7d32;color:#fff;border:none;padding:12px 18px;border-radius:50px;font-size:14px;font-weight:700;cursor:pointer;box-shadow:0 8px 24px rgba(46,125,50,0.4);display:flex;align-items:center;gap:6px;}
            #bb-pop{position:absolute;bottom:60px;right:0;width:330px;max-width:calc(100vw - 32px);max-height:85vh;background:#fff;border-radius:16px;box-shadow:0 16px 40px rgba(0,0,0,0.2),0 0 0 1px rgba(0,0,0,0.08);display:flex;flex-direction:column;overflow:hidden;}
            @media(max-width:480px){#bb-pop{position:fixed;bottom:74px;right:16px;left:16px;width:auto;}}
            .bb-hd{background:#2e7d32;color:#fff;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;font-size:14px;font-weight:700;}
            .bb-hd button{background:rgba(255,255,255,0.2);border:none;color:#fff;width:24px;height:24px;border-radius:50%;cursor:pointer;}
            .bb-tb{display:flex;justify-content:space-between;padding:8px 14px;background:#f8fafc;border-bottom:1px solid #e2e8f0;font-size:12px;font-weight:600;color:#475569;}
            .bb-tb button{background:none;border:none;color:#2e7d32;font-weight:700;cursor:pointer;font-size:11.5px;}
            .bb-list{padding:8px 14px;overflow-y:auto;max-height:210px;display:flex;flex-direction:column;gap:3px;}
            .bb-item{display:flex;align-items:center;gap:10px;padding:4px 0;font-size:12.5px;color:#334155;cursor:pointer;}
            .bb-item input{accent-color:#2e7d32;width:15px;height:15px;}
            .bb-item.disabled{opacity:0.35;cursor:not-allowed;}
            .bb-st-wrap{padding:10px 14px;background:#f8fafc;border-top:1px solid #e2e8f0;display:flex;flex-direction:column;gap:6px;}
            .bb-st{font-size:11.5px;color:#475569;font-weight:600;}
            .bb-pbar-bg{width:100%;height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;display:none;}
            .bb-pbar-fill{height:100%;width:0%;background:#2e7d32;transition:width 0.2s ease;}
            .bb-acts{padding:12px 14px;background:#fff;border-top:1px solid #e2e8f0;display:flex;flex-direction:column;gap:8px;}
            .bb-row{display:flex;gap:8px;}
            .bb-btn{flex:1;padding:10px 12px;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;}
            .bb-btn:disabled{opacity:0.45;cursor:not-allowed;}
            .bb-btn-f{background:#2e7d32;color:#fff;}
            .bb-btn-a{background:#1e293b;color:#fff;}
            .bb-btn-s{background:#dc2626;color:#fff;display:none;width:100%;}
            .bb-btn-m{background:#1976d2;color:#fff;display:none;width:100%;box-shadow:0 4px 12px rgba(25,118,210,0.3);}
            #bb-modal{position:fixed;top:0;left:0;width:100%;height:100%;background:#f8fafc;z-index:2147483646;display:none;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:#0f172a;}
            .bb-m-top{background:#fff;padding:14px 20px;border-bottom:1px solid #e2e8f0;display:flex;flex-direction:column;gap:10px;position:sticky;top:0;z-index:100;}
            .bb-m-th{display:flex;justify-content:space-between;align-items:center;}
            .bb-m-th h2{font-size:18px;color:#1b5e20;margin:0;}
            .bb-m-cls{background:#e2e8f0;border:none;color:#334155;padding:6px 14px;border-radius:6px;font-weight:700;cursor:pointer;}
            .bb-m-ctrl{display:grid;grid-template-columns:2.5fr 1.5fr 1.5fr;gap:10px;}
            @media(max-width:768px){.bb-m-ctrl{grid-template-columns:1fr;}}
            .bb-m-ctrl input,.bb-m-ctrl select{padding:9px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;outline:none;background:#fff;}
            .bb-dd-wrap{position:relative;}
            .bb-dd-btn{width:100%;padding:9px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:13px;background:#fff;color:#0f172a;text-align:left;cursor:pointer;display:flex;justify-content:space-between;align-items:center;}
            .bb-dd-menu{position:absolute;top:calc(100% + 4px);left:0;width:100%;min-width:220px;max-height:280px;background:#fff;border:1px solid #cbd5e1;border-radius:8px;box-shadow:0 10px 25px rgba(0,0,0,0.15);display:none;flex-direction:column;z-index:200;padding:8px;}
            .bb-dd-search{padding:6px 10px;border:1px solid #e2e8f0;border-radius:6px;font-size:12px;margin-bottom:6px;outline:none;}
            .bb-dd-acts{display:flex;justify-content:space-between;padding:4px 2px 6px;border-bottom:1px solid #f1f5f9;margin-bottom:4px;font-size:11px;}
            .bb-dd-acts button{background:none;border:none;color:#2e7d32;font-weight:700;cursor:pointer;padding:0;}
            .bb-dd-list{overflow-y:auto;max-height:180px;display:flex;flex-direction:column;gap:2px;}
            .bb-dd-item{display:flex;align-items:center;gap:8px;padding:4px 6px;font-size:12px;color:#334155;cursor:pointer;border-radius:4px;}
            .bb-dd-item:hover{background:#f8fafc;}
            .bb-dd-item input{accent-color:#2e7d32;cursor:pointer;}
            .bb-m-body{flex:1;overflow-y:auto;padding:20px;}
            .bb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;}
            .bb-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:12px;display:flex;flex-direction:column;position:relative;text-decoration:none;color:inherit;cursor:pointer;transition:transform 0.12s ease-out,box-shadow 0.12s ease-out,border-color 0.12s ease-out;}
            .bb-card:hover{transform:translateY(-1.5px);box-shadow:0 4px 12px rgba(0,0,0,0.06);border-color:#cbd5e1;}
            .bb-card.oos{opacity:0.65;border-style:dashed;}
            .bb-bdg{position:absolute;top:10px;left:10px;background:#2e7d32;color:#fff;border-radius:8px;padding:5px 8px;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.05;text-align:center;min-width:40px;box-shadow:0 2px 6px rgba(46,125,50,0.3);z-index:10;}
            .bb-bdg-val{font-size:14px;font-weight:800;letter-spacing:-0.3px;}
            .bb-bdg-txt{font-size:9px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;}
            .bb-unit{position:absolute;top:10px;right:10px;background:#f1f5f9;color:#334155;border:1px solid #e2e8f0;font-size:11px;font-weight:700;padding:3px 7px;border-radius:6px;z-index:10;}
            .bb-oos{position:absolute;top:44px;left:10px;background:#ef4444;color:#fff;font-size:10px;font-weight:800;padding:3px 6px;border-radius:4px;letter-spacing:0.4px;z-index:12;}
            .bb-img-wrap{width:100%;height:130px;display:flex;align-items:center;justify-content:center;background:#fafafa;border-radius:8px;margin:0 auto 10px auto;position:relative;z-index:1;overflow:hidden;}
            .bb-img-wrap img{max-width:100%;max-height:100%;object-fit:contain;margin:0 auto;display:block;}
            .bb-card.oos .bb-img-wrap img{filter:grayscale(60%);}
            .bb-brand{font-size:12px;color:#0f172a;font-weight:800;text-transform:uppercase;margin-bottom:4px;letter-spacing:0.3px;}
            .bb-ttl{font-size:12.5px;font-weight:600;color:#334155;line-height:1.4;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:35px;}
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
                    <span id="bb-lbl">Pick 1 Category or Fetch All</span>
                    <div>
                        <button id="bb-none">Clear</button>
                    </div>
                </div>
                <div class="bb-list" id="bb-list"></div>
                <div class="bb-st-wrap">
                    <div class="bb-st" id="bb-st">Select 1 category or Fetch All (2 pages each)</div>
                    <div class="bb-pbar-bg" id="bb-pbar-bg">
                        <div class="bb-pbar-fill" id="bb-pbar-fill"></div>
                    </div>
                </div>
                <div class="bb-acts">
                    <div class="bb-row" id="bb-btn-row">
                        <button id="bb-f" class="bb-btn bb-btn-f" disabled>Fetch Selected</button>
                        <button id="bb-a" class="bb-btn bb-btn-a">Fetch All (20)</button>
                    </div>
                    <button id="bb-s" class="bb-btn bb-btn-s">Stop & View Loaded Deals</button>
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
                    <input type="text" id="bb-q" placeholder="Search product name...">
                    <select id="bb-fc"><option value="all">All Categories</option></select>
                    <div class="bb-dd-wrap" id="bb-brand-wrap">
                        <button class="bb-dd-btn" id="bb-brand-btn" type="button">
                            <span id="bb-brand-lbl">All Brands</span>
                            <span>▾</span>
                        </button>
                        <div class="bb-dd-menu" id="bb-brand-menu">
                            <input type="text" class="bb-dd-search" id="bb-brand-search" placeholder="Filter brands...">
                            <div class="bb-dd-acts">
                                <button id="bb-brand-all" type="button">Select All</button>
                                <button id="bb-brand-clr" type="button">Clear</button>
                            </div>
                            <div class="bb-dd-list" id="bb-brand-list"></div>
                        </div>
                    </div>
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
        const sBtn = document.getElementById('bb-s');
        const mBtn = document.getElementById('bb-m-btn');
        const lbl = document.getElementById('bb-lbl');
        const pbarBg = document.getElementById('bb-pbar-bg');
        const pbarFill = document.getElementById('bb-pbar-fill');
        const btnRow = document.getElementById('bb-btn-row');

        document.getElementById('bb-fab').onclick = () => {
            pop.style.display = pop.style.display === 'none' ? 'flex' : 'none';
        };
        document.getElementById('bb-cls').onclick = () => { pop.style.display = 'none'; };

        const updateState = () => {
            const checked = document.querySelectorAll('.bb-cb:checked');
            const cnt = checked.length;

            lbl.innerText = cnt > 0 ? `${cnt} Selected` : `Pick 1 Category or Fetch All`;

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
                fBtn.innerText = cnt > 0 ? `Fetch (${checked[0].parentElement.querySelector('span').innerText})` : 'Fetch Selected';
            }
        };

        list.addEventListener('change', updateState);

        document.getElementById('bb-none').onclick = () => {
            if (isFetching) return;
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.checked = false; });
            updateState();
        };

        const setBusy = (busy, msg = '', percent = 0) => {
            isFetching = busy;
            const statusEl = document.getElementById('bb-st');
            if (statusEl && msg) statusEl.innerText = msg;

            if (busy) {
                btnRow.style.display = 'none';
                sBtn.style.display = 'block';
                pbarBg.style.display = 'block';
                pbarFill.style.width = `${percent}%`;
                mBtn.style.display = 'none';
            } else {
                btnRow.style.display = 'flex';
                sBtn.style.display = 'none';
                pbarBg.style.display = 'none';
                fBtn.disabled = document.querySelectorAll('.bb-cb:checked').length === 0;
                aBtn.disabled = false;
            }
            document.querySelectorAll('.bb-cb').forEach(cb => { cb.disabled = busy; });
        };

        sBtn.onclick = () => {
            abortScan = true;
            sBtn.innerText = 'Stopping scan...';
        };

        const runFetch = async (fetchAll = false) => {
            if (isFetching) return;
            abortScan = false;
            sBtn.innerText = 'Stop & View Loaded Deals';

            const targets = fetchAll ? CATS : Array.from(document.querySelectorAll('.bb-cb:checked')).map(cb => CATS.find(x => x.slug === cb.value)).filter(Boolean);
            if (!targets.length) return;

            setBusy(true, `Starting scan for ${targets.length} categories...`, 0);
            prods = [];

            for (let i = 0; i < targets.length; i++) {
                if (abortScan) break;
                const c = targets[i];
                const pct = Math.round((i / targets.length) * 100);

                const items = await scanCategory(c, (m) => setBusy(true, `[${i + 1}/${targets.length}] ${m}`, pct));
                if (items.length) {
                    prods.push(...items);
                }

                const currPct = Math.round(((i + 1) / targets.length) * 100);
                setBusy(true, `[${i + 1}/${targets.length}] ${c.name} done (${prods.length} total deals)`, currPct);

                if (i < targets.length - 1 && !abortScan) {
                    await sleep(CFG.dMin);
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
            fBtn.innerText = 'Fetch Selected';

            if (prods.length > 0) {
                mBtn.style.display = 'block';
                mBtn.innerText = `View ${prods.length} Deals Grid >`;
                openModal();
            }
        };

        fBtn.onclick = () => runFetch(false);
        aBtn.onclick = () => runFetch(true);

        const bBtn = document.getElementById('bb-brand-btn');
        const bMenu = document.getElementById('bb-brand-menu');
        const bList = document.getElementById('bb-brand-list');
        const bSearch = document.getElementById('bb-brand-search');
        const bLbl = document.getElementById('bb-brand-lbl');

        bBtn.onclick = (e) => {
            e.stopPropagation();
            bMenu.style.display = bMenu.style.display === 'flex' ? 'none' : 'flex';
        };

        document.addEventListener('click', (e) => {
            if (!document.getElementById('bb-brand-wrap')?.contains(e.target)) {
                bMenu.style.display = 'none';
            }
        });

        bSearch.oninput = () => {
            const val = bSearch.value.toLowerCase().trim();
            document.querySelectorAll('.bb-dd-item').forEach(item => {
                const name = item.querySelector('span').innerText.toLowerCase();
                item.style.display = !val || name.includes(val) ? 'flex' : 'none';
            });
        };

        const updateBrandLabel = () => {
            const allBrandsCount = [...new Set(prods.map(p => p.brand))].length;
            if (selectedBrands.size === 0 || selectedBrands.size === allBrandsCount) {
                bLbl.innerText = 'All Brands';
            } else {
                bLbl.innerText = `Brands (${selectedBrands.size})`;
            }
        };

        const populateBrands = () => {
            const brandCounts = {};
            prods.forEach(p => {
                brandCounts[p.brand] = (brandCounts[p.brand] || 0) + 1;
            });

            const sortedBrands = Object.keys(brandCounts).sort((a, b) => a.localeCompare(b));
            selectedBrands = new Set(sortedBrands);

            bList.innerHTML = sortedBrands.map(b => `
                <label class="bb-dd-item">
                    <input type="checkbox" value="${b}" class="bb-bcb" checked>
                    <span>${b} (${brandCounts[b]})</span>
                </label>
            `).join('');

            document.querySelectorAll('.bb-bcb').forEach(cb => {
                cb.onchange = () => {
                    if (cb.checked) {
                        selectedBrands.add(cb.value);
                    } else {
                        selectedBrands.delete(cb.value);
                    }
                    updateBrandLabel();
                    renderModal();
                };
            });

            updateBrandLabel();
        };

        document.getElementById('bb-brand-all').onclick = () => {
            document.querySelectorAll('.bb-bcb').forEach(cb => {
                cb.checked = true;
                selectedBrands.add(cb.value);
            });
            updateBrandLabel();
            renderModal();
        };

        document.getElementById('bb-brand-clr').onclick = () => {
            document.querySelectorAll('.bb-bcb').forEach(cb => {
                cb.checked = false;
                selectedBrands.delete(cb.value);
            });
            updateBrandLabel();
            renderModal();
        };

        const openModal = () => {
            if (!prods.length) return alert('No products fetched yet!');
            const fc = document.getElementById('bb-fc');
            fc.innerHTML = '<option value="all">All Categories</option>';
            [...new Set(prods.map(p => p.cat))].sort().forEach(c => {
                fc.innerHTML += `<option value="${c}">${c}</option>`;
            });

            populateBrands();
            m.style.display = 'flex';
            renderModal();
        };

        const renderModal = () => {
            const q = document.getElementById('bb-q').value.toLowerCase().trim();
            const c = document.getElementById('bb-fc').value;

            let filtered = prods.filter(p => {
                const matchQ = !q || p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q);
                const matchC = c === 'all' || p.cat === c;
                const matchB = selectedBrands.size === 0 || selectedBrands.has(p.brand);
                return matchQ && matchC && matchB;
            });

            filtered.sort((a, b) => b.disc - a.disc);

            document.getElementById('bb-stat').innerText = `Showing ${filtered.length} of ${prods.length} items (sorted by highest discount)`;
            document.getElementById('bb-grid').innerHTML = filtered.map(p => `
                <a href="${p.url}" target="_blank" class="bb-card ${p.isOutOfStock ? 'oos' : ''}">
                    <div class="bb-bdg">
                        <span class="bb-bdg-val">${p.disc}%</span>
                        <span class="bb-bdg-txt">OFF</span>
                    </div>
                    ${p.unitPrice ? `<span class="bb-unit">${p.unitPrice}</span>` : ''}
                    ${p.isOutOfStock ? '<span class="bb-oos">OUT OF STOCK</span>' : ''}
                    <div class="bb-img-wrap"><img src="${p.img}" loading="lazy" onerror="this.src='https://www.bigbasket.com/static/images/default.jpg'"></div>
                    <div class="bb-brand">${p.brand}</div>
                    <div class="bb-ttl" title="${p.name}">${p.name}</div>
                    <div class="bb-prc"><span class="bb-sp">Rs.${p.sp}</span><span class="bb-mrp">Rs.${p.mrp}</span></div>
                </a>
            `).join('');
        };

        mBtn.onclick = openModal;
        document.getElementById('bb-m-cls').onclick = () => { m.style.display = 'none'; };
        document.getElementById('bb-q').oninput = renderModal;
        document.getElementById('bb-fc').onchange = renderModal;
    };

    buildUI();
})();
