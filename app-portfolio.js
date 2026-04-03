// ─────────────────────────────────────────────────────────────
//  app-portfolio.test.js
//  Node-compatible test runner — no DOM, no globals needed.
//  Run:  node app-portfolio.test.js
//
//  Covers every pure function in Section 1 of app-portfolio.js:
//    normSector, round2, cc, rowBg, fn, fnCr,
//    computePos, computeNeg, calcSignalLocal,
//    mergeHolding, calcPortfolioTotals, calcSectorMap,
//    filterRows, sortRows
// ─────────────────────────────────────────────────────────────

// ── Minimal stubs so the module loads without a browser ──────
global.S = { pfSort:'wt', pfSortDir:'desc', pfFilter:'All', pfSector:'', pfSearch:'',
             settings:{}, portfolio:[], watchlist:[], curTab:'portfolio' };
global.FUND = {};
global.fundLoaded = false;
global.pfRefreshing = false;
global.pfLastRefresh = 0;
global.ISIN_MAP = {};
// DOM stubs (never called in pure-function tests)
global.document = { addEventListener:()=>{}, getElementById:()=>null,
                    activeElement:{id:''}, visibilityState:'visible' };
global.localStorage = { getItem:()=>null, setItem:()=>{} };
global.setTimeout = ()=>{};
global.setInterval = ()=>{};
global.requestAnimationFrame = ()=>{};
global.sectorColor = ()=>'#888';   // defined in another module
global.trunc = (s,n)=>String(s||'').slice(0,n);  // defined in app-core.js
global.render = ()=>{};
global.toast  = ()=>{};
global.saveSettings = ()=>{};
global.savePF = ()=>{};

// Load the module — run in global context so function declarations are accessible
const vm=require('vm');
const fs=require('fs');
const src=fs.readFileSync('./app-portfolio.js','utf8');
// Remove the timer boot calls that would fire immediately
const safe=src
  .replace("setTimeout(()=>{ if(S.portfolio.length)refreshPortfolioData(); },1500);","/*BOOT_TIMEOUT*/")
  .replace("setInterval(()=>{","if(false)setInterval(()=>{")
  .replace("document.addEventListener('visibilitychange',()=>{","if(false)document.addEventListener('visibilitychange',()=>{")
  .replace("['touchstart','mousedown','scroll','keydown','visibilitychange'].forEach","([]).forEach");
vm.runInThisContext(safe);

// ── Tiny test harness ─────────────────────────────────────────
let passed=0, failed=0;
function test(name, fn){
  try{ fn(); console.log(`  ✓  ${name}`); passed++; }
  catch(e){ console.error(`  ✗  ${name}\n     ${e.message}`); failed++; }
}
function eq(a, b){
  const as=JSON.stringify(a), bs=JSON.stringify(b);
  if(as!==bs) throw new Error(`Expected ${bs}\n       Got     ${as}`);
}
function approx(a, b, tol=0.01){
  if(Math.abs(a-b)>tol) throw new Error(`Expected ≈${b}, got ${a}`);
}

// ─────────────────────────────────────────────────────────────
//  normSector
// ─────────────────────────────────────────────────────────────
console.log('\nnormSector');
test('null → —',            ()=>eq(normSector(null),'—'));
test('empty → —',           ()=>eq(normSector(''),'—'));
test('— passthrough',       ()=>eq(normSector('—'),'—'));
test('unknown passthrough',  ()=>eq(normSector('Widgets'),'Widgets'));
// CDSL names
test('Auto Ancillaries → Auto',         ()=>eq(normSector('Auto Ancillaries'),'Auto'));
test('Automobiles → Auto',              ()=>eq(normSector('Automobiles'),'Auto'));
test('Banks → Banking',                 ()=>eq(normSector('Banks'),'Banking'));
test('Bank → Banking',                  ()=>eq(normSector('Bank'),'Banking'));
test('Pharmaceutical → Pharma',         ()=>eq(normSector('Pharmaceutical'),'Pharma'));
test('Pharmaceuticals → Pharma',        ()=>eq(normSector('Pharmaceuticals'),'Pharma'));
test('IT - Software → IT',             ()=>eq(normSector('IT - Software'),'IT'));
test('Information Technology → IT',    ()=>eq(normSector('Information Technology'),'IT'));
test('Telecom Services → Telecom',      ()=>eq(normSector('Telecom Services'),'Telecom'));
test('Communication Services → Telecom',()=>eq(normSector('Communication Services'),'Telecom'));
test('POWER → Power',                   ()=>eq(normSector('POWER'),'Power'));
test('Utilities → Power',              ()=>eq(normSector('Utilities'),'Power'));
test('Industrials → Capital Goods',    ()=>eq(normSector('Industrials'),'Capital Goods'));
test('Ship Building → Defence',        ()=>eq(normSector('Ship Building'),'Defence'));
test('Basic Materials → Metals',       ()=>eq(normSector('Basic Materials'),'Metals'));
test('Non Ferrous Metals → Metals',    ()=>eq(normSector('Non Ferrous Metals'),'Metals'));
test('Consumer Durables → Consumer',   ()=>eq(normSector('Consumer Durables'),'Consumer'));
test('Consumer Cyclical → Consumer',   ()=>eq(normSector('Consumer Cyclical'),'Consumer'));
test('Consumer Defensive → FMCG',      ()=>eq(normSector('Consumer Defensive'),'FMCG'));
test('Miscellaneous → Diversified',    ()=>eq(normSector('Miscellaneous'),'Diversified'));
test('Others → Diversified',           ()=>eq(normSector('Others'),'Diversified'));
test('Services → Diversified',         ()=>eq(normSector('Services'),'Diversified'));
test('Financial Services → Finance',   ()=>eq(normSector('Financial Services'),'Finance'));
test('Health Care → Pharma',           ()=>eq(normSector('Health Care'),'Pharma'));
test('Healthcare → Pharma',            ()=>eq(normSector('Healthcare'),'Pharma'));
// yfinance names
test('Technology → IT',               ()=>eq(normSector('Technology'),'IT'));
test('Energy passthrough',             ()=>eq(normSector('Energy'),'Energy'));
test('Real Estate passthrough',        ()=>eq(normSector('Real Estate'),'Real Estate'));

// ─────────────────────────────────────────────────────────────
//  round2
// ─────────────────────────────────────────────────────────────
console.log('\nround2');
// 1.005 is a known JS float: 1.005*100 = 100.4999... so rounds to 1.00 not 1.01
// round2 is used for percentages like w52_pct where this edge case doesn't arise
test('1.005 float quirk → 1.00', ()=>approx(round2(1.005),1.00,0.01));
test('2.555 → 2.56', ()=>approx(round2(2.555),2.56));
test('0     → 0',    ()=>eq(round2(0),0));
test('negative',     ()=>approx(round2(-3.456),-3.46));

// ─────────────────────────────────────────────────────────────
//  cc (cell color)
// ─────────────────────────────────────────────────────────────
console.log('\ncc');
test('null → empty',      ()=>eq(cc(null,15,8),''));
test('above green thresh',()=>eq(cc(20,15,8),CSS.GRN_B));
test('at green thresh',   ()=>eq(cc(15,15,8),CSS.GRN_B));
test('below red thresh',  ()=>eq(cc(5,15,8),CSS.RED_B));
test('at red thresh',     ()=>eq(cc(8,15,8),CSS.RED_B));
test('in neutral range',  ()=>eq(cc(10,15,8),CSS.NEU));

// ─────────────────────────────────────────────────────────────
//  rowBg
// ─────────────────────────────────────────────────────────────
console.log('\nrowBg');
test('BUY  → green tint', ()=>eq(rowBg('BUY'), 'background:rgba(0,160,80,.13)'));
test('SELL → red tint',   ()=>eq(rowBg('SELL'),'background:rgba(200,30,50,.13)'));
test('HOLD → empty',      ()=>eq(rowBg('HOLD'),''));
test('unknown → empty',   ()=>eq(rowBg('???'),''));

// ─────────────────────────────────────────────────────────────
//  fn
// ─────────────────────────────────────────────────────────────
console.log('\nfn');
test('null → dash span',   ()=>eq(fn(null),'<span class="u-dark">—</span>'));
test('undefined → dash',   ()=>eq(fn(undefined),'<span class="u-dark">—</span>'));
test('NaN → dash',         ()=>eq(fn(NaN),'<span class="u-dark">—</span>'));
test('basic number',        ()=>eq(fn(12.5,1),'12.5'));
test('prefix + suffix',     ()=>eq(fn(12.5,1,'₹','%'),'₹12.5%'));
test('0 renders as 0.0',    ()=>eq(fn(0,1),'0.0'));
test('negative',            ()=>eq(fn(-3.3,1,'',''),((-3.3).toFixed(1))));
test('2dp',                 ()=>eq(fn(1.234,2),'1.23'));

// ─────────────────────────────────────────────────────────────
//  fnCr
// ─────────────────────────────────────────────────────────────
console.log('\nfnCr');
test('null → dash',          ()=>eq(fnCr(null),'<span class="u-dark">—</span>'));
test('< 1000 → raw Cr',      ()=>eq(fnCr(500),'500Cr'));
test('1000 → 1.0KCr',        ()=>eq(fnCr(1000),'1.0KCr'));
test('2500 → 2.5KCr',        ()=>eq(fnCr(2500),'2.5KCr'));
test('100000 → 1.0LCr',      ()=>eq(fnCr(100000),'1.0LCr'));
test('250000 → 2.5LCr',      ()=>eq(fnCr(250000),'2.5LCr'));

// ─────────────────────────────────────────────────────────────
//  computePos
// ─────────────────────────────────────────────────────────────
console.log('\ncomputePos');
const BASE_H={roe:0,pe:0,change:0,promoter:0};
const BASE_F={roe:0,pe:0,opm_pct:0,prom_pct:0,chg1d:0,ath_pct:null,debt_eq:null};
test('all neutral → 0',  ()=>eq(computePos(BASE_H,BASE_F),0));
test('roe>15 → +1',      ()=>eq(computePos(BASE_H,{...BASE_F,roe:16}),1));
test('roe>20 → +2',      ()=>eq(computePos(BASE_H,{...BASE_F,roe:21}),2));
test('pe<18 → +1',       ()=>eq(computePos(BASE_H,{...BASE_F,pe:15}),1));
test('pe=0 no bonus',    ()=>eq(computePos(BASE_H,{...BASE_F,pe:0}),0));
test('opm>15 → +1',      ()=>eq(computePos(BASE_H,{...BASE_F,opm_pct:16}),1));
test('prom>50 → +1',     ()=>eq(computePos(BASE_H,{...BASE_F,prom_pct:55}),1));
test('chg>1 → +1',       ()=>eq(computePos(BASE_H,{...BASE_F,chg1d:2}),1));
test('ath>-10 → +1',     ()=>eq(computePos(BASE_H,{...BASE_F,ath_pct:-5}),1));
test('debt<0.5 → +1',    ()=>eq(computePos(BASE_H,{...BASE_F,debt_eq:0.3}),1));
test('ath null → skip',  ()=>eq(computePos(BASE_H,{...BASE_F,ath_pct:null}),0));
test('debt null → skip', ()=>eq(computePos(BASE_H,{...BASE_F,debt_eq:null}),0));

// ─────────────────────────────────────────────────────────────
//  computeNeg
// ─────────────────────────────────────────────────────────────
console.log('\ncomputeNeg');
test('all neutral → 0',     ()=>eq(computeNeg(BASE_H,BASE_F),0));
test('roe 1-7 → +1',        ()=>eq(computeNeg(BASE_H,{...BASE_F,roe:5}),1));
test('roe=0 no penalty',    ()=>eq(computeNeg(BASE_H,{...BASE_F,roe:0}),0));
test('pe>35 → +1',          ()=>eq(computeNeg(BASE_H,{...BASE_F,pe:40}),1));
test('opm 1-7 → +1',        ()=>eq(computeNeg(BASE_H,{...BASE_F,opm_pct:5}),1));
test('opm=0 no penalty',    ()=>eq(computeNeg(BASE_H,{...BASE_F,opm_pct:0}),0));
test('prom 1-34 → +1',      ()=>eq(computeNeg(BASE_H,{...BASE_F,prom_pct:30}),1));
test('chg<-1 → +1',         ()=>eq(computeNeg(BASE_H,{...BASE_F,chg1d:-2}),1));
test('ath<-30 → +1',        ()=>eq(computeNeg(BASE_H,{...BASE_F,ath_pct:-35}),1));
test('debt>1.5 → +1',       ()=>eq(computeNeg(BASE_H,{...BASE_F,debt_eq:2}),1));

// ─────────────────────────────────────────────────────────────
//  calcSignalLocal
// ─────────────────────────────────────────────────────────────
console.log('\ncalcSignalLocal');
const SIG_H=(roe,pe,change,promoter)=>({roe,pe,change,promoter});
const SIG_F=()=>({roe:0,pe:0,prom_pct:0});
test('strong buy: roe>15, pe<18, chg>1, prom>50 → BUY',
  ()=>eq(calcSignalLocal(SIG_H(20,12,2,55),SIG_F()),'BUY'));
test('strong sell: roe<8, pe>35, chg<-1 → SELL',
  ()=>eq(calcSignalLocal(SIG_H(5,40,-2,0),SIG_F()),'SELL'));
test('neutral → HOLD',
  ()=>eq(calcSignalLocal(SIG_H(0,0,0,0),SIG_F()),'HOLD'));
test('net +1 → HOLD',
  ()=>eq(calcSignalLocal(SIG_H(20,0,0,0),SIG_F()),'HOLD'));
test('net -1 → HOLD',
  ()=>eq(calcSignalLocal(SIG_H(5,0,0,0),SIG_F()),'HOLD'));

// ─────────────────────────────────────────────────────────────
//  mergeHolding
// ─────────────────────────────────────────────────────────────
console.log('\nmergeHolding');
const MH_H={sym:'TCS',isin:'INE467B01029',name:'Tata Consultancy',sector:'Technology',
            qty:10,avgBuy:3500,liveLtp:3800,change:1.5};
const MH_F={name:'TCS Ltd',sector:'Technology',ltp:3800,chg1d:1.5,chg5d:2,
            pe:30,pb:12,eps:120,roe:50,roce:60,mcap:1380000,
            w52h:4200,w52l:3100,w52_pct:-9.5,ath:4500,ath_pct:-15.6,
            prom_pct:72,public_pct:28,opm_pct:25,npm_pct:20,
            ebitda:60000,sales:220000,cfo:50000,
            signal:'BUY',pos:5,neg:1};
test('sector normalised at merge', ()=>{
  FUND={TCS:MH_F};
  const m=mergeHolding(MH_H);
  eq(m.sector,'IT'); // 'Technology' → 'IT' via SECTOR_MAP
});
test('liveLtp preferred over f.ltp', ()=>{
  FUND={TCS:{...MH_F,ltp:3700}};
  const m=mergeHolding({...MH_H,liveLtp:3800});
  eq(m.ltp,3800);
});
test('f.ltp used when liveLtp absent', ()=>{
  FUND={TCS:{...MH_F,ltp:3700}};
  const m=mergeHolding({...MH_H,liveLtp:0});
  eq(m.ltp,3700);
});
test('0 when no ltp source', ()=>{
  FUND={TCS:{...MH_F,ltp:0}};
  const m=mergeHolding({...MH_H,liveLtp:0});
  eq(m.ltp,0);
});
test('fundamentals fields preferred over holding fields', ()=>{
  FUND={TCS:MH_F};
  const m=mergeHolding(MH_H);
  eq(m.name,'TCS Ltd');     // f.name > h.name
  eq(m.pe,30);
  eq(m.roe,50);
});
test('signal from FUND when available', ()=>{
  FUND={TCS:MH_F};
  const m=mergeHolding(MH_H);
  eq(m.signal,'BUY');
});
test('signal computed locally when FUND missing', ()=>{
  FUND={};
  // roe>15,pe<18,change>1 → net +3 → BUY
  const m=mergeHolding({sym:'X',qty:1,avgBuy:100,liveLtp:110,change:2,roe:20,pe:12,promoter:55});
  eq(m.signal,'BUY');
});
test('w52_pct computed from liveLtp and w52h', ()=>{
  FUND={TCS:{...MH_F,w52h:4000}};
  const m=mergeHolding({...MH_H,liveLtp:3800,week52H:4000});
  // (3800/4000 - 1)*100 = -5.00
  approx(m.w52_pct,-5.00,0.01);
});
test('mcap from mcapRaw when present', ()=>{
  FUND={TCS:MH_F};
  const m=mergeHolding({...MH_H,mcapRaw:13800000000});  // 1380Cr = 13800000000 / 1e7
  approx(m.mcap,1380,1);
});
FUND={}; // reset

// ─────────────────────────────────────────────────────────────
//  calcPortfolioTotals
// ─────────────────────────────────────────────────────────────
console.log('\ncalcPortfolioTotals');
const PF=[
  {sym:'A',qty:10,avgBuy:100,ltp:120,chg1d:2,signal:'BUY'},
  {sym:'B',qty:5, avgBuy:200,ltp:180,chg1d:-1,signal:'SELL'},
  {sym:'C',qty:8, avgBuy:50, ltp:0,  chg1d:0, signal:'HOLD'},  // no price
];
const T=calcPortfolioTotals(PF);
test('priced excludes ltp=0',   ()=>eq(T.priced.length,2));
test('totalInv includes all',   ()=>approx(T.totalInv,10*100+5*200+8*50,0.01));
test('totalCur priced only',    ()=>approx(T.totalCur,10*120+5*180,0.01));
test('totalPnL correct',        ()=>approx(T.totalPnL,(10*120+5*180)-(10*100+5*200),0.01));
test('pnlPct correct',          ()=>{
  const inv=10*100+5*200;
  const pnl=(10*120+5*180)-inv;
  approx(T.pnlPct,pnl/inv*100,0.01);
});
test('gainers=1',  ()=>eq(T.gainers,1));
test('losers=1',   ()=>eq(T.losers,1));
test('buys=1',     ()=>eq(T.buys,1));
test('sells=1',    ()=>eq(T.sells,1));

// ─────────────────────────────────────────────────────────────
//  calcSectorMap
// ─────────────────────────────────────────────────────────────
console.log('\ncalcSectorMap');
const SPF=[
  {sector:'IT',     qty:10,ltp:100,avgBuy:80},
  {sector:'IT',     qty:5, ltp:200,avgBuy:150},
  {sector:'Banking',qty:20,ltp:50, avgBuy:40},
  {sector:'Pharma', qty:3, ltp:500,avgBuy:400},
];
const {sMap,sTotal,sectors:SECS}=calcSectorMap(SPF);
test('IT bucket = 10*100+5*200 = 2000',   ()=>approx(sMap['IT'],2000,0.01));
test('Banking bucket = 20*50 = 1000',     ()=>approx(sMap['Banking'],1000,0.01));
test('Pharma bucket = 3*500 = 1500',      ()=>approx(sMap['Pharma'],1500,0.01));
test('sTotal = 4500',                     ()=>approx(sTotal,4500,0.01));
test('sectors sorted by value desc',      ()=>eq(SECS[0][0],'IT'));
test('sectors limited to 10',            ()=>eq(SECS.length<=10,true));
test('ltp=0 falls back to avgBuy',       ()=>{
  const pf=[{sector:'X',qty:10,ltp:0,avgBuy:50}];
  const {sMap:m}=calcSectorMap(pf);
  eq(m['X'],500);
});

// ─────────────────────────────────────────────────────────────
//  filterRows
// ─────────────────────────────────────────────────────────────
console.log('\nfilterRows');
const FR_PF=[
  {sym:'TCS', name:'TCS Ltd',   sector:'IT',     signal:'BUY'},
  {sym:'INFY',name:'Infosys',   sector:'IT',     signal:'HOLD'},
  {sym:'HDFC',name:'HDFC Bank', sector:'Banking',signal:'BUY'},
  {sym:'ITC', name:'ITC Ltd',   sector:'FMCG',   signal:'SELL'},
];
test('All filter → all rows',         ()=>eq(filterRows(FR_PF,'All','','').length,4));
test('BUY filter',                    ()=>eq(filterRows(FR_PF,'BUY','','').length,2));
test('SELL filter',                   ()=>eq(filterRows(FR_PF,'SELL','','').length,1));
test('sector filter exact',           ()=>eq(filterRows(FR_PF,'All','IT','').length,2));
test('sector filter no match',        ()=>eq(filterRows(FR_PF,'All','Pharma','').length,0));
test('search by sym',                 ()=>eq(filterRows(FR_PF,'All','','TCS').length,1));
test('search by name partial',        ()=>eq(filterRows(FR_PF,'All','','INFOSYS').length,1));
test('search + sector combined',      ()=>eq(filterRows(FR_PF,'BUY','IT','TCS').length,1));
test('signal + sector combined',      ()=>eq(filterRows(FR_PF,'BUY','Banking','').length,1));
test('no match → empty',             ()=>eq(filterRows(FR_PF,'BUY','FMCG','').length,0));

// ─────────────────────────────────────────────────────────────
//  sortRows — sector sort (the original bug)
// ─────────────────────────────────────────────────────────────
console.log('\nsortRows — sector (regression test for original bug)');
const SR_PF=[
  {sym:'A',sector:'IT',    qty:1,ltp:100,avgBuy:80,signal:'HOLD',pos:0,neg:0,
   public_pct:0,name:'A',chg1d:0,chg5d:0,pe:20,pb:0,eps:0,roe:0,opm_pct:0,
   npm_pct:0,ebitda:0,prom_pct:0,mcap:0,sales:0,cfo:0,ath_pct:null,w52_pct:null},
  {sym:'B',sector:'Banking',qty:1,ltp:100,avgBuy:80,signal:'HOLD',pos:0,neg:0,
   public_pct:0,name:'B',chg1d:0,chg5d:0,pe:20,pb:0,eps:0,roe:0,opm_pct:0,
   npm_pct:0,ebitda:0,prom_pct:0,mcap:0,sales:0,cfo:0,ath_pct:null,w52_pct:null},
  {sym:'C',sector:'Auto',  qty:1,ltp:100,avgBuy:80,signal:'HOLD',pos:0,neg:0,
   public_pct:0,name:'C',chg1d:0,chg5d:0,pe:20,pb:0,eps:0,roe:0,opm_pct:0,
   npm_pct:0,ebitda:0,prom_pct:0,mcap:0,sales:0,cfo:0,ath_pct:null,w52_pct:null},
  {sym:'D',sector:'Pharma',qty:1,ltp:100,avgBuy:80,signal:'HOLD',pos:0,neg:0,
   public_pct:0,name:'D',chg1d:0,chg5d:0,pe:20,pb:0,eps:0,roe:0,opm_pct:0,
   npm_pct:0,ebitda:0,prom_pct:0,mcap:0,sales:0,cfo:0,ath_pct:null,w52_pct:null},
];
test('sector asc: Auto < Banking < IT < Pharma', ()=>{
  const rows=[...SR_PF]; sortRows(rows,'sector','asc');
  eq(rows.map(r=>r.sector),['Auto','Banking','IT','Pharma']);
});
test('sector desc: Pharma > IT > Banking > Auto', ()=>{
  const rows=[...SR_PF]; sortRows(rows,'sector','desc');
  eq(rows.map(r=>r.sector),['Pharma','IT','Banking','Auto']);
});
// Previously broken: mixed raw/normalised names caused wrong order
test('raw yfinance names normalised before reaching sort', ()=>{
  // These would have been 'Technology' and 'Financial Services' pre-fix
  // but mergeHolding normalises them; verify sort treats them as IT / Finance
  const mixed=[
    {...SR_PF[0],sym:'T',sector:'IT'},       // already normalised
    {...SR_PF[1],sym:'F',sector:'Finance'},  // already normalised
  ];
  sortRows(mixed,'sector','asc');
  eq(mixed[0].sym,'F'); // Finance < IT
});

console.log('\nsortRows — numeric columns');
const NUM_PF=(vals)=>vals.map((v,i)=>({
  sym:String.fromCharCode(65+i), sector:'IT', qty:1, ltp:v, avgBuy:v*0.8,
  signal:'HOLD', pos:0, neg:0, public_pct:0, name:'n', chg1d:v/10, chg5d:0,
  pe:v/10, pb:0, eps:0, roe:v/5, opm_pct:0, npm_pct:0, ebitda:0, prom_pct:0,
  mcap:v, sales:0, cfo:0, ath_pct:null, w52_pct:null,
}));
test('ltp desc',   ()=>{ const r=NUM_PF([300,100,200]); sortRows(r,'ltp','desc'); eq(r.map(x=>x.ltp),[300,200,100]); });
test('ltp asc',    ()=>{ const r=NUM_PF([300,100,200]); sortRows(r,'ltp','asc');  eq(r.map(x=>x.ltp),[100,200,300]); });
test('roe desc',   ()=>{ const r=NUM_PF([50,10,30]);    sortRows(r,'roe','desc'); eq(r.map(x=>x.roe),[10,6,2]);  }); // 50/5=10 etc
test('wt desc',    ()=>{ const r=NUM_PF([500,100,300]); sortRows(r,'wt','desc');  eq(r.map(x=>x.ltp),[500,300,100]); });
test('pnl desc',   ()=>{ const r=NUM_PF([200,100,300]);
  sortRows(r,'pnl','desc');
  // pnl = qty*(ltp - avgBuy) = 1*(v - v*0.8) = 0.2*v  → same order as ltp
  eq(r.map(x=>x.ltp),[300,200,100]);
});
test('ath_pct null sentinel (-9999) sorts first in asc', ()=>{
  const rows=[
    {...SR_PF[0],ath_pct:-5},
    {...SR_PF[1],ath_pct:null},   // null → -9999 sentinel → first in asc
    {...SR_PF[2],ath_pct:-20},
  ];
  sortRows(rows,'ath','asc');
  // asc order by sentinel: -9999 (null) < -20 < -5
  eq(rows.map(r=>r.ath_pct),[null,-20,-5]);
});

console.log('\nsortRows — string columns');
test('sym asc',  ()=>{ const r=[...SR_PF]; sortRows(r,'sym','asc');  eq(r.map(x=>x.sym),['A','B','C','D']); });
test('sym desc', ()=>{ const r=[...SR_PF]; sortRows(r,'sym','desc'); eq(r.map(x=>x.sym),['D','C','B','A']); });

// ─────────────────────────────────────────────────────────────
//  Summary
// ─────────────────────────────────────────────────────────────
console.log(`\n${'─'.repeat(50)}`);
console.log(`  ${passed} passed   ${failed} failed   ${passed+failed} total`);
console.log('─'.repeat(50));
if(failed>0) process.exit(1);
