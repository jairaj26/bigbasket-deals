const fs = require('fs');
const path = require('path');

const srcPath = path.join(__dirname, 'bb_deal_finder.js');
let code = fs.readFileSync(srcPath, 'utf8');

// 1. Remove block comments /* ... */
code = code.replace(/\/\*[\s\S]*?\*\//g, '');

// 2. Remove single-line comments safely (without touching http:// or https://)
code = code.split('\n').map(line => {
    const trimmed = line.trim();
    if (trimmed.startsWith('//')) return '';
    // If line has // after code, strip it if not part of a URL
    const idx = line.indexOf('//');
    if (idx !== -1) {
        const before = line.substring(0, idx);
        if (!before.endsWith('http:') && !before.endsWith('https:')) {
            return before;
        }
    }
    return line;
}).join('\n');

// 3. Compact whitespace safely
code = code.replace(/\r\n/g, '\n');
code = code.replace(/\n\s+/g, '\n');
code = code.replace(/\s+/g, ' ').trim();

// 4. Verify syntax
try {
    new Function(code);
    console.log('✅ SYNTAX CHECK PASSED (0 Syntax Errors)');
} catch (e) {
    console.error('❌ SYNTAX ERROR DETECTED:', e.message);
    process.exit(1);
}

const bookmarklet = 'javascript:' + code;

fs.writeFileSync(path.join(__dirname, 'bookmarklet.txt'), bookmarklet, 'utf8');
fs.writeFileSync(path.join(__dirname, 'bb_deal_finder.min.js'), code, 'utf8');

const mobileLoader = "javascript:(function(){if(window.__BB_SNIPER__){const p=document.getElementById('bb-pop');if(p)p.style.display=p.style.display==='none'?'flex':'none';return;}const s=document.createElement('script');s.src='https://jairaj26.github.io/bigbasket-deals/bb_deal_finder.min.js?t='+Date.now();s.onerror=function(){const f=document.createElement('script');f.src='https://cdn.jsdelivr.net/gh/jairaj26/bigbasket-deals@main/bb_deal_finder.min.js?t='+Date.now();document.body.appendChild(f);};document.body.appendChild(s);})();";
fs.writeFileSync(path.join(__dirname, 'mobile_bookmarklet.txt'), mobileLoader, 'utf8');

console.log('Final Bookmarklet Size:', bookmarklet.length, 'characters (~' + (bookmarklet.length / 1024).toFixed(2) + ' KB)');
console.log('Mobile Loader Size:', mobileLoader.length, 'characters');

// Generate self-contained Tampermonkey Userscript
const rawSource = fs.readFileSync(srcPath, 'utf8');
const userScriptHeader = `// ==UserScript==
// @name         BigBasket Deal Sniper
// @namespace    https://github.com/jairaj26/bigbasket-deals
// @version      1.3
// @description  Find flash deals on BigBasket across categories
// @author       jairaj26
// @match        *://*.bigbasket.com/*
// @updateURL    https://raw.githubusercontent.com/jairaj26/bigbasket-deals/main/bb_deal_finder.user.js
// @downloadURL  https://raw.githubusercontent.com/jairaj26/bigbasket-deals/main/bb_deal_finder.user.js
// @run-at       document-end
// @grant        none
// ==/UserScript==

`;

fs.writeFileSync(path.join(__dirname, 'bb_deal_finder.user.js'), userScriptHeader + rawSource, 'utf8');
console.log('bb_deal_finder.user.js generated cleanly (self-contained, offline-ready)');

// Update index.html cleanly
const indexPath = path.join(__dirname, 'index.html');
if (fs.existsSync(indexPath)) {
    let html = fs.readFileSync(indexPath, 'utf8');
    html = html.replace(/<script id="bm-code-src" type="text\/plain">[\s\S]*?<\/script>/,
        '<script id="bm-code-src" type="text/plain">\n' + bookmarklet + '\n  </script>');
    fs.writeFileSync(indexPath, html, 'utf8');
    console.log('index.html updated cleanly with valid bookmarklet');
}
