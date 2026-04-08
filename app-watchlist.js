// Master Render Function - The "Brain" of the display
window.render = function() {
  const container = document.getElementById('stock-list');
  const sectorContainer = document.getElementById('sector-grid');
  if (!container) return;

  // 1. Filter data based on current Tab
  // Portfolio = items with qty > 0 | Watchlist = items with qty == 0
  const data = S.curTab === 'portfolio' 
    ? S.portfolio.filter(h => h.qty > 0)
    : S.portfolio.filter(h => !h.qty || h.qty === 0);

  if (data.length === 0) {
    container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--tx3);">
      No stocks found in ${S.curTab}.<br>Tap "Stock Upload" to add some.
    </div>`;
    if(sectorContainer) sectorContainer.innerHTML = '';
    return;
  }

  // 2. Render Sector Heatmap (Summary)
  renderSectors(data);

  // 3. Render Individual Stock Cards
  container.innerHTML = data.map(stock => `
    <div class="stock-card" style="padding:15px; border-bottom:1px solid var(--b1); display:flex; justify-content:space-between; align-items:center;">
      <div>
        <div style="font-family:'Syne',sans-serif; font-weight:700; font-size:15px;">${stock.sym}</div>
        <div style="font-size:10px; color:var(--tx3);">${stock.sector || 'Others'}</div>
      </div>
      <div style="text-align:right; font-family:var(--mono);">
        <div style="font-size:14px; font-weight:700;">₹${fmt(stock.ltp || 0)}</div>
        <div style="font-size:11px; color:${(stock.change || 0) >= 0 ? 'var(--gr2)' : 'var(--rd2)'};">
          ${(stock.change || 0) >= 0 ? '+' : ''}${stock.change || 0}%
        </div>
      </div>
    </div>
  `).join('');
};

// Sector Aggregator
function renderSectors(data) {
  const sectorGrid = document.getElementById('sector-grid');
  if (!sectorGrid) return;

  const sectors = {};
  data.forEach(s => {
    const name = s.sector || 'Others';
    sectors[name] = (sectors[name] || 0) + ((s.qty || 1) * (s.ltp || 0));
  });

  const sorted = Object.entries(sectors).sort((a, b) => b[1] - a[1]);

  sectorGrid.innerHTML = `
    <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:10px; padding:15px;">
      ${sorted.map(([name, val]) => `
        <div style="background:var(--s2); padding:12px; border-radius:12px;">
          <div style="font-size:10px; color:var(--tx3); text-transform:uppercase;">${name}</div>
          <div style="font-size:14px; font-weight:700; font-family:var(--mono); margin-top:4px;">₹${fmt(val)}</div>
        </div>
      `).join('')}
    </div>
  `;
}

// Global Formatting Helper (if not in app-core.js)
window.fmt = function(num) {
  if (!num) return '0.00';
  return num.toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
};

// Automatically refresh prices every 30 seconds if on portfolio
setInterval(() => {
  if (S.curTab === 'portfolio' && typeof refreshPortfolioData === 'function') {
    refreshPortfolioData();
  }
}, 30000);
