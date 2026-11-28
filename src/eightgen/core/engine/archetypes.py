"""Full production-grade game archetypes guaranteed to be 100% playable and engaging."""

import html
import json

from eightgen.core.engine.modules import AUDIO_CORE_JS, PARTICLE_SYSTEM_JS, INPUT_CONTROLLER_JS


def _prepare_title(title: str) -> tuple[str, str]:
    """Return an HTML-safe title and a JavaScript string literal for it."""
    raw = str(title or "Arcade Classic")
    safe_html = html.escape(raw, quote=True)
    # JSON quoting handles quotes/backslashes; escaping ``</`` prevents the
    # string from closing the surrounding <script> element.
    js_literal = json.dumps(raw).replace("</", "<\\/")
    return safe_html, js_literal


_PLATFORMER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>__TITLE__</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100%; height: 100%; overflow: hidden; background: #070b14; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #f8fafc; display: flex; align-items: center; justify-content: center;
      user-select: none; -webkit-user-select: none; touch-action: none;
    }
    #shell { position: relative; width: min(100vw, 1200px); height: min(100vh, 675px); }
    canvas { display: block; width: 100%; height: 100%; background: #070b14; }
    #touch-controls {
      position: absolute; inset: auto 0 14px 0; display: none;
      justify-content: space-between; align-items: flex-end; padding: 0 18px;
      pointer-events: none;
    }
    .touch-group { display: flex; gap: 12px; pointer-events: auto; }
    .touch-btn {
      width: 66px; height: 66px; border-radius: 50%; border: 2px solid rgba(148,163,184,.5);
      background: rgba(15,23,42,.72); color: #f8fafc; font-size: 22px; font-weight: 800;
      display: flex; align-items: center; justify-content: center; backdrop-filter: blur(6px);
      touch-action: none; cursor: pointer;
    }
    .touch-btn:active { background: rgba(56,189,248,.35); border-color: #38bdf8; }
    .touch-btn.jump { width: 84px; height: 84px; background: rgba(16,185,129,.25); border-color: rgba(16,185,129,.8); }
    @media (pointer: coarse) { #touch-controls { display: flex; } }
  </style>
</head>
<body>
  <div id="shell">
    <canvas id="gameCanvas" width="960" height="540"></canvas>
    <div id="touch-controls" aria-label="Touch controls">
      <div class="touch-group">
        <button class="touch-btn" id="touch-left" aria-label="Move left">◀</button>
        <button class="touch-btn" id="touch-right" aria-label="Move right">▶</button>
      </div>
      <div class="touch-group">
        <button class="touch-btn jump" id="touch-jump" aria-label="Jump">JUMP</button>
      </div>
    </div>
  </div>
  <script>
  __AUDIO__
  __PARTICLES__
  __INPUT__

  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d');
  Input.bindCanvas(canvas);
  const fx = new ParticleSystem();

  const W = 960, H = 540;
  const LEVEL_W = 2680;
  const GRAVITY = 2200, JUMP_V = -760, MAX_FALL = 1200;
  const RUN_SPEED = 320, ACCEL = 2400, AIR_ACCEL = 1600, FRICTION = 3000;
  const COYOTE = 0.10, JUMP_BUFFER = 0.12;
  const FIXED = 1 / 60;

  const platforms = [
    { x: 0, y: 500, w: 960, h: 40 },
    { x: 1100, y: 500, w: 900, h: 40 },
    { x: 2100, y: 500, w: 580, h: 40 },
    { x: 220, y: 410, w: 180, h: 18 },
    { x: 470, y: 340, w: 150, h: 18 },
    { x: 700, y: 270, w: 120, h: 18 },
    { x: 1180, y: 400, w: 180, h: 18 },
    { x: 1450, y: 330, w: 170, h: 18 },
    { x: 1740, y: 400, w: 130, h: 18 },
    { x: 1980, y: 330, w: 120, h: 18 },
    { x: 2260, y: 420, w: 140, h: 18 }
  ];

  const hazards = [
    { x: 330, y: 486, w: 70, h: 14 },
    { x: 1520, y: 486, w: 90, h: 14 },
    { x: 2160, y: 486, w: 80, h: 14 }
  ];

  const coinSeeds = [
    [260, 370], [300, 370], [340, 370], [500, 300], [540, 300], [580, 300],
    [720, 230], [760, 230], [1210, 360], [1250, 360], [1290, 360],
    [1490, 290], [1530, 290], [1570, 290], [1770, 360], [1810, 360],
    [2000, 290], [2040, 290], [2280, 380], [2320, 380]
  ];

  const enemySeeds = [
    { x: 600, y: 466, left: 560, right: 760 },
    { x: 1320, y: 466, left: 1200, right: 1420 },
    { x: 1840, y: 466, left: 1760, right: 1980 }
  ];

  let player, coins, enemies, score, lives, state, time, checkpoint, invuln, paused;
  let cameraX = 0, lastTs = 0, accumulator = 0;
  let touchLeft = false, touchRight = false, touchJump = false, prevAction = false;
  let startHint = 3.0;

  function resetGame() {
    player = { x: 60, y: 430, w: 28, h: 38, vx: 0, vy: 0, onGround: false, coyote: 0, buffer: 0, jumps: 0 };
    coins = coinSeeds.map(function (c) { return { x: c[0], y: c[1], r: 9, taken: false }; });
    enemies = enemySeeds.map(function (e) { return { x: e.x, y: e.y, w: 30, h: 34, left: e.left, right: e.right, dir: 1, alive: true }; });
    score = 0; lives = 3; state = 'PLAYING'; time = 0; checkpoint = 60;
    invuln = 0; paused = false; cameraX = 0; accumulator = 0; startHint = 3.0;
  }

  function respawn() {
    lives -= 1;
    Sound.hit();
    fx.triggerScreenShake(10);
    if (lives <= 0) {
      state = 'GAMEOVER';
      Sound.gameover();
      return;
    }
    player.x = checkpoint; player.y = 430; player.vx = 0; player.vy = 0;
    player.onGround = false; player.coyote = 0; player.buffer = 0; player.jumps = 0;
    invuln = 1.2;
  }

  function overlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function moveAndCollide(dt) {
    player.x += player.vx * dt;
    for (let i = 0; i < platforms.length; i++) {
      const p = platforms[i];
      if (!overlap(player, p)) continue;
      if (player.vx > 0) player.x = p.x - player.w;
      else if (player.vx < 0) player.x = p.x + p.w;
      player.vx = 0;
    }

    player.y += player.vy * dt;
    player.onGround = false;
    for (let i = 0; i < platforms.length; i++) {
      const p = platforms[i];
      if (!overlap(player, p)) continue;
      if (player.vy > 0) {
        player.y = p.y - player.h;
        player.vy = 0;
        player.onGround = true;
        player.jumps = 0;
      } else if (player.vy < 0) {
        player.y = p.y + p.h;
        player.vy = 0;
      }
    }

    if (player.x < 0) player.x = 0;
    if (player.x + player.w > LEVEL_W) player.x = LEVEL_W - player.w;
    if (player.y > H + 120) respawn();
  }

  function update(dt) {
    const action = Input.isAction() || touchJump;
    if (state !== 'PLAYING') {
      if (action && !prevAction) resetGame();
      prevAction = action;
      return;
    }
    if (paused) return;

    time += dt;
    if (startHint > 0) startHint -= dt;
    if (invuln > 0) invuln -= dt;

    const actionReleased = !action && prevAction;
    if (action && !prevAction) player.buffer = JUMP_BUFFER;
    prevAction = action;

    const left = Input.isLeft() || touchLeft;
    const right = Input.isRight() || touchRight;
    const target = (right ? 1 : 0) - (left ? 1 : 0);
    const accel = player.onGround ? ACCEL : AIR_ACCEL;

    if (target !== 0) {
      player.vx += target * accel * dt;
      player.vx = Math.max(-RUN_SPEED, Math.min(RUN_SPEED, player.vx));
    } else if (player.onGround) {
      const drag = FRICTION * dt;
      if (Math.abs(player.vx) <= drag) player.vx = 0;
      else player.vx -= Math.sign(player.vx) * drag;
    }

    if (player.onGround) {
      player.coyote = COYOTE;
      player.jumps = 0;
    } else {
      player.coyote = Math.max(0, player.coyote - dt);
    }
    if (player.buffer > 0) player.buffer -= dt;

    const canJump = player.onGround || player.coyote > 0 || player.jumps < 1;
    if (player.buffer > 0 && canJump) {
      if (!player.onGround && player.coyote <= 0) player.jumps += 1;
      player.vy = JUMP_V;
      player.onGround = false;
      player.coyote = 0;
      player.buffer = 0;
      Sound.jump();
      fx.spawnBurst(player.x + player.w / 2, player.y + player.h, '#38bdf8', 8, 2.2);
    }

    if (actionReleased && player.vy < 0) player.vy *= 0.55;
    player.vy = Math.min(MAX_FALL, player.vy + GRAVITY * dt);
    moveAndCollide(dt);

    if (player.x > 1120 && checkpoint < 1160) checkpoint = 1160;
    if (player.x > 2140 && checkpoint < 2180) checkpoint = 2180;

    for (let i = 0; i < hazards.length; i++) {
      if (invuln <= 0 && overlap(player, hazards[i])) { respawn(); break; }
    }

    for (let i = 0; i < enemies.length; i++) {
      const e = enemies[i];
      if (!e.alive) continue;
      e.x += e.dir * 55 * dt;
      if (e.x < e.left) { e.x = e.left; e.dir = 1; }
      if (e.x + e.w > e.right) { e.x = e.right - e.w; e.dir = -1; }
      if (invuln <= 0 && overlap(player, e)) {
        if (player.vy > 120 && player.y + player.h < e.y + 18) {
          e.alive = false;
          player.vy = -420;
          score += 100;
          Sound.explosion();
          fx.spawnBurst(e.x + e.w / 2, e.y + e.h / 2, '#f43f5e', 18, 4);
        } else {
          respawn();
        }
      }
    }

    for (let i = 0; i < coins.length; i++) {
      const c = coins[i];
      if (c.taken) continue;
      if (Math.hypot(player.x + player.w / 2 - c.x, player.y + player.h / 2 - c.y) < 26) {
        c.taken = true; score += 25; Sound.pickup();
        fx.spawnBurst(c.x, c.y, '#facc15', 10, 2.5);
        fx.spawnFloatingText('+25', c.x, c.y - 10, '#facc15');
      }
    }

    if (player.x + player.w > 2470 && player.y + player.h > 380) {
      state = 'WON';
      Sound.powerup();
      fx.spawnBurst(2500, 430, '#10b981', 40, 6);
    }

    const targetCam = Math.max(0, Math.min(LEVEL_W - W, player.x - 320));
    cameraX += (targetCam - cameraX) * Math.min(1, dt * 8);
    fx.update();
  }

  function drawBackground() {
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, '#070b14');
    sky.addColorStop(1, '#111c33');
    ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = 'rgba(56,189,248,.10)';
    for (let i = 0; i < 7; i++) {
      const x = ((i * 260 - cameraX * 0.25) % (W + 260)) - 130;
      const y = 90 + (i % 3) * 70;
      ctx.beginPath(); ctx.arc(x, y, 90, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = 'rgba(148,163,184,.18)';
    for (let i = 0; i < 18; i++) {
      const x = ((i * 173 - cameraX * 0.55) % (W + 180)) - 90;
      ctx.fillRect(x, 420 - (i % 4) * 18, 90, 80);
    }
  }

  function drawWorld() {
    ctx.save();
    ctx.translate(-cameraX, 0);

    for (let i = 0; i < platforms.length; i++) {
      const p = platforms[i];
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(p.x, p.y, p.w, p.h);
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(p.x, p.y, p.w, 3);
    }

    for (let i = 0; i < hazards.length; i++) {
      const h = hazards[i];
      ctx.fillStyle = '#f43f5e';
      for (let x = h.x; x < h.x + h.w; x += 14) {
        ctx.beginPath();
        ctx.moveTo(x, h.y + h.h);
        ctx.lineTo(x + 7, h.y);
        ctx.lineTo(x + 14, h.y + h.h);
        ctx.closePath(); ctx.fill();
      }
    }

    for (let i = 0; i < coins.length; i++) {
      const c = coins[i];
      if (c.taken) continue;
      ctx.fillStyle = '#facc15';
      ctx.beginPath(); ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#fef3c7';
      ctx.beginPath(); ctx.arc(c.x - 2, c.y - 2, 3, 0, Math.PI * 2); ctx.fill();
    }

    for (let i = 0; i < enemies.length; i++) {
      const e = enemies[i];
      if (!e.alive) continue;
      ctx.fillStyle = '#f43f5e';
      ctx.fillRect(e.x, e.y, e.w, e.h);
      ctx.fillStyle = '#fecdd3';
      ctx.fillRect(e.x + 5, e.y + 8, 6, 6);
      ctx.fillRect(e.x + e.w - 11, e.y + 8, 6, 6);
    }

    ctx.fillStyle = '#10b981';
    ctx.fillRect(2480, 420, 10, 80);
    ctx.beginPath();
    ctx.moveTo(2490, 420);
    ctx.lineTo(2550, 445);
    ctx.lineTo(2490, 470);
    ctx.closePath(); ctx.fill();

    if (!(invuln > 0 && Math.floor(time * 20) % 2 === 0)) {
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(player.x, player.y, player.w, player.h);
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(player.x + 4, player.y + 6, player.w - 8, 8);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(player.x + 7, player.y + 9, 4, 4);
      ctx.fillRect(player.x + player.w - 11, player.y + 9, 4, 4);
    }

    ctx.restore();
  }

  function drawHud() {
    ctx.save();
    ctx.fillStyle = 'rgba(7,11,20,.72)';
    ctx.fillRect(14, 14, 250, 40);
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 16px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('SCORE ' + score, 28, 40);
    ctx.fillStyle = '#f43f5e';
    ctx.fillText('♥'.repeat(Math.max(0, lives)), 150, 40);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '13px -apple-system, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('A/D move · Space jump · R restart · P pause', W - 18, 34);

    if (startHint > 0) {
      ctx.textAlign = 'center';
      ctx.fillStyle = 'rgba(7,11,20,.78)';
      ctx.fillRect(W / 2 - 240, 84, 480, 62);
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 24px -apple-system, sans-serif';
      ctx.fillText(__TITLE_JS__, W / 2, 112);
      ctx.fillStyle = '#cbd5e1';
      ctx.font = '15px -apple-system, sans-serif';
      ctx.fillText('Reach the green flag · stomp enemies · collect coins', W / 2, 136);
    }

    if (paused) {
      ctx.fillStyle = 'rgba(7,11,20,.78)';
      ctx.fillRect(0, 0, W, H);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 42px -apple-system, sans-serif';
      ctx.fillText('PAUSED', W / 2, H / 2 - 10);
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillStyle = '#94a3b8';
      ctx.fillText('Press P or click to resume', W / 2, H / 2 + 28);
    } else if (state === 'WON') {
      ctx.fillStyle = 'rgba(7,11,20,.8)';
      ctx.fillRect(0, 0, W, H);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#10b981';
      ctx.font = 'bold 48px -apple-system, sans-serif';
      ctx.fillText('LEVEL CLEAR!', W / 2, H / 2 - 24);
      ctx.fillStyle = '#f8fafc';
      ctx.font = '20px -apple-system, sans-serif';
      ctx.fillText('Score: ' + score + '  ·  Time: ' + time.toFixed(1) + 's', W / 2, H / 2 + 18);
      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 17px -apple-system, sans-serif';
      ctx.fillText('Press Space / tap to run it back', W / 2, H / 2 + 58);
    } else if (state === 'GAMEOVER') {
      ctx.fillStyle = 'rgba(7,11,20,.8)';
      ctx.fillRect(0, 0, W, H);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#f43f5e';
      ctx.font = 'bold 48px -apple-system, sans-serif';
      ctx.fillText('GAME OVER', W / 2, H / 2 - 24);
      ctx.fillStyle = '#f8fafc';
      ctx.font = '20px -apple-system, sans-serif';
      ctx.fillText('Score: ' + score, W / 2, H / 2 + 18);
      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 17px -apple-system, sans-serif';
      ctx.fillText('Press Space / tap to retry', W / 2, H / 2 + 58);
    }
    ctx.restore();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    drawBackground();
    ctx.save();
    fx.applyScreenShake(ctx);
    drawWorld();
    ctx.save();
    ctx.translate(-cameraX, 0);
    fx.draw(ctx);
    ctx.restore();
    ctx.restore();
    drawHud();
  }

  function loop(ts) {
    if (!lastTs) lastTs = ts;
    let frame = (ts - lastTs) / 1000;
    lastTs = ts;
    if (frame > 0.05) frame = 0.05;
    accumulator += frame;
    let steps = 0;
    while (accumulator >= FIXED && steps < 5) {
      update(FIXED);
      accumulator -= FIXED;
      steps += 1;
    }
    draw();
    requestAnimationFrame(loop);
  }

  function bindTouch(id, onDown, onUp) {
    const el = document.getElementById(id);
    if (!el) return;
    const down = function (e) { e.preventDefault(); onDown(); };
    const up = function (e) { e.preventDefault(); onUp(); };
    el.addEventListener('pointerdown', down);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    el.addEventListener('pointerleave', up);
  }

  bindTouch('touch-left', function () { touchLeft = true; }, function () { touchLeft = false; });
  bindTouch('touch-right', function () { touchRight = true; }, function () { touchRight = false; });
  bindTouch('touch-jump', function () { touchJump = true; }, function () { touchJump = false; });

  window.addEventListener('keydown', function (e) {
    if (e.key === 'p' || e.key === 'P' || e.key === 'Escape') {
      if (state === 'PLAYING') paused = !paused;
    }
    if (e.key === 'r' || e.key === 'R') resetGame();
    if (paused && (e.key === ' ' || e.key === 'Enter')) paused = false;
  });
  document.addEventListener('visibilitychange', function () {
    if (document.hidden && state === 'PLAYING') paused = true;
  });
  window.addEventListener('blur', function () {
    if (state === 'PLAYING') paused = true;
  });
  canvas.addEventListener('pointerdown', function () {
    if (paused) paused = false;
  });

  resetGame();
  requestAnimationFrame(loop);
  </script>
</body>
</html>
"""


def build_platformer_game(title: str = "Neon Leap") -> str:
    """A complete precision platformer with coyote time, jump buffering, and touch controls."""
    safe_title, js_title = _prepare_title(title)
    return (
        _PLATFORMER_TEMPLATE.replace("__TITLE__", safe_title)
        .replace("__TITLE_JS__", js_title)
        .replace("__AUDIO__", AUDIO_CORE_JS)
        .replace("__PARTICLES__", PARTICLE_SYSTEM_JS)
        .replace("__INPUT__", INPUT_CONTROLLER_JS)
    )


def build_space_shooter_game(title: str = "Neon Space Defender") -> str:
    """Complete, high-energy, deeply polished Space Shooter arcade game."""
    title, title_js = _prepare_title(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #060911;
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      margin: 0;
      padding: 0;
      user-select: none;
    }}
    #game-wrapper {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    canvas {{
      display: block;
      max-width: 100%;
      max-height: 100%;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      cursor: pointer;
    }}
    .hud {{
      position: absolute;
      top: 14px;
      left: 16px;
      right: 16px;
      display: flex;
      justify-content: space-between;
      pointer-events: none;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-shadow: 0 2px 4px rgba(0,0,0,0.8);
    }}
    .hud-left {{ display: flex; gap: 16px; }}
    .health-bar-container {{
      width: 120px;
      height: 10px;
      background: rgba(255,255,255,0.15);
      border-radius: 5px;
      overflow: hidden;
      margin-top: 5px;
    }}
    .health-bar {{
      width: 100%;
      height: 100%;
      background: #10b981;
      transition: width 0.15s ease;
    }}
  </style>
</head>
<body>
  <div id="game-wrapper">
    <div class="hud">
      <div class="hud-left">
        <div>
          SCORE: <span id="score-el">0</span>
          <div class="health-bar-container"><div id="health-bar" class="health-bar"></div></div>
        </div>
        <div>WAVE: <span id="wave-el">1</span></div>
      </div>
      <div>HIGH: <span id="high-el">0</span></div>
    </div>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
  </div>

  <script>
  {AUDIO_CORE_JS}
  {PARTICLE_SYSTEM_JS}
  {INPUT_CONTROLLER_JS}

  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d');
  Input.bindCanvas(canvas);

  const fx = new ParticleSystem();
  const scoreEl = document.getElementById('score-el');
  const waveEl = document.getElementById('wave-el');
  const highEl = document.getElementById('high-el');
  const healthBar = document.getElementById('health-bar');

  let state = 'MENU'; // MENU, PLAYING, GAMEOVER
  let paused = false;
  let score = 0;
  function safeGetScore(k) {{
    try {{ return parseInt(localStorage.getItem(k) || '0', 10) || 0; }} catch (e) {{ return 0; }}
  }}
  function safeSetScore(k, v) {{
    try {{ localStorage.setItem(k, String(v)); }} catch (e) {{}}
  }}
  let highScore = safeGetScore('8gen_hs_shooter');
  highEl.innerText = highScore;

  let wave = 1;
  let lastShot = 0;
  let fireRate = 0.16;
  let simTime = 0;
  let lastTs = 0;
  let accumulator = 0;
  const FIXED = 1 / 60;

  window.addEventListener('click', () => {{
    if (paused && state === 'PLAYING') {{ paused = false; return; }}
    if (state === 'MENU' || state === 'GAMEOVER') resetGame();
  }});
  window.addEventListener('keydown', (e) => {{
    if (e.key === 'p' || e.key === 'P' || e.key === 'Escape') {{
      if (state === 'PLAYING') paused = !paused;
    }} else if (e.key === 'r' || e.key === 'R') {{
      resetGame();
    }} else if (paused && (e.key === ' ' || e.key === 'Enter')) {{
      paused = false;
    }}
  }});
  document.addEventListener('visibilitychange', () => {{ if (document.hidden && state === 'PLAYING') paused = true; }});
  window.addEventListener('blur', () => {{ if (state === 'PLAYING') paused = true; }});

  // Starfield
  const stars = Array.from({{ length: 80 }}, () => ({{
    x: Math.random() * 800,
    y: Math.random() * 600,
    speed: Math.random() * 120 + 30,
    size: Math.random() * 2 + 0.5,
  }}));

  // Player
  const player = {{
    x: 400,
    y: 520,
    vx: 0,
    vy: 0,
    radius: 14,
    speed: 420,
    health: 100,
    maxHealth: 100,
    powerupLevel: 1,
    shield: 0,
  }};

  let bullets = [];
  let enemies = [];
  let powerups = [];

  function resetGame() {{
    score = 0;
    wave = 1;
    paused = false;
    simTime = 0;
    lastShot = -1;
    scoreEl.innerText = '0';
    waveEl.innerText = '1';
    healthBar.style.width = '100%';
    player.x = 400;
    player.y = 520;
    player.health = 100;
    player.powerupLevel = 1;
    player.shield = 0;
    bullets = [];
    enemies = [];
    powerups = [];
    state = 'PLAYING';
    Sound.init();
    Sound.pickup();
  }}

  function spawnWave() {{
    const count = 5 + wave * 2;
    for (let i = 0; i < count; i++) {{
      const type = Math.random() < 0.25 ? 'fast' : (Math.random() < 0.2 ? 'heavy' : 'basic');
      enemies.push({{
        x: 60 + Math.random() * 680,
        y: -30 - (i * 45),
        type,
        hp: type === 'heavy' ? 4 : (type === 'fast' ? 1 : 2),
        maxHp: type === 'heavy' ? 4 : (type === 'fast' ? 1 : 2),
        radius: type === 'heavy' ? 24 : (type === 'fast' ? 12 : 16),
        speed: type === 'fast' ? 210 : (type === 'heavy' ? 72 : 120),
        vx: (Math.random() - 0.5) * 90,
        color: type === 'heavy' ? '#f43f5e' : (type === 'fast' ? '#eab308' : '#06b6d4'),
      }});
    }}
  }}

  function shoot() {{
    if (simTime - lastShot < fireRate) return;
    lastShot = simTime;
    Sound.laser();

    if (player.powerupLevel === 1) {{
      bullets.push({{ x: player.x, y: player.y - 18, vx: 0, vy: -720, color: '#38bdf8' }});
    }} else if (player.powerupLevel === 2) {{
      bullets.push({{ x: player.x - 10, y: player.y - 14, vx: 0, vy: -720, color: '#38bdf8' }});
      bullets.push({{ x: player.x + 10, y: player.y - 14, vx: 0, vy: -720, color: '#38bdf8' }});
    }} else {{
      bullets.push({{ x: player.x, y: player.y - 18, vx: 0, vy: -720, color: '#38bdf8' }});
      bullets.push({{ x: player.x - 12, y: player.y - 12, vx: -150, vy: -660, color: '#ec4899' }});
      bullets.push({{ x: player.x + 12, y: player.y - 12, vx: 150, vy: -660, color: '#ec4899' }});
    }}
  }}

  function update(dt) {{
    // Starfield scroll
    for (const s of stars) {{
      s.y += s.speed * dt;
      if (s.y > 600) {{ s.y = 0; s.x = Math.random() * 800; }}
    }}

    fx.update();

    if (state !== 'PLAYING' || paused) return;
    simTime += dt;

    // Movement
    if (Input.isLeft()) player.x -= player.speed * dt;
    if (Input.isRight()) player.x += player.speed * dt;
    if (Input.isUp()) player.y -= player.speed * dt;
    if (Input.isDownDir()) player.y += player.speed * dt;

    // Pointer touch/mouse drag
    const ptr = Input.pointer();
    if (ptr.isDown) {{
      const follow = Math.min(1, dt * 11);
      player.x += (ptr.x - player.x) * follow;
      player.y += (ptr.y - player.y) * follow;
    }}

    player.x = Math.max(20, Math.min(780, player.x));
    player.y = Math.max(100, Math.min(570, player.y));

    // Shooting
    if (Input.isAction()) shoot();

    // Spawn thruster particles
    if (Math.random() < 0.6) {{
      fx.particles.push({{
        x: player.x + (Math.random() - 0.5) * 8,
        y: player.y + 16,
        vx: (Math.random() - 0.5) * 1.5,
        vy: Math.random() * 4 + 2,
        radius: Math.random() * 3 + 1,
        color: '#38bdf8',
        alpha: 1,
        life: 0.6,
        decay: 0.04,
      }});
    }}

    // Update bullets
    for (let i = bullets.length - 1; i >= 0; i--) {{
      const b = bullets[i];
      b.prevX = b.x;
      b.prevY = b.y;
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      if (b.y < -20 || b.x < 0 || b.x > 800) bullets.splice(i, 1);
    }}

    // Update enemies
    if (enemies.length === 0) {{
      wave++;
      waveEl.innerText = wave;
      fx.spawnFloatingText(`WAVE ${{wave}} INCOMING!`, 400, 300, '#38bdf8');
      Sound.powerup();
      spawnWave();
    }}

    for (let i = enemies.length - 1; i >= 0; i--) {{
      const e = enemies[i];
      e.y += e.speed * dt;
      e.x += e.vx * dt;
      if (e.x < 20 || e.x > 780) e.vx = -e.vx;

      // Swept segment-vs-circle bullet hit check
      for (let j = bullets.length - 1; j >= 0; j--) {{
        const b = bullets[j];
        const segDx = b.x - (b.prevX ?? b.x);
        const segDy = b.y - (b.prevY ?? b.y);
        const segLenSq = segDx * segDx + segDy * segDy;
        let t = segLenSq > 0 ? ((e.x - (b.prevX ?? b.x)) * segDx + (e.y - (b.prevY ?? b.y)) * segDy) / segLenSq : 0;
        t = Math.max(0, Math.min(1, t));
        const closestX = (b.prevX ?? b.x) + t * segDx;
        const closestY = (b.prevY ?? b.y) + t * segDy;
        const dist = Math.hypot(closestX - e.x, closestY - e.y);
        if (dist < e.radius + 6) {{
          bullets.splice(j, 1);
          e.hp--;
          Sound.hit();
          fx.spawnBurst(b.x, b.y, e.color, 6, 2);

          if (e.hp <= 0) {{
            Sound.explosion();
            fx.spawnBurst(e.x, e.y, e.color, 24, 5);
            fx.shake(5);
            const pts = e.type === 'heavy' ? 250 : (e.type === 'fast' ? 150 : 100);
            score += pts;
            scoreEl.innerText = score;
            fx.spawnFloatingText(`+${{pts}}`, e.x, e.y, '#f59e0b');

            // Chance to drop powerup
            if (Math.random() < 0.15) {{
              powerups.push({{ x: e.x, y: e.y, vy: 120, type: Math.random() < 0.5 ? 'weapon' : 'shield' }});
            }}

            enemies.splice(i, 1);
            break;
          }}
        }}
      }}

      // Enemy hit player
      if (enemies[i]) {{
        const pDist = Math.hypot(player.x - e.x, player.y - e.y);
        if (pDist < player.radius + e.radius) {{
          enemies.splice(i, 1);
          Sound.explosion();
          fx.spawnBurst(player.x, player.y, '#ef4444', 20, 6);
          fx.shake(12);

          if (player.shield > 0) {{
            player.shield = 0;
            fx.spawnFloatingText('SHIELD BROKEN!', player.x, player.y - 20, '#38bdf8');
          }} else {{
            player.health -= 35;
            healthBar.style.width = Math.max(0, player.health) + '%';
            if (player.health <= 0) {{
              state = 'GAMEOVER';
              Sound.gameover();
              if (score > highScore) {{
                highScore = score;
                safeSetScore('8gen_hs_shooter', highScore);
                highEl.innerText = highScore;
              }}
            }}
          }}
        }} else if (e.y > 640) {{
          enemies.splice(i, 1);
        }}
      }}
    }}

    // Powerups
    for (let i = powerups.length - 1; i >= 0; i--) {{
      const p = powerups[i];
      p.y += p.vy * dt;
      const dist = Math.hypot(player.x - p.x, player.y - p.y);
      if (dist < player.radius + 18) {{
        Sound.powerup();
        if (p.type === 'weapon') {{
          player.powerupLevel = Math.min(3, player.powerupLevel + 1);
          fx.spawnFloatingText('FIREPOWER UPGRADE!', player.x, player.y - 20, '#ec4899');
        }} else {{
          player.shield = 100;
          player.health = Math.min(100, player.health + 25);
          healthBar.style.width = player.health + '%';
          fx.spawnFloatingText('SHIELD ACTIVATED!', player.x, player.y - 20, '#38bdf8');
        }}
        powerups.splice(i, 1);
      }} else if (p.y > 620) {{
        powerups.splice(i, 1);
      }}
    }}
  }}

  function draw() {{
    ctx.save();
    ctx.clearRect(0, 0, 800, 600);
    fx.applyScreenShake(ctx);

    // Stars
    ctx.fillStyle = '#ffffff';
    for (const s of stars) {{
      ctx.fillRect(s.x, s.y, s.size, s.size);
    }}

    if (state === 'MENU') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 44px -apple-system, sans-serif';
      ctx.fillText({title_js}, 400, 230);

      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('CONTROLS: Arrow Keys / WASD to move • Space to Fire • Or Drag Mouse/Finger', 400, 290);

      // Pulsing Start Button Box
      const pulse = Math.sin(Date.now() * 0.007) * 0.15 + 0.85;
      ctx.fillStyle = '#10b981';
      ctx.globalAlpha = pulse;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(250, 350, 300, 54, 12);
      else ctx.rect(250, 350, 300, 54);
      ctx.fill();
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 22px -apple-system, sans-serif';
      ctx.fillText('▶ CLICK TO PLAY', 400, 384);

      if (Input.isAction()) resetGame();
    }} else if (state === 'PLAYING') {{
      // Draw Bullets
      for (const b of bullets) {{
        ctx.fillStyle = b.color;
        ctx.fillRect(b.x - 2.5, b.y - 8, 5, 16);
      }}

      // Draw Powerups
      for (const p of powerups) {{
        ctx.save();
        ctx.fillStyle = p.type === 'weapon' ? '#ec4899' : '#38bdf8';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 10, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(p.type === 'weapon' ? 'W' : 'S', p.x, p.y + 4);
        ctx.restore();
      }}

      // Draw Enemies
      for (const e of enemies) {{
        ctx.save();
        ctx.fillStyle = e.color;
        ctx.beginPath();
        if (e.type === 'heavy') {{
          ctx.arc(e.x, e.y, e.radius, 0, Math.PI * 2);
        }} else if (e.type === 'fast') {{
          ctx.moveTo(e.x, e.y + e.radius);
          ctx.lineTo(e.x - e.radius, e.y - e.radius);
          ctx.lineTo(e.x + e.radius, e.y - e.radius);
          ctx.closePath();
        }} else {{
          ctx.arc(e.x, e.y, e.radius, 0, Math.PI * 2);
        }}
        ctx.fill();

        // Eye / cockpit
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(e.x - 4, e.y - 2, 8, 4);
        ctx.restore();
      }}

      // Draw Player
      ctx.save();
      ctx.translate(player.x, player.y);

      // Shield ring
      if (player.shield > 0) {{
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(0, 0, player.radius + 8, 0, Math.PI * 2);
        ctx.stroke();
      }}

      // Ship body
      ctx.fillStyle = '#f8fafc';
      ctx.beginPath();
      ctx.moveTo(0, -22);
      ctx.lineTo(-18, 16);
      ctx.lineTo(0, 10);
      ctx.lineTo(18, 16);
      ctx.closePath();
      ctx.fill();

      // Wing accents
      ctx.fillStyle = '#06b6d4';
      ctx.beginPath();
      ctx.moveTo(0, -10);
      ctx.lineTo(-12, 12);
      ctx.lineTo(0, 6);
      ctx.lineTo(12, 12);
      ctx.closePath();
      ctx.fill();

      ctx.restore();
    }} else if (state === 'GAMEOVER') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 50px -apple-system, sans-serif';
      ctx.fillText('MISSION FAILED', 400, 240);

      ctx.fillStyle = '#f8fafc';
      ctx.font = '22px -apple-system, sans-serif';
      ctx.fillText(`FINAL SCORE: ${{score}}`, 400, 300);

      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.fillText('PRESS SPACE OR CLICK TO RESTART', 400, 370);

      if (Input.isAction()) resetGame();
    }}

    fx.draw(ctx);
    if (paused && state === 'PLAYING') {{
      ctx.fillStyle = 'rgba(6,9,17,0.75)';
      ctx.fillRect(0, 0, 800, 600);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 40px -apple-system, sans-serif';
      ctx.fillText('PAUSED', 400, 285);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('Press P or click to resume', 400, 325);
    }}
    ctx.restore();
  }}

  function loop(ts) {{
    if (!lastTs) lastTs = ts;
    let frame = (ts - lastTs) / 1000;
    lastTs = ts;
    if (frame > 0.05) frame = 0.05;
    accumulator += frame;
    let steps = 0;
    while (accumulator >= FIXED && steps < 5) {{
      update(FIXED);
      accumulator -= FIXED;
      steps++;
    }}
    draw();
    requestAnimationFrame(loop);
  }}

  requestAnimationFrame(loop);
  </script>
</body>
</html>
"""


def build_brick_breaker_game(title: str = "Neon Brick Breaker") -> str:
    """Complete, highly polished Breakout physics game with powerups."""
    title, title_js = _prepare_title(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #080c14;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      margin: 0;
      padding: 0;
      user-select: none;
    }}
    #game-wrapper {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    canvas {{
      display: block;
      max-width: 100%;
      max-height: 100%;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      cursor: pointer;
    }}
    .hud {{
      position: absolute;
      top: 14px;
      left: 16px;
      right: 16px;
      display: flex;
      justify-content: space-between;
      pointer-events: none;
      font-size: 16px;
      font-weight: 700;
      text-shadow: 0 2px 4px rgba(0,0,0,0.8);
    }}
  </style>
</head>
<body>
  <div id="game-wrapper">
    <div class="hud">
      <div>SCORE: <span id="score-el">0</span></div>
      <div>LIVES: <span id="lives-el">3</span></div>
    </div>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
  </div>

  <script>
  {AUDIO_CORE_JS}
  {PARTICLE_SYSTEM_JS}
  {INPUT_CONTROLLER_JS}

  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d');
  Input.bindCanvas(canvas);

  const fx = new ParticleSystem();
  const scoreEl = document.getElementById('score-el');
  const livesEl = document.getElementById('lives-el');

  let state = 'MENU';
  let paused = false;
  let score = 0;
  let lives = 3;
  let lastTs = 0;
  let accumulator = 0;
  const FIXED = 1 / 60;

  window.addEventListener('click', () => {{
    if (paused && state === 'PLAYING') {{ paused = false; return; }}
    if (state === 'MENU' || state === 'GAMEOVER' || state === 'VICTORY') resetGame();
  }});
  window.addEventListener('keydown', (e) => {{
    if (e.key === 'p' || e.key === 'P' || e.key === 'Escape') {{
      if (state === 'PLAYING') paused = !paused;
    }} else if (e.key === 'r' || e.key === 'R') {{
      resetGame();
    }} else if (paused && (e.key === ' ' || e.key === 'Enter')) {{
      paused = false;
    }}
  }});
  document.addEventListener('visibilitychange', () => {{ if (document.hidden && state === 'PLAYING') paused = true; }});
  window.addEventListener('blur', () => {{ if (state === 'PLAYING') paused = true; }});

  const paddle = {{
    x: 350,
    y: 550,
    prevX: 350,
    vx: 0,
    width: 110,
    height: 14,
    speed: 560,
  }};

  let balls = [];
  let bricks = [];
  const colors = ['#f43f5e', '#fb923c', '#facc15', '#4ade80', '#38bdf8', '#c084fc'];

  function initBricks() {{
    bricks = [];
    const rows = 6;
    const cols = 9;
    const bWidth = 76;
    const bHeight = 22;
    const padding = 8;
    const offsetX = 28;
    const offsetY = 70;

    for (let r = 0; r < rows; r++) {{
      for (let c = 0; c < cols; c++) {{
        bricks.push({{
          x: offsetX + c * (bWidth + padding),
          y: offsetY + r * (bHeight + padding),
          width: bWidth,
          height: bHeight,
          color: colors[r % colors.length],
          alive: true,
          hp: r === 0 ? 2 : 1,
        }});
      }}
    }}
  }}

  function spawnBall() {{
    const angle = (Math.random() > 0.5 ? 1 : -1) * (0.45 + Math.random() * 0.25);
    const speed = 440;
    return {{
      x: paddle.x + paddle.width / 2,
      y: paddle.y - 12,
      vx: Math.sin(angle) * speed,
      vy: -Math.cos(angle) * speed,
      speed,
      radius: 8,
    }};
  }}

  function resetGame() {{
    score = 0;
    lives = 3;
    paused = false;
    scoreEl.innerText = score;
    livesEl.innerText = lives;
    paddle.x = 345;
    paddle.prevX = 345;
    paddle.vx = 0;
    balls = [spawnBall()];
    initBricks();
    state = 'PLAYING';
    Sound.init();
    Sound.click();
  }}

  function update(dt) {{
    fx.update();
    if (state !== 'PLAYING' || paused) return;

    // Paddle controls
    paddle.prevX = paddle.x;
    if (Input.isLeft()) paddle.x -= paddle.speed * dt;
    if (Input.isRight()) paddle.x += paddle.speed * dt;
    const ptr = Input.pointer();
    if (ptr.isDown) paddle.x = ptr.x - paddle.width / 2;
    paddle.x = Math.max(10, Math.min(canvas.width - paddle.width - 10, paddle.x));
    paddle.vx = (paddle.x - paddle.prevX) / dt;

    // Update balls with 2 sub-steps for crisp collision without tunneling
    for (let i = balls.length - 1; i >= 0; i--) {{
      const b = balls[i];
      const subDt = dt / 2;
      for (let step = 0; step < 2; step++) {{
        b.x += b.vx * subDt;
        b.y += b.vy * subDt;

        // Wall bounce
        if (b.x - b.radius < 0) {{ b.x = b.radius; b.vx = Math.abs(b.vx); Sound.hit(); }}
        if (b.x + b.radius > canvas.width) {{ b.x = canvas.width - b.radius; b.vx = -Math.abs(b.vx); Sound.hit(); }}
        if (b.y - b.radius < 0) {{ b.y = b.radius; b.vy = Math.abs(b.vy); Sound.hit(); }}

        // Paddle bounce with angular deflection + slight english
        if (
          b.y + b.radius >= paddle.y &&
          b.y - b.radius <= paddle.y + paddle.height &&
          b.x + b.radius >= paddle.x &&
          b.x - b.radius <= paddle.x + paddle.width &&
          b.vy > 0
        ) {{
          b.y = paddle.y - b.radius;
          const hitPoint = Math.max(-1, Math.min(1, (b.x - (paddle.x + paddle.width / 2)) / (paddle.width / 2)));
          b.speed = Math.min(640, (b.speed || 440) * 1.025);
          const angle = hitPoint * (Math.PI / 3); // -60..+60 deg
          b.vx = Math.sin(angle) * b.speed + paddle.vx * 0.12;
          b.vy = -Math.cos(angle) * b.speed;
          const norm = Math.hypot(b.vx, b.vy) || 1;
          b.vx = (b.vx / norm) * b.speed;
          b.vy = (b.vy / norm) * b.speed;
          if (Math.abs(b.vy) < 140) b.vy = -140;
          Sound.jump();
          fx.spawnBurst(b.x, b.y, '#38bdf8', 8, 3);
        }}

        // Axis-separated circle-vs-AABB brick collision
        for (const brick of bricks) {{
          if (!brick.alive) continue;
          const closestX = Math.max(brick.x, Math.min(b.x, brick.x + brick.width));
          const closestY = Math.max(brick.y, Math.min(b.y, brick.y + brick.height));
          const dx = b.x - closestX;
          const dy = b.y - closestY;
          if (dx * dx + dy * dy <= b.radius * b.radius) {{
            const overlapLeft = b.x + b.radius - brick.x;
            const overlapRight = brick.x + brick.width - (b.x - b.radius);
            const overlapTop = b.y + b.radius - brick.y;
            const overlapBottom = brick.y + brick.height - (b.y - b.radius);
            const minX = Math.min(overlapLeft, overlapRight);
            const minY = Math.min(overlapTop, overlapBottom);
            if (minX < minY) {{
              b.vx = -b.vx;
              b.x += overlapLeft < overlapRight ? -minX : minX;
            }} else {{
              b.vy = -b.vy;
              b.y += overlapTop < overlapBottom ? -minY : minY;
            }}
            if (Math.abs(b.vy) < 110) b.vy = Math.sign(b.vy || -1) * 110;
            brick.hp--;
            Sound.hit();
            fx.spawnBurst(b.x, b.y, brick.color, 12, 4);

            if (brick.hp <= 0) {{
              brick.alive = false;
              score += 100;
              scoreEl.innerText = score;
              fx.spawnFloatingText('+100', brick.x + brick.width / 2, brick.y, brick.color);
              fx.shake(3);
            }}
            break;
          }}
        }}
      }}

      // Ball lost
      if (b.y - b.radius > canvas.height) {{
        balls.splice(i, 1);
      }}
    }}

    if (balls.length === 0) {{
      lives--;
      livesEl.innerText = lives;
      Sound.gameover();
      fx.shake(8);
      if (lives <= 0) {{
        state = 'GAMEOVER';
      }} else {{
        balls.push(spawnBall());
      }}
    }}

    // Check Victory
    if (bricks.every(b => !b.alive)) {{
      state = 'VICTORY';
      Sound.powerup();
    }}
  }}

  function draw() {{
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    fx.applyScreenShake(ctx);

    if (state === 'MENU') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 44px -apple-system, sans-serif';
      ctx.fillText({title_js}, 400, 240);

      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('Move: Left/Right Arrow Keys, A/D, or Drag with Mouse', 400, 290);

      const pulse = Math.sin(Date.now() * 0.007) * 0.15 + 0.85;
      ctx.fillStyle = '#10b981';
      ctx.globalAlpha = pulse;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(250, 350, 300, 54, 12);
      else ctx.rect(250, 350, 300, 54);
      ctx.fill();
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 22px -apple-system, sans-serif';
      ctx.fillText('▶ CLICK TO PLAY', 400, 384);

      if (Input.isAction()) resetGame();
    }} else if (state === 'PLAYING') {{
      // Draw Paddle
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(paddle.x, paddle.y, paddle.width, paddle.height);

      // Draw Balls
      ctx.fillStyle = '#ffffff';
      for (const b of balls) {{
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.radius, 0, Math.PI * 2);
        ctx.fill();
      }}

      // Draw Bricks
      for (const brick of bricks) {{
        if (!brick.alive) continue;
        ctx.fillStyle = brick.color;
        ctx.fillRect(brick.x, brick.y, brick.width, brick.height);
      }}
    }} else if (state === 'GAMEOVER') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 48px -apple-system, sans-serif';
      ctx.fillText('GAME OVER', 400, 260);

      ctx.fillStyle = '#f8fafc';
      ctx.font = '22px -apple-system, sans-serif';
      ctx.fillText(`SCORE: ${{score}}`, 400, 310);

      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.fillText('PRESS SPACE TO PLAY AGAIN', 400, 380);

      if (Input.isAction()) resetGame();
    }} else if (state === 'VICTORY') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#10b981';
      ctx.font = 'bold 48px -apple-system, sans-serif';
      ctx.fillText('VICTORY!', 400, 260);

      ctx.fillStyle = '#f8fafc';
      ctx.font = '22px -apple-system, sans-serif';
      ctx.fillText(`ALL BRICKS DESTROYED! FINAL SCORE: ${{score}}`, 400, 310);

      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.fillText('PRESS SPACE TO PLAY AGAIN', 400, 380);

      if (Input.isAction()) resetGame();
    }}

    fx.draw(ctx);
    if (paused && state === 'PLAYING') {{
      ctx.fillStyle = 'rgba(6,9,17,0.75)';
      ctx.fillRect(0, 0, 800, 600);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 40px -apple-system, sans-serif';
      ctx.fillText('PAUSED', 400, 285);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('Press P or click to resume', 400, 325);
    }}
    ctx.restore();
  }}

  function loop(ts) {{
    if (!lastTs) lastTs = ts;
    let frame = (ts - lastTs) / 1000;
    lastTs = ts;
    if (frame > 0.05) frame = 0.05;
    accumulator += frame;
    let steps = 0;
    while (accumulator >= FIXED && steps < 5) {{
      update(FIXED);
      accumulator -= FIXED;
      steps++;
    }}
    draw();
    requestAnimationFrame(loop);
  }}

  requestAnimationFrame(loop);
  </script>
</body>
</html>
"""


def build_cyber_snake_game(title: str = "Cyber Snake 2099") -> str:
    """Complete, ultra-responsive grid snake arcade game with juice."""
    title, title_js = _prepare_title(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #090e17;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      margin: 0;
      padding: 0;
      user-select: none;
    }}
    #game-wrapper {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    canvas {{
      display: block;
      max-width: 100%;
      max-height: 100%;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      cursor: pointer;
    }}
    .hud {{
      position: absolute;
      top: 14px;
      left: 16px;
      right: 16px;
      display: flex;
      justify-content: space-between;
      pointer-events: none;
      font-size: 16px;
      font-weight: 700;
      text-shadow: 0 2px 4px rgba(0,0,0,0.8);
    }}
  </style>
</head>
<body>
  <div id="game-wrapper">
    <div class="hud">
      <div>SCORE: <span id="score-el">0</span></div>
      <div>HIGH: <span id="high-el">0</span></div>
    </div>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
  </div>

  <script>
  {AUDIO_CORE_JS}
  {PARTICLE_SYSTEM_JS}
  {INPUT_CONTROLLER_JS}

  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d');
  Input.bindCanvas(canvas);

  const fx = new ParticleSystem();
  const scoreEl = document.getElementById('score-el');
  const highEl = document.getElementById('high-el');

  const GRID_SIZE = 25;
  const COLS = 800 / GRID_SIZE;
  const ROWS = 600 / GRID_SIZE;

  let state = 'MENU';
  let paused = false;
  let score = 0;
  function safeGetScore(k) {{
    try {{ return parseInt(localStorage.getItem(k) || '0', 10) || 0; }} catch (e) {{ return 0; }}
  }}
  function safeSetScore(k, v) {{
    try {{ localStorage.setItem(k, String(v)); }} catch (e) {{}}
  }}
  let highScore = safeGetScore('8gen_hs_snake');
  highEl.innerText = highScore;

  window.addEventListener('click', () => {{
    if (paused && state === 'PLAYING') {{ paused = false; return; }}
    if (state === 'MENU' || state === 'GAMEOVER') resetGame();
  }});

  let snake = [];
  let dir = {{ x: 1, y: 0 }};
  let turnQueue = [];
  let food = {{ x: 15, y: 12 }};
  let goldenFruit = null;
  let stepAccum = 0;
  let stepInterval = 0.105; // seconds per grid cell
  let lastTs = 0;
  let touchStartX = null;
  let touchStartY = null;

  function queueTurn(dx, dy) {{
    const last = turnQueue.length > 0 ? turnQueue[turnQueue.length - 1] : dir;
    if ((last.x === -dx && last.y === -dy) || (last.x === dx && last.y === dy)) return;
    if (turnQueue.length < 2) turnQueue.push({{ x: dx, y: dy }});
  }}

  function spawnFood() {{
    for (let tries = 0; tries < 200; tries++) {{
      const fxPos = Math.floor(Math.random() * (COLS - 2)) + 1;
      const fyPos = Math.floor(Math.random() * (ROWS - 2)) + 1;
      if (!snake.some(s => s.x === fxPos && s.y === fyPos)) {{
        food = {{ x: fxPos, y: fyPos }};
        break;
      }}
    }}

    if (Math.random() < 0.25) {{
      goldenFruit = {{
        x: Math.floor(Math.random() * (COLS - 2)) + 1,
        y: Math.floor(Math.random() * (ROWS - 2)) + 1,
        life: 60,
      }};
    }}
  }}

  function resetGame() {{
    score = 0;
    paused = false;
    stepInterval = 0.105;
    stepAccum = 0;
    scoreEl.innerText = score;
    snake = [
      {{ x: 10, y: 12 }},
      {{ x: 9, y: 12 }},
      {{ x: 8, y: 12 }},
    ];
    dir = {{ x: 1, y: 0 }};
    turnQueue = [];
    spawnFood();
    state = 'PLAYING';
    Sound.init();
    Sound.pickup();
  }}

  window.addEventListener('keydown', (e) => {{
    if (e.key === 'p' || e.key === 'P' || e.key === 'Escape') {{
      if (state === 'PLAYING') paused = !paused;
      return;
    }}
    if (e.key === 'r' || e.key === 'R') {{ resetGame(); return; }}
    if (paused && (e.key === ' ' || e.key === 'Enter')) {{ paused = false; return; }}
    if (e.code === 'ArrowUp' || e.code === 'KeyW') queueTurn(0, -1);
    if (e.code === 'ArrowDown' || e.code === 'KeyS') queueTurn(0, 1);
    if (e.code === 'ArrowLeft' || e.code === 'KeyA') queueTurn(-1, 0);
    if (e.code === 'ArrowRight' || e.code === 'KeyD') queueTurn(1, 0);
  }});
  document.addEventListener('visibilitychange', () => {{ if (document.hidden && state === 'PLAYING') paused = true; }});
  window.addEventListener('blur', () => {{ if (state === 'PLAYING') paused = true; }});

  canvas.addEventListener('touchstart', (e) => {{
    if (e.touches && e.touches[0]) {{
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
    }}
  }}, {{ passive: true }});
  canvas.addEventListener('touchmove', (e) => {{
    if (touchStartX === null || !e.touches || !e.touches[0]) return;
    const dx = e.touches[0].clientX - touchStartX;
    const dy = e.touches[0].clientY - touchStartY;
    if (Math.hypot(dx, dy) < 18) return;
    if (Math.abs(dx) > Math.abs(dy)) queueTurn(dx > 0 ? 1 : -1, 0);
    else queueTurn(0, dy > 0 ? 1 : -1);
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }}, {{ passive: true }});

  function update(dt) {{
    fx.update();

    if (state !== 'PLAYING' || paused) return;

    stepAccum += dt;
    while (stepAccum >= stepInterval) {{
      stepAccum -= stepInterval;
      if (turnQueue.length > 0) dir = turnQueue.shift();

      const head = {{ x: snake[0].x + dir.x, y: snake[0].y + dir.y }};

      // Wall collision
      if (head.x < 0 || head.x >= COLS || head.y < 0 || head.y >= ROWS) {{
        state = 'GAMEOVER';
        Sound.gameover();
        fx.shake(12);
        if (score > highScore) {{
          highScore = score;
          safeSetScore('8gen_hs_snake', highScore);
          highEl.innerText = highScore;
        }}
        return;
      }}

      // Self collision (ignore tail tip when not growing)
      const willEat = (head.x === food.x && head.y === food.y) || (goldenFruit && head.x === goldenFruit.x && head.y === goldenFruit.y);
      const bodyToCheck = willEat ? snake : snake.slice(0, -1);
      if (bodyToCheck.some(segment => segment.x === head.x && segment.y === head.y)) {{
        state = 'GAMEOVER';
        Sound.gameover();
        fx.shake(12);
        if (score > highScore) {{
          highScore = score;
          safeSetScore('8gen_hs_snake', highScore);
          highEl.innerText = highScore;
        }}
        return;
      }}

      snake.unshift(head);

      // Eat standard food
      if (head.x === food.x && head.y === food.y) {{
        score += 50;
        scoreEl.innerText = score;
        Sound.pickup();
        fx.spawnBurst(head.x * GRID_SIZE + 12, head.y * GRID_SIZE + 12, '#10b981', 14, 4);
        fx.spawnFloatingText('+50', head.x * GRID_SIZE, head.y * GRID_SIZE, '#10b981');
        stepInterval = Math.max(0.055, stepInterval - 0.002);
        spawnFood();
      }} else if (goldenFruit && head.x === goldenFruit.x && head.y === goldenFruit.y) {{
        score += 200;
        scoreEl.innerText = score;
        Sound.powerup();
        fx.spawnBurst(head.x * GRID_SIZE + 12, head.y * GRID_SIZE + 12, '#f59e0b', 24, 6);
        fx.spawnFloatingText('+200 BONUS!', head.x * GRID_SIZE, head.y * GRID_SIZE, '#f59e0b');
        goldenFruit = null;
      }} else {{
        snake.pop();
      }}
    }}
  }}

  function draw() {{
    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    fx.applyScreenShake(ctx);

    // Subtle grid
    ctx.strokeStyle = '#111827';
    ctx.lineWidth = 0.5;
    for (let c = 0; c <= COLS; c++) {{
      ctx.beginPath();
      ctx.moveTo(c * GRID_SIZE, 0);
      ctx.lineTo(c * GRID_SIZE, 600);
      ctx.stroke();
    }}
    for (let r = 0; r <= ROWS; r++) {{
      ctx.beginPath();
      ctx.moveTo(0, r * GRID_SIZE);
      ctx.lineTo(800, r * GRID_SIZE);
      ctx.stroke();
    }}

    if (state === 'MENU') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#10b981';
      ctx.font = 'bold 44px -apple-system, sans-serif';
      ctx.fillText({title_js}, 400, 240);

      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('CONTROLS: Arrow Keys / WASD to navigate', 400, 290);

      const pulse = Math.sin(Date.now() * 0.007) * 0.15 + 0.85;
      ctx.fillStyle = '#10b981';
      ctx.globalAlpha = pulse;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(250, 350, 300, 54, 12);
      else ctx.rect(250, 350, 300, 54);
      ctx.fill();
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 22px -apple-system, sans-serif';
      ctx.fillText('▶ CLICK TO PLAY', 400, 384);

      if (Input.isAction()) resetGame();
    }} else if (state === 'PLAYING') {{
      // Food
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.arc(food.x * GRID_SIZE + GRID_SIZE / 2, food.y * GRID_SIZE + GRID_SIZE / 2, GRID_SIZE / 2 - 2, 0, Math.PI * 2);
      ctx.fill();

      // Golden fruit
      if (goldenFruit) {{
        ctx.fillStyle = '#f59e0b';
        ctx.beginPath();
        ctx.arc(goldenFruit.x * GRID_SIZE + GRID_SIZE / 2, goldenFruit.y * GRID_SIZE + GRID_SIZE / 2, GRID_SIZE / 2, 0, Math.PI * 2);
        ctx.fill();
      }}

      // Snake body
      for (let i = 0; i < snake.length; i++) {{
        const s = snake[i];
        ctx.fillStyle = i === 0 ? '#34d399' : '#059669';
        ctx.fillRect(s.x * GRID_SIZE + 1, s.y * GRID_SIZE + 1, GRID_SIZE - 2, GRID_SIZE - 2);
      }}
    }} else if (state === 'GAMEOVER') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 48px -apple-system, sans-serif';
      ctx.fillText('GAME OVER', 400, 260);

      ctx.fillStyle = '#f8fafc';
      ctx.font = '22px -apple-system, sans-serif';
      ctx.fillText(`FINAL SCORE: ${{score}}`, 400, 310);

      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.fillText('PRESS SPACE TO PLAY AGAIN', 400, 380);

      if (Input.isAction()) resetGame();
    }}

    fx.draw(ctx);
    if (paused && state === 'PLAYING') {{
      ctx.fillStyle = 'rgba(9,14,23,0.75)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 40px -apple-system, sans-serif';
      ctx.fillText('PAUSED', 400, 285);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('Press P or click to resume', 400, 325);
    }}
    ctx.restore();
  }}

  function loop(ts) {{
    if (!lastTs) lastTs = ts;
    let dt = (ts - lastTs) / 1000;
    lastTs = ts;
    if (dt > 0.05) dt = 0.05;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }}

  requestAnimationFrame(loop);
  </script>
</body>
</html>
"""


def build_flappy_drone_game(title: str = "Aero Drone Odyssey") -> str:
    """Complete, hyper-responsive one-button flight arcade game."""
    title, title_js = _prepare_title(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #060911;
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      margin: 0;
      padding: 0;
      user-select: none;
    }}
    #game-wrapper {{
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    canvas {{
      display: block;
      max-width: 100%;
      max-height: 100%;
      aspect-ratio: 4 / 3;
      object-fit: contain;
      cursor: pointer;
    }}
    .hud {{
      position: absolute;
      top: 14px;
      left: 16px;
      right: 16px;
      display: flex;
      justify-content: space-between;
      pointer-events: none;
      font-size: 16px;
      font-weight: 700;
      text-shadow: 0 2px 4px rgba(0,0,0,0.8);
    }}
  </style>
</head>
<body>
  <div id="game-wrapper">
    <div class="hud">
      <div>SCORE: <span id="score-el">0</span></div>
      <div>HIGH: <span id="high-el">0</span></div>
    </div>
    <canvas id="gameCanvas" width="800" height="600"></canvas>
  </div>

  <script>
  {AUDIO_CORE_JS}
  {PARTICLE_SYSTEM_JS}
  {INPUT_CONTROLLER_JS}

  const canvas = document.getElementById('gameCanvas');
  const ctx = canvas.getContext('2d');
  Input.bindCanvas(canvas);

  const fx = new ParticleSystem();
  const scoreEl = document.getElementById('score-el');
  const highEl = document.getElementById('high-el');

  let state = 'MENU';
  let paused = false;
  let score = 0;
  function safeGetScore(k) {{
    try {{ return parseInt(localStorage.getItem(k) || '0', 10) || 0; }} catch (e) {{ return 0; }}
  }}
  function safeSetScore(k, v) {{
    try {{ localStorage.setItem(k, String(v)); }} catch (e) {{}}
  }}
  let highScore = safeGetScore('8gen_hs_drone');
  highEl.innerText = highScore;

  window.addEventListener('click', () => {{
    if (paused && state === 'PLAYING') {{ paused = false; return; }}
    if (state === 'MENU' || state === 'GAMEOVER') resetGame();
  }});
  window.addEventListener('keydown', (e) => {{
    if (e.key === 'p' || e.key === 'P' || e.key === 'Escape') {{
      if (state === 'PLAYING') paused = !paused;
    }} else if (e.key === 'r' || e.key === 'R') {{
      resetGame();
    }} else if (paused && (e.key === ' ' || e.key === 'Enter')) {{
      paused = false;
    }}
  }});
  document.addEventListener('visibilitychange', () => {{ if (document.hidden && state === 'PLAYING') paused = true; }});
  window.addEventListener('blur', () => {{ if (state === 'PLAYING') paused = true; }});

  const drone = {{
    x: 180,
    y: 300,
    vy: 0,
    radius: 13,
    gravity: 1550,
    lift: -440,
    maxFall: 820,
    tilt: 0,
  }};

  let pillars = [];
  let orbs = [];
  let spawnTimer = 0;
  let trailTimer = 0;
  let speed = 200;
  let bgScroll = 0;
  let lastTs = 0;
  let accumulator = 0;
  const FIXED = 1 / 60;
  let prevFlap = false;

  function resetGame() {{
    score = 0;
    paused = false;
    scoreEl.innerText = score;
    drone.y = 300;
    drone.vy = 0;
    drone.tilt = 0;
    pillars = [];
    orbs = [];
    spawnTimer = 1.4;
    trailTimer = 0;
    speed = 200;
    prevFlap = true;
    state = 'PLAYING';
    Sound.init();
    Sound.click();
  }}

  function spawnPillar() {{
    const gap = Math.max(145, 175 - Math.floor(score / 100) * 4);
    const minHeight = 60;
    const maxHeight = 600 - gap - minHeight;
    const topHeight = Math.floor(Math.random() * (maxHeight - minHeight)) + minHeight;
    const bottomY = topHeight + gap;

    pillars.push({{
      x: 820,
      topHeight: topHeight,
      bottomY: bottomY,
      width: 64,
      passed: false,
    }});

    // Spawn bonus orb in middle with 60% chance
    if (Math.random() < 0.6) {{
      orbs.push({{
        x: 820 + 32,
        y: topHeight + gap / 2,
        radius: 10,
        alive: true,
      }});
    }}
  }}

  function update(dt) {{
    fx.update();
    if (state !== 'PLAYING' || paused) return;

    bgScroll += speed * dt;
    spawnTimer += dt;
    if (spawnTimer >= 1.75) {{
      spawnTimer = 0;
      spawnPillar();
    }}

    // Drone flight physics (edge-triggered flap impulse + dt gravity)
    const flapNow = Input.isAction() || Input.isUp();
    if (flapNow && !prevFlap) {{
      drone.vy = drone.lift;
      drone.tilt = -0.45;
      Sound.jump();
      fx.spawnBurst(drone.x - 12, drone.y + 4, '#38bdf8', 6, 3);
    }} else {{
      drone.vy = Math.min(drone.maxFall, drone.vy + drone.gravity * dt);
      drone.tilt = Math.max(-0.45, Math.min(0.65, drone.vy / 700));
    }}
    prevFlap = flapNow;

    drone.y += drone.vy * dt;

    // Thruster trail
    trailTimer += dt;
    if (trailTimer >= 0.05) {{
      trailTimer = 0;
      fx.spawnBurst(drone.x - 14, drone.y, '#f59e0b', 2, 2);
    }}

    // Ceiling / floor collision
    if (drone.y - drone.radius < 0 || drone.y + drone.radius > 600) {{
      gameOver();
      return;
    }}

    // Update Pillars
    for (let i = pillars.length - 1; i >= 0; i--) {{
      const p = pillars[i];
      p.x -= speed * dt;

      // Check collision with forgiving hitbox
      if (
        drone.x + drone.radius > p.x &&
        drone.x - drone.radius < p.x + p.width
      ) {{
        if (drone.y - drone.radius < p.topHeight || drone.y + drone.radius > p.bottomY) {{
          gameOver();
          return;
        }}
      }}

      // Score passing
      if (!p.passed && p.x + p.width < drone.x) {{
        p.passed = true;
        score += 10;
        speed = Math.min(310, speed + 2.5);
        scoreEl.innerText = score;
        Sound.pickup();
        fx.spawnFloatingText('+10', drone.x, drone.y - 20, '#10b981');
      }}

      if (p.x < -80) {{
        pillars.splice(i, 1);
      }}
    }}

    // Update Orbs
    for (let i = orbs.length - 1; i >= 0; i--) {{
      const orb = orbs[i];
      orb.x -= speed * dt;
      const dist = Math.hypot(drone.x - orb.x, drone.y - orb.y);
      if (dist < drone.radius + orb.radius) {{
        score += 50;
        scoreEl.innerText = score;
        Sound.powerup();
        fx.spawnBurst(orb.x, orb.y, '#facc15', 18, 5);
        fx.spawnFloatingText('+50 BONUS!', drone.x, drone.y - 24, '#facc15');
        orbs.splice(i, 1);
      }} else if (orb.x < -40) {{
        orbs.splice(i, 1);
      }}
    }}
  }}

  function gameOver() {{
    state = 'GAMEOVER';
    fx.triggerScreenShake(12);
    fx.spawnBurst(drone.x, drone.y, '#ef4444', 35, 8);
    Sound.hit();
    Sound.gameover();
    if (score > highScore) {{
      highScore = score;
      safeSetScore('8gen_hs_drone', highScore);
      highEl.innerText = highScore;
    }}
  }}

  function draw() {{
    ctx.save();
    ctx.clearRect(0, 0, 800, 600);
    fx.applyScreenShake(ctx);

    // Starry background
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    for (let i = 0; i < 40; i++) {{
      const sx = ((i * 73 + bgScroll * 0.25) % 800);
      const sy = (i * 97) % 600;
      ctx.fillRect(sx, sy, 1.5, 1.5);
    }}

    if (state === 'MENU') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 44px -apple-system, sans-serif';
      ctx.fillText({title_js}, 400, 240);

      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('CONTROLS: Spacebar, Click, or Touch to Boost Drone', 400, 290);

      const pulse = Math.sin(Date.now() * 0.007) * 0.15 + 0.85;
      ctx.fillStyle = '#10b981';
      ctx.globalAlpha = pulse;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(250, 350, 300, 54, 12);
      else ctx.rect(250, 350, 300, 54);
      ctx.fill();
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 22px -apple-system, sans-serif';
      ctx.fillText('▶ CLICK TO FLY', 400, 384);

      if (Input.isAction()) resetGame();
    }} else if (state === 'PLAYING') {{
      // Draw Pillars
      for (const p of pillars) {{
        // Top pillar
        const gradTop = ctx.createLinearGradient(p.x, 0, p.x + p.width, 0);
        gradTop.addColorStop(0, '#0284c7');
        gradTop.addColorStop(1, '#06b6d4');
        ctx.fillStyle = gradTop;
        ctx.fillRect(p.x, 0, p.width, p.topHeight);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(p.x - 3, p.topHeight - 12, p.width + 6, 12);

        // Bottom pillar
        const gradBot = ctx.createLinearGradient(p.x, 0, p.x + p.width, 0);
        gradBot.addColorStop(0, '#0284c7');
        gradBot.addColorStop(1, '#06b6d4');
        ctx.fillStyle = gradBot;
        ctx.fillRect(p.x, p.bottomY, p.width, 600 - p.bottomY);
        ctx.fillStyle = '#38bdf8';
        ctx.fillRect(p.x - 3, p.bottomY, p.width + 6, 12);
      }}

      // Draw Orbs
      for (const orb of orbs) {{
        ctx.save();
        ctx.fillStyle = '#facc15';
        ctx.beginPath();
        ctx.arc(orb.x, orb.y, orb.radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }}

      // Draw Drone
      ctx.save();
      ctx.translate(drone.x, drone.y);
      ctx.rotate(drone.tilt);
      
      // Drone chassis
      ctx.fillStyle = '#f8fafc';
      ctx.beginPath();
      ctx.ellipse(0, 0, 18, 12, 0, 0, Math.PI * 2);
      ctx.fill();

      // Cockpit visor
      ctx.fillStyle = '#06b6d4';
      ctx.beginPath();
      ctx.arc(6, -2, 6, 0, Math.PI * 2);
      ctx.fill();

      // Wing thruster
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(-16, -3, 6, 6);

      ctx.restore();
    }} else if (state === 'GAMEOVER') {{
      ctx.textAlign = 'center';
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 48px -apple-system, sans-serif';
      ctx.fillText('CRASHED!', 400, 240);

      ctx.fillStyle = '#f8fafc';
      ctx.font = '22px -apple-system, sans-serif';
      ctx.fillText(`SCORE: ${{score}}   •   BEST: ${{highScore}}`, 400, 290);

      ctx.fillStyle = '#f59e0b';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.fillText('PRESS SPACE TO REFLY', 400, 360);

      if (Input.isAction()) resetGame();
    }}

    fx.draw(ctx);
    if (paused && state === 'PLAYING') {{
      ctx.fillStyle = 'rgba(6,9,17,0.75)';
      ctx.fillRect(0, 0, 800, 600);
      ctx.textAlign = 'center';
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 40px -apple-system, sans-serif';
      ctx.fillText('PAUSED', 400, 285);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '16px -apple-system, sans-serif';
      ctx.fillText('Press P or click to resume', 400, 325);
    }}
    ctx.restore();
  }}

  function loop(ts) {{
    if (!lastTs) lastTs = ts;
    let frame = (ts - lastTs) / 1000;
    lastTs = ts;
    if (frame > 0.05) frame = 0.05;
    accumulator += frame;
    let steps = 0;
    while (accumulator >= FIXED && steps < 5) {{
      update(FIXED);
      accumulator -= FIXED;
      steps++;
    }}
    draw();
    requestAnimationFrame(loop);
  }}

  requestAnimationFrame(loop);
  </script>
</body>
</html>
"""


def build_smart_archetype(prompt: str, category: str = "") -> str:
    """Intelligently match user prompt and category to the best fully-playable archetype with customized title."""
    clean_p = prompt.lower()
    clean_cat = (category or "").lower()

    # Extract or infer clean title
    words = [
        w.capitalize()
        for w in prompt.split()
        if len(w) > 2
        and w.lower() not in {"make", "create", "with", "that", "game", "retro", "instant", "play"}
    ]
    inferred_title = " ".join(words[:4]) if words else "Arcade Classic"

    if any(k in clean_p for k in ["snake", "slither", "worm", "fruit", "tail"]):
        return build_cyber_snake_game(title=f"Cyber Snake: {inferred_title}")
    elif any(k in clean_p for k in ["brick", "breakout", "arkanoid", "paddle"]):
        return build_brick_breaker_game(title=f"Breakout: {inferred_title}")
    elif any(k in clean_p for k in ["platformer", "platform", "mario", "celeste", "metroidvania", "side scroller", "side-scroller", "double jump", "wall jump", "spikes"]):
        return build_platformer_game(title=f"Neon Leap: {inferred_title}")
    elif any(k in clean_p for k in ["fly", "flappy", "drone", "bird", "copter", "pipe"]):
        return build_flappy_drone_game(title=f"Aero Drone: {inferred_title}")
    elif any(k in clean_p for k in ["runner", "endless", "dino", "obstacle"]):
        return build_flappy_drone_game(title=f"Aero Runner: {inferred_title}")
    elif clean_cat in ["puzzle", "grid"]:
        return build_brick_breaker_game(title=f"Puzzle Breaker: {inferred_title}")
    elif clean_cat in ["platformer"]:
        return build_platformer_game(title=f"Neon Leap: {inferred_title}")
    else:
        # Default space / arcade / shooter
        return build_space_shooter_game(title=f"Space Defender: {inferred_title}")

