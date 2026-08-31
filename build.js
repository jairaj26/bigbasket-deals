const fs = require('fs');
const path = require('path');

const srcPath = path.join(__dirname, 'bb_deal_finder.js');
let code = fs.readFileSync(srcPath, 'utf8');

// 1. Remove block comments
code = code.replace(/\/\*[\s\S]*?\*\//g, '');

// 2. Remove single-line comments safely (only whole comment lines)
code = code.split('\n').filter(line => !line.trim().startsWith('//')).join('\n');

// 3. Compact whitespace safely
code = code.replace(/\r\n/g, '\n');
code = code.replace(/\n\s+/g, '\n');
code = code.replace(/\s+/g, ' ').trim();

// Verify syntax
try {
    new Function(code);
    console.log('✅ SYNTAX CHECK PASSED (0 Syntax Errors)');
} catch (e) {
    console.error('❌ SYNTAX ERROR DETECTED:', e.message);
    process.exit(1);
}

const bookmarklet = 'javascript:' + code;

fs.writeFileSync(path.join(__dirname, 'bookmarklet.txt'), bookmarklet, 'utf8');
console.log('Final Bookmarklet Size:', bookmarklet.length, 'characters (~' + (bookmarklet.length / 1024).toFixed(2) + ' KB)');

// Update index.html cleanly
const indexPath = path.join(__dirname, 'index.html');
if (fs.existsSync(indexPath)) {
    let html = fs.readFileSync(indexPath, 'utf8');
    html = html.replace(/<script id="bm-code-src" type="text\/plain">[\s\S]*?<\/script>/,
        '<script id="bm-code-src" type="text/plain">\n' + bookmarklet + '\n  </script>');
    fs.writeFileSync(indexPath, html, 'utf8');
    console.log('index.html updated cleanly with valid bookmarklet');
}
