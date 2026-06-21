/* BharatMarkets - simple client-side password gate
   Include this script at the very top of <head>, before any other content loads.
   Blocks casual visitors; NOT real security (page source is always viewable).

   Uses localStorage with an expiry timestamp (not sessionStorage) because
   iOS Home Screen web apps run in a standalone WebKit instance that gets
   terminated/relaunched frequently, which clears sessionStorage almost
   every time the app is reopened. localStorage survives that.

   ============================================================
   TO SET / CHANGE THE PASSWORD:
   1. Run: echo -n "yourpassword" | shasum -a 256
   2. Copy the hex string (before the "  -")
   3. Paste it as the value of CONFIG.PASSWORD_HASH below
   ============================================================ */

var CONFIG = {
  PASSWORD_HASH: "REPLACE_WITH_YOUR_SHA256_HASH"   // <-- SET PASSWORD HASH HERE
};

(function () {
  var PASSWORD_HASH = CONFIG.PASSWORD_HASH;

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
    overlay.style.cssText =
      "position:fixed;inset:0;background:#0b0e14;color:#e6e6e6;" +
      "display:flex;align-items:center;justify-content:center;" +
      "font-family:-apple-system,sans-serif;z-index:999999;visibility:visible;";

    overlay.innerHTML =
      '<form id="bm-auth-form" style="text-align:center;">' +
      '<div style="margin-bottom:12px;font-size:15px;">Enter password</div>' +
      '<input id="bm-auth-input" type="password" autocomplete="off" ' +
      'style="padding:10px 12px;font-size:16px;border-radius:6px;border:1px solid #444;' +
      'background:#1a1e27;color:#fff;width:220px;text-align:center;" />' +
      '<div id="bm-auth-error" style="color:#ff6b6b;font-size:13px;margin-top:8px;height:16px;"></div>' +
      "</form>";

    document.documentElement.style.visibility = "visible";
    document.body.innerHTML = "";
    document.body.appendChild(overlay);

    var input = document.getElementById("bm-auth-input");
    var errorEl = document.getElementById("bm-auth-error");
    input.focus();

    document.getElementById("bm-auth-form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var entered = await sha256(input.value);
      if (entered === PASSWORD_HASH) {
        var until = Date.now() + UNLOCK_DAYS * 24 * 60 * 60 * 1000;
        localStorage.setItem(STORAGE_KEY, String(until));
        location.reload();
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
