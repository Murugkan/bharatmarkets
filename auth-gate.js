/* BharatMarkets - simple client-side password gate
   Include this script at the very top of <head>, before any other content loads.
   Blocks casual visitors; NOT real security (page source is always viewable —
   anyone who views source can read the password directly).

   Uses localStorage with an expiry timestamp (not sessionStorage) because
   iOS Home Screen web apps run in a standalone WebKit instance that gets
   terminated/relaunched frequently, which clears sessionStorage almost
   every time the app is reopened. localStorage survives that.

   ============================================================
   TO SET / CHANGE THE PASSWORD:
   Just edit CONFIG.PASSWORD below directly from GitHub's mobile
   web editor (no terminal/shasum needed). The script hashes it
   automatically at runtime before comparing.
   ============================================================ */

var CONFIG = {
  PASSWORD: "Xample"   // <-- SET PASSWORD HERE (plain text)
};

(function () {
  var STORAGE_KEY = "bm_auth_until";
  var UNLOCK_DAYS = 7; // how many days to stay unlocked after entering password

  var unlockedUntil = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10);

  if (Date.now() < unlockedUntil) {
    return; // still within unlock window
  }

  // Hide page content immediately while we check
  document.documentElement.style.visibility = "hidden";

  async function sha256(text) {
    var enc = new TextEncoder().encode(text);
    var buf = await crypto.subtle.digest("SHA-256", enc);
    return Array.from(new Uint8Array(buf))
      .map(function (b) { return b.toString(16).padStart(2, "0"); })
      .join("");
  }

  function showPrompt() {
    var overlay = document.createElement("div");
    overlay.id = "bm-auth-overlay";
    overlay.style.cssText =
      "position:fixed;inset:0;background:#0b0e14;color:#e6e6e6;" +
      "display:flex;align-items:center;justify-content:center;" +
      "font-family:-apple-system,sans-serif;z-index:999999;";

    overlay.innerHTML =
      '<form id="bm-auth-form" style="text-align:center;">' +
      '<div style="margin-bottom:12px;font-size:15px;">Enter password</div>' +
      '<input id="bm-auth-input" type="password" autocomplete="off" ' +
      'style="padding:10px 12px;font-size:16px;border-radius:6px;border:1px solid #444;' +
      'background:#1a1e27;color:#fff;width:220px;text-align:center;" />' +
      '<div id="bm-auth-error" style="color:#ff6b6b;font-size:13px;margin-top:8px;height:16px;"></div>' +
      "</form>";

    // Overlay on top of the page WITHOUT touching existing body content,
    // so the host page's own scripts/DOM are left intact.
    document.body.appendChild(overlay);
    document.documentElement.style.visibility = "visible";
    document.body.style.overflow = "hidden"; // prevent scrolling page behind overlay

    var input = document.getElementById("bm-auth-input");
    var errorEl = document.getElementById("bm-auth-error");
    input.focus();

    document.getElementById("bm-auth-form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var entered = await sha256(input.value);
      var expected = await sha256(CONFIG.PASSWORD);
      if (entered === expected) {
        var until = Date.now() + UNLOCK_DAYS * 24 * 60 * 60 * 1000;
        localStorage.setItem(STORAGE_KEY, String(until));
        overlay.remove();
        document.body.style.overflow = "";
      } else {
        errorEl.textContent = "Incorrect password";
        input.value = "";
        input.focus();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showPrompt);
  } else {
    showPrompt();
  }
})();
