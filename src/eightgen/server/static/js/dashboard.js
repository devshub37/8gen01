// 8Gen Autonomous Game Studio - Universal SaaS Dashboard Logic

let activeGameId = null;
let selectedGameReference = null;
let lastReferencePrompt = "";
let snapCooldownUntil = 0;
let wbController = null;
let modalController = null;
const generatedHtmlCache = {};
const VERCEL_CACHE_KEY = "eightgen_vercel_games_v1";
const THEME_KEY = "eightgen_theme_v1";
const THEME_ORDER = ["light", "dark", "gaming"];
const THEME_LABELS = {
  light: "☀️ Light",
  dark: "🌙 Dark",
  gaming: "🎮 Gaming",
};

function setSnapCooldown(ms = 750) {
  snapCooldownUntil = Math.max(snapCooldownUntil, Date.now() + ms);
}

function isWsEnabled() {
  const wb = document.getElementById("workbench");
  return wb ? wb.getAttribute("data-ws-enabled") !== "false" : true;
}

function getLatestHtmlFromGame(game) {
  if (!game || !Array.isArray(game.versions) || game.versions.length === 0) {
    return null;
  }
  const latest = game.versions[game.versions.length - 1];
  return latest && latest.html_content ? latest.html_content : null;
}

function cacheGameLocally(game) {
  if (!game || !game.id) return;
  const html = getLatestHtmlFromGame(game);
  if (html) {
    generatedHtmlCache[game.id] = html;
  }
  if (isWsEnabled()) return;
  try {
    const existing = JSON.parse(localStorage.getItem(VERCEL_CACHE_KEY) || "[]");
    const filtered = existing.filter((g) => g && g.id !== game.id);
    filtered.unshift(game);
    localStorage.setItem(VERCEL_CACHE_KEY, JSON.stringify(filtered.slice(0, 8)));
  } catch (e) {}
}

function removeCachedGame(gameId) {
  delete generatedHtmlCache[gameId];
  if (isWsEnabled()) return;
  try {
    const existing = JSON.parse(localStorage.getItem(VERCEL_CACHE_KEY) || "[]");
    localStorage.setItem(VERCEL_CACHE_KEY, JSON.stringify(existing.filter((g) => g && g.id !== gameId)));
  } catch (e) {}
}

function getCachedGames() {
  try {
    const items = JSON.parse(localStorage.getItem(VERCEL_CACHE_KEY) || "[]");
    return Array.isArray(items) ? items : [];
  } catch (e) {
    return [];
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupThemeSwitcher();
  setupGameControllers();
  setupNavScrollIndicator();
  setupGameReferenceSelector();
  setupEventListeners();
  setupViewportFocus();
  fetchGames();
});

function applyTheme(themeName) {
  const resolved = THEME_ORDER.includes(themeName) ? themeName : "light";
  document.documentElement.setAttribute("data-theme", resolved);
  try {
    localStorage.setItem(THEME_KEY, resolved);
  } catch (e) {}

  const btn = document.getElementById("theme-toggle-btn");
  if (btn) {
    btn.textContent = THEME_LABELS[resolved];
    btn.setAttribute("data-theme-mode", resolved);
  }
}

function setupThemeSwitcher() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  applyTheme(current);

  const btn = document.getElementById("theme-toggle-btn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const active = document.documentElement.getAttribute("data-theme") || "light";
    const idx = THEME_ORDER.indexOf(active);
    const next = THEME_ORDER[(idx + 1) % THEME_ORDER.length];
    applyTheme(next);
  });
}

function appendCtrlQuery(url) {
  if (!url) return url;
  const sep = url.includes("?") ? "&" : "?";
  return url.includes("ctrl=") ? url : `${url}${sep}ctrl=1`;
}

function injectControlShimIntoHtml(html) {
  if (!html || html.includes("window.__egCtrl")) return html;
  const shim = `<script>
(function () {
  if (window.__egCtrl) return;
  var paused = false, offset = 0, pAt = null;
  var oRaf = window.requestAnimationFrame.bind(window);
  var oCRaf = window.cancelAnimationFrame.bind(window);
  var oSI = window.setInterval.bind(window);
  var oCI = window.clearInterval.bind(window);
  var oPNow = (window.performance && window.performance.now)
    ? window.performance.now.bind(window.performance)
    : function () { return Date.now(); };
  var vid = 1, rafState = new Map(), queuedIds = [], intervals = new Map(), iid = 900000, audioCtxs = [];
  if (window.performance) {
    try { Object.defineProperty(window.performance, "now", { configurable: true, value: function () { return (pAt !== null ? pAt : oPNow()) - offset; } }); } catch (e) {}
  }
  var AC = window.AudioContext || window.webkitAudioContext;
  if (AC) {
    var WAC = function () { var c = new AC(); audioCtxs.push(c); return c; };
    WAC.prototype = AC.prototype;
    try { if (window.AudioContext) window.AudioContext = WAC; if (window.webkitAudioContext) window.webkitAudioContext = WAC; } catch (e) {}
  }
  function scheduleVirtualRaf(id, cb) {
    if (paused) { queuedIds.push(id); return; }
    var realId = oRaf(function (ts) {
      var entry = rafState.get(id);
      if (!entry || entry.cancelled) { rafState.delete(id); return; }
      if (paused) { entry.realId = null; queuedIds.push(id); return; }
      rafState.delete(id);
      cb(ts - offset);
    });
    var entry = rafState.get(id);
    if (entry) entry.realId = realId;
  }
  window.requestAnimationFrame = function (cb) {
    var id = vid++;
    rafState.set(id, { cb: cb, realId: null, cancelled: false });
    scheduleVirtualRaf(id, cb);
    return id;
  };
  window.cancelAnimationFrame = function (id) {
    var entry = rafState.get(id);
    if (entry) { entry.cancelled = true; if (entry.realId !== null) oCRaf(entry.realId); rafState.delete(id); } else { oCRaf(id); }
  };
  window.setInterval = function (fn, ms) {
    var args = Array.prototype.slice.call(arguments, 2);
    var id = iid++;
    intervals.set(id, oSI(function () { if (!paused && typeof fn === "function") fn.apply(window, args); }, ms));
    return id;
  };
  window.clearInterval = function (id) {
    if (intervals.has(id)) { oCI(intervals.get(id)); intervals.delete(id); } else { oCI(id); }
  };
  window.__egCtrl = {
    pause: function () {
      if (paused) return;
      paused = true; pAt = oPNow();
      audioCtxs.forEach(function (c) { try { if (c.state === "running") c.suspend(); } catch (e) {} });
    },
    resume: function () {
      if (!paused) return;
      paused = false;
      if (pAt !== null) { offset += oPNow() - pAt; pAt = null; }
      audioCtxs.forEach(function (c) { try { if (c.state === "suspended") c.resume(); } catch (e) {} });
      var ids = queuedIds.slice(); queuedIds = [];
      ids.forEach(function (id) { var entry = rafState.get(id); if (entry && !entry.cancelled) scheduleVirtualRaf(id, entry.cb); });
    },
    isPaused: function () { return paused; }
  };
})();
</` + `script>`;
  if (/<head\b[^>]*>/i.test(html)) {
    return html.replace(/<head\b[^>]*>/i, (m) => `${m}\n${shim}`);
  }
  return `${shim}\n${html}`;
}

function createIframeGameController(config) {
  const iframe = document.getElementById(config.iframeId);
  if (!iframe) return null;

  const titleEl = config.titleId ? document.getElementById(config.titleId) : null;
  const dotEl = config.dotId ? document.getElementById(config.dotId) : null;
  const pauseBtn = config.pauseBtnId ? document.getElementById(config.pauseBtnId) : null;
  const restartBtn = config.restartBtnId ? document.getElementById(config.restartBtnId) : null;
  const exitBtn = config.exitBtnId ? document.getElementById(config.exitBtnId) : null;
  const pauseOverlay = config.pauseOverlayId ? document.getElementById(config.pauseOverlayId) : null;
  const idleOverlay = config.idleOverlayId ? document.getElementById(config.idleOverlayId) : null;

  const state = {
    iframe,
    paused: false,
    exited: false,
    lastSource: config.initialSource || null,
  };

  function syncUi() {
    if (dotEl) {
      dotEl.classList.toggle("is-paused", state.paused && !state.exited);
      dotEl.classList.toggle("is-exited", state.exited);
    }
    if (pauseBtn) {
      pauseBtn.disabled = state.exited;
      pauseBtn.classList.toggle("is-active", state.paused && !state.exited);
      pauseBtn.textContent = state.paused ? "▶ Resume" : "⏸ Pause";
    }
    if (restartBtn) {
      restartBtn.disabled = !state.lastSource;
    }
    if (exitBtn) {
      exitBtn.disabled = state.exited;
    }
    if (pauseOverlay) {
      pauseOverlay.classList.toggle("is-visible", state.paused && !state.exited);
    }
    if (idleOverlay) {
      idleOverlay.classList.toggle("is-visible", state.exited);
    }
  }

  function focusFrame() {
    try {
      if (iframe.contentWindow) iframe.contentWindow.focus();
    } catch (e) {}
  }

  function loadSource(source) {
    if (!source) return;
    state.lastSource = source;
    state.paused = false;
    state.exited = false;
    if (titleEl && source.title) titleEl.innerText = source.title;

    if (source.useSrcdoc && source.srcdoc) {
      iframe.dataset.useSrcdoc = "1";
      iframe.removeAttribute("src");
      iframe.srcdoc = injectControlShimIntoHtml(source.srcdoc);
    } else if (source.src) {
      iframe.dataset.useSrcdoc = "0";
      iframe.removeAttribute("srcdoc");
      const base = source.src.replace(/([?&])t=\d+/g, "").replace(/[?&]$/, "");
      const withTime = `${base}${base.includes("?") ? "&" : "?"}t=${Date.now()}`;
      iframe.src = appendCtrlQuery(withTime);
    }
    syncUi();
    setTimeout(focusFrame, 300);
  }

  function pause() {
    if (state.exited || state.paused) return;
    state.paused = true;
    try {
      const win = iframe.contentWindow;
      if (win && win.__egCtrl) {
        win.__egCtrl.pause();
      }
    } catch (e) {}
    syncUi();
    if (pauseOverlay) pauseOverlay.focus();
  }

  function resume() {
    if (state.exited || !state.paused) return;
    state.paused = false;
    try {
      const win = iframe.contentWindow;
      if (win && win.__egCtrl) {
        win.__egCtrl.resume();
      }
    } catch (e) {}
    syncUi();
    setTimeout(focusFrame, 80);
  }

  function togglePause() {
    if (state.paused) resume();
    else pause();
  }

  function restart() {
    if (!state.lastSource) return;
    loadSource(state.lastSource);
  }

  function exit() {
    state.paused = false;
    state.exited = true;
    try {
      const win = iframe.contentWindow;
      if (win && win.__egCtrl) win.__egCtrl.pause();
    } catch (e) {}
    iframe.dataset.useSrcdoc = "0";
    iframe.removeAttribute("srcdoc");
    iframe.src = "about:blank";
    if (config.onExit) {
      config.onExit();
    } else if (titleEl) {
      titleEl.innerText = "No Active Game";
    }
    syncUi();
  }

  iframe.addEventListener("load", () => {
    if (state.exited) return;
    try {
      const win = iframe.contentWindow;
      if (win && !win.__egCtrl && win.location && win.location.href !== "about:blank") {
        // Fallback patch if external game loaded without query control shim
        const script = iframe.contentDocument && iframe.contentDocument.createElement("script");
        if (script) {
          script.textContent = injectControlShimIntoHtml("<head></head>").replace(/<\/?head>/g, "");
          iframe.contentDocument.head && iframe.contentDocument.head.prepend(script);
        }
      }
    } catch (e) {}
    if (state.paused) {
      pause();
    }
  });

  if (pauseBtn) pauseBtn.addEventListener("click", togglePause);
  if (restartBtn) restartBtn.addEventListener("click", restart);
  if (exitBtn) exitBtn.addEventListener("click", exit);
  (config.resumeTriggerIds || []).forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", resume);
  });
  (config.restartTriggerIds || []).forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", restart);
  });
  (config.exitTriggerIds || []).forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", exit);
  });

  syncUi();

  return {
    get paused() {
      return state.paused;
    },
    get exited() {
      return state.exited;
    },
    loadSource,
    pause,
    resume,
    togglePause,
    restart,
    exit,
  };
}

function setupGameControllers() {
  wbController = createIframeGameController({
    iframeId: "workbench-frame",
    titleId: "workbench-title-label",
    dotId: "wb-status-dot",
    pauseBtnId: "wb-pause-btn",
    restartBtnId: "wb-restart-btn",
    exitBtnId: "wb-exit-btn",
    pauseOverlayId: "wb-pause-overlay",
    idleOverlayId: "wb-idle-overlay",
    resumeTriggerIds: ["wb-overlay-resume-btn"],
    restartTriggerIds: ["wb-overlay-restart-btn", "wb-relaunch-btn"],
    exitTriggerIds: ["wb-overlay-exit-btn"],
    initialSource: {
      title: "Live Viewport: Neon Space Defender",
      src: "/api/games/archetype/shooter",
      useSrcdoc: false,
    },
  });

  modalController = createIframeGameController({
    iframeId: "game-frame",
    titleId: "modal-game-title",
    dotId: "modal-status-dot",
    pauseBtnId: "modal-pause-btn",
    restartBtnId: "modal-restart-btn",
    exitBtnId: "modal-close",
    pauseOverlayId: "modal-pause-overlay",
    resumeTriggerIds: ["modal-overlay-resume-btn"],
    restartTriggerIds: ["modal-overlay-restart-btn"],
    exitTriggerIds: ["modal-overlay-exit-btn"],
    onExit: closeModalDom,
  });
}

function setupNavScrollIndicator() {
  const navLinksContainer = document.getElementById("nav-links");
  const indicator = document.getElementById("nav-indicator");
  if (!navLinksContainer || !indicator) return;

  const navLinks = Array.from(navLinksContainer.querySelectorAll(".nav-link[data-section]"));
  if (navLinks.length === 0) return;

  document.documentElement.classList.add("page-snap-root");

  const sections = navLinks
    .map((link) => {
      const id = link.getAttribute("data-section");
      const el = id ? document.getElementById(id) : null;
      return el ? { id, el, link } : null;
    })
    .filter(Boolean);

  let activeSectionId = null;
  let scrollLock = null;
  let rafScheduled = false;
  let snapSettleTimer = null;

  function getSnapTop(el) {
    if (!el) return 0;
    return Math.max(0, Math.round(el.getBoundingClientRect().top + window.scrollY - 64));
  }

  function positionIndicator(targetLink, animate) {
    if (!targetLink) return;
    if (!animate) {
      indicator.classList.remove("is-ready");
    }
    const containerRect = navLinksContainer.getBoundingClientRect();
    const linkRect = targetLink.getBoundingClientRect();
    const left = linkRect.left - containerRect.left;
    const width = linkRect.width;
    if (width <= 0) return;

    indicator.style.width = `${width}px`;
    indicator.style.transform = `translateX(${left}px)`;

    if (!animate) {
      requestAnimationFrame(() => {
        indicator.classList.add("is-ready");
      });
    } else {
      indicator.classList.add("is-ready");
    }
  }

  function setActiveSection(sectionId, animate = true) {
    const targetLink =
      navLinks.find((l) => l.getAttribute("data-section") === sectionId) || navLinks[0];
    if (!targetLink) return;

    const resolvedId = targetLink.getAttribute("data-section");
    navLinks.forEach((l) => {
      l.classList.toggle("active", l === targetLink);
    });
    activeSectionId = resolvedId;
    positionIndicator(targetLink, animate);
  }

  function detectActiveSection() {
    if (sections.length === 0) {
      return activeSectionId || navLinks[0].getAttribute("data-section");
    }

    if (
      window.scrollY > 0 &&
      Math.ceil(window.innerHeight + window.scrollY) >= document.documentElement.scrollHeight - 24
    ) {
      return sections[sections.length - 1].id;
    }

    const currentY = window.scrollY;
    let closest = sections[0];
    let minDistance = Infinity;
    for (const sec of sections) {
      const dist = Math.abs(getSnapTop(sec.el) - currentY);
      if (dist < minDistance) {
        minDistance = dist;
        closest = sec;
      }
    }
    return closest.id;
  }

  function snapToNearestPage() {
    if (snapSettleTimer) {
      clearTimeout(snapSettleTimer);
      snapSettleTimer = null;
    }
    if (window.innerWidth <= 900 || sections.length === 0) return;
    if (Date.now() < snapCooldownUntil) return;

    const modal = document.getElementById("game-modal");
    if (modal && modal.style.display && modal.style.display !== "none") return;

    const currentY = window.scrollY;
    const libraryTop = getSnapTop(sections[sections.length - 1].el);
    // Allow browsing long local game libraries & footer cleanly past Page 4 start
    if (currentY > libraryTop + 80) return;

    let nearest = sections[0];
    let nearestTop = getSnapTop(nearest.el);
    let minDiff = Math.abs(nearestTop - currentY);

    for (let i = 1; i < sections.length; i++) {
      const top = getSnapTop(sections[i].el);
      const diff = Math.abs(top - currentY);
      if (diff < minDiff) {
        minDiff = diff;
        nearest = sections[i];
        nearestTop = top;
      }
    }

    if (minDiff > 4) {
      setActiveSection(nearest.id, true);
      setSnapCooldown(650);
      window.scrollTo({ top: nearestTop, behavior: "smooth" });
    }
  }

  function scheduleSnap() {
    if (snapSettleTimer) clearTimeout(snapSettleTimer);
    snapSettleTimer = setTimeout(snapToNearestPage, 110);
  }

  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (e) => {
      const href = anchor.getAttribute("href");
      const targetId = href ? href.slice(1) : "";
      if (!targetId) return;
      const targetEl = document.getElementById(targetId);
      if (!targetEl) return;

      e.preventDefault();
      const targetTop = getSnapTop(targetEl);
      if (sections.some((s) => s.id === targetId)) {
        scrollLock = { id: targetId, el: targetEl, targetTop, until: Date.now() + 750 };
        setActiveSection(targetId, true);
      }
      setSnapCooldown(750);
      window.scrollTo({ top: targetTop, behavior: "smooth" });
    });
  });

  function syncOnScroll() {
    rafScheduled = false;
    if (scrollLock) {
      const arrived = Math.abs(window.scrollY - scrollLock.targetTop) < 12;
      if (arrived || Date.now() >= scrollLock.until) {
        scrollLock = null;
      } else {
        return;
      }
    }
    const nextId = detectActiveSection();
    if (nextId && nextId !== activeSectionId) {
      setActiveSection(nextId, true);
    }
  }

  const hashId = window.location.hash ? window.location.hash.slice(1) : "";
  const initialId =
    sections.some((s) => s.id === hashId) ? hashId : detectActiveSection();
  setActiveSection(initialId, false);

  if (sections.length > 0) {
    window.addEventListener(
      "scroll",
      () => {
        if (!rafScheduled) {
          rafScheduled = true;
          requestAnimationFrame(syncOnScroll);
        }
        if (Date.now() >= snapCooldownUntil) {
          scheduleSnap();
        }
      },
      { passive: true }
    );

    if ("onscrollend" in window) {
      window.addEventListener("scrollend", () => {
        if (Date.now() >= snapCooldownUntil) {
          snapToNearestPage();
        }
      });
    }

    ["wheel", "touchstart"].forEach((evt) => {
      window.addEventListener(
        evt,
        () => {
          if (snapSettleTimer) {
            clearTimeout(snapSettleTimer);
            snapSettleTimer = null;
          }
        },
        { passive: true }
      );
    });
  }

  window.addEventListener("resize", () => {
    const activeLink = navLinksContainer.querySelector(".nav-link.active") || navLinks[0];
    positionIndicator(activeLink, false);
  });

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      const activeLink = navLinksContainer.querySelector(".nav-link.active") || navLinks[0];
      positionIndicator(activeLink, false);
    });
  }
}

function setupGameReferenceSelector() {
  const refSelect = document.getElementById("game-reference-select");
  const promptInput = document.getElementById("prompt-input");
  const hintEl = document.getElementById("reference-controls-hint");
  if (!refSelect) return;

  const defaultHint =
    "Selecting a game generates a simpler runnable version with basic controls & logic.";

  refSelect.addEventListener("change", () => {
    const refId = refSelect.value;
    if (!refId) {
      selectedGameReference = null;
      lastReferencePrompt = "";
      if (hintEl) hintEl.textContent = defaultHint;
      return;
    }

    const opt = refSelect.options[refSelect.selectedIndex];
    const refPrompt = opt ? opt.getAttribute("data-prompt") || "" : "";
    const refControls = opt ? opt.getAttribute("data-controls") || "" : "";

    selectedGameReference = refId;
    lastReferencePrompt = refPrompt;
    if (promptInput && refPrompt) {
      promptInput.value = refPrompt;
    }
    if (hintEl) {
      hintEl.textContent = refControls ? `Controls: ${refControls}` : defaultHint;
    }

    handleGenerate(refId);
  });

  if (promptInput) {
    promptInput.addEventListener("input", () => {
      if (selectedGameReference && promptInput.value !== lastReferencePrompt) {
        selectedGameReference = null;
        lastReferencePrompt = "";
        refSelect.value = "";
        if (hintEl) hintEl.textContent = defaultHint;
      }
    });
  }
}

function setupViewportFocus() {
  const wbViewport = document.querySelector(".studio-viewport");
  if (wbViewport) {
    wbViewport.addEventListener("mouseenter", focusWorkbenchFrame);
    wbViewport.addEventListener("click", focusWorkbenchFrame);
  }

  // Forward keyboard controls from parent window to workbench iframe
  window.addEventListener("keydown", (e) => {
    const active = document.activeElement;
    if (active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName)) {
      return;
    }
    if (wbController && (wbController.paused || wbController.exited)) {
      return;
    }
    const handledKeys = ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "KeyW", "KeyA", "KeyS", "KeyD"];
    if (handledKeys.includes(e.code)) {
      const wb = document.getElementById("workbench-frame");
      if (wb && wb.contentWindow) {
        try {
          wb.contentWindow.focus();
          wb.contentWindow.dispatchEvent(new KeyboardEvent("keydown", { code: e.code, key: e.key, bubbles: true }));
        } catch (err) {}
      }
    }
  });
}

function focusWorkbenchFrame() {
  if (wbController && (wbController.paused || wbController.exited)) {
    return;
  }
  const wb = document.getElementById("workbench-frame");
  if (wb && wb.contentWindow) {
    try {
      wb.contentWindow.focus();
    } catch (e) {}
  }
}

function setupEventListeners() {
  const generateBtn = document.getElementById("generate-btn");
  const promptInput = document.getElementById("prompt-input");
  const fullscreenBtn = document.getElementById("fullscreen-btn");
  const refreshGamesBtn = document.getElementById("refresh-games-btn");
  const saveKeyBtn = document.getElementById("save-key-btn");
  const wbFullscreenBtn = document.getElementById("wb-fullscreen-btn");

  if (generateBtn) {
    generateBtn.addEventListener("click", handleGenerate);
  }

  if (promptInput) {
    promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleGenerate();
      }
    });
  }

  if (fullscreenBtn) {
    fullscreenBtn.addEventListener("click", () => {
      const iframe = document.getElementById("game-frame");
      if (iframe && iframe.requestFullscreen) {
        iframe.requestFullscreen();
      }
    });
  }

  if (wbFullscreenBtn) {
    wbFullscreenBtn.addEventListener("click", () => {
      const wb = document.getElementById("workbench-frame");
      if (wb && wb.requestFullscreen) {
        wb.requestFullscreen();
      }
    });
  }

  if (refreshGamesBtn) {
    refreshGamesBtn.addEventListener("click", fetchGames);
  }

  if (saveKeyBtn) {
    saveKeyBtn.addEventListener("click", async () => {
      const keyInput = document.getElementById("gemini-key-input");
      const key = keyInput.value.trim();
      if (!key) return;
      saveKeyBtn.disabled = true;
      saveKeyBtn.innerText = "Saving...";
      try {
        const res = await fetch("/api/settings/key", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: key, provider: "gemini" }),
        });
        if (res.ok) {
          saveKeyBtn.innerText = "✔ Saved!";
          setTimeout(() => { location.reload(); }, 600);
        } else {
          throw new Error("Save failed");
        }
      } catch (e) {
        alert("Failed to save Gemini key.");
        saveKeyBtn.disabled = false;
        saveKeyBtn.innerText = "Save Key";
      }
    });
  }

  // Preset chips click: Fill prompt AND launch archetype immediately!
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", (e) => {
      e.preventDefault();
      const prompt = chip.getAttribute("data-prompt");
      const archetype = chip.getAttribute("data-archetype");
      const title = chip.getAttribute("data-title");
      const refSelect = document.getElementById("game-reference-select");
      if (prompt && promptInput) promptInput.value = prompt;
      selectedGameReference = null;
      lastReferencePrompt = "";
      if (refSelect) refSelect.value = "";

      if (archetype) {
        loadArchetypeIntoWorkbench(archetype, title || "Live Archetype");
      }
    });
  });

  // Image Generation Handler
  setupImageGenerator();
}

async function rasterizeSvgToPng(svgDataUrl, size = 1024) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, size, size);
        resolve(canvas.toDataURL("image/png"));
      } catch (e) {
        resolve(null);
      }
    };
    img.onerror = () => resolve(null);
    img.src = svgDataUrl;
  });
}

function setupImageGenerator() {
  const generateImgBtn = document.getElementById("generate-image-btn");
  const imgPromptInput = document.getElementById("image-prompt-input");
  const imgStyleSelect = document.getElementById("image-style-select");
  const imgResultBox = document.getElementById("image-result-box");
  const imgResultThumb = document.getElementById("image-result-thumb");
  const imgResultDesc = document.getElementById("image-result-desc");
  const copyDataUrlBtn = document.getElementById("copy-data-url-btn");
  const downloadAssetLink = document.getElementById("download-asset-link");

  let lastImageDataUrl = "";

  async function triggerImageGeneration() {
    const prompt = imgPromptInput ? imgPromptInput.value.trim() : "";
    if (!prompt) {
      if (imgPromptInput) imgPromptInput.focus();
      return;
    }

    generateImgBtn.disabled = true;
    generateImgBtn.innerHTML = "<span>🎨 Synthesizing...</span>";

    try {
      const res = await fetch("/api/images/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt,
          style: imgStyleSelect ? imgStyleSelect.value : "pixel-art",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Image generation failed");
      }

      const data = await res.json();
      let finalDataUrl = data.data_url;
      let finalFilename = data.filename || "asset.png";

      if (data.mime_type === "image/svg+xml" || (finalDataUrl && finalDataUrl.startsWith("data:image/svg+xml"))) {
        const pngDataUrl = await rasterizeSvgToPng(finalDataUrl, 1024);
        if (pngDataUrl) {
          finalDataUrl = pngDataUrl;
          finalFilename = finalFilename.replace(/\.svg$/i, ".png");
        }
      }

      lastImageDataUrl = finalDataUrl;
      imgResultThumb.src = finalDataUrl;
      imgResultDesc.innerText = prompt;
      downloadAssetLink.href = finalDataUrl;
      downloadAssetLink.download = finalFilename;
      imgResultBox.style.display = "flex";
    } catch (err) {
      alert(`Image Generation: ${err.message}`);
    } finally {
      generateImgBtn.disabled = false;
      generateImgBtn.innerHTML = "<span>🎨 Synthesize Asset</span>";
    }
  }

  if (generateImgBtn) {
    generateImgBtn.addEventListener("click", triggerImageGeneration);
  }

  if (imgPromptInput) {
    imgPromptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        triggerImageGeneration();
      }
    });
  }

  if (copyDataUrlBtn) {
    copyDataUrlBtn.addEventListener("click", () => {
      if (lastImageDataUrl) {
        navigator.clipboard.writeText(lastImageDataUrl);
        copyDataUrlBtn.innerText = "✔ Copied!";
        setTimeout(() => { copyDataUrlBtn.innerText = "📋 Copy Data URL"; }, 2000);
      }
    });
  }
}

function setGenerationBusy(isBusy) {
  const generateBtn = document.getElementById("generate-btn");
  const refSelect = document.getElementById("game-reference-select");
  if (generateBtn) {
    generateBtn.disabled = isBusy;
    if (!isBusy) {
      generateBtn.innerHTML = `<span>⚡ Generate & Launch Game</span>`;
    }
  }
  if (refSelect) {
    refSelect.disabled = isBusy;
  }
}

async function handleGenerate(overrideRefId = null) {
  const promptInput = document.getElementById("prompt-input");
  const generateBtn = document.getElementById("generate-btn");
  const streamPanel = document.getElementById("stream-panel");
  const instantToggle = document.getElementById("instant-mode-toggle");

  const gameReference =
    typeof overrideRefId === "string" && overrideRefId
      ? overrideRefId
      : selectedGameReference || null;

  let prompt = promptInput ? promptInput.value.trim() : "";
  if (!prompt && !gameReference) {
    prompt = "Retro Space Invaders with laser cannons and simple keyboard controls";
    if (promptInput) promptInput.value = prompt;
  }

  const instant = instantToggle ? instantToggle.checked : false;

  setGenerationBusy(true);
  if (generateBtn) {
    generateBtn.innerHTML = instant
      ? `<span>⚡ Loading Template...</span>`
      : `<span>🧠 AI Generating Game (~10-20s)...</span>`;
  }
  streamPanel.style.display = "block";
  streamPanel.textContent = gameReference
    ? `Generating simple runnable "${gameReference}" game...\n`
    : instant
      ? `Loading instant template...\n`
      : `Connecting to 8Gen AI engine (custom synthesis)...\n`;

  if (!isWsEnabled()) {
    fallbackHttpGenerate(prompt, gameReference, instant);
    return;
  }

  // WebSocket or fallback to HTTP
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/generate`;

  let ws;
  let opened = false;
  let completed = false;
  let errored = false;

  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.warn("WebSocket unavailable, falling back to HTTP");
  }

  if (ws) {
    ws.onopen = () => {
      opened = true;
      ws.send(JSON.stringify({ prompt, game_reference: gameReference, instant }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "start") {
        streamPanel.textContent += `Synthesizing game for: "${data.prompt || prompt}"...\n\n`;
      } else if (data.type === "delta") {
        streamPanel.textContent += data.chunk;
        streamPanel.scrollTop = streamPanel.scrollHeight;
      } else if (data.type === "completed") {
        completed = true;
        streamPanel.textContent += "\n\n✔ Game successfully synthesized and validated!";
        streamPanel.scrollTop = streamPanel.scrollHeight;
        setGenerationBusy(false);
        if (data.game) {
          cacheGameLocally(data.game);
          loadGameIntoWorkbench(data.game.id, data.game.title);
        }
        fetchGames();
      } else if (data.type === "error") {
        errored = true;
        streamPanel.textContent += `\n\n✖ Notice: ${data.message}\nFalling back to REST generation...`;
        fallbackHttpGenerate(prompt, gameReference, instant);
      }
    };

    ws.onerror = () => {
      if (!completed && !errored) {
        errored = true;
        fallbackHttpGenerate(prompt, gameReference, instant);
      }
    };

    ws.onclose = () => {
      if (!completed && !errored) {
        if (!opened) {
          errored = true;
          fallbackHttpGenerate(prompt, gameReference, instant);
        } else {
          setGenerationBusy(false);
          streamPanel.textContent += "\n\n⚠️ Connection closed unexpectedly. Please try again.";
        }
      }
    };
  } else {
    fallbackHttpGenerate(prompt, gameReference, instant);
  }
}

async function fallbackHttpGenerate(prompt, gameReference, instant) {
  const streamPanel = document.getElementById("stream-panel");

  try {
    streamPanel.textContent += "\nDispatching AI synthesis request...";
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, game_reference: gameReference, instant }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Generation failed");
    }

    const game = await res.json();
    cacheGameLocally(game);
    streamPanel.textContent += "\n✔ Game created successfully!";
    loadGameIntoWorkbench(game.id, game.title);
    fetchGames();
  } catch (err) {
    streamPanel.textContent += `\n✖ Error: ${err.message}`;
  } finally {
    setGenerationBusy(false);
  }
}

function loadGameIntoWorkbench(gameId, title) {
  activeGameId = gameId;
  const cachedHtml = generatedHtmlCache[gameId];
  const useSrcdoc = !isWsEnabled() && Boolean(cachedHtml);
  const source = useSrcdoc
    ? { title: `Live Viewport: ${title}`, useSrcdoc: true, srcdoc: cachedHtml }
    : { title: `Live Viewport: ${title}`, useSrcdoc: false, src: `/api/games/${gameId}/play` };

  if (wbController) {
    wbController.loadSource(source);
  } else {
    const wbFrame = document.getElementById("workbench-frame");
    const wbTitle = document.getElementById("workbench-title-label");
    if (wbTitle) wbTitle.innerText = source.title;
    if (wbFrame) {
      if (useSrcdoc) {
        wbFrame.removeAttribute("src");
        wbFrame.srcdoc = injectControlShimIntoHtml(cachedHtml);
      } else {
        wbFrame.removeAttribute("srcdoc");
        wbFrame.src = appendCtrlQuery(`/api/games/${gameId}/play?t=${Date.now()}`);
      }
    }
  }

  const wbSection = document.getElementById("workbench");
  if (wbSection) {
    setSnapCooldown(750);
    wbSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

window.loadArchetypeIntoWorkbench = function(type, title) {
  const source = {
    title: `Live Viewport: ${title}`,
    useSrcdoc: false,
    src: `/api/games/archetype/${type}`,
  };
  if (wbController) {
    wbController.loadSource(source);
  } else {
    const wbFrame = document.getElementById("workbench-frame");
    const wbTitle = document.getElementById("workbench-title-label");
    if (wbTitle) wbTitle.innerText = source.title;
    if (wbFrame) {
      wbFrame.removeAttribute("srcdoc");
      wbFrame.src = appendCtrlQuery(`/api/games/archetype/${type}?t=${Date.now()}`);
    }
  }

  const wbSection = document.getElementById("workbench");
  if (wbSection) {
    setSnapCooldown(750);
    wbSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
};

async function fetchGames() {
  const grid = document.getElementById("games-grid");
  const countEl = document.getElementById("game-count");

  try {
    const res = await fetch("/api/games");
    let games = await res.json();
    if (!Array.isArray(games)) games = [];
    games.forEach(cacheGameLocally);

    if (!isWsEnabled()) {
      const serverIds = new Set(games.map((g) => g.id));
      for (const localGame of getCachedGames()) {
        if (localGame && localGame.id && !serverIds.has(localGame.id)) {
          const html = getLatestHtmlFromGame(localGame);
          if (html) generatedHtmlCache[localGame.id] = html;
          games.push(localGame);
        }
      }
    }

    if (countEl) countEl.innerText = `${games.length} Games`;
    renderGallery(games);
  } catch (err) {
    console.error("Failed to fetch games:", err);
    if (grid) grid.innerHTML = `<div class="product-mockup-card" style="grid-column: 1 / -1; padding: 32px; text-align: center;"><p class="body-sm">Unable to connect to local game repository.</p></div>`;
  }
}

function renderGallery(games) {
  const grid = document.getElementById("games-grid");
  if (!grid) return;

  if (!games || games.length === 0) {
    grid.innerHTML = `
      <div class="product-mockup-card" style="grid-column: 1 / -1; padding: 48px; text-align: center;">
        <h3 class="title-md" style="margin-bottom: 8px;">No games generated yet</h3>
        <p class="body-sm" style="margin-bottom: 16px;">Pick a starter preset above or click Generate to create your first game.</p>
        <a href="#workbench" class="btn-primary">Launch Studio Workbench</a>
      </div>`;
    return;
  }

  grid.innerHTML = games.map((g) => {
    const icon = getCategoryIcon(g.category);
    return `
      <div class="product-mockup-card" style="padding: 24px; display: flex; flex-direction: column;" data-id="${g.id}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <div style="font-size: 28px;">${icon}</div>
          <div style="display: flex; gap: 6px;">
            <span class="badge-pill">v${g.current_version}</span>
            <span class="badge-pill" style="text-transform: capitalize;">${escapeHtml(g.category || 'arcade')}</span>
          </div>
        </div>

        <h3 class="title-md" style="margin-bottom: 6px; font-size: 17px;">${escapeHtml(g.title)}</h3>
        <p class="body-sm" style="flex: 1; margin-bottom: 16px; font-size: 13px; line-height: 1.4; color: var(--color-muted); max-height: 40px; overflow: hidden; text-overflow: ellipsis;">
          ${escapeHtml(g.description || g.title)}
        </p>

        <div style="display: flex; gap: 8px; align-items: center; margin-top: auto;">
          <button class="btn-primary" style="flex: 1; height: 34px; font-size: 12px; padding: 0 10px;" onclick="loadGameIntoWorkbench('${g.id}', '${escapeHtml(g.title)}')">
            ▶ Play
          </button>
          <button class="btn-secondary" style="height: 34px; font-size: 12px; padding: 0 10px;" onclick="promptRefine('${g.id}', '${escapeHtml(g.title)}')">
            ⚡ Refine
          </button>
          <a href="/api/games/${g.id}/download" class="btn-secondary" style="height: 34px; font-size: 12px; padding: 0 10px; display: inline-flex; align-items: center;" title="Export HTML" download onclick="return handleDownloadGame(event, '${g.id}', '${escapeHtml(g.slug || g.title)}')">
            ⬇
          </a>
          <button class="btn-icon-circular" style="width: 34px; height: 34px; font-size: 12px; flex-shrink: 0;" onclick="deleteGame('${g.id}')" title="Delete">
            ✕
          </button>
        </div>
      </div>
    `;
  }).join("");
}

function getCategoryIcon(cat) {
  const c = (cat || "").toLowerCase();
  if (c.includes("shooter") || c.includes("space")) return "🚀";
  if (c.includes("snake") || c.includes("worm")) return "🐍";
  if (c.includes("brick") || c.includes("break")) return "🧱";
  if (c.includes("drone") || c.includes("fly") || c.includes("platform")) return "⚡";
  if (c.includes("puzzle") || c.includes("match")) return "🧩";
  return "🎮";
}

function openGame(gameId, title) {
  activeGameId = gameId;
  const modal = document.getElementById("game-modal");
  const source = {
    title: title || "Play Game",
    useSrcdoc: false,
    src: `/api/games/${gameId}/play`,
  };
  if (modalController) {
    modalController.loadSource(source);
  } else {
    const modalTitle = document.getElementById("modal-game-title");
    const iframe = document.getElementById("game-frame");
    if (modalTitle) modalTitle.innerText = source.title;
    if (iframe) iframe.src = appendCtrlQuery(`${source.src}?t=${Date.now()}`);
  }
  if (modal) modal.style.display = "flex";
}

function closeModalDom() {
  const modal = document.getElementById("game-modal");
  if (modal) modal.style.display = "none";
}

function closeModal() {
  if (modalController) {
    modalController.exit();
    return;
  }
  const iframe = document.getElementById("game-frame");
  if (iframe) iframe.src = "about:blank";
  closeModalDom();
}

function promptRefine(gameId, title) {
  const instruction = prompt(`Refine game "${title}":\n(e.g. "add sound effects", "make enemies shoot lasers", "add double jump")`);
  if (!instruction || !instruction.trim()) return;

  const streamPanel = document.getElementById("stream-panel");
  if (streamPanel) {
    streamPanel.style.display = "block";
    streamPanel.textContent = `Refining "${title}" with: "${instruction}"...\nPlease wait...`;
  }

  fetch(`/api/games/${gameId}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  })
    .then((res) => {
      if (!res.ok) throw new Error("Refinement failed");
      return res.json();
    })
    .then((updated) => {
      cacheGameLocally(updated);
      if (streamPanel) streamPanel.textContent = `✔ Refinement complete! Game updated to v${updated.current_version}.`;
      loadGameIntoWorkbench(updated.id, updated.title);
      fetchGames();
    })
    .catch((err) => {
      if (streamPanel) streamPanel.textContent = `✖ Refinement error: ${err.message}`;
    });
}

function handleDownloadGame(event, gameId, slug) {
  if (!isWsEnabled() && generatedHtmlCache[gameId]) {
    event.preventDefault();
    const blob = new Blob([generatedHtmlCache[gameId]], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(slug || "game").replace(/[^a-z0-9-_]+/gi, "-")}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return false;
  }
  return true;
}

async function deleteGame(gameId) {
  if (!confirm("Are you sure you want to delete this game?")) return;
  try {
    await fetch(`/api/games/${gameId}`, { method: "DELETE" });
    removeCachedGame(gameId);
    fetchGames();
  } catch (err) {
    alert("Could not delete game.");
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
