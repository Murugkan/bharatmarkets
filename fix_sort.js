const fs = require('fs');
let js = fs.readFileSync('app.js', 'utf8');

// Fix 1: Replace togglePfSort inline sort block with sortRows() call
// Find the function and replace the entire sort block
const tfStart = js.indexOf('function togglePfSort(k){');
if(tfStart === -1){ console.error('togglePfSort not found'); process.exit(1); }

// Find end of function — look for the tfoot update section after the sort
const tfEnd = js.indexOf('  // Update header arrows', tfStart);
if(tfEnd === -1){ console.error('Update header arrows not found'); process.exit(1); }

// Find the line just before "// Update header arrows"
// Replace everything from start of function to that point
const oldFn = js.slice(tfStart, tfEnd);
const newFn = `function togglePfSort(k){
  if(S.pfSort===k) S.pfSortDir=S.pfSortDir==='desc'?'asc':'desc';
  else{ S.pfSort=k; S.pfSortDir='desc'; }
  const tbody=document.getElementById('bls-tbody');
  if(!tbody){ render(); return; }
  const tc = S.portfolio.map(mergeHolding);
  const filt = S.pfFilter||'All';
  const srch = (S.pfSearch||'').toUpperCase().trim();
  const secFilt = S.pfSector||'';
  let rows = filt==='All' ? [...tc] : tc.filter(h=>h.signal===filt);
  if(srch) rows = rows.filter(h=>h.sym.includes(srch)||(h.name||'').toUpperCase().includes(srch));
  if(secFilt) rows = rows.filter(h=>(h.sector||'').includes(secFilt));
  const totalCur = tc.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp,0);
  sortRows(rows, S.pfSort||'wt', S.pfSortDir||'desc');
  `;

js = js.slice(0, tfStart) + newFn + js.slice(tfEnd);
console.log('Fix 1 applied: togglePfSort now uses sortRows()');

// Fix 2: Add normSector function before sortRows
const normSectorFn = `
function normSector(raw){
  const map={
    'Auto Ancillaries':'Auto','Automobiles':'Auto',
    'Banks':'Banking','Bank':'Banking',
    'Pharmaceutical':'Pharma','Pharmaceuticals':'Pharma',
    'IT - Software':'IT','Information Technology':'IT','Technology':'IT',
    'Telecomm Equipment & Infra Services':'Telecom',
    'Telecom Services':'Telecom','Communication Services':'Telecom',
    'Power Generation & Distribution':'Power','Utilities':'Power','POWER':'Power',
    'Capital Goods-Non Electrical Equipment':'Capital Goods',
    'Capital Goods - Electrical Equipment':'Capital Goods','Industrials':'Capital Goods',
    'Infrastructure Developers & Operators':'Infrastructure',
    'Ship Building':'Defence','Non Ferrous Metals':'Metals','Basic Materials':'Metals',
    'Mining & Mineral products':'Mining',
    'Consumer Durables':'Consumer','Consumer Cyclical':'Consumer',
    'Consumer Defensive':'FMCG','Tobacco Products':'FMCG',
    'Miscellaneous':'Diversified','Others':'Diversified','Other':'Diversified',
    'Services':'Diversified','Refineries':'Energy','Crude Oil & Natural Gas':'Energy',
    'Financial Services':'Finance','Health Care':'Pharma','Healthcare':'Pharma',
    'Shipping':'Infrastructure','Steel':'Metals','Construction':'Infrastructure',
    'Trading':'Diversified',
  };
  return map[raw]||raw;
}
`;

if(!js.includes('function normSector(')){
  js = js.replace('function sortRows(', normSectorFn + '\nfunction sortRows(');
  console.log('Fix 2 applied: normSector added');
}

// Fix 3: Use normSector in sortRows sector case
js = js.replace(
  "      case 'sector': av=a.sector||''; bv=b.sector||''; break;",
  "      case 'sector': av=normSector(a.sector||''); bv=normSector(b.sector||''); break;"
);
console.log('Fix 3 applied: sector sort normalised');

// Fix 4: Add computePos/computeNeg before mergeHolding
const computeFns = `
function computePos(h, f){
  let pos = 0;
  const roe  = f.roe  || h.roe  || 0;
  const pe   = f.pe   || h.pe   || 0;
  const opm  = f.opm_pct || 0;
  const prom = f.prom_pct || h.promoter || 0;
  const chg  = f.chg1d || h.change || 0;
  const ath  = f.ath_pct != null ? f.ath_pct : null;
  const debt = f.debt_eq != null ? f.debt_eq : null;
  if(roe > 15)  pos++;
  if(roe > 20)  pos++;
  if(pe > 0 && pe < 18) pos++;
  if(opm > 15)  pos++;
  if(prom > 50) pos++;
  if(chg > 1)   pos++;
  if(ath !== null && ath > -10) pos++;
  if(debt !== null && debt < 0.5) pos++;
  return pos;
}

function computeNeg(h, f){
  let neg = 0;
  const roe  = f.roe  || h.roe  || 0;
  const pe   = f.pe   || h.pe   || 0;
  const opm  = f.opm_pct || 0;
  const prom = f.prom_pct || h.promoter || 0;
  const chg  = f.chg1d || h.change || 0;
  const ath  = f.ath_pct != null ? f.ath_pct : null;
  const debt = f.debt_eq != null ? f.debt_eq : null;
  if(roe > 0 && roe < 8)  neg++;
  if(pe > 35)  neg++;
  if(opm > 0 && opm < 8)  neg++;
  if(prom > 0 && prom < 35) neg++;
  if(chg < -1) neg++;
  if(ath !== null && ath < -30) neg++;
  if(debt !== null && debt > 1.5) neg++;
  return neg;
}
`;

if(!js.includes('function computePos(')){
  js = js.replace('function mergeHolding(', computeFns + '\nfunction mergeHolding(');
  console.log('Fix 4 applied: computePos/computeNeg added');
}

// Fix 5: Use computePos/computeNeg in mergeHolding
js = js.replace(
  '    pos:       f.pos||0,',
  '    pos:       f.pos || computePos(h, f),'
);
js = js.replace(
  '    neg:       f.neg||0,',
  '    neg:       f.neg || computeNeg(h, f),'
);
console.log('Fix 5 applied: mergeHolding uses computed pos/neg');

fs.writeFileSync('app.js', js);

// Verification
const checks = [
  ['togglePfSort uses sortRows',   js.includes('sortRows(rows, S.pfSort')],
  ['normSector defined',           js.includes('function normSector(')],
  ['sector sort normalised',       js.includes('normSector(a.sector')],
  ['computePos defined',           js.includes('function computePos(')],
  ['computeNeg defined',           js.includes('function computeNeg(')],
  ['pos uses computePos',          js.includes('computePos(h, f)')],
  ['neg uses computeNeg',          js.includes('computeNeg(h, f)')],
  ['sortRows defined',             js.includes('function sortRows(')],
  ['mergeHolding present',         js.includes('function mergeHolding(')],
  ['renderPortfolio present',      js.includes('function renderPortfolio(')],
];

console.log('\nVerification:');
checks.forEach(([name, pass]) => console.log((pass ? '  PASS' : '  FAIL') + ' ' + name));
const failed = checks.filter(([,pass]) => !pass);
if(failed.length){ console.error('\n' + failed.length + ' checks failed'); process.exit(1); }
console.log('\nAll checks passed!');
