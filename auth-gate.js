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

   Changing the password automatically forces everyone to log in
   again on their next page load — no extra step needed. Session
   validity is tied to a hash of the current password, so an old
   unlock token only works while the password it was created
   under is still the current one.
   ============================================================ */

var CONFIG = {
  PASSWORD: "Xample "   // <-- SET PASSWORD HERE (plain text)
};

(function () {
  var STORAGE_KEY = "bm_auth_until";
  var TOKEN_KEY = "bm_auth_token"; // hash of the password the unlock was created under
  var UNLOCK_DAYS = 7; // how many days to stay unlocked after entering password

  var unlockedUntil = parseInt(localStorage.getItem(STORAGE_KEY) || "0", 10);
  var storedToken = localStorage.getItem(TOKEN_KEY) || "";

  async function sha256(text) {
    var enc = new TextEncoder().encode(text);
    var buf = await crypto.subtle.digest("SHA-256", enc);
    return Array.from(new Uint8Array(buf))
      .map(function (b) { return b.toString(16).padStart(2, "0"); })
      .join("");
  }

  function showPrompt(currentToken) {
    var overlay = document.createElement("div");
    overlay.id = "bm-auth-overlay";
    overlay.style.cssText =
      "position:fixed;inset:0;background:#0b0e14;color:#e6e6e6;" +
      "display:flex;align-items:flex-start;justify-content:center;" +
      "padding-top:25vh;" +
      "font-family:-apple-system,sans-serif;z-index:999999;";

    overlay.innerHTML =
      '<form id="bm-auth-form" style="text-align:center;">' +
      '<div style="margin-bottom:12px;font-size:15px;">Enter password</div>' +
      '<input id="bm-auth-input" type="password" autocomplete="off" ' +
      'style="padding:10px 12px;font-size:16px;border-radius:6px;border:1px solid #444;' +
      'background:#1a1e27;color:#fff;width:220px;text-align:center;display:block;margin:0 auto;" />' +
      '<button id="bm-auth-submit" type="submit" ' +
      'style="margin-top:12px;padding:10px 24px;font-size:15px;border-radius:6px;border:none;' +
      'background:#2a6ef5;color:#fff;width:220px;">Unlock</button>' +
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
      if (entered === currentToken) {
        var until = Date.now() + UNLOCK_DAYS * 24 * 60 * 60 * 1000;
        localStorage.setItem(STORAGE_KEY, String(until));
        localStorage.setItem(TOKEN_KEY, currentToken);
        overlay.remove();
        document.body.style.overflow = "";
      } else {
        errorEl.textContent = "Incorrect password";
        input.value = "";
        input.focus();
      }
    });
  }

  async function main() {
    var currentToken = await sha256(CONFIG.PASSWORD);

    // Skip the prompt only if unlocked AND the password hasn't changed since.
    if (storedToken === currentToken && Date.now() < unlockedUntil) {
      return;
    }

    // Hide page content immediately while we check/prompt
    document.documentElement.style.visibility = "hidden";

    function start() {
      showPrompt(currentToken);
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }

  main();
})();
