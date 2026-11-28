"""Simple, runnable reference game catalog and minimal HTML5 builders."""

import html
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class ReferenceGameSpec:
    """Metadata and builder for a simple popular reference game."""

    id: str
    label: str
    category: str
    controls: str
    mechanics: str
    prompt: str
    builder: Callable[[], str]


def _wrap_simple_game(title: str, controls_hint: str, body_html: str, extra_css: str, script_js: str) -> str:
    """Wrap a simple game inside a clean, single-file responsive HTML5 shell."""
    title = html.escape(str(title or "Arcade Classic"), quote=True)
    controls_hint = html.escape(str(controls_hint or ""), quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0b0f19;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      gap: 10px;
      user-select: none;
    }}
    .topbar {{
      display: flex;
      gap: 20px;
      align-items: center;
      font-size: 14px;
      font-weight: 600;
      color: #cbd5e1;
    }}
    .controls-hint {{
      font-size: 12px;
      color: #94a3b8;
    }}
    canvas {{
      background: #111827;
      border: 2px solid #334155;
      border-radius: 8px;
      max-width: 94vw;
      max-height: 78vh;
      display: block;
    }}
    button.action-btn {{
      background: #2563eb;
      color: #ffffff;
      border: none;
      border-radius: 6px;
      padding: 6px 14px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }}
    button.action-btn:hover {{ background: #1d4ed8; }}
    {extra_css}
  </style>
</head>
<body>
  <div class="topbar">
    <span>{title}</span>
    <span class="controls-hint">{controls_hint}</span>
  </div>
  {body_html}
  <script>
    window.addEventListener('keydown', (e) => {{
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space', ' '].includes(e.key)) {{
        e.preventDefault();
      }}
    }});
    {script_js}
  </script>
</body>
</html>"""


def _build_simple_pong() -> str:
    return _wrap_simple_game(
        title="Simple Pong",
        controls_hint="Controls: W/S or Up/Down Arrows (or Mouse)",
        body_html='<div class="topbar">Score: <span id="score">0 - 0</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><canvas id="c" width="640" height="400"></canvas>',
        extra_css="",
        script_js="""
const c = document.getElementById('c'), ctx = c.getContext('2d'), scoreEl = document.getElementById('score');
const keys = {};
let pY = 160, cpuY = 160, bX = 320, bY = 200, bVX = 260, bVY = 180, pScore = 0, cScore = 0, over = false, lastTs = 0;
window.addEventListener('keydown', e => { keys[e.key] = true; if (e.key === ' ' && over) resetGame(); });
window.addEventListener('keyup', e => { keys[e.key] = false; });
function movePaddle(clientY) { const r = c.getBoundingClientRect(); pY = Math.max(0, Math.min(320, ((clientY - r.top) / r.height) * c.height - 40)); }
c.addEventListener('mousemove', e => movePaddle(e.clientY));
c.addEventListener('touchstart', e => { e.preventDefault(); if (over) resetGame(); else if (e.touches[0]) movePaddle(e.touches[0].clientY); }, { passive: false });
c.addEventListener('touchmove', e => { e.preventDefault(); if (e.touches[0]) movePaddle(e.touches[0].clientY); }, { passive: false });
function resetBall(dir = 1) { bX = 320; bY = 200; bVX = 260 * dir; bVY = (Math.random() > 0.5 ? 190 : -190); }
function resetGame() { pScore = 0; cScore = 0; pY = 160; cpuY = 160; over = false; scoreEl.textContent = '0 - 0'; resetBall(1); }
function loop(ts) {
  if (!lastTs) lastTs = ts;
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (!over) {
    if (keys['ArrowUp'] || keys['w'] || keys['W']) pY -= 380 * dt;
    if (keys['ArrowDown'] || keys['s'] || keys['S']) pY += 380 * dt;
    pY = Math.max(0, Math.min(320, pY));
    if (cpuY + 40 < bY - 8) cpuY += 230 * dt; else if (cpuY + 40 > bY + 8) cpuY -= 230 * dt;
    cpuY = Math.max(0, Math.min(320, cpuY));
    bX += bVX * dt; bY += bVY * dt;
    if (bY < 8) { bY = 8; bVY = Math.abs(bVY); }
    if (bY > 392) { bY = 392; bVY = -Math.abs(bVY); }
    if (bX < 28 && bX > 14 && bY > pY && bY < pY + 80) { bX = 28; bVX = Math.min(540, Math.abs(bVX) * 1.04); bVY += (bY - (pY + 40)) * 4.5; }
    if (bX > 612 && bX < 626 && bY > cpuY && bY < cpuY + 80) { bX = 612; bVX = -Math.min(540, Math.abs(bVX) * 1.04); }
    if (bX < 0) { cScore++; resetBall(1); }
    if (bX > 640) { pScore++; resetBall(-1); }
    scoreEl.textContent = pScore + ' - ' + cScore;
    if (pScore >= 5 || cScore >= 5) over = true;
  }
  ctx.clearRect(0, 0, 640, 400);
  ctx.fillStyle = '#334155'; ctx.fillRect(319, 0, 2, 400);
  ctx.fillStyle = '#38bdf8'; ctx.fillRect(16, pY, 12, 80);
  ctx.fillStyle = '#f87171'; ctx.fillRect(612, cpuY, 12, 80);
  ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(bX, bY, 8, 0, Math.PI * 2); ctx.fill();
  if (over) {
    ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fillRect(0, 0, 640, 400);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 28px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(pScore >= 5 ? 'You Win!' : 'CPU Wins!', 320, 190);
    ctx.font = '15px sans-serif'; ctx.fillText('Press Space or Restart', 320, 224);
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
""",
    )


def _build_simple_snake() -> str:
    return _wrap_simple_game(
        title="Simple Snake",
        controls_hint="Controls: Arrow Keys or WASD to move",
        body_html='<div class="topbar">Score: <span id="score">0</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><canvas id="c" width="400" height="400"></canvas>',
        extra_css="",
        script_js="""
const c = document.getElementById('c'), ctx = c.getContext('2d'), scoreEl = document.getElementById('score');
const GRID = 20, CELLS = 20;
let snake, dir, turnQueue, food, score, over, accum = 0, lastTs = 0, tx = null, ty = null;
function queueTurn(dx, dy) {
  const last = turnQueue.length ? turnQueue[turnQueue.length - 1] : dir;
  if ((last.x === -dx && last.y === -dy) || (last.x === dx && last.y === dy)) return;
  if (turnQueue.length < 2) turnQueue.push({ x: dx, y: dy });
}
function spawnFood() {
  do { food = { x: Math.floor(Math.random() * CELLS), y: Math.floor(Math.random() * CELLS) }; }
  while (snake.some(s => s.x === food.x && s.y === food.y));
}
function resetGame() {
  snake = [{ x: 10, y: 10 }, { x: 9, y: 10 }, { x: 8, y: 10 }];
  dir = { x: 1, y: 0 }; turnQueue = []; score = 0; over = false; accum = 0;
  scoreEl.textContent = '0'; spawnFood();
}
window.addEventListener('keydown', e => {
  const k = e.key.toLowerCase();
  if (k === 'arrowup' || k === 'w') queueTurn(0, -1);
  if (k === 'arrowdown' || k === 's') queueTurn(0, 1);
  if (k === 'arrowleft' || k === 'a') queueTurn(-1, 0);
  if (k === 'arrowright' || k === 'd') queueTurn(1, 0);
  if (e.key === ' ' && over) resetGame();
});
c.addEventListener('touchstart', e => { if (over) resetGame(); else if (e.touches[0]) { tx = e.touches[0].clientX; ty = e.touches[0].clientY; } }, { passive: true });
c.addEventListener('touchmove', e => {
  if (tx === null || !e.touches[0]) return;
  const dx = e.touches[0].clientX - tx, dy = e.touches[0].clientY - ty;
  if (Math.hypot(dx, dy) < 16) return;
  if (Math.abs(dx) > Math.abs(dy)) queueTurn(dx > 0 ? 1 : -1, 0); else queueTurn(0, dy > 0 ? 1 : -1);
  tx = e.touches[0].clientX; ty = e.touches[0].clientY;
}, { passive: true });
resetGame();
function loop(ts) {
  if (!lastTs) lastTs = ts;
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (!over) {
    accum += dt;
    while (accum >= 0.12) {
      accum -= 0.12;
      if (turnQueue.length) dir = turnQueue.shift();
      const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };
      const willEat = head.x === food.x && head.y === food.y;
      const body = willEat ? snake : snake.slice(0, -1);
      if (head.x < 0 || head.x >= CELLS || head.y < 0 || head.y >= CELLS || body.some(s => s.x === head.x && s.y === head.y)) {
        over = true; break;
      }
      snake.unshift(head);
      if (willEat) { score++; scoreEl.textContent = score; spawnFood(); }
      else snake.pop();
    }
  }
  ctx.clearRect(0, 0, 400, 400);
  ctx.fillStyle = '#ef4444'; ctx.fillRect(food.x * GRID + 2, food.y * GRID + 2, GRID - 4, GRID - 4);
  snake.forEach((s, i) => {
    ctx.fillStyle = i === 0 ? '#34d399' : '#10b981';
    ctx.fillRect(s.x * GRID + 1, s.y * GRID + 1, GRID - 2, GRID - 2);
  });
  if (over) {
    ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fillRect(0, 0, 400, 400);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 26px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('Game Over', 200, 190);
    ctx.font = '15px sans-serif'; ctx.fillText('Press Space or Restart', 200, 222);
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
""",
    )


def _build_simple_tic_tac_toe() -> str:
    return _wrap_simple_game(
        title="Simple Tic-Tac-Toe",
        controls_hint="Controls: Click any square (You = X, CPU = O)",
        body_html='<div class="topbar"><span id="status">Your Turn (X)</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><div id="board" class="ttt-board"></div>',
        extra_css="""
    .ttt-board { display: grid; grid-template-columns: repeat(3, 100px); gap: 8px; margin-top: 8px; }
    .ttt-cell {
      width: 100px; height: 100px; background: #111827; border: 2px solid #334155;
      border-radius: 10px; font-size: 44px; font-weight: 700; color: #f8fafc;
      display: flex; align-items: center; justify-content: center; cursor: pointer;
    }
    .ttt-cell:hover { border-color: #60a5fa; }
    .ttt-cell.win { background: #14532d; border-color: #22c55e; }
""",
        script_js="""
const boardEl = document.getElementById('board'), statusEl = document.getElementById('status');
const WINS = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
let cells, over, winLine;
function checkWin(b) {
  for (const line of WINS) {
    const [a, m, c] = line;
    if (b[a] && b[a] === b[m] && b[a] === b[c]) return { winner: b[a], line };
  }
  return b.every(Boolean) ? { winner: 'DRAW', line: [] } : null;
}
function cpuMove() {
  const empty = cells.map((v, i) => v ? -1 : i).filter(i => i >= 0);
  if (!empty.length || over) return;
  const pick = empty[Math.floor(Math.random() * empty.length)];
  cells[pick] = 'O';
  finishCheck('Your Turn (X)');
}
function finishCheck(nextText) {
  const res = checkWin(cells);
  if (res) {
    over = true; winLine = res.line;
    statusEl.textContent = res.winner === 'DRAW' ? 'Draw!' : (res.winner === 'X' ? 'You Win!' : 'CPU Wins!');
  } else {
    statusEl.textContent = nextText;
  }
  render();
}
function clickCell(i) {
  if (over || cells[i]) return;
  cells[i] = 'X';
  finishCheck('CPU Thinking...');
  if (!over) setTimeout(cpuMove, 220);
}
function render() {
  boardEl.innerHTML = '';
  cells.forEach((val, i) => {
    const div = document.createElement('div');
    div.className = 'ttt-cell' + (winLine.includes(i) ? ' win' : '');
    div.style.color = val === 'X' ? '#38bdf8' : '#f87171';
    div.textContent = val;
    div.onclick = () => clickCell(i);
    boardEl.appendChild(div);
  });
}
function resetGame() { cells = Array(9).fill(''); over = false; winLine = []; statusEl.textContent = 'Your Turn (X)'; render(); }
resetGame();
""",
    )


def _build_simple_flappy() -> str:
    return _wrap_simple_game(
        title="Simple Flappy Bird",
        controls_hint="Controls: Space, Up Arrow, or Click to Flap",
        body_html='<div class="topbar">Score: <span id="score">0</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><canvas id="c" width="420" height="480"></canvas>',
        extra_css="",
        script_js="""
const c = document.getElementById('c'), ctx = c.getContext('2d'), scoreEl = document.getElementById('score');
let birdY, vel, pipes, score, over, started, spawnTimer, lastTs = 0;
function resetGame() { birdY = 220; vel = 0; pipes = []; score = 0; over = false; started = false; spawnTimer = 0.8; scoreEl.textContent = '0'; }
function flap() {
  if (over) { resetGame(); return; }
  started = true; vel = -390;
}
window.addEventListener('keydown', e => { if (e.key === ' ' || e.key === 'ArrowUp') flap(); });
c.addEventListener('pointerdown', e => { e.preventDefault(); flap(); });
resetGame();
function loop(ts) {
  if (!lastTs) lastTs = ts;
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (started && !over) {
    vel += 1260 * dt; birdY += vel * dt;
    spawnTimer += dt;
    if (spawnTimer >= 1.55) {
      spawnTimer = 0;
      const gapY = 90 + Math.random() * 200;
      pipes.push({ x: 420, gapY, passed: false });
    }
    pipes.forEach(p => {
      p.x -= 170 * dt;
      if (!p.passed && p.x + 48 < 90) { p.passed = true; score++; scoreEl.textContent = score; }
      if (90 + 11 > p.x && 90 - 11 < p.x + 48 && (birdY - 11 < p.gapY || birdY + 11 > p.gapY + 130)) over = true;
    });
    pipes = pipes.filter(p => p.x > -60);
    if (birdY < 12 || birdY > 468) over = true;
  }
  ctx.clearRect(0, 0, 420, 480);
  ctx.fillStyle = '#22c55e';
  pipes.forEach(p => {
    ctx.fillRect(p.x, 0, 48, p.gapY);
    ctx.fillRect(p.x, p.gapY + 130, 48, 480 - p.gapY - 130);
  });
  ctx.fillStyle = '#facc15';
  ctx.beginPath(); ctx.arc(90, birdY, 14, 0, Math.PI * 2); ctx.fill();
  if (!started || over) {
    ctx.fillStyle = 'rgba(0,0,0,0.55)'; ctx.fillRect(0, 0, 420, 480);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 24px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(over ? 'Game Over - Score: ' + score : 'Click or Press Space', 210, 235);
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
""",
    )


def _build_simple_breakout() -> str:
    return _wrap_simple_game(
        title="Simple Breakout",
        controls_hint="Controls: Left/Right Arrows or Mouse",
        body_html='<div class="topbar">Score: <span id="score">0</span> | Lives: <span id="lives">3</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><canvas id="c" width="520" height="400"></canvas>',
        extra_css="",
        script_js="""
const c = document.getElementById('c'), ctx = c.getContext('2d');
const scoreEl = document.getElementById('score'), livesEl = document.getElementById('lives');
const keys = {};
let pX, bX, bY, bVX, bVY, bricks, score, lives, state, lastTs = 0;
function makeBricks() {
  const arr = [], colors = ['#ef4444','#f97316','#eab308','#22c55e'];
  for (let r = 0; r < 4; r++) for (let col = 0; col < 8; col++)
    arr.push({ x: 24 + col * 60, y: 40 + r * 26, w: 52, h: 18, color: colors[r], alive: true });
  return arr;
}
function resetBall() { bX = 260; bY = 320; bVX = 210; bVY = -220; }
function resetGame() { pX = 215; bricks = makeBricks(); score = 0; lives = 3; state = 'PLAY'; scoreEl.textContent = '0'; livesEl.textContent = '3'; resetBall(); }
window.addEventListener('keydown', e => { keys[e.key] = true; if (e.key === ' ' && state !== 'PLAY') resetGame(); });
window.addEventListener('keyup', e => { keys[e.key] = false; });
function movePaddle(clientX) { const r = c.getBoundingClientRect(); pX = Math.max(0, Math.min(430, ((clientX - r.left) / r.width) * c.width - 45)); }
c.addEventListener('mousemove', e => movePaddle(e.clientX));
c.addEventListener('touchstart', e => { e.preventDefault(); if (state !== 'PLAY') resetGame(); else if (e.touches[0]) movePaddle(e.touches[0].clientX); }, { passive: false });
c.addEventListener('touchmove', e => { e.preventDefault(); if (e.touches[0]) movePaddle(e.touches[0].clientX); }, { passive: false });
resetGame();
function loop(ts) {
  if (!lastTs) lastTs = ts;
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (state === 'PLAY') {
    if (keys['ArrowLeft'] || keys['a']) pX -= 360 * dt;
    if (keys['ArrowRight'] || keys['d']) pX += 360 * dt;
    pX = Math.max(0, Math.min(430, pX));
    bX += bVX * dt; bY += bVY * dt;
    if (bX < 8) { bX = 8; bVX = Math.abs(bVX); }
    if (bX > 512) { bX = 512; bVX = -Math.abs(bVX); }
    if (bY < 8) { bY = 8; bVY = Math.abs(bVY); }
    if (bY > 362 && bY < 378 && bX > pX && bX < pX + 90 && bVY > 0) { bY = 362; bVY = -Math.abs(bVY); bVX = (bX - (pX + 45)) * 7.2; }
    for (const br of bricks) {
      if (br.alive && bX + 7 > br.x && bX - 7 < br.x + br.w && bY + 7 > br.y && bY - 7 < br.y + br.h) {
        br.alive = false; bVY *= -1; score += 10; scoreEl.textContent = score; break;
      }
    }
    if (bricks.every(b => !b.alive)) state = 'WIN';
    if (bY > 400) {
      lives--; livesEl.textContent = lives;
      if (lives <= 0) state = 'OVER'; else resetBall();
    }
  }
  ctx.clearRect(0, 0, 520, 400);
  bricks.forEach(br => { if (br.alive) { ctx.fillStyle = br.color; ctx.fillRect(br.x, br.y, br.w, br.h); } });
  ctx.fillStyle = '#38bdf8'; ctx.fillRect(pX, 370, 90, 12);
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(bX, bY, 7, 0, Math.PI * 2); ctx.fill();
  if (state !== 'PLAY') {
    ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fillRect(0, 0, 520, 400);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 26px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(state === 'WIN' ? 'You Cleared All Bricks!' : 'Game Over', 260, 195);
    ctx.font = '15px sans-serif'; ctx.fillText('Press Space or Restart', 260, 225);
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
""",
    )


def _build_simple_space_invaders() -> str:
    return _wrap_simple_game(
        title="Simple Space Invaders",
        controls_hint="Controls: Left/Right Arrows to move, Space to shoot",
        body_html='<div class="topbar">Score: <span id="score">0</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><canvas id="c" width="520" height="420"></canvas>',
        extra_css="",
        script_js="""
const c = document.getElementById('c'), ctx = c.getContext('2d'), scoreEl = document.getElementById('score');
const keys = {};
let shipX, bullets, aliens, alienDir, score, state, shotCooldown = 0, lastTs = 0;
function resetGame() {
  shipX = 240; bullets = []; alienDir = 90; score = 0; state = 'PLAY'; shotCooldown = 0; scoreEl.textContent = '0';
  aliens = [];
  for (let r = 0; r < 3; r++) for (let col = 0; col < 8; col++)
    aliens.push({ x: 50 + col * 52, y: 40 + r * 36, w: 32, h: 22, alive: true });
}
function fire() {
  if (state !== 'PLAY') { resetGame(); return; }
  if (shotCooldown <= 0 && bullets.length < 4) { bullets.push({ x: shipX + 18, y: 374 }); shotCooldown = 0.18; }
}
window.addEventListener('keydown', e => {
  keys[e.key] = true;
  if (e.key === ' ') fire();
});
window.addEventListener('keyup', e => { keys[e.key] = false; });
c.addEventListener('pointerdown', e => { e.preventDefault(); const r = c.getBoundingClientRect(); shipX = Math.max(10, Math.min(470, ((e.clientX - r.left) / r.width) * c.width - 20)); fire(); });
c.addEventListener('pointermove', e => { if (e.buttons) { const r = c.getBoundingClientRect(); shipX = Math.max(10, Math.min(470, ((e.clientX - r.left) / r.width) * c.width - 20)); } });
resetGame();
function loop(ts) {
  if (!lastTs) lastTs = ts;
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (state === 'PLAY') {
    shotCooldown = Math.max(0, shotCooldown - dt);
    if (keys['ArrowLeft'] || keys['a']) shipX -= 300 * dt;
    if (keys['ArrowRight'] || keys['d']) shipX += 300 * dt;
    shipX = Math.max(10, Math.min(470, shipX));
    bullets.forEach(b => b.y -= 440 * dt);
    bullets = bullets.filter(b => b.y > 0);
    let hitEdge = false;
    aliens.forEach(a => {
      if (!a.alive) return;
      a.x += alienDir * dt;
      if (a.x < 10 || a.x + a.w > 510) hitEdge = true;
      if (a.y + a.h >= 375) state = 'OVER';
      bullets.forEach(b => {
        if (b.x > a.x && b.x < a.x + a.w && b.y > a.y && b.y < a.y + a.h) {
          a.alive = false; b.y = -10; score += 10; scoreEl.textContent = score;
        }
      });
    });
    if (hitEdge) { alienDir *= -1; aliens.forEach(a => a.y += 18); }
    if (aliens.every(a => !a.alive)) state = 'WIN';
  }
  ctx.clearRect(0, 0, 520, 420);
  ctx.fillStyle = '#38bdf8'; ctx.fillRect(shipX, 380, 40, 16);
  ctx.fillStyle = '#facc15'; bullets.forEach(b => ctx.fillRect(b.x, b.y, 4, 10));
  ctx.fillStyle = '#a855f7'; aliens.forEach(a => { if (a.alive) ctx.fillRect(a.x, a.y, a.w, a.h); });
  if (state !== 'PLAY') {
    ctx.fillStyle = 'rgba(0,0,0,0.65)'; ctx.fillRect(0, 0, 520, 420);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 26px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(state === 'WIN' ? 'Wave Cleared!' : 'Game Over', 260, 200);
    ctx.font = '15px sans-serif'; ctx.fillText('Press Space or Restart', 260, 232);
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
""",
    )


def _build_simple_memory_match() -> str:
    return _wrap_simple_game(
        title="Simple Memory Match",
        controls_hint="Controls: Click two cards to match all 8 pairs",
        body_html='<div class="topbar">Moves: <span id="moves">0</span> | Pairs: <span id="pairs">0/8</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><div id="grid" class="mem-grid"></div>',
        extra_css="""
    .mem-grid { display: grid; grid-template-columns: repeat(4, 78px); gap: 10px; margin-top: 8px; }
    .mem-card {
      width: 78px; height: 78px; background: #1e293b; border: 2px solid #334155;
      border-radius: 10px; font-size: 30px; display: flex; align-items: center;
      justify-content: center; cursor: pointer;
    }
    .mem-card.open { background: #0f172a; border-color: #38bdf8; }
    .mem-card.matched { background: #14532d; border-color: #22c55e; }
""",
        script_js="""
const grid = document.getElementById('grid'), movesEl = document.getElementById('moves'), pairsEl = document.getElementById('pairs');
const ICONS = ['🚀','🐍','⚡','🎮','💎','🔥','⭐','🍀'];
let deck, flipped, matchedCount, moves, locked;
function resetGame() {
  deck = [...ICONS, ...ICONS].sort(() => Math.random() - 0.5).map((icon, i) => ({ id: i, icon, open: false, matched: false }));
  flipped = []; matchedCount = 0; moves = 0; locked = false;
  movesEl.textContent = '0'; pairsEl.textContent = '0/8'; render();
}
function pickCard(card) {
  if (locked || card.open || card.matched) return;
  card.open = true; flipped.push(card); render();
  if (flipped.length === 2) {
    moves++; movesEl.textContent = moves; locked = true;
    const [a, b] = flipped;
    if (a.icon === b.icon) {
      a.matched = b.matched = true; matchedCount++; pairsEl.textContent = matchedCount + '/8';
      flipped = []; locked = false; render();
    } else {
      setTimeout(() => { a.open = false; b.open = false; flipped = []; locked = false; render(); }, 600);
    }
  }
}
function render() {
  grid.innerHTML = '';
  deck.forEach(card => {
    const el = document.createElement('div');
    el.className = 'mem-card' + (card.matched ? ' matched' : (card.open ? ' open' : ''));
    el.textContent = (card.open || card.matched) ? card.icon : '?';
    el.onclick = () => pickCard(card);
    grid.appendChild(el);
  });
}
resetGame();
""",
    )


def _build_simple_dino_runner() -> str:
    return _wrap_simple_game(
        title="Simple Dino Runner",
        controls_hint="Controls: Space, Up Arrow, or Click to Jump",
        body_html='<div class="topbar">Score: <span id="score">0</span> <button class="action-btn" onclick="resetGame()">Restart</button></div><canvas id="c" width="600" height="300"></canvas>',
        extra_css="",
        script_js="""
const c = document.getElementById('c'), ctx = c.getContext('2d'), scoreEl = document.getElementById('score');
const GROUND = 240;
let dinoY, velY, obstacles, score, scoreTimer, spawnTimer, over, lastTs = 0;
function resetGame() { dinoY = GROUND - 40; velY = 0; obstacles = []; score = 0; scoreTimer = 0; spawnTimer = 0.8; over = false; scoreEl.textContent = '0'; }
function jump() {
  if (over) { resetGame(); return; }
  if (dinoY >= GROUND - 40) velY = -660;
}
window.addEventListener('keydown', e => { if (e.key === ' ' || e.key === 'ArrowUp') jump(); });
c.addEventListener('pointerdown', e => { e.preventDefault(); jump(); });
resetGame();
function loop(ts) {
  if (!lastTs) lastTs = ts;
  const dt = Math.min(0.05, (ts - lastTs) / 1000);
  lastTs = ts;
  if (!over) {
    scoreTimer += dt;
    if (scoreTimer >= 0.1) { scoreTimer -= 0.1; score++; scoreEl.textContent = score; }
    velY += 1950 * dt; dinoY = Math.min(GROUND - 40, dinoY + velY * dt);
    spawnTimer += dt;
    if (spawnTimer >= 1.35) { spawnTimer = 0; obstacles.push({ x: 600, w: 20 + Math.random() * 14, h: 32 + Math.random() * 18 }); }
    const speed = Math.min(520, 310 + score * 0.4);
    obstacles.forEach(o => {
      o.x -= speed * dt;
      if (70 + 24 > o.x && 74 < o.x + o.w && dinoY + 38 > GROUND - o.h) over = true;
    });
    obstacles = obstacles.filter(o => o.x > -40);
  }
  ctx.clearRect(0, 0, 600, 300);
  ctx.fillStyle = '#475569'; ctx.fillRect(0, GROUND, 600, 3);
  ctx.fillStyle = '#34d399'; ctx.fillRect(70, dinoY, 28, 40);
  ctx.fillStyle = '#f87171'; obstacles.forEach(o => ctx.fillRect(o.x, GROUND - o.h, o.w, o.h));
  if (over) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(0, 0, 600, 300);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 24px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('Game Over - Score: ' + score, 300, 140);
    ctx.font = '14px sans-serif'; ctx.fillText('Press Space, Click, or Restart', 300, 170);
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
""",
    )


REFERENCE_GAMES: List[ReferenceGameSpec] = [
    ReferenceGameSpec(
        id="pong",
        label="Pong (Classic Paddle)",
        category="arcade",
        controls="W/S or Up/Down arrows (or mouse) to move your paddle",
        mechanics="Single bouncing ball, player paddle vs simple CPU paddle, first to 5 points wins",
        prompt="Simple classic Pong game with W/S or Up/Down paddle controls and basic CPU opponent, first to 5 wins",
        builder=_build_simple_pong,
    ),
    ReferenceGameSpec(
        id="snake",
        label="Snake (Classic Grid)",
        category="arcade",
        controls="Arrow keys or WASD to change direction",
        mechanics="Simple grid snake moves step-by-step, eats red food to grow and score +1, game over on wall or self hit",
        prompt="Simple classic Snake game on a 20x20 grid with Arrow/WASD controls and basic food scoring",
        builder=_build_simple_snake,
    ),
    ReferenceGameSpec(
        id="tic-tac-toe",
        label="Tic-Tac-Toe (3x3)",
        category="puzzle",
        controls="Click or tap any empty cell to place X",
        mechanics="Classic 3x3 board against a simple O CPU opponent, detects wins and draws cleanly with instant restart",
        prompt="Simple classic 3x3 Tic-Tac-Toe game where you click cells as X against a basic O CPU opponent",
        builder=_build_simple_tic_tac_toe,
    ),
    ReferenceGameSpec(
        id="flappy-bird",
        label="Flappy Bird (One-Button)",
        category="platformer",
        controls="Spacebar, Up Arrow, or Click/Tap to flap",
        mechanics="Simple gravity and upward flap impulse through scrolling pipe gaps, +1 per pipe passed",
        prompt="Simple Flappy Bird style game with one-button Space/Click flap control and simple pipe gaps",
        builder=_build_simple_flappy,
    ),
    ReferenceGameSpec(
        id="breakout",
        label="Breakout (Brick Breaker)",
        category="arcade",
        controls="Left/Right arrows, A/D, or Mouse to move paddle",
        mechanics="1 paddle, 1 bouncing ball, 4 rows of colored bricks, 3 lives, clear all bricks to win",
        prompt="Simple classic Breakout brick breaker with basic paddle movement, 1 ball, and 4 brick rows",
        builder=_build_simple_breakout,
    ),
    ReferenceGameSpec(
        id="space-invaders",
        label="Space Invaders (Classic)",
        category="shooter",
        controls="Left/Right arrows to move, Space to shoot",
        mechanics="Grid of simple alien blocks marching left/right and stepping down, basic shots, clear all aliens to win",
        prompt="Simple classic Space Invaders with Left/Right movement, Spacebar laser shots, and marching alien rows",
        builder=_build_simple_space_invaders,
    ),
    ReferenceGameSpec(
        id="memory-match",
        label="Memory Match (Cards)",
        category="puzzle",
        controls="Click or tap cards to flip two at a time",
        mechanics="4x4 grid of 8 emoji pairs, matching pairs stay revealed, track moves until all pairs match",
        prompt="Simple 4x4 Memory Card Match game where clicking flips cards to match 8 pairs in fewest moves",
        builder=_build_simple_memory_match,
    ),
    ReferenceGameSpec(
        id="dino-runner",
        label="Dino Runner (Endless Jump)",
        category="platformer",
        controls="Space, Up Arrow, or Click/Tap to jump",
        mechanics="Runner on a ground line jumping over approaching obstacle blocks with basic gravity and score counter",
        prompt="Simple Dino endless runner game with Space/Click jump control over approaching blocks",
        builder=_build_simple_dino_runner,
    ),
]

REFERENCE_GAME_MAP: Dict[str, ReferenceGameSpec] = {spec.id: spec for spec in REFERENCE_GAMES}


def get_reference_spec(ref_id: Optional[str]) -> Optional[ReferenceGameSpec]:
    """Lookup a reference game spec by ID."""
    if not ref_id:
        return None
    return REFERENCE_GAME_MAP.get(ref_id.strip().lower())


def build_simple_reference_game(ref_id: str) -> Optional[str]:
    """Compile the guaranteed simple runnable HTML5 version of a reference game."""
    spec = get_reference_spec(ref_id)
    if spec is None:
        return None
    return spec.builder()
