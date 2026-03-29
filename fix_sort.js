const fs = require('fs');
let js = fs.readFileSync('app.js', 'utf8');

const normSector = `
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
    'Capital Goods - Electrical Equipment':'Capital Goods',
    'Industrials':'Capital Goods',
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

if (!js.includes('function normSector(')) {
  js = js.replace('function sortRows(', normSector + '\nfunction sortRows(');
}

if (!js.includes('function computePos(')) {
  js = js.replace('function mergeHolding(', computeFns + '\nfunction mergeHolding(');
}

js = js.replace(
  "      case 'sector': av=a.sector||''; bv=b.sector||''; break;",
  "      case 'sector': av=normSector(a.sector||''); bv=normSector(b.sector||''); break;"
);

js = js.replace(
  '    pos:       f.pos||0,',
  '    pos:       f.pos || computePos(h, f),'
);

js = js.replace(
  '    neg:       f.neg||0,',
  '    neg:       f.neg || computeNeg(h, f),'
);

fs.writeFileSync('app.js', js);

const checks = [
  ['normSector defined',     js.includes('function normSector(')],
  ['computePos defined',     js.includes('function computePos(')],
  ['computeNeg defined',     js.includes('function computeNeg(')],
  ['sector uses normSector', js.includes('normSector(a.sector')],
  ['pos uses computePos',    js.includes('computePos(h, f)')],
  ['neg uses computeNeg',    js.includes('computeNeg(h, f)')],
  ['sortRows present',       js.includes('function sortRows(')],
  ['mergeHolding present',   js.includes('function mergeHolding(')],
];

console.log('\nVerification:');
checks.forEach(([name, pass]) => console.log((pass ? '  PASS' : '  FAIL') + ' ' + name));
const failed = checks.filter(([,pass]) => !pass);
if (failed.length) { console.error(failed.length + ' checks failed'); process.exit(1); }
console.log('\nAll checks passed!');
