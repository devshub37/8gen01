// 8Gen Autonomous Game Studio - Universal SaaS Dashboard Logic

let activeGameId = null;
let selectedCategory = "arcade";
const generatedHtmlCache = {};
const VERCEL_CACHE_KEY = "eightgen_vercel_games_v1";

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
  setupNavScrollIndicator();
  setupCategoryTabs();
  setupEventListeners();
  setupViewportFocus();
  fetchGames();
});

function setupNavScrollIndicator() {
  const navLinksContainer = document.getElementById("nav-links");
  const indicator = document.getElementById("nav-indicator");
  if (!navLinksContainer || !indicator) return;

  const navLinks = Array.from(navLinksContainer.querySelectorAll(".nav-link[data-section]"));
  if (navLinks.length === 0) return;

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

    const triggerY = 64 + Math.min(200, Math.round(window.innerHeight * 0.28));
    let currentId = sections[0].id;
    for (const sec of sections) {
      if (sec.el.getBoundingClientRect().top <= triggerY) {
        currentId = sec.id;
      }
    }
    return currentId;
  }

  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      const targetId = link.getAttribute("data-section");
      if (!targetId) return;
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        scrollLock = { id: targetId, el: targetEl, until: Date.now() + 700 };
        setActiveSection(targetId, true);
      }
    });
  });

  function syncOnScroll() {
    rafScheduled = false;
    if (scrollLock) {
      const arrived = Math.abs(scrollLock.el.getBoundingClientRect().top - 80) < 36;
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
      },
      { passive: true }
    );
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

function setupCategoryTabs() {
  const tabs = document.querySelectorAll(".category-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      selectedCategory = tab.getAttribute("data-cat") || "arcade";
    });
  });
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
  const modalClose = document.getElementById("modal-close");
  const fullscreenBtn = document.getElementById("fullscreen-btn");
  const refreshGamesBtn = document.getElementById("refresh-games-btn");
  const saveKeyBtn = document.getElementById("save-key-btn");
  const wbRestartBtn = document.getElementById("wb-restart-btn");
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

  if (modalClose) {
    modalClose.addEventListener("click", closeModal);
  }

  if (fullscreenBtn) {
    fullscreenBtn.addEventListener("click", () => {
      const iframe = document.getElementById("game-frame");
      if (iframe && iframe.requestFullscreen) {
        iframe.requestFullscreen();
      }
    });
  }

  if (wbRestartBtn) {
    wbRestartBtn.addEventListener("click", () => {
      const wb = document.getElementById("workbench-frame");
      if (wb) {
        if (wb.dataset.useSrcdoc === "1") {
          const doc = wb.srcdoc;
          wb.srcdoc = "";
          setTimeout(() => {
            wb.srcdoc = doc;
            setTimeout(focusWorkbenchFrame, 300);
          }, 60);
        } else {
          const src = wb.src;
          wb.src = "about:blank";
          setTimeout(() => {
            wb.src = src;
            setTimeout(focusWorkbenchFrame, 300);
          }, 60);
        }
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
      const cat = chip.getAttribute("data-category");
      if (prompt && promptInput) promptInput.value = prompt;
      if (cat) {
        selectedCategory = cat;
        document.querySelectorAll(".category-tab").forEach((t) => {
          if (t.getAttribute("data-cat") === cat) t.classList.add("active");
          else t.classList.remove("active");
        });
      }

      // Immediately launch the matching playable archetype into the workbench!
      if (cat === "shooter" || (prompt && prompt.includes("Space"))) {
        loadArchetypeIntoWorkbench("shooter", "Neon Space Defender");
      } else if (prompt && prompt.includes("Snake")) {
        loadArchetypeIntoWorkbench("snake", "Cyber Snake 2099");
      } else if (prompt && prompt.includes("Brick")) {
        loadArchetypeIntoWorkbench("brick", "Quantum Breakout");
      } else if (prompt && (prompt.includes("Drone") || prompt.includes("Flappy"))) {
        loadArchetypeIntoWorkbench("drone", "Aero Drone Odyssey");
      }
    });
  });

  // Image Generation Handler
  setupImageGenerator();
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

  if (generateImgBtn) {
    generateImgBtn.addEventListener("click", async () => {
      const prompt = imgPromptInput.value.trim();
      if (!prompt) return;

      generateImgBtn.disabled = true;
      generateImgBtn.innerHTML = "<span>🎨 Synthesizing...</span>";

      try {
        const res = await fetch("/api/images/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: prompt,
            style: imgStyleSelect.value,
          }),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Image generation failed");
        }

        const data = await res.json();
        lastImageDataUrl = data.data_url;
        imgResultThumb.src = data.data_url;
        imgResultDesc.innerText = prompt;
        downloadAssetLink.href = data.data_url;
        downloadAssetLink.download = data.filename || "asset.png";
        imgResultBox.style.display = "flex";
      } catch (err) {
        alert(`Image Generation: ${err.message}`);
      } finally {
        generateImgBtn.disabled = false;
        generateImgBtn.innerHTML = "<span>🎨 Synthesize Asset</span>";
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

async function handleGenerate() {
  const promptInput = document.getElementById("prompt-input");
  const generateBtn = document.getElementById("generate-btn");
  const streamPanel = document.getElementById("stream-panel");
  const instantToggle = document.getElementById("instant-mode-toggle");

  let prompt = promptInput ? promptInput.value.trim() : "";
  if (!prompt) {
    prompt = "Retro Space Invaders with laser cannons and alien boss waves";
    if (promptInput) promptInput.value = prompt;
  }

  const category = selectedCategory || "arcade";
  const instant = instantToggle ? instantToggle.checked : false;

  generateBtn.disabled = true;
  generateBtn.innerHTML = instant
    ? `<span>⚡ Loading Template...</span>`
    : `<span>🧠 AI Generating Game (~10-20s)...</span>`;
  streamPanel.style.display = "block";
  streamPanel.textContent = instant
    ? `Loading instant template...\n`
    : `Connecting to 8Gen AI engine (custom synthesis)...\n`;

  if (!isWsEnabled()) {
    fallbackHttpGenerate(prompt, category, instant);
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
      ws.send(JSON.stringify({ prompt, category, instant }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "start") {
        streamPanel.textContent += `Synthesizing game for: "${prompt}"...\n\n`;
      } else if (data.type === "delta") {
        streamPanel.textContent += data.chunk;
        streamPanel.scrollTop = streamPanel.scrollHeight;
      } else if (data.type === "completed") {
        completed = true;
        streamPanel.textContent += "\n\n✔ Game successfully synthesized and validated!";
        streamPanel.scrollTop = streamPanel.scrollHeight;
        generateBtn.disabled = false;
        generateBtn.innerHTML = `<span>⚡ Generate & Launch Game</span>`;
        if (data.game) {
          cacheGameLocally(data.game);
          loadGameIntoWorkbench(data.game.id, data.game.title);
        }
        fetchGames();
      } else if (data.type === "error") {
        errored = true;
        streamPanel.textContent += `\n\n✖ Notice: ${data.message}\nFalling back to REST generation...`;
        fallbackHttpGenerate(prompt, category, instant);
      }
    };

    ws.onerror = () => {
      if (!completed && !errored) {
        errored = true;
        fallbackHttpGenerate(prompt, category, instant);
      }
    };

    ws.onclose = () => {
      if (!completed && !errored) {
        if (!opened) {
          errored = true;
          fallbackHttpGenerate(prompt, category, instant);
        } else {
          generateBtn.disabled = false;
          generateBtn.innerHTML = `<span>⚡ Generate & Launch Game</span>`;
          streamPanel.textContent += "\n\n⚠️ Connection closed unexpectedly. Please try again.";
        }
      }
    };
  } else {
    fallbackHttpGenerate(prompt, category, instant);
  }
}

async function fallbackHttpGenerate(prompt, category, instant) {
  const generateBtn = document.getElementById("generate-btn");
  const streamPanel = document.getElementById("stream-panel");

  try {
    streamPanel.textContent += "\nDispatching AI synthesis request...";
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, category, instant }),
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
    generateBtn.disabled = false;
    generateBtn.innerHTML = `<span>⚡ Generate & Launch Game</span>`;
  }
}

function loadGameIntoWorkbench(gameId, title) {
  activeGameId = gameId;
  const wbFrame = document.getElementById("workbench-frame");
  const wbTitle = document.getElementById("workbench-title-label");

  if (wbTitle) wbTitle.innerText = `Live Viewport: ${title}`;
  if (wbFrame) {
    const cachedHtml = generatedHtmlCache[gameId];
    if (!isWsEnabled() && cachedHtml) {
      wbFrame.dataset.useSrcdoc = "1";
      wbFrame.removeAttribute("src");
      wbFrame.srcdoc = cachedHtml;
    } else {
      wbFrame.dataset.useSrcdoc = "0";
      wbFrame.removeAttribute("srcdoc");
      wbFrame.src = `/api/games/${gameId}/play?t=${Date.now()}`;
    }
    setTimeout(focusWorkbenchFrame, 350);
  }

  const wbSection = document.getElementById("workbench");
  if (wbSection) {
    wbSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

window.loadArchetypeIntoWorkbench = function(type, title) {
  const wbFrame = document.getElementById("workbench-frame");
  const wbTitle = document.getElementById("workbench-title-label");

  if (wbTitle) wbTitle.innerText = `Live Viewport: ${title}`;
  if (wbFrame) {
    wbFrame.dataset.useSrcdoc = "0";
    wbFrame.removeAttribute("srcdoc");
    wbFrame.src = `/api/games/archetype/${type}?t=${Date.now()}`;
    setTimeout(focusWorkbenchFrame, 350);
  }

  const wbSection = document.getElementById("workbench");
  if (wbSection) {
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
  const modalTitle = document.getElementById("modal-game-title");
  const iframe = document.getElementById("game-frame");

  if (modalTitle) modalTitle.innerText = title || "Play Game";
  if (iframe) iframe.src = `/api/games/${gameId}/play?t=${Date.now()}`;
  if (modal) modal.style.display = "flex";
}

function closeModal() {
  const modal = document.getElementById("game-modal");
  const iframe = document.getElementById("game-frame");
  if (modal) modal.style.display = "none";
  if (iframe) iframe.src = "about:blank";
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
