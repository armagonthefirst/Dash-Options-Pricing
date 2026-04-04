/* ── Page loading overlay controller ──────────────────────────── */

(function () {
  // Timed messages — cycle through these based on page age
  var TIMED_MESSAGES = [
    { at: 0,  text: "Fetching market data\u2026" },
    { at: 2,  text: "Calculating binomial trees\u2026" },
    { at: 7,  text: "Loading option chains\u2026" },
    { at: 14, text: "Crunching the numbers\u2026" },
    { at: 22, text: "Just a moment\u2026" },
    { at: 32, text: "Almost there\u2026" },
    { at: 45, text: "Still working on it\u2026" },
  ];

  // Record when the script first runs (page start)
  var pageStartTime = Date.now();
  var lastMessageIndex = -1;

  // Simple ticker that runs every second from the moment the script loads.
  // It finds the overlay text element and updates it based on elapsed time.
  // No dependency on DOMContentLoaded or any event — just a clock.
  setInterval(function () {
    var textEl = document.getElementById("page-loading-text");
    if (!textEl) return;

    var overlay = document.getElementById("page-loading-overlay");
    if (!overlay || overlay.classList.contains("hidden")) return;

    var elapsed = (Date.now() - pageStartTime) / 1000;

    // Find the latest message whose time has passed
    var targetIndex = 0;
    for (var i = TIMED_MESSAGES.length - 1; i >= 0; i--) {
      if (elapsed >= TIMED_MESSAGES[i].at) {
        targetIndex = i;
        break;
      }
    }

    if (targetIndex !== lastMessageIndex) {
      lastMessageIndex = targetIndex;
      textEl.textContent = TIMED_MESSAGES[targetIndex].text;
    }
  }, 500);

  // Content detection — hide overlay as soon as real page content appears.
  // Runs on a simple interval. No MutationObserver complexity.
  setInterval(function () {
    var overlay = document.getElementById("page-loading-overlay");
    if (!overlay || overlay.classList.contains("hidden")) return;

    var markers = [
      ".ticker-grid",
      ".kpi-grid",
      ".method-accordion",
      ".methodology-grid",
    ];

    for (var i = 0; i < markers.length; i++) {
      var el = document.querySelector(markers[i]);
      if (el && el.children.length > 0) {
        // 1. Fade out opacity
        overlay.classList.add("hidden");

        // 2. Snapshot rendered height, then animate collapse
        var h = overlay.offsetHeight;
        overlay.style.minHeight = "0";
        overlay.style.height = h + "px";
        // Force reflow so the browser registers the locked height before transitioning
        void overlay.offsetHeight;
        overlay.style.height = "0";
        overlay.style.paddingTop = "0";
        overlay.style.paddingBottom = "0";

        // 3. Remove from flow after animation finishes
        setTimeout(function () { overlay.style.display = "none"; }, 600);

        // 4. Trigger KPI counter animation after content fades in
        setTimeout(animateAllKpiValues, 300);
        return;
      }
    }
  }, 300);

})();


/* ── Clickable table rows ────────────────────────────────────── */

(function () {
  document.addEventListener("click", function (e) {
    var row = e.target.closest("tr[data-href]");
    if (!row) return;
    // Don't intercept clicks on the Analyze button itself
    if (e.target.closest("a")) return;
    window.location.href = row.getAttribute("data-href");
  });
})();


/* ── Methodology accordion ───────────────────────────────────── */

(function () {
  document.addEventListener("click", function (e) {
    var header = e.target.closest(".method-section-header");
    if (!header) return;
    var section = header.closest(".method-section");
    if (section) {
      section.classList.toggle("open");
    }
  });
})();


/* ── Market status badge ─────────────────────────────────────── */

(function () {
  function isUSMarketOpen() {
    var now = new Date();
    // Convert to US Eastern Time
    var etString = now.toLocaleString("en-US", { timeZone: "America/New_York" });
    var et = new Date(etString);

    var day = et.getDay(); // 0=Sun, 6=Sat
    if (day === 0 || day === 6) return false;

    var hours = et.getHours();
    var minutes = et.getMinutes();
    var totalMinutes = hours * 60 + minutes;

    // Market open 9:30 AM (570 min) to 4:00 PM (960 min) ET
    return totalMinutes >= 570 && totalMinutes < 960;
  }

  function formatETTime() {
    var now = new Date();
    return now.toLocaleString("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }) + " ET";
  }

  function updateBadge() {
    var badge = document.getElementById("market-status-badge");
    var text = document.getElementById("market-status-text");
    if (!badge || !text) return;

    var etTime = formatETTime();

    if (isUSMarketOpen()) {
      badge.className = "market-status-badge market-open";
      text.textContent = "Market Open \u00b7 " + etTime;
    } else {
      badge.className = "market-status-badge market-closed";
      text.textContent = "Market Closed \u00b7 " + etTime;
    }
  }

  // Poll until the badge element exists (Dash renders via React after DOMContentLoaded),
  // then update immediately and every 60 seconds.
  function waitForBadge() {
    if (document.getElementById("market-status-badge")) {
      updateBadge();
      setInterval(updateBadge, 60000);
    } else {
      setTimeout(waitForBadge, 100);
    }
  }
  waitForBadge();
})();


/* ── KPI counter animation ───────────────────────────────────── */

function animateKpiValue(el) {
  var original = el.textContent.trim();

  // Find the first number in the string (handles $1,234.56 / +12.34% / 0.532 / 185)
  var match = original.match(/[\d,]+\.?\d*/);
  if (!match) return;

  var numStr = match[0].replace(/,/g, '');
  var target = parseFloat(numStr);
  if (isNaN(target) || target === 0) return;

  var decimalPlaces = numStr.includes('.') ? numStr.split('.')[1].length : 0;
  var numStart = original.indexOf(match[0]);
  var prefix = original.slice(0, numStart);
  var suffix = original.slice(numStart + match[0].length);

  var duration = 750;
  var startTime = null;

  function step(ts) {
    if (!startTime) startTime = ts;
    var progress = Math.min((ts - startTime) / duration, 1);
    // Ease-out cubic
    var eased = 1 - Math.pow(1 - progress, 3);
    var current = target * eased;

    var formatted = current.toFixed(decimalPlaces);
    var parts = formatted.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    formatted = parts.join('.');

    el.textContent = prefix + formatted + suffix;

    if (progress < 1) {
      requestAnimationFrame(step);
    } else {
      el.textContent = original; // ensure exact final value
    }
  }

  requestAnimationFrame(step);
}

function animateAllKpiValues() {
  document.querySelectorAll('.kpi-value, .spot-price').forEach(function (el) {
    animateKpiValue(el);
  });
}


/* ── Scroll-triggered reveal (IntersectionObserver) ─────────── */

(function () {
  if (!window.IntersectionObserver) return;

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  function observeAll() {
    document.querySelectorAll('.reveal-on-scroll').forEach(function (el) {
      // Only observe elements not yet visible
      if (!el.classList.contains('visible')) {
        observer.observe(el);
      }
    });
  }

  // Poll until reveal elements exist in the DOM
  function waitForRevealElements() {
    if (document.querySelectorAll('.reveal-on-scroll').length > 0) {
      observeAll();
      // Re-observe on Dash page transitions via a lightweight MutationObserver
      var mo = new MutationObserver(function () { observeAll(); });
      mo.observe(document.body, { childList: true, subtree: true });
    } else {
      setTimeout(waitForRevealElements, 200);
    }
  }

  waitForRevealElements();
})();
