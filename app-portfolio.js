function cellColor(val, goodAbove, badBelow) {
  if(val==null||isNaN(val)) return 'color:var(--tx3)';
  if(val>=goodAbove) return 'color:var(--gr2)';
  if(val<=badBelow)  return 'color:var(--rd2)';
  return 'color:var(--yw2)';
}

//  BLOOMBERG-STYLE 37-COLUMN PORTFOLIO SCREENER
//  Data sources:
//    prices.json       → LTP, %1D, %5D, P/E, P/B, EPS, MCAP, 52Wk
//    fundamentals.json → ATH%, Prom%, Pledge%, OPM%, NPM%, ROE,
//                        Sales, CFO, EBITDA, Signal, Pos, Neg

// App-level fundamentals cache (loaded from ./fundamentals.json)
// FUND, GUIDANCE, fundLoaded, pfRefreshing, pfLastRefresh declared in app-core.js

// Load fundamentals.json on boot (same-origin, CORS-safe)
const FUND_CACHE_TTL = 60 * 60 * 1000; // 1 hour in ms

async function loadFundamentals(forceRefresh){
  try{
    // Check localStorage cache first — fundamentals only update once daily
    const cached   = localStorage.getItem('fund_cache');
    const cacheTs  = parseInt(localStorage.getItem('fund_cache_ts') || '0');
    const cacheAge = Date.now() - cacheTs;

    if(!forceRefresh && cached && cacheAge < FUND_CACHE_TTL){
      const d = JSON.parse(cached);
      FUND = d.stocks || {};
      fundLoaded = true;
      if(d.updated && !S.settings._fundUpdated){
        S.settings._fundUpdated = d.updated;
        S.settings._fundStatus  = 'ok';
        saveSettings();
      }
      return;
    }

    const repo = S.settings.ghRepo?.trim();
    const fundUrl = repo
      ? `https://raw.githubusercontent.com/${repo}/main/fundamentals.json?t=${Date.now()}`
      : `./fundamentals.json?t=${Date.now()}`;

    const r = await fetch(fundUrl, {cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const d = await r.json();

    FUND = d.stocks || {};
    fundLoaded = true;

    // Save to cache
    try {
      localStorage.setItem('fund_cache', JSON.stringify(d));
      localStorage.setItem('fund_cache_ts', Date.now().toString());
    } catch(e){}

    if(d && d.updated){
      S.settings._fundUpdated = d.updated;
      S.settings._fundStatus  = 'ok';
    }
    saveSettings();
  } catch(e){
    // Fallback to expired cache if fetch fails
    try {
      const cached = localStorage.getItem('fund_cache');
      if(cached){
        const cd = JSON.parse(cached);
        FUND = cd.stocks || {}; fundLoaded = true;
        if(cd.updated){
          S.settings._fundUpdated = cd.updated;
          S.settings._fundStatus  = 'stale';
          saveSettings();
        }
        return;
      }
    } catch(err){}
  }
}

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

function mergeHolding(h){
  const f = FUND[h.sym] || {};
  // Use liveLtp if available from app-core, else from fundamentals/prices
  const liveLtp = h.liveLtp || f.ltp || 0;

  return {
    sym:       h.sym,
    isin:      h.isin || '',
    name:      f.name || h.name || h.sym,
    sector:    f.sector || h.sector || '—',
    qty:       h.qty || 0,
    avgBuy:    h.avgBuy || 0,
    ltp:       liveLtp,
    chg1d:     h.change || f.chg1d || 0,
    chg5d:     f.chg5d || 0,
    pe:        h.pe   ?? f.pe   ?? null,
    pb:        h.pb   ?? f.pb   ?? null,
    eps:       h.eps  ?? f.eps  ?? null,
    roe:       h.roe  ?? f.roe  ?? null,
    roce:      h.roce ?? f.roce ?? null,
    mcap:      h.mcapRaw ? h.mcapRaw/1e7 : (f.mcap ?? null),
    w52h:      h.week52H ?? f.w52h ?? null,
    w52l:      h.week52L ?? f.w52l ?? null,
    w52_pct:   (liveLtp && (h.week52H ?? f.w52h)) ? round2((liveLtp/(h.week52H??f.w52h)-1)*100) : (f.w52_pct ?? null),
    ath:       f.ath  ?? null,
    ath_pct:   f.ath_pct ?? null,
    prom_pct:  f.prom_pct ?? h.promoter ?? null,
    public_pct:f.public_pct ?? null,
    opm_pct:   f.opm_pct ?? h.ebitdaMargin ?? null,
    npm_pct:   f.npm_pct ?? h.netMargin ?? null,
    ebitda:    f.ebitda ?? null,
    sales:     f.sales ?? null,
    cfo:       f.cfo ?? null,
    signal:    f.signal || calcSignalLocal(h, f),
    pos:       f.pos || computePos(h, f),
    neg:       f.neg || computeNeg(h, f),
  };
}

function round2(n){ return Math.round(n*100)/100; }

function calcSignalLocal(h, f){
  let pos = 0, neg = 0;
  const roe  = h.roe || f.roe || 0;
  const pe   = h.pe  || f.pe  || 0;
  const chg  = h.change || 0;
  const prom = h.promoter || f.prom_pct || 0;

  if(roe > 15) pos++; else if(roe > 0 && roe < 8) neg++;
  if(pe > 0 && pe < 18) pos++; else if(pe > 35) neg++;
  if(chg > 1) pos++; else if(chg < -1) neg++;
  if(prom > 50) pos++; else if(prom > 0 && prom < 35) neg++;

  const net = pos - neg;
  if(net >= 2) return 'BUY';
  if(net <= -2) return 'SELL';
  return 'HOLD';
}

function cc(val, greenAbove, redBelow){
  if(val === null || val === undefined || isNaN(val)) return '';
  if(val >= greenAbove) return 'background:#003a20;color:#fff;font-weight:600';
  if(val <= redBelow)   return 'background:#3a0010;color:#fff;font-weight:600';
  return 'color:#c8dff5';
}

function rowBg(sig){
  if(sig === 'BUY')  return 'background:rgba(0,160,80,.13)';
  if(sig === 'SELL') return 'background:rgba(200,30,50,.13)';
  return '';
}

function sigBadge(sig){
  const cfg = {
    BUY:  { bg: '#00a050', bd: '#00d084' },
    SELL: { bg: '#c01e32', bd: '#ff3b5c' },
    HOLD: { bg: '#7a6010', bd: '#f5a623' },
  }[sig] || { bg: '#1a3050', bd: '#4a6888' };

  return `<span style="display:inline-block;font-size:8px;font-weight:800;padding:2px 7px;border-radius:3px;background:${cfg.bg};border:1px solid ${cfg.bd};color:#fff">${sig}</span>`;
}

function fn(v, dp=1, prefix='', suffix=''){
  if(v === null || v === undefined || isNaN(v)) return '<span class="u-dark">—</span>';
  return prefix + Number(v).toFixed(dp) + suffix;
}

function fnCr(v){
  if(v === null || v === undefined || isNaN(v)) return '<span class="u-dark">—</span>';
  if(v >= 100000) return (v/100000).toFixed(1) + 'LCr';
  if(v >= 1000)   return (v/1000).toFixed(1) + 'KCr';
  return v.toFixed(0) + 'Cr';
}

function normSector(raw){
  const map = {
    'Auto Ancillaries':'Auto','Automobiles':'Auto','Banks':'Banking','Bank':'Banking',
    'Pharmaceutical':'Pharma','Pharmaceuticals':'Pharma','IT - Software':'IT',
    'Information Technology':'IT','Technology':'IT','Telecomm Equipment & Infra Services':'Telecom',
    'Telecom Services':'Telecom','Communication Services':'Telecom',
    'Power Generation & Distribution':'Power','Utilities':'Power','Financial Services':'Finance',
    'Health Care':'Pharma','Healthcare':'Pharma','Refineries':'Energy',
    'Crude Oil & Natural Gas':'Energy','Construction':'Infrastructure','Shipping':'Infrastructure',
    'Steel':'Metals','Consumer Durables':'Consumer','Consumer Cyclical':'Consumer','Industrials':'Capital Goods'
  };
  return map[raw] || raw;
}
function sortRows(rows, skey, sdir) {
  rows.sort((a,b) => {
    let av, bv;
    switch(skey) {
      case 'sym':    av = a.sym; bv = b.sym; break;
      case 'sector': av = normSector(a.sector || ''); bv = normSector(b.sector || ''); break;
      case 'pos':    av = a.pos || 0; bv = b.pos || 0; break;
      case 'neg':    av = a.neg || 0; bv = b.neg || 0; break;
      case 'name':   av = a.name || ''; bv = b.name || ''; break;
      case 'pe':     av = a.pe   || 999; bv = b.pe   || 999; break;
      case 'roe':    av = a.roe  || 0; bv = b.roe  || 0; break;
      case 'mcap':   av = a.mcap || 0; bv = b.mcap || 0; break;
      case 'chg1d':  av = a.chg1d || 0; bv = b.chg1d || 0; break;
      case 'wt':     av = a.qty * (a.ltp || 0); bv = b.qty * (b.ltp || 0); break;
      case 'sig':    av = a.signal || 'HOLD'; bv = b.signal || 'HOLD'; break;
      case 'ath':    av = a.ath_pct != null ? a.ath_pct : -9999; bv = b.ath_pct != null ? b.ath_pct : -9999; break;
      default:       av = a[skey] || 0; bv = b[skey] || 0;
    }
    // Fixed alphabetical sorting for string keys
    if(typeof av === 'string') {
      return sdir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return sdir === 'asc' ? av - bv : bv - av;
  });
}

function renderPortfolio(c){
  const activeEl = document.activeElement;
  if(activeEl && activeEl.id === 'pf-search'){
    const tbody = document.getElementById('bls-tbody');
    if(tbody){
      const pf2 = S.portfolio.map(mergeHolding);
      const filt2 = S.pfFilter || 'All';
      const srch2 = S.pfSearch.trim();
      let rows2 = filt2 === 'All' ? [...pf2] : pf2.filter(h => h.signal === filt2);
      if(srch2) rows2 = rows2.filter(h => h.sym.includes(srch2) || (h.name||'').toUpperCase().includes(srch2));
      sortRows(rows2, S.pfSort || 'wt', S.pfSortDir || 'desc');
      const totalCur2 = pf2.filter(h => h.ltp > 0).reduce((a,h) => a + (h.qty * h.ltp), 0);
      tbody.innerHTML = renderBLSRows(rows2, totalCur2);
      return;
    }
  }

  if(!S.portfolio.length){
    c.innerHTML = `<div class="empty-state" style="padding:40px;text-align:center">
      <div style="font-size:32px;margin-bottom:16px">📊</div>
      <p style="color:var(--tx3);margin-bottom:20px">No holdings found in portfolio.</p>
      <button class="btn-p" onclick="openImport()">📂 Import Holdings</button>
    </div>`;
    return;
  }

  const pf = S.portfolio.map(mergeHolding);
  const priced = pf.filter(h => h.ltp > 0);
  const totalInv = pf.reduce((a,h) => a + (h.qty * (h.avgBuy || 0)), 0);
  const totalCur = priced.reduce((a,h) => a + (h.qty * h.ltp), 0);
  const totalPnL = totalCur - priced.reduce((a,h) => a + (h.qty * (h.avgBuy || 0)), 0);
  const pnlPct   = totalInv > 0 ? (totalPnL / totalInv * 100) : 0;

  const filt = S.pfFilter || 'All';
  const srch = (S.pfSearch || '').toUpperCase().trim();

  let rows = pf.filter(h => filt === 'All' || h.signal === filt)
               .filter(h => !srch || h.sym.includes(srch) || (h.name||'').toUpperCase().includes(srch));

  sortRows(rows, S.pfSort || 'wt', S.pfSortDir || 'desc');

  c.innerHTML = `
    <div class="bls">
      <div class="kpi-strip">
        <div class="kpi"><span>Invested</span><b>₹${(totalInv/100000).toFixed(2)}L</b></div>
        <div class="kpi"><span>Mkt Value</span><b>₹${(totalCur/100000).toFixed(2)}L</b></div>
        <div class="kpi"><span>Total P&L</span><b style="color:${totalPnL >= 0 ? '#00e896' : '#ff6b85'}">${pnlPct.toFixed(2)}%</b></div>
      </div>

      <div class="bls-tb">
        <div class="tb-search">
          <input id="pf-search" type="text" value="${S.pfSearch||''}" oninput="pfSearchUpdate(this.value)" placeholder="SEARCH..."/>
        </div>
        <div class="tb-chips">
          ${['All','BUY','SELL','HOLD'].map(f => `
            <div class="tb-chip ${filt === f ? 'on' : ''}" onclick="setPfFilter('${f}')">${f}</div>
          `).join('')}
        </div>
      </div>

      <div class="bls-table-outer">
        <table class="bls-t">
          <thead>
            <tr>
              <th class="th-fix" onclick="togglePfSort('sym')">${pfSortArrow('sym')}Ticker</th>
              <th onclick="togglePfSort('sector')">${pfSortArrow('sector')}Sector</th>
              <th onclick="togglePfSort('pos')">Pos</th>
              <th onclick="togglePfSort('neg')">Neg</th>
              <th onclick="togglePfSort('ath')">ATH%</th>
              <th onclick="togglePfSort('roe')">ROE%</th>
              <th onclick="togglePfSort('pe')">P/E</th>
              <th onclick="togglePfSort('mcap')">MCAP</th>
              <th onclick="togglePfSort('chg1d')">%1D</th>
              <th onclick="togglePfSort('ltp')">LTP</th>
              <th onclick="togglePfSort('wt')">Wt%</th>
              <th>Sig</th>
            </tr>
          </thead>
          <tbody id="bls-tbody">
            ${renderBLSRows(rows, totalCur)}
          </tbody>
        </table>
      </div>
    </div>`;
}

function renderBLSRows(rows, totalCur){
  return rows.map(h => {
    const ltp = h.ltp || 0;
    const inv = h.qty * (h.avgBuy || 0);
    const cur = ltp > 0 ? h.qty * ltp : null;
    const pnl = cur !== null ? cur - inv : null;
    const wt  = (cur !== null && totalCur > 0) ? (cur / totalCur * 100) : 0;
    const sig = h.signal || 'HOLD';

    return `
      <tr style="${rowBg(sig)}" onclick="openPortfolioStock('${h.sym}')">
        <td class="td-fix">
          <b>${h.sym}</b><br>
          <small style="color:var(--tx3);font-size:9px">${h.name.substring(0,10)}</small>
        </td>
        <td style="color:#7a9ab8;font-size:9px">${normSector(h.sector)}</td>
        <td style="text-align:center"><span class="pn-p">${h.pos}</span></td>
        <td style="text-align:center"><span class="pn-n">${h.neg}</span></td>
        <td style="text-align:right;${cc(h.ath_pct, -5, -20)}">${fn(h.ath_pct, 1, '', '%')}</td>
        <td style="text-align:right;${cc(h.roe, 15, 8)}">${fn(h.roe, 1, '', '%')}</td>
        <td style="text-align:right;${h.pe < 18 ? 'color:#00e896' : h.pe > 35 ? 'color:#ff6b85' : ''}">${fn(h.pe, 1, '', 'x')}</td>
        <td style="text-align:right">${fnCr(h.mcap)}</td>
        <td style="text-align:right;${h.chg1d >= 0 ? 'color:#00e896' : 'color:#ff6b85'}">${h.chg1d.toFixed(2)}%</td>
        <td style="text-align:right;font-weight:600">₹${ltp.toFixed(1)}</td>
        <td style="text-align:right;color:var(--tx3)">${wt.toFixed(1)}%</td>
        <td style="text-align:center">${sigBadge(sig)}</td>
      </tr>`;
  }).join('');
}

function pfSearchUpdate(val){
  S.pfSearch = val.toUpperCase();
  const tbody = document.getElementById('bls-tbody');
  if(!tbody) return;
  const pf = S.portfolio.map(mergeHolding);
  let rows = pf.filter(h => h.sym.includes(S.pfSearch) || (h.name||'').toUpperCase().includes(S.pfSearch));
  sortRows(rows, S.pfSort || 'wt', S.pfSortDir || 'desc');
  const totalCur = pf.filter(h => h.ltp > 0).reduce((a,h) => a + (h.qty * h.ltp), 0);
  tbody.innerHTML = renderBLSRows(rows, totalCur);
}

function setPfFilter(f){ S.pfFilter = f; renderPortfolio(); }

function togglePfSort(k){
  if(S.pfSort === k) {
    S.pfSortDir = S.pfSortDir === 'desc' ? 'asc' : 'desc';
  } else {
    S.pfSort = k;
    S.pfSortDir = ['sym','sector','sig'].includes(k) ? 'asc' : 'desc';
  }
  renderPortfolio();
}

function pfSortArrow(k){
  if(S.pfSort !== k) return '';
  return S.pfSortDir === 'asc' ? '↑ ' : '↓ ';
}

async function refreshPortfolioData(){
  if(pfRefreshing) return;
  pfRefreshing = true;
  try {
    const repo = S.settings.ghRepo?.trim();
    const url = `https://raw.githubusercontent.com/${repo}/main/prices.json?t=${Date.now()}`;
    const r = await fetch(url, {cache: 'no-store'});
    if(r.ok){
      const d = await r.json();
      const q = d.quotes || d;
      S.portfolio.forEach(h => {
        if(q[h.sym]){
          h.liveLtp = q[h.sym].ltp;
          h.change  = q[h.sym].changePct;
        }
      });
    }
  } catch(e){ console.error(e); }
  finally {
    pfRefreshing = false;
    pfLastRefresh = Date.now();
    renderPortfolio();
  }
}

function openPortfolioStock(sym){
  const h = S.portfolio.find(p => p.sym === sym);
  if(!h) return;
  S.selStock = mergeHolding(h);
  S.drillTab = 'overview';
  render();
}

function showPfDebug(){
  const out = [];
  out.push('=== PORTFOLIO DEBUG ===');
  out.push('Total stocks: ' + S.portfolio.length);
  out.push('');
  out.push('=== FUND keys: ' + Object.keys(FUND).length + ' ===');
  out.push('');

  S.portfolio.forEach(h => {
    const f = FUND[h.sym];
    const hasFund = !!f;
    const hasLtp  = f && f.ltp > 0;
    out.push(
      h.sym.padEnd(16) +
      ' ltp='    + (h.ltp||h.liveLtp||0) +
      ' FUND='   + (hasFund ? 'YES' : 'NO') +
      (hasFund ? ' f.ltp='+f.ltp+' f.pe='+f.pe+' f.roe='+f.roe : '')
    );
  });
  out.push('');

  out.push('=== ISIN_MAP: ' + Object.keys(ISIN_MAP).length + ' entries ===');
  out.push('');

  out.push('=== Stocks NOT in FUND ===');
  S.portfolio.forEach(h => {
    if(!FUND[h.sym]) out.push('  ' + h.sym.padEnd(16) + ' isin=' + (h.isin||'—') + ' ISIN_MAP=' + (ISIN_MAP[h.isin]||'—'));
  });

  const modal = document.createElement('div');
  modal.style.cssText = 'position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.85);display:flex;flex-direction:column;padding:16px;';
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-family:'Syne',sans-serif;font-size:14px;color:#fff">DIAGNOSTICS</span>
      <button onclick="this.parentElement.parentElement.remove()" style="background:none;border:1px solid #444;color:#fff;padding:4px 12px;border-radius:4px">CLOSE</button>
    </div>
    <div style="flex:1;overflow:auto;background:#000;border:1px solid #333;padding:12px;border-radius:4px">
      <pre style="color:#0f0;font-family:monospace;font-size:10px;margin:0;white-space:pre-wrap">${out.join('\n')}</pre>
    </div>`;
  document.body.appendChild(modal);
}
