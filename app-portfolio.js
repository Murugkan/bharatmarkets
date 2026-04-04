/**
 * STEP 1: DIAGNOSTIC LOADER
 * This version will tell us EXACTLY why it's stuck.
 */
async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    console.log("📡 Attempting fetch: ./fundamentals.json");
    const response = await fetch(`./fundamentals.json?v=${Date.now()}`);
    
    if (!response.ok) {
        throw new Error(`File Not Found (HTTP ${response.status})`);
    }

    const data = await response.json();
    // Ensure we handle both {stocks: {...}} and raw {...} formats
    window.FUND = data.stocks || data;
    
    window.ISIN_MAP = {};
    Object.keys(window.FUND).forEach(sym => {
      const s = window.FUND[sym];
      if (s && s.isin) window.ISIN_MAP[s.isin] = sym;
    });

    window.fundLoaded = true;
    return true;
  } catch (e) {
    console.error("❌ Diagnostic Failure:", e.message);
    // STICK THE ERROR ON THE SCREEN SO YOU CAN SEE IT
    document.body.insertAdjacentHTML('beforeend', 
      `<div style="position:fixed;top:0;left:0;background:red;color:white;z-index:9999;padding:10px;font-size:10px;">
        ENGINE ERROR: ${e.message}
      </div>`
    );
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

async function renderPortfolio(container) {
  if (!container) return;

  // 1. Force hide the loading overlay
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // 2. Try to boot the engine
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING DATA ENGINE...</div>`;
    const success = await loadFundamentals();
    
    // If it fails, don't stop! Let's try to render anyway with empty data
    if (!success) {
        console.warn("⚠️ Continuing without fundamentals...");
        window.FUND = window.FUND || {};
        window.fundLoaded = true; 
    }
  }

  // 3. Ensure S.portfolio exists for the 37-column logic
  if (!window.S || !S.portfolio || S.portfolio.length === 0) {
      // IF BROKER SYNC IS MISSING, CREATE A DUMMY LIST FROM FUND TO TEST UI
      if (window.FUND && Object.keys(window.FUND).length > 0) {
          window.S = window.S || {};
          window.S.portfolio = Object.keys(window.FUND).slice(0, 10).map(sym => ({
              sym: sym, 
              isin: window.FUND[sym].isin || ''
          }));
      } else {
          container.innerHTML = `<div style="padding:40px;color:var(--rd2);">❌ No Data Found in JSON or Portfolio.</div>`;
          return;
      }
  }

  // 4. RUN YOUR ORIGINAL 37-COLUMN LOGIC
  console.log("🚀 Drawing Table...");
  // Paste your original table drawing code here...
}
