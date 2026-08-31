const fs = require('fs');
const path = require('path');

const srcPath = path.join(__dirname, 'bb_deal_finder.js');
let code = fs.readFileSync(srcPath, 'utf8');

// Minify safely
code = code.replace(/\/\*[\s\S]*?\*\/|\/\/.*/g, '');
code = code.replace(/\s+/g, ' ').replace(/\s*([=+\-*/%&|!<>?:;{},()\[\]])\s*/g, '$1').trim();

const bookmarklet = 'javascript:' + code;

fs.writeFileSync(path.join(__dirname, 'bookmarklet.txt'), bookmarklet, 'utf8');
console.log('Final Bookmarklet Size:', bookmarklet.length, 'characters (~' + (bookmarklet.length / 1024).toFixed(2) + ' KB)');

// Update index.html
const indexPath = path.join(__dirname, 'index.html');
if (fs.existsSync(indexPath)) {
    let html = fs.readFileSync(indexPath, 'utf8');
    html = html.replace(/href="javascript:[^"]+"/, 'href="' + bookmarklet.replace(/"/g, '&quot;') + '"');
    fs.writeFileSync(indexPath, html, 'utf8');
    console.log('index.html updated successfully with new bookmarklet');
}
