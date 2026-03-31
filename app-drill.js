function renderDrill(c){
  const s=S.selStock;
  if(!s){closeStock();return;}
  const bull=s.change>=0;
  const col=bull?'var(--gr2)':'var(--rd2)';
  c.innerHTML=`<div class="drill-wrap">
    <div class="drill-hdr">
      <button class="back-btn" onclick="closeStock()">← Back</button>
      <div class="u-f1min0">
        <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
          <span class="dsym">${s.symbol}</span>
          <span class="dchg" style="color:${col}">₹${fmt(s.ltp)} ${bull?'▲':'▼'} ${Math.abs(s.change||0).toFixed(2)}%</span>
        </div>
        <div style="font-size:11px;color:var(--tx3);margin-top:2px">${trunc(s.name,40)} · ${s.sector||''}</div>
      </div>
      <div class="score-ring" style="border-color:${scoreColor(s.score||65)};background:${scoreColor(s.score||65)}15">
        <div class="score-num" style="color:${scoreColor(s.score||65)}">${s.score||65}</div>
        <div class="score-lbl" style="color:${scoreColor(s.score||65)}">${scoreLabel(s.score||65)}</div>
      </div>
      <button id="btn-del-${s.symbol}" onclick="deletePortfolioStock('${s.symbol}')"
        style="flex-shrink:0;padding:5px 9px;background:rgba(255,59,92,.08);
        border:1px solid rgba(255,59,92,.25);border-radius:7px;color:#ff6b85;
        font-size:10px;font-weight:700;cursor:pointer">✕</button>
    </div>
    <div class="dtabs">
      ${['overview','technical','fundamentals','news','insights'].map(t=>`
        <button class="dtab ${S.drillTab===t?'active':''}" data-t="${t}" onclick="setDrillTab('${t}')">
          ${{overview:'Overview',technical:'📉 Technical',fundamentals:'📊 Fundamentals',news:'📰 News',insights:'💡 Insights'}[t]}
        </button>`).join('')}
    </div>
    <div id="dc">${renderDC(s)}</div>
  </div>`;

}

// ── Insights Tab ──────────────────────────────────────────
function renderDC(s){
  if(S.drillTab==='overview')     return renderOverview(s);
  if(S.drillTab==='technical')    return renderTechnical(s);
  if(S.drillTab==='fundamentals') return renderFundamentals(s);
  if(S.drillTab==='news')         return renderNewsTab(s);
  if(S.drillTab==='insights')     return renderInsights(s);
  return '';
}

// Insights tab: AI portfolio signal generated from concall + holding data
// Distinct from concall signal: this is personal to YOUR position
function renderInsights(s){
  const sym  = s.symbol;
  const f    = FUND[sym]||{};
  const g    = GUIDANCE[sym];
  const h    = S.portfolio.find(p=>p.sym===sym);
  const ins  = g?.insights;

  // Build insight prompt from all available data
  function buildInsightPrompt(){
    const qtrs = (f.quarterly||[]).slice(0,8);
    const yoyRevs = [];
    for(let i=0;i<Math.min(4,qtrs.length-4);i++){
      if(qtrs[i]?.rev&&qtrs[i+4]?.rev)
        yoyRevs.push(+((qtrs[i].rev-qtrs[i+4].rev)/qtrs[i+4].rev*100).toFixed(1));
    }
    const opmTrend = qtrs.length>=8
      ? +(qtrs.slice(0,4).reduce((a,q)=>a+(q.opm||0),0)/4 - qtrs.slice(4,8).reduce((a,q)=>a+(q.opm||0),0)/4).toFixed(1)
      : null;

    // Sector peers from portfolio
    const peers = S.portfolio.map(p=>mergeHolding(p))
      .filter(p=>p.sym!==sym && (FUND[p.sym]?.sector||'')===f.sector)
      .map(p=>p.sym+' PE:'+( FUND[p.sym]?.pe||'?')+'x ROE:'+(FUND[p.sym]?.roe||'?')+'%');

    // Guidance summary
    const gLines = g ? Object.entries(g)
      .filter(([k,v])=>v && typeof v==='string' && !['sym','updated','raw_table','insights'].includes(k))
      .map(([k,v])=>`${k.replace(/_/g,' ')}: ${v}`)
      .slice(0,25).join('\n') : 'No guidance data available';

    return `You are a senior portfolio manager. Analyse this stock and generate sharp, actionable insights.

STOCK: ${sym} — ${f.name||sym}
SECTOR: ${f.sector||'Unknown'}

VALUATION:
- Current PE: ${f.pe||'?'}x | Forward PE: ${f.fwd_pe||'?'}x
- ROE: ${f.roe||'?'}% | OPM: ${f.opm_pct||'?'}% | Debt/Equity: ${f.debt_eq||'?'}
- 52W position: ${f.ath_pct||'?'}% from ATH | MCap: ₹${f.mcap||'?'}Cr

${h?`MY HOLDING:
- Avg Buy: ₹${h.avgBuy||'?'} | Qty: ${h.qty||'?'} | CMP: ₹${f.ltp||'?'}
- Unrealised P&L: ${f.ltp&&h.avgBuy?((f.ltp-h.avgBuy)/h.avgBuy*100).toFixed(1)+'%':'?'}
- Invested: ₹${h.qty&&h.avgBuy?(h.qty*h.avgBuy/100000).toFixed(2)+'L':'?'}`:'Not in portfolio'}

REVENUE DELIVERY (YoY growth last ${yoyRevs.length} quarters): ${yoyRevs.map(v=>(v>=0?'+':'')+v+'%').join(', ')||'Insufficient data'}
MARGIN TREND: ${opmTrend!==null?(opmTrend>0?'Expanding +':'Contracting ')+Math.abs(opmTrend)+'% (4Q avg)':'Insufficient data'}

SECTOR PEERS IN MY PORTFOLIO: ${peers.length?peers.join(' | '):'None'}

CONCALL GUIDANCE EXTRACTED:
${gLines}

---
Generate EXACTLY 6 insights in this format. Each must be sharp, specific, and tell me what to DO:

INSIGHT 1 — [CATEGORY in caps]: [2-3 sentence insight connecting data points]
INSIGHT 2 — [CATEGORY]: [insight]
INSIGHT 3 — [CATEGORY]: [insight]  
INSIGHT 4 — [CATEGORY]: [insight]
INSIGHT 5 — [CATEGORY]: [insight]
INSIGHT 6 — MOAT: [Is the competitive advantage real, widening or narrowing? Rate moat as WIDE/NARROW/NONE. Identify which moat type applies: Switching Cost, Scale Advantage, Intangible Assets, Cost Moat, or Network Effect. Will it protect returns at scale and justify the current valuation?]

Then on a new line:
ACTION: [BUY MORE / AVERAGE DOWN / HOLD / REDUCE / EXIT] — [specific reason with price or trigger]
TRIGGER: [One specific event or price that would change your view]

CATEGORIES to use (pick most relevant): VALUATION | GROWTH QUALITY | MARGIN RISK | SECTOR CYCLE | MANAGEMENT SIGNAL | POSITION RISK | OPPORTUNITY | RED FLAG | CATALYST | COMPETITIVE RISK | MOAT

Rules:
- Be brutally honest — do not be positive just because I hold the stock
- Use actual numbers from the data above
- Each insight must connect at least 2 data points
- No generic statements — every line must be specific to this company`;
  }

  // Parse pasted insights
  function parseInsights(text){
    const lines = text.split('\n').map(l=>l.trim()).filter(Boolean);
    const bullets = lines
      .filter(l=>l.match(/^INSIGHT\s*\d/i))
      .map(l=>{
        const m = l.match(/^INSIGHT\s*\d+\s*[—\-–:]\s*\[?([A-Z\s]+)\]?\s*[—\-–:]\s*(.+)$/i);
        return m ? {cat: m[1].trim(), text: m[2].trim()} : {cat:'INSIGHT', text: l.replace(/^INSIGHT\s*\d+[—\-–:\s]*/i,'').trim()};
      });
    const actionLine = lines.find(l=>l.match(/^ACTION:/i));
    const triggerLine = lines.find(l=>l.match(/^TRIGGER:/i));
    const action  = actionLine?.replace(/^ACTION:\s*/i,'').trim() || null;
    const trigger = triggerLine?.replace(/^TRIGGER:\s*/i,'').trim() || null;
    const headline = bullets[0]?.text?.slice(0,120) || null;
    return { bullets, action, trigger, headline, updated: new Date().toISOString() };
  }

  return `<div style="padding-bottom:80px">

    <!-- Header -->
    <div style="padding:12px 14px 8px;border-bottom:1px solid var(--b1)">
      <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:14px;color:var(--ac)">💡 AI Insights — ${sym}</div>
      <div class="u-sub">Generated from concall data + your holding + sector context</div>
    </div>

    <!-- Existing insights -->
    ${ins && ins.bullets?.length ? `
      <div style="padding:12px 14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div class="u-tx3-9">Last updated: ${new Date(ins.updated).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</div>
          <button onclick="document.getElementById('insight-gen').style.display='block';this.style.display='none'"
            style="background:rgba(249,115,22,.1);border:1px solid rgba(249,115,22,.3);border-radius:5px;padding:3px 10px;color:var(--ac);font-size:8px;font-weight:700;cursor:pointer">
            ↺ Refresh
          </button>
        </div>

        <!-- Action Signal -->
        ${ins.action ? `
        <div style="padding:10px 12px;margin-bottom:10px;border-radius:8px;
          background:rgba(${ins.action.match(/BUY/i)?'0,232,150':ins.action.match(/REDUCE|EXIT/i)?'255,107,133':'255,191,71'},.1);
          border:1px solid rgba(${ins.action.match(/BUY/i)?'0,232,150':ins.action.match(/REDUCE|EXIT/i)?'255,107,133':'255,191,71'},.3)">
          <div style="font-size:8px;color:var(--tx3);margin-bottom:4px">RECOMMENDED ACTION</div>
          <div style="font-size:12px;font-weight:800;color:${ins.action.match(/BUY/i)?'#00e896':ins.action.match(/REDUCE|EXIT/i)?'#ff6b85':'#ffbf47'};line-height:1.4">${ins.action}</div>
        </div>` : ''}

        <!-- Insight bullets -->
        <div style="display:flex;flex-direction:column;gap:8px">
          ${(ins.bullets||[]).map((b,i)=>{
            const catCol = b.cat.match(/RED FLAG|RISK|COMPETITIVE/i)?'#ff6b85':
                           b.cat.match(/OPPORTUNITY|CATALYST|GROWTH/i)?'#00e896':
                           b.cat.match(/VALUATION/i)?'#ffbf47':
                           b.cat.match(/MOAT/i)?'#a78bfa':'#64b5f6';
            return `<div style="padding:10px 12px;background:var(--card);border-radius:8px;
              border-left:3px solid ${catCol};border:1px solid var(--b1);border-left:3px solid ${catCol}">
              <div style="font-size:7px;font-weight:800;color:${catCol};letter-spacing:.8px;margin-bottom:5px">${b.cat}</div>
              <div style="font-size:10px;color:var(--tx1);line-height:1.55">${b.text}</div>
            </div>`;
          }).join('')}
        </div>

        <!-- Trigger -->
        ${ins.trigger ? `
        <div style="margin-top:10px;padding:10px 12px;background:rgba(99,102,241,.08);
          border:1px solid rgba(99,102,241,.25);border-radius:8px">
          <div style="font-size:8px;color:#818cf8;font-weight:700;margin-bottom:4px">🎯 WATCH FOR THIS TRIGGER</div>
          <div style="font-size:10px;color:var(--tx1);line-height:1.5">${ins.trigger}</div>
        </div>` : ''}
      </div>` : ''}

    <!-- Generate section -->
    <div id="insight-gen" style="${ins?'display:none':'display:block'};padding:12px 14px">
      <div class="u-title-10">
        <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
          display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">1</span>
        Generate Insight Prompt
      </div>
      <div style="font-size:9px;color:var(--tx3);margin-bottom:8px">
        Combines your concall data + holding + quarterly trend → tailored prompt for Claude
      </div>
      <button onclick="generateInsightPrompt('${sym}')"
        style="width:100%;padding:10px;background:rgba(249,115,22,.12);border:1px solid rgba(249,115,22,.4);
        border-radius:8px;color:var(--ac);font-size:11px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
        📋 Copy Prompt &amp; Open Claude.ai ↗
      </button>
      ${!g?`<div style="margin-top:6px;font-size:8px;color:#ffbf47">⚠ Run Analysis tab first to extract concall data for richer insights</div>`:''}

      <div style="margin-top:16px;font-size:10px;font-weight:700;color:var(--title);margin-bottom:8px">
        <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
          display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">2</span>
        Paste Claude's Response
      </div>
      <textarea id="ta-insights" placeholder="Paste Claude's 5 insights here..."
        style="width:100%;box-sizing:border-box;height:180px;background:var(--s1);
        border:1px solid var(--b1);border-radius:8px;padding:10px;color:var(--tx1);
        font-size:10px;font-family:var(--mono);resize:vertical;outline:none"></textarea>
      <button onclick="saveInsights('${sym}')"
        style="margin-top:8px;width:100%;padding:10px;background:var(--ac);border:none;
        border-radius:8px;color:#fff;font-size:12px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
        💾 Save Insights
      </button>
    </div>

  </div>`;
}

// Build insight prompt combining concall data + holding + peers
function generateInsightPrompt(sym){
  const f  = FUND[sym]||{};
  const g  = GUIDANCE[sym];
  const h  = S.portfolio.find(p=>p.sym===sym);
  const qtrs = (f.quarterly||[]).slice(0,8);
  const yoyRevs = [];
  for(let i=0;i<Math.min(4,qtrs.length-4);i++){
    if(qtrs[i]?.rev&&qtrs[i+4]?.rev)
      yoyRevs.push(+((qtrs[i].rev-qtrs[i+4].rev)/qtrs[i+4].rev*100).toFixed(1));
  }
  const opmR = qtrs.slice(0,4).filter(q=>q.opm>0);
  const opmO = qtrs.slice(4,8).filter(q=>q.opm>0);
  const opmTrend = opmR.length&&opmO.length
    ? +(opmR.reduce((a,q)=>a+q.opm,0)/opmR.length - opmO.reduce((a,q)=>a+q.opm,0)/opmO.length).toFixed(1)
    : null;

  const peers = S.portfolio.map(p=>mergeHolding(p))
    .filter(p=>p.sym!==sym && (FUND[p.sym]?.sector||'')===f.sector)
    .map(p=>p.sym+' PE:'+(FUND[p.sym]?.pe||'?')+'x ROE:'+(FUND[p.sym]?.roe||'?')+'%');

  const gLines = g ? Object.entries(g)
    .filter(([k,v])=>v && typeof v==='string' && !['sym','updated','raw_table','insights'].includes(k))
    .map(([k,v])=>`${k.replace(/_/g,' ')}: ${v}`)
    .slice(0,25).join('\n') : 'No concall data — run Analysis tab first';

  const prompt = `You are a senior portfolio manager. Analyse this stock and generate sharp, actionable insights.

STOCK: ${sym} — ${f.name||sym}
SECTOR: ${f.sector||'Unknown'}

VALUATION:
- Current PE: ${f.pe||'?'}x | Forward PE: ${f.fwd_pe||'?'}x
- ROE: ${f.roe||'?'}% | OPM: ${f.opm_pct||'?'}% | Debt/Equity: ${f.debt_eq||'?'}
- MCap: ₹${f.mcap||'?'}Cr | ATH%: ${f.ath_pct||'?'}%

${h?`MY HOLDING:
- Avg Buy: ₹${h.avgBuy||'?'} | Qty: ${h.qty||'?'} | CMP: ₹${f.ltp||'?'}
- Unrealised P&L: ${f.ltp&&h.avgBuy?((f.ltp-h.avgBuy)/h.avgBuy*100).toFixed(1)+'%':'?'}
- Invested: ₹${h.qty&&h.avgBuy?(h.qty*h.avgBuy/100000).toFixed(2)+'L':'?'}`:'Not held in portfolio'}

REVENUE TREND (YoY last ${yoyRevs.length}Q): ${yoyRevs.map(v=>(v>=0?'+':'')+v+'%').join(', ')||'Insufficient data'}
MARGIN TREND: ${opmTrend!=null?(opmTrend>0?'Expanding +':'Contracting ')+Math.abs(opmTrend)+'%':'Insufficient data'}

SECTOR PEERS IN MY PORTFOLIO: ${peers.length?peers.join(' | '):'None'}

CONCALL DATA EXTRACTED:
${gLines}

---
Generate EXACTLY 6 insights in this format:

INSIGHT 1 — [CATEGORY]: [2-3 sentence insight connecting multiple data points]
INSIGHT 2 — [CATEGORY]: [insight]
INSIGHT 3 — [CATEGORY]: [insight]
INSIGHT 4 — [CATEGORY]: [insight]
INSIGHT 5 — [CATEGORY]: [insight]
INSIGHT 6 — MOAT: [Is the competitive advantage real, widening or narrowing? Rate moat as WIDE/NARROW/NONE. Identify which moat type applies: Switching Cost, Scale Advantage, Intangible Assets, Cost Moat, or Network Effect. Will it protect returns at scale and justify the current valuation?]

ACTION: [BUY MORE / AVERAGE DOWN / HOLD / REDUCE / EXIT] — [specific reason with price or trigger]
TRIGGER: [One specific event or price that would change your view]

CATEGORIES: VALUATION | GROWTH QUALITY | MARGIN RISK | SECTOR CYCLE | MANAGEMENT SIGNAL | POSITION RISK | OPPORTUNITY | RED FLAG | CATALYST | COMPETITIVE RISK | MOAT

Rules:
- Brutally honest — do not be positive just because I hold it
- Use actual numbers from the data
- Each insight must connect at least 2 data points
- Every line must be specific — no generic statements`;

  // Show prompt modal
  showPromptPanel(sym, prompt);
  if(navigator.clipboard && window.isSecureContext){
    navigator.clipboard.writeText(prompt)
      .then(()=>toast('Insight prompt copied — paste in Claude'))
      .catch(()=>toast('Copy prompt from the panel'));
  }
}

// Parse and save AI insights response to GUIDANCE[sym].insights
function saveInsights(sym){
  const ta = document.getElementById('ta-insights');
  if(!ta||!ta.value.trim()){toast('Paste Claude response first');return;}
  const text = ta.value.trim();

  // Parse bullets
  const lines = text.split('\n').map(l=>l.trim()).filter(Boolean);
  const bullets = lines
    .filter(l=>l.match(/^INSIGHT\s*\d/i))
    .map(l=>{
      const m = l.match(/^INSIGHT\s*\d+\s*[—\-–:]\s*\[?([^\]:\-–]+)\]?\s*[—\-–:]\s*(.+)$/i);
      return m?{cat:m[1].trim().toUpperCase(), text:m[2].trim()}:{cat:'INSIGHT',text:l.replace(/^INSIGHT\s*\d+[—\-–:\s]*/i,'').trim()};
    });
  const actionLine  = lines.find(l=>l.match(/^ACTION:/i));
  const triggerLine = lines.find(l=>l.match(/^TRIGGER:/i));

  if(!bullets.length){toast('Could not parse insights — ensure format matches');return;}

  const ins = {
    bullets,
    action:   actionLine?.replace(/^ACTION:\s*/i,'').trim()||null,
    trigger:  triggerLine?.replace(/^TRIGGER:\s*/i,'').trim()||null,
    headline: bullets[0]?.text?.slice(0,150)||null,
    updated:  new Date().toISOString(),
  };

  if(!GUIDANCE[sym]) GUIDANCE[sym]={sym, updated:new Date().toISOString()};
  GUIDANCE[sym].insights = ins;
  saveGuidanceAll();

  toast('Insights saved for '+sym+' ✓');
  ta.value='';
  render();
}

// Toggle collapsible overview card open/closed
function toggleOvCard(cid){
  const body  = document.getElementById(cid+'-body');
  const chev  = document.getElementById(cid+'-chev');
  if(!body) return;
  const open  = body.style.maxHeight !== '0px' && body.style.maxHeight !== '0';
  body.style.maxHeight = open ? '0'     : '600px';
  body.style.padding   = open ? '0 13px': '10px 13px';
  if(chev) chev.style.transform = open ? 'rotate(0deg)' : 'rotate(180deg)';
}

// Overview tab: price strip, metrics chips, position, insights,
// implied growth, concall signal card, collapsible guidance cards
// ── Overview helpers (shared, top-level) ──────────────────
function pill(txt, col){ return `<span style="display:inline-flex;align-items:center;font-size:8px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:.3px;background:${col}18;color:${col};border:1px solid ${col}40">${txt}</span>`; }
function krow(label, val, col){
  const empty = !val||val==='Not mentioned'||val==='—';
  return `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">
    <span style="font-size:11px;color:var(--tx3);flex-shrink:0;padding-top:1px;min-width:90px">${label}</span>
    <span style="font-size:11px;font-weight:${empty?'400':'600'};color:${empty?'var(--mu)':(col||'var(--tx1)')};text-align:right;line-height:1.45">${empty?'—':val}</span>
  </div>`;
}
function blist(arr, col){
  if(!arr||!arr.length) return '';
  const items = Array.isArray(arr) ? arr : arr.split(/[;,]|\d[.)]\s*/).map(x=>x.trim()).filter(x=>x.length>4);
  return items.map(x=>`<div style="display:flex;gap:8px;padding:5px 0"><span style="color:${col};flex-shrink:0;margin-top:2px;font-size:12px">›</span><span style="font-size:12px;color:var(--tx2);line-height:1.5">${x}</span></div>`).join('');
}
  function gv(k){ return g ? (g[k]||g[k.replace(/_/g,' ')]||null) : null; }


function renderOverview(s){
  const sym = s.symbol;
  const g   = GUIDANCE[sym];
  const ins = g?.insights;
  const f   = FUND[sym]||{};
  const ltp = s.ltp||0;


  // [F] badge — data from fundamentals.json, not concall
  const FB = `<span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:rgba(33,150,243,.15);color:#64b5f6;border:1px solid rgba(33,150,243,.3);margin-left:4px;vertical-align:middle">[F]</span>`;

  // krowF — show concall value first, fall back to FUND value with [F] badge
  function krowF(label, concallVal, fundVal, fundLabel, col){
    if(concallVal && concallVal!=='Not mentioned'){
      return krow(label, concallVal, col);
    } else if(fundVal!=null && fundVal!==''){
      const display = fundLabel ? fundLabel : String(fundVal);
      return krow(label, display+' ${FB}', col||'var(--tx2)');
    }
    return krow(label, null, col); // shows —
  }

  // Web search link — shown when both concall and FUND missing
  function wsLink(label, query){
    const url = 'https://www.google.com/search?q='+encodeURIComponent(query);
    return `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">
      <span style="font-size:11px;color:var(--tx3);flex-shrink:0;min-width:90px">${label}</span>
      <a href="${url}" target="_blank" rel="noopener"
        style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:rgba(100,181,246,.08);border:1px solid rgba(100,181,246,.2);color:#64b5f6;text-decoration:none;white-space:nowrap">🔍 Search</a>
    </div>`;
  }

  // ── 1. PRICE HEADER STRIP ─────────────────────────────────────
  const candles = s.candles||[];
  const hi  = candles.length ? Math.max(...candles.map(c=>c.h)) : ltp;
  const lo  = candles.length ? Math.min(...candles.map(c=>c.l)) : ltp;
  const vol = candles.length ? candles.reduce((a,c)=>a+c.v,0).toFixed(1) : '—';
  const chgCol = (s.change||0)>=0 ? '#00e896' : '#ff6b85';

  const priceStrip = `
    <div style="background:var(--s1);border-bottom:1px solid var(--b1);padding:10px 13px">
      <div class="u-sb-top">
        <div>
          <div style="font-size:24px;font-weight:800;color:var(--tx1);font-family:'JetBrains Mono',monospace;line-height:1">₹${fmt(ltp)}</div>
          <div style="font-size:11px;font-weight:700;color:${chgCol};margin-top:3px">${(s.change||0)>=0?'▲':'▼'} ${Math.abs(s.change||0).toFixed(2)}%</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;text-align:right">
          ${[['Open',fmt(candles[0]?.o||ltp)],['High',fmt(hi)],['Low',fmt(lo)],['Vol',vol+'L']].map(([l,v])=>`
            <div><div style="font-size:7px;color:var(--tx3);text-transform:uppercase;letter-spacing:.4px">${l}</div>
            <div style="font-size:10px;font-weight:600;color:var(--tx2);font-family:var(--mono)">${v}</div></div>`).join('')}
        </div>
      </div>
      ${s.week52H&&s.week52L&&ltp?`
      <div class="u-mt10">
        <div style="display:flex;justify-content:space-between;font-size:7px;color:var(--tx3);margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px">
          <span>52W Low ₹${fmt(s.week52L)}</span>
          <span class="u-bl2">${((ltp-s.week52L)/(s.week52H-s.week52L)*100).toFixed(0)}th percentile</span>
          <span>52W High ₹${fmt(s.week52H)}</span>
        </div>
        <div style="position:relative;height:4px;background:var(--b2);border-radius:2px">
          <div style="position:absolute;top:50%;left:${Math.min(95,Math.max(5,(ltp-s.week52L)/(s.week52H-s.week52L)*100)).toFixed(1)}%;transform:translate(-50%,-50%);width:10px;height:10px;border-radius:50%;background:var(--bl);border:2px solid var(--bg)"></div>
        </div>
      </div>`:''}
    </div>`;

  // ── 2. KEY METRICS ROW (scrollable chips) ─────────────────────
  const metrics = [
    {l:'P/E', v:s.pe?s.pe+'x':null, good:s.pe&&s.pe<18, bad:s.pe&&s.pe>35},
    {l:'P/B', v:s.pb?s.pb+'x':null, good:s.pb&&s.pb<2,  bad:s.pb&&s.pb>5},
    {l:'ROE', v:s.roe?s.roe+'%':null, good:s.roe&&s.roe>15, bad:s.roe&&s.roe<8},
    {l:'ROCE',v:s.roce?s.roce+'%':null, good:s.roce&&s.roce>20, bad:s.roce&&s.roce<10},
    {l:'D/E', v:s.debtEq!=null?s.debtEq+'x':null, good:s.debtEq!=null&&s.debtEq<0.5, bad:s.debtEq!=null&&s.debtEq>1.5},
    {l:'Div', v:s.divYield?s.divYield+'%':null},
    {l:'Prom',v:s.promoter?s.promoter+'%':null, good:s.promoter&&s.promoter>50},
    {l:'Beta',v:s.beta||null, good:s.beta&&s.beta<1, bad:s.beta&&s.beta>1.5},
    {l:'EPS', v:s.eps?'₹'+fmt(s.eps):null},
  ].filter(m=>m.v);

  const metricsRow = metrics.length ? `
    <div style="overflow-x:auto;display:flex;gap:6px;padding:8px 13px;scrollbar-width:none;border-bottom:1px solid var(--b1)">
      ${metrics.map(m=>`
        <div style="flex-shrink:0;background:var(--card);border:1px solid var(--b1);border-radius:8px;padding:8px 11px;text-align:center;min-width:52px;border-top:2px solid ${m.good?'#00d084':m.bad?'#ff3b5c':'var(--b2)'}">
          <div style="font-size:10px;color:var(--tx3);text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px">${m.l}</div>
          <div style="font-size:13px;font-weight:700;color:${m.good?'#00e896':m.bad?'#ff6b85':'var(--tx1)'};font-family:var(--mono)">${m.v}</div>
        </div>`).join('')}
    </div>` : '';

  // ── 3. MY POSITION (if held) ──────────────────────────────────
  const posCard = S.selStock?.qty&&s.avgBuy ? (()=>{
    const pnl    = s.qty*(ltp-s.avgBuy);
    const pnlPct = ((ltp-s.avgBuy)/s.avgBuy*100).toFixed(2);
    const up     = pnl>=0;
    return `<div style="margin:8px 12px;padding:10px 13px;background:var(--card);border-radius:10px;border:1px solid var(--b1);border-left:3px solid ${up?'#00d084':'#ff3b5c'}">
      <div style="font-size:8px;font-weight:700;color:var(--label);text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px">My Position</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
        ${[['Qty',s.qty],['Avg Buy','₹'+fmt(s.avgBuy)],['P&L',(up?'+':'')+pnlPct+'%'],['Value','₹'+fmt(s.qty*ltp)]].map(([l,v],i)=>`
          <div><div style="font-size:7px;color:var(--tx3);margin-bottom:2px">${l}</div>
          <div style="font-size:10px;font-weight:700;color:${i===2?(up?'#00e896':'#ff6b85'):'var(--tx1)'};font-family:var(--mono)">${v}</div></div>`).join('')}
      </div>
    </div>`;
  })() : '';

  // ── 4. AI INSIGHTS STRIP ──────────────────────────────────────
  const insStrip = ins ? `
    <div style="margin:0 12px 0;padding:10px 13px;background:rgba(249,115,22,.07);border:1px solid rgba(249,115,22,.2);border-radius:10px;cursor:pointer" onclick="setDrillTab('insights')">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
        <div style="display:flex;align-items:baseline;gap:6px;flex:1;min-width:0">
          <span style="font-size:11px;font-weight:800;color:var(--ac);flex-shrink:0">💡 Portfolio Signal</span>
          <span style="font-size:11px;color:var(--tx2);line-height:1.45;font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">"${ins.headline||ins.bullets?.[0]||''}"</span>
        </div>
        <span style="font-size:11px;font-weight:700;color:var(--ac);flex-shrink:0">→</span>
      </div>
      ${ins.action?`<div style="margin-top:6px;font-size:9px;font-weight:700;color:${ins.action.match(/BUY/i)?'#00e896':ins.action.match(/REDUCE|EXIT/i)?'#ff6b85':'#ffbf47'}">${ins.action.split('—')[0].trim()}</div>`:''}
    </div>` : `
    <div style="margin:0 12px 0;padding:10px 13px;background:rgba(249,115,22,.03);border:1px dashed rgba(249,115,22,.15);border-radius:10px;cursor:pointer;text-align:center" onclick="setDrillTab('insights')">
      <span style="font-size:12px;color:var(--tx3)">💡 No Portfolio Signal — tap to generate</span>
    </div>`;

  // ── 5. GUIDANCE SECTION (only if g exists) ────────────────────
  if(!g) return `<div>${priceStrip}${metricsRow}${posCard}
    <div style="margin:10px 12px 0">${insStrip}</div>
    <div style="margin:10px 12px;padding:16px;background:var(--card);border-radius:10px;border:1px solid var(--b1);text-align:center">
      <div class="u-28mb">📋</div>
      <div style="font-size:12px;font-weight:700;color:var(--tx1);margin-bottom:5px">No analysis yet</div>
      <div style="font-size:9px;color:var(--tx3);margin-bottom:12px;line-height:1.5">Go to Analysis tab → select ${sym} → copy prompt → paste Claude's response</div>
      <button onclick="showTab('analysis',document.querySelector('.nb:last-child'))"
        style="background:var(--ac);color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:11px;font-weight:700;cursor:pointer">
        Open Analysis Tab
      </button>
    </div>
  </div>`;

  // ── g exists — build full overview ────────────────────────────
  const actionVal  = g.action_signal||g['action signal']||'';
  const actionType = actionVal.match(/BUY MORE/i)?'BUY MORE':actionVal.match(/\bBUY\b/i)?'BUY':actionVal.match(/REDUCE/i)?'REDUCE':actionVal.match(/EXIT/i)?'EXIT':'HOLD';
  const actionCol  = ['BUY MORE','BUY'].includes(actionType)?'#00e896':['REDUCE','EXIT'].includes(actionType)?'#ff6b85':'#ffbf47';
  const actionReason = actionVal.replace(/BUY MORE|BUY|REDUCE|EXIT|HOLD/gi,'').replace(/^[\s\-–:]+/,'').trim();
  const verdict    = g.one_line_verdict||g['one line verdict']||g.summary||'';
  const tone       = g.tone||'Neutral';
  const toneCol    = tone==='Positive'?'#00e896':tone==='Negative'?'#ff6b85':'#ffbf47';
  const conf       = g.confidence||g.confidence_level||'Medium';
  const confCol    = conf==='High'?'#00e896':conf==='Low'?'#ff6b85':'#ffbf47';
  const updated    = g.updated ? new Date(g.updated).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '';

  // Implied growth
  let igBadge = '';
  if(f.pe>0&&f.fwd_pe>0){
    const ig = +((f.pe/f.fwd_pe-1)*100).toFixed(1);
    igBadge = `<div style="margin:8px 12px 0;padding:9px 12px;background:rgba(${ig>=0?'0,232,150':'255,107,133'},.06);border:1px solid rgba(${ig>=0?'0,232,150':'255,107,133'},.2);border-radius:8px;display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:7px;color:var(--tx3);text-transform:uppercase;letter-spacing:.5px">Implied Earnings Growth</div>
      <div style="font-size:18px;font-weight:800;color:${ig>=0?'#00e896':'#ff6b85'};font-family:var(--mono);margin-top:2px">${ig>=0?'+':''}${ig}%</div></div>
      <div class="u-tar">
        <div style="font-size:8px;color:var(--tx3)">Trailing</div><div style="font-size:11px;font-weight:700;color:var(--tx2);font-family:var(--mono)">${f.pe.toFixed(1)}x</div>
        <div style="font-size:8px;color:var(--tx3);margin-top:3px">Forward</div><div style="font-size:11px;font-weight:700;color:var(--tx2);font-family:var(--mono)">${f.fwd_pe.toFixed(1)}x</div>
      </div>
    </div>`;
  }

  // ── CARD: Action Signal ────────────────────────────────────────
  const signalCard = `
    <div style="margin:10px 12px 0;border-radius:12px;overflow:hidden;border:1px solid ${actionCol}35">
      <div style="padding:12px 14px;background:${actionCol}12">
        <!-- Row 1: label + date -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-size:10px;font-weight:700;color:var(--tx3);text-transform:uppercase;letter-spacing:.8px">📋 Concall Signal</span>
          <span class="u-tx3-10">${updated}</span>
        </div>
        <!-- Row 2: action word + conf pill same line, tone separate -->
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span style="font-size:16px;font-weight:900;color:${actionCol};font-family:'Syne',sans-serif;letter-spacing:.5px">${actionType}</span>
          ${pill(conf,confCol)}
          ${pill(tone,toneCol)}
        </div>
        <!-- Row 3: reason -->
        ${actionReason?`<div style="font-size:9px;color:${actionCol};opacity:.85;margin-top:5px;line-height:1.45">${actionReason}</div>`:''}
        <!-- Row 4: verdict quote — no italics -->
        ${verdict?`<div style="margin-top:8px;padding:9px 11px;background:rgba(0,0,0,.2);border-radius:8px;font-size:12px;color:var(--tx1);line-height:1.55">"${verdict}"</div>`:''}
      </div>
    </div>`;

  // ── CARDS: Collapsible sections ───────────────────────────────
  const cardId = id => 'ov-'+sym+'-'+id;
  function colCard(id, icon, title, col, isOpen, bodyHtml){
    if(!bodyHtml||!bodyHtml.trim()) return '';
    const cid = cardId(id);
    return `<div style="margin:6px 12px 0;border-radius:10px;overflow:hidden;border:1px solid var(--b1)">
      <div onclick="toggleOvCard('${cid}')" style="display:flex;justify-content:space-between;align-items:center;padding:10px 13px;background:var(--card);cursor:pointer;-webkit-tap-highlight-color:transparent">
        <div style="display:flex;align-items:center;gap:7px">
          <span style="font-size:13px">${icon}</span>
          <span style="font-size:12px;font-weight:700;color:var(--tx1)">${title}</span>
          <div style="width:6px;height:6px;border-radius:50%;background:${col};flex-shrink:0"></div>
        </div>
        <span id="${cid}-chev" style="font-size:9px;color:var(--tx3);display:inline-block;transform:${isOpen?'rotate(180deg)':'rotate(0deg)'};transition:transform .2s">▼</span>
      </div>
      <div id="${cid}-body" style="background:var(--s2);padding:${isOpen?'10px 13px':'0 13px'};max-height:${isOpen?'800px':'0'};overflow:hidden;transition:max-height .28s ease,padding .2s ease">
        ${bodyHtml}
      </div>
    </div>`;
  }

  // Forward Guidance body
  const guidBody = [
    krow('Revenue Target',  gv('revenue_guidance')),
    krow('Growth Guided',   gv('revenue_growth_target')||gv('growth_target')),
    krowF('EBITDA Margin',  gv('ebitda_margin_target')||gv('margin_guidance'), f.opm_pct!=null?f.opm_pct.toFixed(1)+'%':null, null),
    krowF('PAT Margin',     gv('pat_margin_target'), f.npm_pct!=null?f.npm_pct.toFixed(1)+'%':null, null),
    krowF('EPS Estimate',   gv('eps_estimate')||gv('analyst_eps_estimate'), f.eps?'₹'+f.eps.toFixed(1)+' (TTM)':null, null),
    krow('Order Book',      gv('order_book')),
    krow('Pipeline',        gv('pipeline')),
    krow('Deal Wins',       gv('deal_wins')),
  ].join('');

  // Geography body — chips
  const geoRawKey = Object.keys(g).find(k=>k.includes('geographic'));
  const geoRaw    = geoRawKey ? g[geoRawKey] : null;
  let geoBody = '';
  if(!geoRaw||geoRaw==='Not mentioned'){
    geoBody = `<div style="font-size:11px;color:var(--mu);padding:4px 0">— Not mentioned in concall</div>`;
  } else {
    const parts = geoRaw.split(/[;,]/).map(x=>x.trim()).filter(x=>x.length>1);
    const palG  = ['#64b5f6','#4dd0e1','#80cbc4','#81d4fa','#b39ddb','#ef9a9a'];
    geoBody = `<div style="display:flex;flex-wrap:wrap;gap:6px;padding:2px 0">`
      + parts.map((p,i)=>{
          const m   = p.match(/([\d.]+)%/);
          const pct = m?+m[1]:null;
          const loc = p.replace(/[\d.]+%/,'').replace(/[:\-]/g,'').trim();
          const col = palG[i%palG.length];
          return `<div style="background:${col}10;border:1px solid ${col}30;border-radius:8px;padding:6px 10px;text-align:center;min-width:52px">`
            +`<div style="font-size:8px;color:${col};font-weight:700;margin-bottom:1px">${loc}</div>`
            +(pct?`<div style="font-size:12px;font-weight:800;color:var(--tx1);font-family:var(--mono)">${pct}%</div>`:'')+`</div>`;
        }).join('')+'</div>';
  }

  // Products body — bar rows
  const kpRawKey = Object.keys(g).find(k=>k.includes('key_product')||k.includes('product_mix')||k.includes('products_portfolio'));
  const kpRaw    = (kpRawKey?g[kpRawKey]:null)||gv('segment_growth')||gv('key_segments');
  let prodBody = '';
  if(!kpRaw||kpRaw==='Not mentioned'){
    prodBody = `<div style="font-size:11px;color:var(--mu);padding:4px 0">— Not mentioned in concall</div>`;
  } else {
    const parts = kpRaw.split(/[;,]/).map(x=>x.trim()).filter(x=>x.length>2);
    const palP  = ['#f59e0b','#22d3ee','#4ade80','#fb923c','#a78bfa','#f472b6'];
    prodBody = `<div style="display:flex;flex-direction:column;gap:7px;padding:2px 0">`
      + parts.map((p,i)=>{
          const m   = p.match(/([\d.]+)%/);
          const pct = m?+m[1]:null;
          const nm  = p.replace(/[\d.]+%/,'').replace(/[:\-]/g,'').trim();
          const col = palP[i%palP.length];
          return `<div class="u-row">`
            +`<div style="width:100px;font-size:9px;color:var(--tx2);text-align:right;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${nm}</div>`
            +(pct
              ?`<div style="flex:1;background:var(--b1);border-radius:3px;height:14px;position:relative;overflow:hidden"><div style="position:absolute;left:0;top:0;height:100%;width:${Math.min(100,pct)}%;background:${col};opacity:.7;border-radius:3px"></div></div><div style="font-size:9px;font-weight:700;color:${col};width:32px;text-align:right;flex-shrink:0">${pct}%</div>`
              :`<div style="flex:1;font-size:9px;color:var(--tx2);line-height:1.4">${p}</div>`)
            +'</div>';
        }).join('')+'</div>';
  }

  // Business & Capital body
  const _name = f.name||sym;
  const bizBody = [
    gv('market_share')
      ? krow('Market Share', gv('market_share'))
      : wsLink('Market Share', _name+' market share 2025'),
    krow('New Products',    gv('new_products')),
    gv('capex_plan')
      ? krow('Capex Plan', gv('capex_plan'))
      : wsLink('Capex Plan', _name+' capex plan FY26'),
    krow('Debt Reduction',  gv('debt_reduction_plan')),
    krowF('Dividend',       gv('dividend_guidance'), f.div_yield?f.div_yield.toFixed(2)+'%':null, null),
    krow('M&A / JV',        gv('acquisitions')),
    gv('raw_material_outlook')
      ? krow('Raw Materials', gv('raw_material_outlook'))
      : wsLink('Raw Materials', _name+' raw material cost outlook 2025'),
    gv('headcount_plans')
      ? krow('Headcount', gv('headcount_plans'))
      : wsLink('Headcount', _name+' employee headcount 2025'),
    gv('working_capital')
      ? krow('Working Capital', gv('working_capital'))
      : wsLink('Working Capital', _name+' working capital days FY26'),
    krowF('Sales TTM',      null, f.sales?(f.sales/100).toFixed(0)+'Cr':null, null),
    krowF('CFO TTM',        null, f.cfo?(f.cfo/100).toFixed(0)+'Cr':null, null),
  ].join('');

  // Management & Analyst body
  const mgmtBody = [
    krow('Tone',          tone, toneCol),
    krow('Credibility',   gv('management_credibility'), (gv('management_credibility')||'').match(/Yes/i)?'#00e896':(gv('management_credibility')||'').match(/No/i)?'#ff6b85':'#ffbf47'),
    gv('analyst_consensus')||gv('analyst_rating')
      ? krow('Consensus', gv('analyst_consensus')||gv('analyst_rating'), '#64b5f6')
      : wsLink('Consensus', _name+' analyst consensus rating 2025'),
    gv('price_target')||gv('analyst_price_target')
      ? krow('Price Target', gv('price_target')||gv('analyst_price_target'), '#64b5f6')
      : wsLink('Price Target', _name+' analyst price target 2025'),
    krow('Currency Risk', gv('currency_exposure')),
    krow('Regulatory',    gv('regulatory_impact')),
  ].join('');

  // Commitments & Risks body
  const commitArr = g.specific_commitments||g['specific commitments']||g.key_commitments||[];
  const risksArr  = g.key_risks||g['key risks']||g.risks_flagged||[];
  const riskBody  =
    `<div style="margin-bottom:10px">
      <div style="font-size:10px;font-weight:700;color:#00e896;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Commitments</div>
      ${commitArr.length ? blist(commitArr,'#00e896') : '<div style="font-size:11px;color:var(--mu)">— Not mentioned in concall</div>'}
    </div>`
  + `<div>
      <div style="font-size:10px;font-weight:700;color:#ff6b85;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Key Risks</div>
      ${risksArr.length ? blist(risksArr,'#ff6b85') : '<div style="font-size:11px;color:var(--mu)">— Not mentioned in concall</div>'}
    </div>`;

  return `<div style="padding-bottom:16px">
    ${priceStrip}
    ${metricsRow}
    ${posCard}
    <div style="padding:8px 12px 0;display:flex;flex-direction:column;gap:0">
      ${insStrip}
      ${igBadge}
      ${signalCard}
      ${colCard('guid', '📈', 'Forward Guidance',    '#64b5f6', false, guidBody)}
      ${colCard('geo',  '🌍', 'Geographic Mix',      '#4dd0e1', false, geoBody)}
      ${colCard('prod', '📦', 'Products & Segments', '#f59e0b', false, prodBody)}
      ${colCard('biz',  '⚙️', 'Business & Capital',  '#a78bfa', false, bizBody)}
      ${colCard('mgmt', '👔', 'Management & Analyst','#8eb0d0', false, mgmtBody)}
      ${colCard('risk', '⚠️', 'Commitments & Risks', '#ff6b85', false, riskBody)}
    </div>
  </div>`;
}

//  FIX #6: PROPER CANDLESTICK CHART
// Technical tab: candlestick chart + MA overlays + signal table
function renderTechnical(s){
  const signals=[
    {n:'RSI (14)',v:s.rsi,sub:'Value: '+s.rsi,sig:s.rsi>70?'Overbought':s.rsi<30?'Oversold':'Neutral',sc:s.rsi>70?'sig-sell':s.rsi<30?'sig-buy':'sig-neutral'},
    {n:'MACD',v:s.macd?.toFixed(1)||'—',sub:'Signal: '+(s.macdSignal?.toFixed(1)||'—'),sig:s.macd>s.macdSignal?'Bullish':'Bearish',sc:s.macd>s.macdSignal?'sig-buy':'sig-sell'},
    {n:'Stoch %K',v:s.stochK||'—',sub:'%D: '+(s.stochD||'—'),sig:s.stochK>80?'Overbought':s.stochK<20?'Oversold':'Neutral',sc:s.stochK>80?'sig-sell':s.stochK<20?'sig-buy':'sig-neutral'},
    {n:'ADX',v:s.adx||'—',sub:s.adx>25?'Strong trend':'Ranging',sig:s.adx>25?'Trending':'No Trend',sc:s.adx>25?'sig-buy':'sig-neutral'},
    {n:'SMA 20',v:'₹'+fmt(s.sma20),sub:s.ltp>s.sma20?'Above':'Below',sig:s.ltp>s.sma20?'Bullish':'Bearish',sc:s.ltp>s.sma20?'sig-buy':'sig-sell'},
    {n:'SMA 50',v:'₹'+fmt(s.sma50),sub:s.ltp>s.sma50?'Above':'Below',sig:s.ltp>s.sma50?'Bullish':'Bearish',sc:s.ltp>s.sma50?'sig-buy':'sig-sell'},
    {n:'EMA 200',v:'₹'+fmt(s.ema200),sub:s.ltp>s.ema200?'Above':'Below',sig:s.ltp>s.ema200?'Bull LT':'Bear LT',sc:s.ltp>s.ema200?'sig-buy':'sig-sell'},
  ];
  const buys=signals.filter(x=>x.sc==='sig-buy').length;
  const sells=signals.filter(x=>x.sc==='sig-sell').length;
  const verdict=buys>=5?'Strong Buy':buys>=4?'Buy':buys>=3?'Weak Buy':sells>=4?'Strong Sell':sells>=3?'Sell':'Neutral';
  const vc=verdict.includes('Buy')?'var(--gr2)':verdict.includes('Sell')?'var(--rd2)':'var(--yw2)';
  const vbg=verdict.includes('Buy')?'rgba(0,208,132,.1)':verdict.includes('Sell')?'rgba(255,59,92,.1)':'rgba(245,166,35,.1)';

  return `<div>
    <!-- Chart controls -->
    <div style="padding:6px 10px;background:var(--s2);border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center;gap:8px">
      <div style="font-family:var(--mono);font-size:11px;color:var(--tx2);white-space:nowrap">${s.symbol} · Price Chart</div>
      <div style="display:flex;gap:6px;align-items:center">
        <!-- Interval dropdown -->
        <select onchange="setChartInterval(this.value)" style="background:var(--s1);color:var(--tx1);border:1px solid var(--b1);border-radius:6px;padding:4px 6px;font-size:11px;font-family:var(--mono);cursor:pointer;outline:none">
          <option value="D" ${S.chartInterval==='D'?'selected':''}>Daily</option>
          <option value="W" ${S.chartInterval==='W'?'selected':''}>Weekly</option>
          <option value="M" ${S.chartInterval==='M'?'selected':''}>Monthly</option>
        </select>
        <!-- Range dropdown -->
        <select onchange="setChartRange(this.value)" style="background:var(--s1);color:var(--tx1);border:1px solid var(--b1);border-radius:6px;padding:4px 6px;font-size:11px;font-family:var(--mono);cursor:pointer;outline:none">
          <option value="1M" ${S.chartRange==='1M'?'selected':''}>1 Month</option>
          <option value="3M" ${S.chartRange==='3M'?'selected':''}>3 Months</option>
          <option value="6M" ${S.chartRange==='6M'?'selected':''}>6 Months</option>
          <option value="1Y" ${S.chartRange==='1Y'?'selected':''}>1 Year</option>
          <option value="5Y" ${S.chartRange==='5Y'?'selected':''}>5 Years</option>
        </select>
      </div>
    </div>

    <!-- Unified overlay bar: MAs + KPIs as checkboxes -->
    <div style="padding:5px 10px;background:var(--s2);border-bottom:1px solid var(--b1);display:flex;flex-wrap:wrap;gap:8px;align-items:center">
      <!-- MA overlays -->
      ${[
        {k:'sma20', label:'SMA20',  col:'#f59e0b', type:'ma'},
        {k:'sma50', label:'SMA50',  col:'#3b82f6', type:'ma'},
        {k:'ema200',label:'EMA200', col:'#a855f7', type:'ma'},
        {k:'vol',   label:'Volume', col:'#22c55e', type:'ma'},
      ].map(({k,label,col,type})=>`
        <label style="display:flex;align-items:center;gap:3px;cursor:pointer">
          <input type="checkbox" ${S.maVis[k]?'checked':''}
            onchange="toggleMA('${k}')"
            style="accent-color:${col};width:11px;height:11px;cursor:pointer">
          <span style="font-size:9px;color:${col};font-weight:600">${label}</span>
        </label>`).join('')}
      <span style="width:1px;height:14px;background:var(--b1);margin:0 2px"></span>
      <!-- KPI overlays -->
      ${[
        {k:'pe',  label:'P/E',    col:'#fbbf24', avail:!!(s.pe)},
        {k:'rev', label:'Revenue',col:'#22d3ee', avail:!!(s.sales||(s.quarterly&&s.quarterly.some(q=>q.rev)))},
        {k:'net', label:'Net',    col:'#4ade80', avail:!!(s.npm_pct||(s.quarterly&&s.quarterly.some(q=>q.net)))},
        {k:'cfo', label:'CFO',    col:'#34d399', avail:!!(s.cfo||(s.quarterly&&s.quarterly.some(q=>q.cfo)))},
        {k:'opm', label:'OPM%',   col:'#fb923c', avail:!!(s.opm_pct||(s.quarterly&&s.quarterly.some(q=>q.opm)))},
        {k:'debt',label:'Debt',   col:'#f87171', avail:!!(s.debt_eq||(s.quarterly&&s.quarterly.some(q=>q.debt)))},
      ].map(({k,label,col,avail})=>`
        <label style="display:flex;align-items:center;gap:3px;cursor:pointer;opacity:${avail?1:0.4}" title="${avail?'':'Run Actions to fetch quarterly data'}">
          <input type="checkbox" ${S.kpiVis[k]?'checked':''} ${avail?'':'disabled'}
            onchange="toggleKPI('${k}')"
            style="accent-color:${col};width:11px;height:11px;cursor:pointer">
          <span style="font-size:9px;color:${col};font-weight:600">${label}</span>
        </label>`).join('')}
    </div>

    <!-- MAIN CANDLESTICK CANVAS — KPI overlays drawn here -->
    <div style="position:relative;background:var(--s1);border-bottom:1px solid var(--b1)">
      <div id="chart-wrap" style="position:relative;width:100%;height:240px">
        <canvas id="cv-candle" style="position:absolute;top:0;left:0;width:100%;height:100%"></canvas>
      </div>
      <!-- Volume: bars + optional line trend -->
      ${S.maVis.vol?`<div id="vol-wrap" style="position:relative;width:100%;height:50px;border-top:1px solid var(--b1)">
        <canvas id="cv-vol" style="position:absolute;top:0;left:0;width:100%;height:100%"></canvas>
      </div>`:''}
    </div>

    <div class="chart-stats" style="border-top:1px solid var(--b1);background:var(--s2)">
      <div class="cstat"><div class="cstat-l">Return</div><div class="cstat-v" id="cstat-ret">—</div></div>
      <div class="cstat"><div class="cstat-l">Period High</div><div class="cstat-v" id="cstat-hi">—</div></div>
      <div class="cstat"><div class="cstat-l">Period Low</div><div class="cstat-v" id="cstat-lo">—</div></div>
      <div class="cstat"><div class="cstat-l">Volatility</div><div class="cstat-v" id="cstat-vol">—</div></div>

    </div>

    <!-- Verdict -->
    <div style="margin:10px 12px;padding:14px;border-radius:10px;text-align:center;border:1px solid ${vc}30;background:${vbg}">
      <div style="font-size:9px;font-weight:700;color:var(--label);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Composite Signal</div>
      <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:${vc}">${verdict}</div>
      <div style="height:5px;background:var(--b1);border-radius:3px;overflow:hidden;margin:8px 0 4px">
        <div style="height:100%;width:${(buys/signals.length*100).toFixed(0)}%;background:${vc};border-radius:3px"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--tx3)">
        <span>${buys} Bullish</span><span>${sells} Bearish</span>
      </div>
    </div>

    <!-- Signal rows -->
    <div style="padding:0 12px 14px">
      <div class="sec-lbl">Technical Indicators</div>
      ${signals.map(sg=>`
        <div class="sig-row">
          <div>
            <div class="sig-name">${sg.n}</div>
            <div class="sig-sub">${sg.sub}</div>
          </div>
          <div class="u-row">
            <span class="sig-pill ${sg.sc}">${sg.sig}</span>
            <span class="sig-val">${sg.v}</span>
          </div>
        </div>`).join('')}

      <!-- S&R levels -->
      <div class="u-mt10"><div class="sec-lbl">Support & Resistance</div></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px">
        ${[
          {l:'Resistance 2',v:s.resist1?fmt(s.resist1*(1.03)):fmt((s.ltp||100)*1.06),c:'var(--rd2)'},
          {l:'Resistance 1',v:s.resist1?fmt(s.resist1):fmt((s.ltp||100)*1.03),c:'var(--rd)'},
          {l:'Support 1',v:s.support1?fmt(s.support1):fmt((s.ltp||100)*0.97),c:'var(--gr)'},
          {l:'Support 2',v:s.support1?fmt(s.support1*(0.97)):fmt((s.ltp||100)*0.94),c:'var(--gr2)'},
        ].map(x=>`
          <div style="background:var(--s2);border:1px solid var(--b1);border-left:3px solid ${x.c};border-radius:8px;padding:9px 11px">
            <div style="font-size:8px;font-weight:700;color:var(--label);text-transform:uppercase;letter-spacing:.5px">${x.l}</div>
            <div style="font-family:var(--mono);font-size:14px;font-weight:700;color:${x.c};margin-top:3px">₹${x.v}</div>
          </div>`).join('')}
      </div>
    </div>
  </div>`;
}

function setChartRange(r){
  S.chartRange=r;
  if(S.drillTab==='technical') scheduleChartRedraw();
}
function setChartInterval(iv){
  S.chartInterval=iv;
  if(S.drillTab==='technical') scheduleChartRedraw();
}
function toggleMA(key){
  S.maVis[key]=!S.maVis[key];
  if(S.drillTab==='technical'){
    // vol toggle needs HTML re-render (shows/hides vol canvas)
    if(key==='vol'){
      const dc=document.getElementById('dc');
      if(dc){ dc.innerHTML=renderDC(S.selStock); }
    }
    scheduleChartRedraw();
  }
}
function toggleKPI(k){
  S.kpiVis[k]=!S.kpiVis[k];
  if(S.drillTab==='technical') scheduleChartRedraw();
}
// Redraw canvases without destroying HTML structure
function scheduleChartRedraw(){
  // Data already in chartCache after first load — just redraw
  if(S.selStock && chartCache[S.selStock.symbol]){
    S.selStock.candles = chartCache[S.selStock.symbol];
  }
  requestAnimationFrame(()=>requestAnimationFrame(()=>scheduleTACharts(S.selStock)));
}

// ── Chart Drawing Engine ──────────────────────────────

// Aggregate daily bars → weekly or monthly OHLCV
function aggregateCandles(daily, interval){
  if(interval === 'D' || !daily.length) return daily;

  const buckets = {};
  daily.forEach(c => {
    const d = new Date(c.d);
    let key;
    if(interval === 'W'){
      // Week key = Monday of that week (ISO)
      const day = d.getDay(); // 0=Sun
      const monday = new Date(d);
      monday.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
      key = monday.toISOString().slice(0,10);
    } else {
      // Month key = YYYY-MM
      key = c.d.slice(0,7);
    }
    if(!buckets[key]){
      buckets[key] = { d: key, o: c.o, h: c.h, l: c.l, c: c.c, v: c.v };
    } else {
      const b = buckets[key];
      b.h = Math.max(b.h, c.h);
      b.l = Math.min(b.l, c.l);
      b.c = c.c;       // last close in period
      b.v += c.v;
    }
  });
  return Object.values(buckets).sort((a,b) => a.d.localeCompare(b.d));
}

// Schedule chart redraws after DOM paint (2x rAF for reliable width)
function scheduleTACharts(s){
  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      drawCandlestick(s);
      if(S.maVis.vol) drawVolume(s);
      updateChartStats(s);
    });
  });
}

// Redraw on resize — canvas width changes when panel opens/rotates
let _chartResizeObs = null;
function attachChartResizeObserver(s){
  if(_chartResizeObs) _chartResizeObs.disconnect();
  const wrap = document.getElementById('chart-wrap');
  if(!wrap || !window.ResizeObserver) return;
  _chartResizeObs = new ResizeObserver(()=>{ scheduleTACharts(s); });
  _chartResizeObs.observe(wrap);
}

function getSlicedCandles(s, canvasWidth){
  const daily = s.candles || [];
  if(!daily.length) return daily;

  // Step 1: Aggregate all daily bars to chosen interval
  const allAgg = aggregateCandles(daily, S.chartInterval);
  if(!allAgg.length) return [];

  // Step 2: Filter by date range (calendar-based)
  const now = new Date();
  const rangeMs = {'1M':30,'3M':91,'6M':182,'1Y':365,'5Y':1825}[S.chartRange] || 91;
  const cutoff = new Date(now - rangeMs*864e5).toISOString().slice(0,10);
  let rangeCandles = allAgg.filter(c => c.d >= cutoff);
  if(!rangeCandles.length) rangeCandles = allAgg.slice(-60);

  // Step 3: Fit to canvas — ideal bar width is 6-8px, minimum 4px
  // This drives HOW MANY bars show, not just caps them
  if(canvasWidth && canvasWidth > 0){
    const PAD_L = 6, PAD_R = 52;
    const chartW = canvasWidth - PAD_L - PAD_R;
    const IDEAL_BAR_W = 7;   // px — comfortable readable width
    const MIN_BAR_W  = 4;    // px — absolute minimum before bars become unreadable
    const maxFit = Math.floor(chartW / MIN_BAR_W);
    const idealFit = Math.floor(chartW / IDEAL_BAR_W);

    if(rangeCandles.length > maxFit){
      // Too many bars — take most recent maxFit
      return rangeCandles.slice(-maxFit);
    }
    // If fewer bars than ideal, that's fine — bars just get wider (up to 10px cap in draw)
  }
  return rangeCandles;
}

// Main candlestick chart with MA overlays and KPI overlays
// KPI overlays use a dedicated Y-axis scale separate from price
function drawCandlestick(s){
  const cv=document.getElementById('cv-candle');
  if(!cv)return;
  const wrap=document.getElementById('chart-wrap');
  // offsetWidth gives the rendered pixel width — reliable after DOM paint
  const W2=Math.max(wrap?wrap.offsetWidth:0, cv.offsetWidth, 280);
  const H2=200;
  const dpr=window.devicePixelRatio||1;
  cv.width=W2*dpr; cv.height=H2*dpr;
  cv.style.width=W2+'px'; cv.style.height=H2+'px';
  const ctx=cv.getContext('2d');
  ctx.scale(dpr,dpr);

  const candles=getSlicedCandles(s, W2);
  if(!candles.length){
    ctx.fillStyle='#060c18'; ctx.fillRect(0,0,W2,H2);
    ctx.textAlign='center';
    if(s._noChartData){
      ctx.fillStyle='rgba(245,166,35,.7)'; ctx.font='bold 11px DM Sans';
      ctx.fillText('No chart data for '+s.symbol, W2/2, H2/2-16);
      ctx.fillStyle='rgba(140,176,208,.5)'; ctx.font='10px DM Sans';
      ctx.fillText('Add to watchlist.txt → run GitHub Actions', W2/2, H2/2+4);
      ctx.fillText('(fetch_type: new_symbol)', W2/2, H2/2+20);
    } else {
      ctx.fillStyle='rgba(120,150,180,.4)'; ctx.font='12px DM Sans';
      ctx.fillText('Loading chart data…', W2/2, H2/2);
    }
    return;
  }

  const W=W2,H=H2;
  const PAD={l:6,r:52,t:8,b:22};
  const cW=W-PAD.l-PAD.r, cH=H-PAD.t-PAD.b;
  const n=candles.length;
  const gap=cW/n;
  const bw=Math.max(2,Math.min(14,gap*0.7));

  // Full history + visible date range — used by both MAs and KPI overlays
  const allCandles = s.candles || candles;
  const visFirst = candles.length ? new Date(candles[0].d).getTime() : 0;
  const visLast  = candles.length ? new Date(candles[candles.length-1].d).getTime() : 1;
  const visRange = visLast - visFirst || 1;

  const allPrices=candles.flatMap(c=>[c.h,c.l]);
  if(s.sma20&&S.maVis.sma20)allPrices.push(s.sma20);
  if(s.sma50&&S.maVis.sma50)allPrices.push(s.sma50);
  if(s.ema200&&S.maVis.ema200)allPrices.push(s.ema200);
  const mn=Math.min(...allPrices), mx=Math.max(...allPrices), rng=mx-mn||1;
  const toY=p=>PAD.t+((mx-p)/rng)*cH;
  const barX=i=>PAD.l+i*gap+gap/2;

  // Background
  ctx.fillStyle='#070c18';
  ctx.fillRect(0,0,W,H);

  // Grid lines
  for(let i=0;i<=4;i++){
    const y=PAD.t+(cH/4)*i;
    ctx.strokeStyle='rgba(255,255,255,.04)';ctx.lineWidth=.5;
    ctx.beginPath();ctx.moveTo(PAD.l,y);ctx.lineTo(PAD.l+cW,y);ctx.stroke();
    // Price label
    const price=mx-(mx-mn)*(i/4);
    ctx.fillStyle='rgba(140,176,208,.65)';
    ctx.font='8px JetBrains Mono,monospace';ctx.textAlign='right';
    ctx.fillText('₹'+Math.round(price).toLocaleString('en-IN'),W-2,y+(i===0?9:-2));
  }

  // Right axis separator
  ctx.fillStyle='rgba(7,12,24,.8)';
  ctx.fillRect(W-PAD.r,0,PAD.r,H);
  ctx.strokeStyle='rgba(30,51,80,.8)';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(W-PAD.r,0);ctx.lineTo(W-PAD.r,H);ctx.stroke();

  // Candles
  candles.forEach((c,i)=>{
    const bull=c.c>=c.o;
    const cx=barX(i);
    const bodyTop=toY(Math.max(c.o,c.c));
    const bodyH=Math.max(1,Math.abs(toY(c.o)-toY(c.c)));

    // Wick
    ctx.strokeStyle=bull?'rgba(0,232,150,.8)':'rgba(255,107,133,.8)';
    ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(cx,toY(c.h));ctx.lineTo(cx,toY(c.l));ctx.stroke();

    // Body
    ctx.fillStyle=bull?'#00d084':'#ff3b5c';
    if(ctx.roundRect)ctx.roundRect(cx-bw/2,bodyTop,bw,bodyH,1);
    else ctx.rect(cx-bw/2,bodyTop,bw,bodyH);
    ctx.fill();

    if(!bull){ctx.strokeStyle='rgba(255,59,92,.3)';ctx.lineWidth=.5;ctx.stroke();}
  });

  // ── Moving Average curves computed from candle close prices ──
  function calcSMA(arr, period){
    return arr.map((c,i)=>{
      if(i < period-1) return null;
      const sum = arr.slice(i-period+1, i+1).reduce((a,b)=>a+b.c, 0);
      return sum / period;
    });
  }
  function calcEMA(arr, period){
    const k = 2/(period+1);
    const result = new Array(arr.length).fill(null);
    // Find first valid index
    let first = period-1;
    if(first >= arr.length) return result;
    result[first] = arr.slice(0,period).reduce((a,b)=>a+b.c,0)/period;
    for(let i=first+1; i<arr.length; i++){
      result[i] = arr[i].c * k + result[i-1] * (1-k);
    }
    return result;
  }
  function drawMALine(vals, col, dash, label){
    ctx.strokeStyle=col; ctx.lineWidth=1.2; ctx.setLineDash(dash||[]);
    ctx.beginPath();
    let started=false;
    vals.forEach((v,i)=>{
      if(v===null) return;
      const x=barX(i), y=toY(v);
      if(!started){ ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
    });
    ctx.stroke(); ctx.setLineDash([]);
    // Label at last valid point
    const lastIdx = vals.reduce((best,v,i)=>v!==null?i:best, -1);
    if(lastIdx>=0 && label){
      const lv = vals[lastIdx];
      ctx.fillStyle=col; ctx.font='bold 7px JetBrains Mono,monospace'; ctx.textAlign='right';
      ctx.fillText(label+' ₹'+Math.round(lv).toLocaleString('en-IN'), W-2, toY(lv)-3);
    }
  }
  // MAs computed on allCandles (full history), then only visible portion drawn
  // This ensures EMA200 is correct even on short-range views
  if(S.maVis.sma20 || S.maVis.sma50 || S.maVis.ema200){
    const allC = s.candles || candles;
    const sma20vals  = S.maVis.sma20  ? calcSMA(allC, 20)  : null;
    const sma50vals  = S.maVis.sma50  ? calcSMA(allC, 50)  : null;
    const ema200vals = S.maVis.ema200 ? calcEMA(allC, 200) : null;

    // Map allCandles index → visible x position using date
    function maX(allIdx){
      const t = new Date(allC[allIdx].d).getTime();
      return PAD.l + ((t - visFirst) / visRange) * cW;
    }
    function drawMAFull(vals, col, dash, label){
      if(!vals) return;
      ctx.strokeStyle = col; ctx.lineWidth = 1.2; ctx.setLineDash(dash||[]);
      ctx.beginPath();
      let started = false;
      vals.forEach((v,i)=>{
        if(v === null) return;
        const x = maX(i);
        if(x < PAD.l - 2 || x > PAD.l + cW + 2){ started = false; return; } // off-screen
        const y = toY(v);
        if(!started){ ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
      });
      ctx.stroke(); ctx.setLineDash([]);
      // Label at rightmost visible point
      let lastV = null, lastX = 0;
      vals.forEach((v,i)=>{
        if(v===null) return;
        const x = maX(i);
        if(x >= PAD.l && x <= PAD.l+cW){ lastV=v; lastX=x; }
      });
      if(lastV !== null){
        ctx.fillStyle=col; ctx.font='bold 7px JetBrains Mono,monospace'; ctx.textAlign='right';
        ctx.fillText(label+' ₹'+Math.round(lastV).toLocaleString('en-IN'), W-2, toY(lastV)-3);
      }
    }
    drawMAFull(sma20vals,  '#f59e0b', [],    'SMA20');
    drawMAFull(sma50vals,  '#3b82f6', [],    'SMA50');
    drawMAFull(ema200vals, '#a855f7', [4,3], 'EMA200');
  }

  // Current price dashed line
  if(s.ltp){
    const lastY=toY(s.ltp);
    const bull=s.candles?.length&&s.ltp>=(s.candles[0]?.c||s.ltp);
    ctx.strokeStyle=bull?'rgba(0,208,132,.5)':'rgba(255,59,92,.5)';
    ctx.lineWidth=.6;ctx.setLineDash([3,3]);
    ctx.beginPath();ctx.moveTo(PAD.l,lastY);ctx.lineTo(PAD.l+cW,lastY);ctx.stroke();
    ctx.setLineDash([]);
    // Price badge on right axis
    ctx.fillStyle=bull?'#00d084':'#ff3b5c';
    ctx.font='bold 9px JetBrains Mono,monospace';ctx.textAlign='right';
    ctx.fillText('₹'+Math.round(s.ltp).toLocaleString('en-IN'),W-2,Math.max(lastY+4,PAD.t+10));
  }

  // X-axis date labels — use actual candle.d dates, show ~5 evenly spaced
  const maxLabels = Math.min(6, Math.floor(cW / 40));
  const lblStep = Math.max(1, Math.floor(n / maxLabels));
  ctx.fillStyle='rgba(140,176,208,.55)'; ctx.font='7px JetBrains Mono,monospace';
  candles.forEach((c,i)=>{
    if(i % lblStep !== 0 && i !== n-1) return;
    const d = new Date(c.d);
    let lbl;
    if(S.chartInterval==='M')      lbl = (d.getMonth()+1)+'/'+String(d.getFullYear()).slice(2);
    else if(S.chartRange==='5Y'||S.chartRange==='1Y') lbl = (d.getMonth()+1)+'/'+String(d.getFullYear()).slice(2);
    else                            lbl = d.getDate()+'/'+(d.getMonth()+1);
    const x = barX(i);
    if(x > PAD.l+cW-8) return;
    ctx.textAlign = i===0 ? 'left' : (i===n-1 ? 'right' : 'center');
    ctx.fillText(lbl, x, H-4);
  });

  // ── KPI overlays on price chart ──────────────────────────────────
  const quarterly = s.quarterly || [];

  const KPI_DEFS = [
    {k:'pe',   label:'P/E',     col:'#f59e0b'},
    {k:'rev',  label:'Rev',     col:'#22d3ee'},
    {k:'net',  label:'Net',     col:'#4ade80'},
    {k:'cfo',  label:'CFO',     col:'#34d399'},
    {k:'opm',  label:'OPM%',    col:'#fb923c'},
    {k:'debt', label:'Debt',    col:'#f87171'},
  ];

  // Use FULL candle history for price lookups — not just visible slice
  // (allCandles, visFirst, visRange already defined above)

  function xForDate(dateStr){
    const t = new Date(dateStr).getTime();
    return PAD.l + ((t - visFirst) / visRange) * cW;
  }

  // Search FULL history for price on/before a date
  function priceAt(dateStr){
    for(let i=allCandles.length-1; i>=0; i--){
      if(allCandles[i].d <= dateStr) return allCandles[i].c;
    }
    return allCandles.length ? allCandles[0].c : (s.ltp || 0);
  }

  // Log raw quarterly data once
  if(quarterly.length){
        }

  KPI_DEFS.forEach(({k, label, col})=>{
    if(!S.kpiVis[k]) return;

    let pts = [];
    if(k === 'pe'){
      quarterly.forEach(q=>{
        if(!q.eps || q.eps <= 0) return;
        const annEPS = q.eps * 4;
        const price = priceAt(q.d);
        if(price > 0) pts.push({x: xForDate(q.d), v: price/annEPS, d: q.d});
      });
      // Always add current PE at far right
      if(s.pe > 0 && candles.length > 0){
        const rightX = PAD.l + cW;
        if(!pts.length || pts[pts.length-1].x < rightX - 10)
          pts.push({x: rightX, v: s.pe, d: 'now'});
      }
    } else {
      quarterly.forEach(q=>{
        const v = q[k];
        if(v != null) pts.push({x: xForDate(q.d), v, d: q.d});
      });
      // Add current value as rightmost anchor if available
      const curVal = k==='cfo'?s.cfo : k==='rev'?s.sales : k==='net'?s.npm_pct : k==='opm'?s.opm_pct : k==='debt'?s.debt_eq : null;
      if(curVal != null && pts.length){
        pts.push({x: PAD.l + cW, v: curVal, d: 'now'});
      }
    }

      // Keep points that fall within or near visible chart area
    // Extend margin so points just outside edges still connect to line
    pts = pts.filter(p => p.x >= PAD.l - 20 && p.x <= PAD.l + cW + 20);
    // If nothing visible, show all points spread across full width
    if(!pts.length && (quarterly.length || s.pe)){
      const allPts2 = [];
      if(k==='pe'){
        quarterly.forEach(q=>{
          if(!q.eps||q.eps<=0) return;
          const pr = priceAt(q.d);
          if(pr>0) allPts2.push({x:0, v:pr/(q.eps*4), d:q.d});
        });
        if(s.pe>0) allPts2.push({x:0, v:s.pe, d:'now'});
      } else {
        quarterly.forEach(q=>{ const v=q[k]; if(v!=null) allPts2.push({x:0,v,d:q.d}); });
      }
      if(allPts2.length>=2){
        const t0=new Date(allPts2[0].d==='now'?Date.now():allPts2[0].d).getTime();
        const t1=new Date(allPts2[allPts2.length-1].d==='now'?Date.now():allPts2[allPts2.length-1].d).getTime();
        const tr=t1-t0||1;
        allPts2.forEach(p=>{
          const t=new Date(p.d==='now'?Date.now():p.d).getTime();
          p.x = PAD.l + ((t-t0)/tr)*cW;
        });
        pts = allPts2;
      }
    }
      if(!pts.length) return;

    const drawLine = pts.length >= 2;

    // Map values to Y using a DEDICATED right-side scale for this KPI
    // This avoids the problem of small PE values (eg 18x) mapping to price range (eg 500-800)
    const vals = pts.map(p=>p.v);
    const vMin = Math.min(...vals)*0.92, vMax = Math.max(...vals)*1.08;
    const vRng = vMax - vMin || 1;
    // Use top 80% of chart height, leaving room for x-axis labels at bottom
    const yTop = PAD.t + 4, yBot = H - PAD.b - 16;
    const kpiY = v => yBot - ((v - vMin) / vRng) * (yBot - yTop);

    ctx.save();
    ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.globalAlpha = 0.9;

    if(drawLine){
      // Subtle fill under line
      ctx.beginPath();
      pts.forEach((p,j)=>{ j===0 ? ctx.moveTo(p.x, kpiY(p.v)) : ctx.lineTo(p.x, kpiY(p.v)); });
      ctx.lineTo(pts[pts.length-1].x, yBot);
      ctx.lineTo(pts[0].x, yBot);
      ctx.closePath();
      ctx.fillStyle = col;
      ctx.globalAlpha = 0.08;
      ctx.fill();
      // Line
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      pts.forEach((p,j)=>{ j===0 ? ctx.moveTo(p.x, kpiY(p.v)) : ctx.lineTo(p.x, kpiY(p.v)); });
      ctx.stroke();
    }

    // Dots
    ctx.fillStyle = col; ctx.globalAlpha = 1;
    pts.forEach(p=>{
      ctx.beginPath();
      ctx.arc(p.x, kpiY(p.v), 2.5, 0, Math.PI*2);
      ctx.fill();
    });

    // Value labels above each dot (skip if too crowded)
    const labelEvery = pts.length > 6 ? 2 : 1;
    pts.forEach((p,j)=>{
      if(j % labelEvery !== 0 && j !== pts.length-1) return;
      const dispV = k==='pe'  ? p.v.toFixed(0)+'x' :
                    k==='opm' ? p.v.toFixed(1)+'%' :
                    Math.abs(p.v)>=1000 ? (p.v/1000).toFixed(1)+'K' : p.v.toFixed(0);
      ctx.fillStyle = col; ctx.globalAlpha = 0.85;
      ctx.font = '6px JetBrains Mono,monospace'; ctx.textAlign = 'center';
      ctx.fillText(dispV, p.x, kpiY(p.v) - 4);
    });

    // Label on right axis strip
    const last = pts[pts.length-1];
    const dispVal = k==='pe'  ? last.v.toFixed(0)+'x' :
                    k==='opm' ? last.v.toFixed(1)+'%' :
                    Math.abs(last.v)>=1000 ? (last.v/1000).toFixed(1)+'KCr' : last.v.toFixed(0)+'Cr';
    ctx.fillStyle = col; ctx.globalAlpha = 1;
    ctx.font = 'bold 7px JetBrains Mono,monospace'; ctx.textAlign = 'right';
    ctx.fillText(label+' '+dispVal, W-2, Math.max(kpiY(last.v)-3, PAD.t+8));
    ctx.restore();
  });
}

// Volume bars with 5-period MA trend line
function drawVolume(s){
  const cv=document.getElementById('cv-vol');
  if(!cv)return;
  const wrap=document.getElementById('vol-wrap');
  const W2=Math.max(wrap?wrap.offsetWidth:0, 280);
  const H2=50;
  const dpr=window.devicePixelRatio||1;
  cv.width=W2*dpr;cv.height=H2*dpr;
  cv.style.width=W2+'px';cv.style.height=H2+'px';
  const ctx=cv.getContext('2d');
  ctx.scale(dpr,dpr);

  const candles=getSlicedCandles(s, W2);
  if(!candles.length)return;

  ctx.fillStyle='#070c18';ctx.fillRect(0,0,W2,H2);

  const W=W2,H=H2;
  const PAD={l:6,r:52,t:4,b:4};
  const cW=W-PAD.l-PAD.r,cH=H-PAD.t-PAD.b;
  const n=candles.length,gap=cW/n,bw=Math.max(2,Math.min(14,gap*0.7));
  const mv=Math.max(...candles.map(c=>c.v))||1;

  // Right axis strip
  ctx.fillStyle='rgba(7,12,24,.8)';
  ctx.fillRect(W-PAD.r,0,PAD.r,H);
  ctx.strokeStyle='rgba(30,51,80,.8)';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(W-PAD.r,0);ctx.lineTo(W-PAD.r,H);ctx.stroke();
  ctx.fillStyle='rgba(140,176,208,.5)';ctx.font='7px JetBrains Mono,monospace';ctx.textAlign='right';
  ctx.fillText('Vol',W-2,10);

  candles.forEach((c,i)=>{
    const bh=Math.max(2,(c.v/mv)*cH);
    const x=PAD.l+i*gap+(gap-bw)/2;
    ctx.fillStyle=c.c>=c.o?'rgba(0,208,132,.5)':'rgba(255,59,92,.45)';
    if(ctx.roundRect)ctx.roundRect(x,PAD.t+cH-bh,bw,bh,1);
    else ctx.rect(x,PAD.t+cH-bh,bw,bh);
    ctx.fill();
  });

  // Volume trend line (smoothed MA5)
  const volMA = candles.map((c,i)=>{
    if(i<4) return null;
    return candles.slice(i-4,i+1).reduce((a,b)=>a+b.v,0)/5;
  });
  ctx.strokeStyle='rgba(255,255,255,.4)'; ctx.lineWidth=1; ctx.beginPath();
  let started=false;
  volMA.forEach((v,i)=>{
    if(v===null) return;
    const x=PAD.l+i*gap+gap/2;
    const y=PAD.t+cH-(v/mv)*cH;
    if(!started){ctx.moveTo(x,y);started=true;} else ctx.lineTo(x,y);
  });
  ctx.stroke();
}

// ── Quarterly CFO bar panel ───────────────────────────
// ── Quarterly P/E line panel ──────────────────────────
function updateChartStats(s){
  const candles=getSlicedCandles(s, 0);
  if(!candles.length)return;
  const closes=candles.map(c=>c.c);
  const first=closes[0],last=closes[closes.length-1];
  const ret=((last-first)/first*100).toFixed(2);
  const hi=Math.max(...candles.map(c=>c.h));
  const lo=Math.min(...candles.map(c=>c.l));
  const vol=((hi-lo)/lo*100).toFixed(1);
  const up=last>=first;

  const retEl=document.getElementById('cstat-ret');
  const hiEl=document.getElementById('cstat-hi');
  const loEl=document.getElementById('cstat-lo');
  const volEl=document.getElementById('cstat-vol');
  if(retEl){retEl.textContent=(up?'+':'')+ret+'%';retEl.style.color=up?'var(--gr2)':'var(--rd2)';}
  if(hiEl)hiEl.textContent='₹'+fmt(hi);
  if(loEl)loEl.textContent='₹'+fmt(lo);
  if(volEl)volEl.textContent=vol+'%';
}

// Fundamentals tab
function renderFundamentals(s){
  return `<div style="padding:10px 13px 14px">
    <div class="fund-grid">
      ${[
        {l:'Market Cap',v:s.mcap||'N/A',sub:'',st:'neutral'},
        {l:'P/E Ratio',v:s.pe?s.pe+'x':'—',sub:'Sector ~22x',st:s.pe?(s.pe<18?'good':s.pe<30?'warn':'bad'):'neutral'},
        {l:'P/B Ratio',v:s.pb?s.pb+'x':'—',sub:'Price/Book',st:s.pb?(s.pb<2?'good':s.pb<5?'warn':'bad'):'neutral'},
        {l:'ROE',v:s.roe?s.roe+'%':'—',sub:'>15% strong',st:s.roe?(s.roe>15?'good':s.roe>10?'warn':'bad'):'neutral'},
        {l:'ROCE',v:s.roce?s.roce+'%':'—',sub:'>20% excellent',st:s.roce?(s.roce>20?'good':s.roce>12?'warn':'bad'):'neutral'},
        {l:'EPS TTM',v:s.eps?'₹'+fmt(s.eps):'—',sub:'Earnings/Share',st:'neutral'},
        {l:'Div Yield',v:s.divYield?s.divYield+'%':'—',sub:'Annual',st:'neutral'},
        {l:'Debt/Equity',v:s.debtEq!=null?s.debtEq:'—',sub:'<0.5 safe',st:s.debtEq!=null?(s.debtEq<0.5?'good':s.debtEq<1?'warn':'bad'):'neutral'},
      ].map(({l,v,sub,st})=>`
        <div class="fund-cell ${st}">
          <div class="fc-lbl">${l}</div>
          <div class="fc-val">${v}</div>
          <div class="fc-sub">${sub}</div>
        </div>`).join('')}
    </div>

    <div class="sec-lbl">Shareholding</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px">
      <div class="mbox ${s.promoter>50?'good':'neutral'}">
        <div class="ml">Promoter Holding</div>
        <div class="mv">${s.promoter||'—'}%</div>
        <div class="ms">${s.promoter>50?'Strong':'Below 50%'}</div>
      </div>
      <div class="mbox neutral">
        <div class="ml">Pledging</div>
        <div class="mv">—</div>
        <div class="ms">Not available</div>
      </div>
    </div>
  </div>`;
}

// News tab with RSS
function renderNewsTab(s){
  return `<div>
    <div style="padding:10px 12px 4px">
      <div class="sec-lbl">News Sources</div>
    </div>
    <div id="stock-news-list">
      <div class="u-pad14c">Loading news…</div>
    </div>
    <div style="padding:10px 12px">
      <div class="sec-lbl">Research Links</div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${[
          {l:'NSE Official',u:`https://www.nseindia.com/get-quotes/equity?symbol=${s.symbol}`,c:'#2196f3',d:'Live quotes & filings'},
          {l:'Screener.in',u:`https://www.screener.in/company/${s.symbol}/`,c:'#a855f7',d:'Annual reports & ratios'},
          {l:'Economic Times',u:`https://economictimes.indiatimes.com/topic/${s.symbol}`,c:'#f97316',d:'Latest news coverage'},
          {l:'Moneycontrol',u:`https://www.moneycontrol.com/india/stockpricequote/${s.symbol}/${s.symbol}`,c:'#00d084',d:'Price & analysis'},
          {l:'TradingView',u:`https://in.tradingview.com/symbols/NSE-${s.symbol}/`,c:'#64b5f6',d:'Advanced charts'},
          {l:'Google News',u:`https://news.google.com/search?q=${encodeURIComponent(s.symbol+' NSE stock India')}`,c:'#4285f4',d:'News aggregator'},
        ].map(lk=>`
          <a href="${lk.u}" target="_blank" rel="noopener"
            style="display:flex;align-items:center;gap:12px;padding:11px 13px;
            background:var(--card);border:1px solid var(--b1);border-radius:9px;
            text-decoration:none;border-left:3px solid ${lk.c}">
            <div style="flex:1">
              <div style="font-size:13px;font-weight:700;color:var(--tx)">${lk.l}</div>
              <div class="u-tx3-10mt">${lk.d}</div>
            </div>
            <span style="font-size:11px;color:var(--b3)">↗</span>
          </a>`).join('')}
      </div>
    </div>
  </div>`;
}

// Load news for a stock
async function loadStockNews(sym,name){
  const el=document.getElementById('stock-news-list');
  if(!el)return;
  try{
    const query=encodeURIComponent(sym+' '+name+' NSE India stock');
    const url='https://api.rss2json.com/v1/api.json?rss_url='+encodeURIComponent('https://news.google.com/rss/search?q='+query+'&hl=en-IN&gl=IN&ceid=IN:en')+'&count=8';
    const res=await fetch(url);
    const d=await res.json();
    const items=d.items||[];
    if(!items.length){el.innerHTML=`<div class="u-pad14c">No recent news for ${sym}</div>`;return;}
    el.innerHTML=items.map(item=>{
      const{tag,imp}=classifyNews(item.title);
      const src=item.source?.name||extractDomain(item.link)||'News';
      return `<div class="news-item" style="margin:0;border-radius:0;border-left:none;border-right:none;border-top:none">
        <div class="news-src">
          <span>${src}</span>
          <span class="imp-badge imp-${imp}">${imp==='H'?'HIGH':imp==='M'?'MED':'LOW'}</span>
          <span class="pill pill-bl" style="font-size:7px">${tag}</span>
          <span>${timeAgo(new Date(item.pubDate))}</span>
        </div>
        <div class="news-title">${item.title}</div>
      </div>`;
    }).join('');
  }catch(e){
    el.innerHTML=`<div class="u-pad14c">Could not load news</div>`;
  }
}

function setDrillTab(t){
  S.drillTab=t;
  const dc=document.getElementById('dc');
  if(dc){dc.innerHTML=renderDC(S.selStock);}
  document.querySelectorAll('.dtab').forEach(b=>b.classList.toggle('active',b.dataset.t===t));
  if(t==='technical') loadAndDrawChart(S.selStock);
  if(t==='news'&&S.selStock) loadStockNews(S.selStock.symbol,S.selStock.name);
}

// Central chart loader — fetch OHLC data then draw all panels
// Fetch OHLC data from charts/SYM.json then draw all chart panels
function loadAndDrawChart(s){
  if(!s) return;
  const sym = s.symbol;
  // After 2 rAF the DOM is painted and offsetWidth is correct
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(chartCache[sym]){
      s.candles = chartCache[sym];
      scheduleTACharts(s);
      attachChartResizeObserver(s);
      return;
    }
    fetch('./charts/'+sym+'.json', {cache:'force-cache'})
      .then(r=>r.ok?r.json():null)
      .then(d=>{
        if(d && d.bars && d.bars.length){
          chartCache[sym] = d.bars;
          s.candles = d.bars;
        } else {
          // Mark as no-data so canvas shows helpful message
          s.candles = [];
          s._noChartData = true;
        }
        scheduleTACharts(s);
        attachChartResizeObserver(s);
      })
      .catch(()=>{
        s.candles = [];
        s._noChartData = true;
        scheduleTACharts(s);
      });
  }));
}

//  ANALYSIS TAB — redesigned
let analysisState = {
  selSym:       null,   // stock open in bottom sheet
  filing:       null,   // { url, title, date, quarter }
  loading:      false,
  statusFilter: null,   // 'pending'|'outdated'|'done'|null
  search:       '',     // live search filter
  showDone:     false,  // toggle collapsed done section
};

// ── helpers ──────────────────────────────────────────────
