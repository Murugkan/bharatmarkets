#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'app.js');
let src = fs.readFileSync(filePath, 'utf8');

// Fix 1: pos/neg in mergeHolding — use null-check not || (0 is falsy)
const OLD1 = `    pos:       f.pos || computePos(h, f),\n    neg:       f.neg || computeNeg(h, f),`;
const NEW1 = `    pos:       f.pos != null ? f.pos : computePos(h, f),\n    neg:       f.neg != null ? f.neg : computeNeg(h, f),`;

if (src.includes(OLD1)) {
  src = src.replace(OLD1, NEW1);
  console.log('✅ Fix 1 applied: pos/neg null-check');
} else if (src.includes('f.pos != null')) {
  console.log('ℹ Fix 1 already applied — skipping');
} else {
  console.error('❌ Fix 1 pattern not found');
  process.exit(1);
}

// Fix 2: normSector — treat '—' and empty as sortable unknown
const OLD2 = `  return map[raw]||raw;\n}`;
const NEW2 = `  if(!raw||raw==='—') return 'zzz_unknown';\n  return map[raw]||raw;\n}`;

if (src.includes(OLD2)) {
  src = src.replace(OLD2, NEW2);
  console.log('✅ Fix 2 applied: normSector handles blank/dash sectors');
} else if (src.includes('zzz_unknown')) {
  console.log('ℹ Fix 2 already applied — skipping');
} else {
  console.warn('⚠ Fix 2 pattern not matched — skipping (non-critical)');
}

fs.writeFileSync(filePath, src, 'utf8');
console.log('✅ app.js saved');
