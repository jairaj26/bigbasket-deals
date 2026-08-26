const fs = require('fs');
const path = require('path');

const srcPath = path.join(__dirname, 'bb_deal_finder.js');
let code = fs.readFileSync(srcPath, 'utf8');

// Basic JS minification
// 1. Remove comments
code = code.replace(/\/\*[\s\S]*?\*\/|([^:]|^)\/\/.*$/gm, '$1');
// 2. Remove extra spaces and newlines outside strings
// For safety, let's keep it safe or use a clean minification
fs.writeFileSync(path.join(__dirname, 'bb_deal_finder.min.js'), code, 'utf8');

const bookmarklet = 'javascript:' + encodeURIComponent('(function(){' + code + '})();');
fs.writeFileSync(path.join(__dirname, 'bookmarklet.txt'), bookmarklet, 'utf8');
console.log('Built bookmarklet! Size:', bookmarklet.length, 'bytes');
