const fs = require('fs');
let s = fs.readFileSync('app.js', 'utf8');

// ── Fix 1: pos/neg null-check in mergeHolding ──────────────
const o1 = `    pos:       f.pos || computePos(h, f),
    neg:       f.neg || computeNeg(h, f),`;
const n1 = `    pos:       f.pos != null ? f.pos : computePos(h, f),
    neg:       f.neg != null ? f.neg : computeNeg(h, f),`;
if (s.includes(o1)) { s = s.replace(o1, n1); console.log('✅ Fix 1: pos/neg null-check'); }
else if (s.includes('f.pos != null')) { console.log('ℹ Fix 1 already applied'); }
else { console.error('❌ Fix 1 not found'); process.exit(1); }

// ── Fix 2: normSector — blank/dash sorts to bottom ─────────
const o2 = `  return map[raw]||raw;\n}`;
const n2 = `  if(!raw||raw==='—') return 'zzz_unknown';\n  return map[raw]||raw;\n}`;
if (s.includes(o2)) { s = s.replace(o2, n2); console.log('✅ Fix 2: normSector blank handling'); }
else if (s.includes('zzz_unknown')) { console.log('ℹ Fix 2 already applied'); }
else { console.warn('⚠ Fix 2 not found — skipping'); }

// ── Fix 3: add sorted class to Sector th ───────────────────
const o3 = `<th class="th-l th-fix th-fix2" onclick="togglePfSort('sector')" style="cursor:pointer">\${pfSortArrow('sector')}Sector</th>`;
const n3 = `<th class="th-l th-fix th-fix2 \${S.pfSort==='sector'?'sorted':''}" onclick="togglePfSort('sector')">\${pfSortArrow('sector')}Sector</th>`;
if (s.includes(o3)) { s = s.replace(o3, n3); console.log('✅ Fix 3: Sector sorted class'); }
else { console.warn('⚠ Fix 3 not matched — skipping'); }

// ── Fix 4: add sorted class to Pos th ──────────────────────
const o4 = `<th title="Bullish signals" onclick="togglePfSort('pos')" style="cursor:pointer">\${pfSortArrow('pos')}Pos</th>`;
const n4 = `<th title="Bullish signals" class="\${S.pfSort==='pos'?'sorted':''}" onclick="togglePfSort('pos')">\${pfSortArrow('pos')}Pos</th>`;
if (s.includes(o4)) { s = s.replace(o4, n4); console.log('✅ Fix 4: Pos sorted class'); }
else { console.warn('⚠ Fix 4 not matched — skipping');​​​​​​​​​​​​​​​​
