function renderPortfolio(container) {
    container.innerHTML = `<div id="diag" style="padding:20px;color:#0f0;font-family:monospace;font-size:12px;background:#000;min-height:100vh;"></div>`;
    const report = (msg) => document.getElementById('diag').innerHTML += msg + "<br>";

    report("--- SYSTEM CHECK ---");
    // Check 1: Portfolio Data
    if (window.S && S.portfolio) {
        report(`✅ Portfolio Found: ${S.portfolio.length} stocks`);
        report(`   Sample Ticker: ${S.portfolio[0].sym}`);
    } else {
        report("❌ S.portfolio is MISSING");
    }

    // Check 2: Fundamentals Data
    report("<br>--- FUNDAMENTALS CHECK ---");
    if (window.FUND) {
        report("✅ Global 'FUND' variable exists");
        if (FUND.stocks) {
            report(`✅ FUND.stocks contains ${Object.keys(FUND.stocks).length} keys`);
            report(`   Sample Key: ${Object.keys(FUND.stocks)[0]}`);
        } else {
            report("❌ FUND exists but '.stocks' is missing");
        }
    } else {
        report("❌ Global 'FUND' is MISSING");
    }

    // Check 3: Fetch Test
    report("<br>--- NETWORK TEST ---");
    fetch('fundamentals.json')
        .then(r => report(`🌐 Fetch fundamentals.json: ${r.status} ${r.statusText}`))
        .catch(e => report(`🌐 Fetch FAILED: ${e.message}`));
}
