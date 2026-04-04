/* ═══════════════════════════════════════════════════════════
   app-boot.js — MISSION CONTROL (Bootstrapping)
   Logic: This must be the last script loaded in index.html.
   Flow: Engine Sync → Static Data → Core Init → Render
═══════════════════════════════════════════════════════════ */

async function boot() {
    console.log("🚀 BharatMarkets Pro: Boot Sequence Initiated...");

    try {
        // 1. Initialize & Sync the Unified Data Engine
        // This pulls from GitHub and populates IndexedDB with computed fields
        if (typeof runEngineSync === 'function') {
            await runEngineSync();
        } else {
            console.error("❌ Engine Module (app-engine.js) not found!");
        }

        // 2. Load Static Symbols & ISIN Maps
        // Essential for resolving CDSL imports and Watchlist searches
        if (typeof loadStaticData === 'function') {
            await loadStaticData();
        }

        // 3. Initialize Core State (localStorage, Tabs, Global Routing)
        if (typeof init === 'function') {
            init();
        }

        // 4. Initial Render
        // If engine synced successfully, S.portfolio will now reflect the latest data
        if (typeof render === 'function') {
            render();
        }

        console.log("✅ Boot Sequence Complete: System Ready.");
        showToast("System Ready", 1500);

    } catch (error) {
        console.error("Critical Boot Failure:", error);
        if (typeof showToast === 'function') {
            showToast("Boot Error: Check Console", 5000);
        }
    }
}

// ── Trigger Boot on DOM Load ─────────────────────────────
window.addEventListener('DOMContentLoaded', boot);

/**
 * Global Engine Update Listener
 * Listens for 'engine-updated' events to refresh the UI automatically
 */
window.addEventListener('engine-updated', () => {
    console.log("🔄 Engine Update Detected: Re-rendering UI...");
    if (typeof render === 'function') render();
});
