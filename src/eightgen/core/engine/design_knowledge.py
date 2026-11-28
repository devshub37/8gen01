"""Curated game-design knowledge distilled from proven games.

The generator cannot browse the web at runtime, so this module carries the
useful part of that research: compact, concrete controls and physics tuning
inspired by genre-defining games.  The briefs below are starting points, not
rules — the model is told to adapt the numbers to the requested fantasy while
keeping the same *feel* and input contract.

Keeping this data local also means generation stays deterministic, offline,
and free of third-party API keys.  ``sources`` records where the ideas come
from so the corpus can be reviewed and extended over time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class DesignSpec:
    """A compact design brief for one game genre."""

    id: str
    label: str
    category: str
    keywords: Tuple[str, ...]
    reference_ids: Tuple[str, ...]
    inspirations: Tuple[str, ...]
    sources: Tuple[str, ...]
    controls: Tuple[str, ...]
    physics: Tuple[str, ...]
    mechanics: Tuple[str, ...]
    level_design: Tuple[str, ...]
    feel: Tuple[str, ...]
    avoid: Tuple[str, ...]


_PLATFORMER = DesignSpec(
    id="platformer",
    label="Precision platformer",
    category="platformer",
    keywords=(
        "platformer", "platform", "jump", "jumping", "double jump", "wall jump",
        "mario", "celeste", "metroidvania", "side scroller", "side-scroller",
        "hollow knight", "ori", "pixel art", "spikes", "checkpoint",
    ),
    reference_ids=(),
    inspirations=("Super Mario Bros.", "Celeste", "Hollow Knight", "Ori and the Blind Forest"),
    sources=(
        "https://en.wikipedia.org/wiki/Super_Mario_Bros.",
        "https://en.wikipedia.org/wiki/Celeste_(video_game)",
        "https://en.wikipedia.org/wiki/Hollow_Knight",
    ),
    controls=(
        "A/D or Left/Right = run; Space/W/Up = jump; hold jump for a higher arc; Shift = dash (if the prompt asks for one).",
        "Touch: left/right buttons plus a large jump button; never require a keyboard on mobile.",
        "Pause on P/Escape and on window blur; R restarts instantly from the game-over overlay.",
        "Call preventDefault() for arrows and Space so the page never scrolls while playing.",
    ),
    physics=(
        "Use a fixed 1/60 s timestep with an accumulator (max 5 steps per frame) and clamp frame delta to 0.05 s.",
        "Starting tuning at 800x600: gravity 2200 px/s^2, jump impulse -760 px/s, max fall 1200 px/s, run speed 320 px/s.",
        "Ground acceleration 2400 px/s^2, air acceleration 1600 px/s^2, ground friction 3000 px/s^2; stop instantly when input is released at low speed.",
        "Coyote time 0.10 s after leaving a ledge and jump buffering 0.12 s before landing; releasing jump early cuts upward velocity to 50%.",
        "Resolve collisions axis-by-axis against solid tiles/platforms (move X, resolve; move Y, resolve) so corners never tunnel.",
        "Use a slightly forgiving player hitbox (about 80% of the sprite) and separate hurtboxes for enemies.",
    ),
    mechanics=(
        "Core loop: traverse a short handcrafted level, collect coins, avoid spikes/enemies, reach a goal flag, then loop with a harder remix.",
        "Include at least one moving platform, one patrol enemy with a readable telegraph, and one optional risk/reward collectible.",
        "Checkpoint at the midpoint; death respawns there in under 1 second and never resets the whole run.",
        "Add a visible timer or coin counter, a best score, and a clear win overlay with instant restart.",
    ),
    level_design=(
        "Teach one verb at a time: safe run -> jump gap -> jump onto a platform -> avoid a slow enemy -> combine under light pressure.",
        "Use a 32 px tile grid, 3-5 screens of content, and a camera with a small dead zone that follows the player smoothly.",
        "Place hazards so the player can see them at least 0.5 s before they matter; never spawn an enemy on top of the player.",
        "Add landmarks and parallax layers so motion and depth are readable.",
    ),
    feel=(
        "Squash/stretch the player 10-15% on jump/land, spawn dust on landing, and add 2-4 px screen shake on a hard landing.",
        "Add 40-60 ms hitstop on enemy hits, a brief invulnerability flash, and a clear audio cue for jump, coin, hurt, and goal.",
        "Keep the first playable frame under 1 s: show the level immediately, with a small 'press a key / tap to start' prompt.",
    ),
    avoid=(
        "Do not use floaty gravity, instant direction changes in the air, or one-frame death pits with no telegraph.",
        "Do not require pixel-perfect jumps on the first screen; the opening must be forgiving.",
        "Do not put the player in a state where they can get stuck against a wall or ceiling.",
    ),
)

_TWIN_STICK = DesignSpec(
    id="twin-stick",
    label="Twin-stick / arena shooter",
    category="shooter",
    keywords=(
        "twin stick", "twin-stick", "arena shooter", "top down shooter", "top-down shooter",
        "geometry wars", "vampire survivors", "bullet hell", "survivor", "horde",
        "wave shooter", "roguelite", "auto aim", "auto-aim",
    ),
    reference_ids=(),
    inspirations=("Geometry Wars", "Vampire Survivors", "Enter the Gungeon", "Nuclear Throne"),
    sources=(
        "https://en.wikipedia.org/wiki/Geometry_Wars",
        "https://en.wikipedia.org/wiki/Vampire_Survivors",
        "https://en.wikipedia.org/wiki/Enter_the_Gungeon",
    ),
    controls=(
        "WASD/arrows = move; mouse aim + left click or Space = fire; right stick on gamepad if available.",
        "Touch: virtual left stick to move, right stick (or drag-to-aim) to shoot; auto-fire when the right stick is held.",
        "Shift/Space = dash with a short cooldown; show the cooldown as a ring around the player.",
        "Pause on Escape/P and on blur; R restarts; show the control legend on the start overlay.",
    ),
    physics=(
        "Use a fixed 1/60 s timestep with delta clamping; move entities with velocity * dt, not per-frame pixel constants.",
        "Player speed 260 px/s, dash 520 px/s for 0.15 s with 0.8 s cooldown; add 0.1 s of post-dash invulnerability.",
        "Bullet speed 900 px/s, fire rate 6-8 shots/s, bullet lifetime 1.2 s; use circle-vs-circle collision for reliability.",
        "Enemy separation steering (small repulsion force) prevents clumping and makes crowds readable.",
        "Knockback enemies 20-40 px on hit; scale hitstop to 30-50 ms and screen shake to 2-6 px.",
    ),
    mechanics=(
        "Core loop: survive escalating waves, collect XP/gems, choose one of three upgrades every level, die -> instant retry.",
        "Enemy roles: chaser (fast, weak), shooter (telegraphed projectile), tank (slow, high HP), splitter (spawns two small ones).",
        "Spawn waves on a 20-30 s cadence with a visible 'wave incoming' banner and a short breather between waves.",
        "Give the player one meaningful choice per upgrade (damage, fire rate, move speed, pierce, orbit drone) and cap the run at 8-12 minutes.",
        "Auto-aim assist of about 10 degrees makes touch and gamepad play feel fair without removing skill.",
    ),
    level_design=(
        "Use one readable arena with a few cover blocks and clear spawn lanes; keep the playfield free of unreadable clutter.",
        "Telegraph every ranged attack for at least 0.35 s with a line, flash, or growing circle.",
        "Spawn enemies just outside the camera edge, never inside the player's safety radius.",
        "Add a minimap or edge indicators only if the arena is larger than one screen.",
    ),
    feel=(
        "Muzzle flash, shell/particle burst, hit flash, floating damage numbers, and a bass thump on every kill.",
        "Add a short slow-motion pulse (0.15 s at 30% speed) when the player clears a wave or picks a rare upgrade.",
        "Make the player's silhouette and bullets the brightest things on screen; desaturate the background.",
    ),
    avoid=(
        "Do not let enemies stack into a single invisible blob; use separation and spawn spacing.",
        "Do not make the player stop moving to shoot; moving and shooting must feel simultaneous.",
        "Do not hide projectiles behind particles or UI.",
    ),
)

_SPACE_SHOOTER = DesignSpec(
    id="space-shooter",
    label="Arcade space shooter",
    category="shooter",
    keywords=(
        "space invaders", "galaga", "space shooter", "spaceship", "asteroids",
        "alien", "invaders", "laser", "starfighter", "shmup", "vertical shooter",
    ),
    reference_ids=("space-invaders",),
    inspirations=("Space Invaders", "Galaga", "Asteroids", "Ikaruga"),
    sources=(
        "https://en.wikipedia.org/wiki/Space_Invaders",
        "https://en.wikipedia.org/wiki/Galaga",
        "https://en.wikipedia.org/wiki/Asteroids_(video_game)",
    ),
    controls=(
        "A/D or Left/Right = move; Space or left click = fire; mouse/touch drag can also steer.",
        "Touch: drag anywhere on the lower half to move; auto-fire while touching, or a dedicated fire button.",
        "Pause on P/Escape and on blur; Space/click restarts from the game-over screen.",
        "Call preventDefault() for arrows and Space.",
    ),
    physics=(
        "Fixed 1/60 s timestep; player speed 420 px/s, fire rate 8 shots/s, bullet speed 900 px/s.",
        "Enemy formation drifts at 40-80 px/s and dives at 180-260 px/s; accelerate dives with a visible wind-up.",
        "Use swept collision for fast bullets (segment vs circle) so shots never tunnel through thin enemies.",
        "Player hitbox is a small core (about 6 px), not the whole ship sprite; this is the classic shmup fairness rule.",
    ),
    mechanics=(
        "Core loop: clear formations, dodge descending fire, collect power-ups, beat a boss every 3-4 waves.",
        "Enemy roles: formation grunt, diving kamikaze, shielded tank, turret that fires aimed shots.",
        "Power-ups: spread shot, shield, fire-rate boost; drop one every 12-18 kills and despawn after 8 s.",
        "Score combos for consecutive kills without getting hit; show a multiplier and a brief chain-break flash.",
    ),
    level_design=(
        "Use a starfield with 2-3 parallax layers; keep the playfield 800x600 or a 4:3 canvas scaled to fit.",
        "Introduce one enemy type at a time for the first 20 s, then combine.",
        "Boss telegraphs each pattern for 0.6 s and has 3 distinct phases with a health bar.",
    ),
    feel=(
        "Muzzle flash, bullet trails, explosion rings, screen shake 4-8 px, and a short hitstop on boss hits.",
        "Add a subtle zoom punch on player death and a clear 'MISSION FAILED' overlay with score and restart.",
        "Use Web Audio oscillator sweeps for lasers and noise bursts for explosions.",
    ),
    avoid=(
        "Do not make enemy bullets the same color/size as the player's bullets.",
        "Do not spawn bullets directly on top of the player.",
        "Do not let the player's ship cover the bottom 20% of the screen.",
    ),
)

_SNAKE = DesignSpec(
    id="snake",
    label="Grid snake",
    category="arcade",
    keywords=("snake", "slither", "worm", "tail", "fruit", "grid", "grow", "nokia"),
    reference_ids=("snake",),
    inspirations=("Snake", "Slither.io", "Nokia Snake", "Google Snake"),
    sources=(
        "https://en.wikipedia.org/wiki/Snake_(video_game_genre)",
        "https://en.wikipedia.org/wiki/Slither.io",
    ),
    controls=(
        "Arrows or WASD = turn; queue up to 2 turns so fast inputs are never lost; reject 180-degree reversals.",
        "Touch: swipe in the direction you want to turn; also support four on-screen direction buttons for accessibility.",
        "Space/P = pause; R or Space on game-over = restart; preventDefault() for arrows.",
    ),
    physics=(
        "Grid step every 120 ms at the start, speeding up by 3 ms per food to a floor of 65 ms.",
        "Interpolate the snake's rendered position between grid cells (t = elapsed / step) so movement looks smooth.",
        "Only apply one queued direction per tick; never let a single tick consume two turns.",
        "Spawn food uniformly on free cells; if the board is nearly full, fall back to any free cell and show a win state.",
    ),
    mechanics=(
        "Core loop: eat food -> grow +1 -> score +10 -> speed up; die on wall or self-collision.",
        "Add one special golden fruit every 5 foods worth +50 and a brief slow-motion pickup.",
        "Show score, high score, and length; persist the high score in a try/catch-wrapped localStorage.",
        "Add a short grace period (one tick) after eating so the new tail segment cannot instantly kill you.",
    ),
    level_design=(
        "Use a 20x20 to 28x28 grid with a clear border; if wrapping is requested, make the wrap visually obvious.",
        "Keep the board uncluttered; draw a subtle grid and a high-contrast head with eyes showing direction.",
        "Scale the canvas to fit the viewport while preserving square cells.",
    ),
    feel=(
        "Pop particles and a rising tone on eat; screen shake 2-4 px on death; smooth head rotation.",
        "Add a short 'buffering' glow when a turn is queued so input feels responsive.",
        "Use a distinct color for the head, a gradient body, and a pulsing food sprite.",
    ),
    avoid=(
        "Do not read input directly inside the tick in a way that drops quick double-turns.",
        "Do not spawn food under the snake or on the border.",
        "Do not use a variable timestep that makes speed depend on monitor refresh rate.",
    ),
)

_BREAKOUT = DesignSpec(
    id="breakout",
    label="Breakout / brick breaker",
    category="arcade",
    keywords=("breakout", "brick", "breaker", "arkanoid", "paddle", "ball", "bricks"),
    reference_ids=("breakout",),
    inspirations=("Breakout", "Arkanoid", "DX Ball", "Wizorb"),
    sources=(
        "https://en.wikipedia.org/wiki/Breakout_(video_game)",
        "https://en.wikipedia.org/wiki/Arkanoid",
    ),
    controls=(
        "A/D or Left/Right = move paddle; mouse/touch drag also moves it; Space launches the ball.",
        "Touch: drag horizontally anywhere on the canvas; keep the paddle under the finger with an offset so it is visible.",
        "P/Escape = pause; Space/click = launch/restart; preventDefault() for arrows and Space.",
    ),
    physics=(
        "Fixed 1/60 s timestep; paddle 100x14 at 620 px/s; ball starts at 360 px/s and gains 3% per paddle hit, capped at 620 px/s.",
        "Paddle bounce angle: map hit offset (-1..1) to -60..+60 degrees; add a small amount of 'english' from paddle motion.",
        "Use swept/continuous collision against bricks and walls to prevent tunneling at high speed.",
        "Reflect only once per frame per brick; nudge the ball out of the brick before flipping velocity.",
        "Ball radius 8 px, paddle hitbox slightly wider than the sprite, and a 0.15 s launch delay.",
    ),
    mechanics=(
        "Core loop: clear all bricks, keep the ball alive, collect power-ups, clear the wave, repeat with a new layout.",
        "Power-ups: multiball, wider paddle, sticky paddle, laser; drop chance 12-18% and despawn after 8 s.",
        "3 lives, score per brick by row, combo multiplier for consecutive bricks without touching the paddle.",
        "Add a visible aim guide for the first 2 seconds after launch.",
    ),
    level_design=(
        "Start with 5 rows x 8 columns, then introduce gaps, indestructible blocks, and moving bricks in later waves.",
        "Keep the top 25% of the screen for bricks and the bottom 20% for the paddle; avoid clutter in the ball's path.",
        "Use color-coded brick HP and a subtle crack overlay so damage is readable.",
    ),
    feel=(
        "Brick pop particles, a rising pitch per brick in a combo, paddle squash, and 2-4 px screen shake on a lost ball.",
        "Add a short hitstop (20-30 ms) on brick break and a bright trail on the ball.",
        "Show 'READY' then 'GO' so the player is never surprised by the launch.",
    ),
    avoid=(
        "Do not let the ball get stuck in a horizontal bounce loop; add a small angle jitter when |vy| is too small.",
        "Do not make the paddle leave the screen or the ball spawn inside a brick.",
        "Do not use frame-count movement; use dt.",
    ),
)

_FLAPPY = DesignSpec(
    id="flappy",
    label="One-button flyer",
    category="arcade",
    keywords=("flappy", "flap", "pipe", "bird", "drone", "helicopter", "one button", "one-button", "copter"),
    reference_ids=("flappy-bird",),
    inspirations=("Flappy Bird", "Jetpack Joyride", "Helicopter Game"),
    sources=(
        "https://en.wikipedia.org/wiki/Flappy_Bird",
        "https://en.wikipedia.org/wiki/Jetpack_Joyride",
    ),
    controls=(
        "Space/Up/left click/tap = flap; one input, zero ambiguity.",
        "Touch: tap anywhere on the canvas; add a large invisible tap target over the whole play area.",
        "P/Escape = pause; tap/Space on game-over = instant restart; preventDefault() for Space/Up.",
    ),
    physics=(
        "Fixed 1/60 s timestep; gravity 1800 px/s^2, flap impulse -520 px/s, max fall 900 px/s.",
        "Scroll speed 220 px/s, pipe gap 170-210 px (shrink slowly with score), spawn every 1.6 s.",
        "Use an 80% forgiving collision hitbox and a 0.08 s grace period after passing a pipe.",
        "Clamp the bird/drone inside the top/bottom bounds with a bounce or death, never let it leave the canvas.",
    ),
    mechanics=(
        "Core loop: flap through gaps, score +1 per pipe, die on collision, instant retry.",
        "Add a small collectible in 20% of gaps for risk/reward and a brief speed-up every 10 points.",
        "Show score and best score; persist best in a try/catch-wrapped localStorage.",
        "Add a 'get ready' state with a gentle hover before the first flap.",
    ),
    level_design=(
        "Use a 420x480 or 480x640 portrait-friendly canvas scaled to fit; keep the flight lane centered.",
        "Vary gap heights but never place two hard gaps back-to-back in the first 10 seconds.",
        "Add parallax clouds/city silhouettes and a ground line for speed readability.",
    ),
    feel=(
        "Wing/thruster particles on flap, rotation based on velocity, and a satisfying 'whoosh' sound.",
        "Add 3-6 px screen shake and a flash on death; show a clear score card with a restart button.",
        "Use a bright player silhouette against a muted background.",
    ),
    avoid=(
        "Do not make the hitbox the full sprite; players must feel the near-miss.",
        "Do not spawn pipes with an impossible gap or directly at the player's altitude.",
        "Do not require a click on a tiny button; the whole canvas is the control.",
    ),
)

_RUNNER = DesignSpec(
    id="runner",
    label="Endless runner",
    category="platformer",
    keywords=("runner", "endless", "dino", "subway", "obstacle", "run", "sprint", "lane", "auto-run"),
    reference_ids=("dino-runner",),
    inspirations=("Chrome Dino", "Subway Surfers", "Jetpack Joyride", "Canabalt"),
    sources=(
        "https://en.wikipedia.org/wiki/Dinosaur_Game",
        "https://en.wikipedia.org/wiki/Subway_Surfers",
        "https://en.wikipedia.org/wiki/Canabalt",
    ),
    controls=(
        "Space/Up/left click/tap = jump; Down = slide/duck; hold jump for a slightly higher arc.",
        "Touch: tap to jump, swipe down to slide; keep both gestures forgiving.",
        "P/Escape = pause; R or Space on game-over = restart; preventDefault() for arrows/Space.",
    ),
    physics=(
        "Fixed 1/60 s timestep; gravity 2200 px/s^2, jump impulse -780 px/s, max fall 1300 px/s.",
        "Scroll speed starts at 300 px/s and ramps to 650 px/s over 90 s; obstacle spacing scales with speed.",
        "Coyote time 0.08 s and jump buffer 0.10 s; allow a short double-jump only if the prompt asks for it.",
        "Use AABB collision with a slightly inset player hitbox; never spawn an obstacle inside the jump arc's landing zone.",
    ),
    mechanics=(
        "Core loop: auto-run, jump/slide over obstacles, score by distance, collect coins, die -> instant retry.",
        "Introduce one obstacle type at a time: low block -> high block -> gap -> moving obstacle.",
        "Add a coin trail that teaches the jump arc and a magnet power-up as a rare reward.",
        "Show distance, coins, and best; persist best in a try/catch-wrapped localStorage.",
    ),
    level_design=(
        "Use a side-view 800x450 canvas with a strong ground line and 2-3 parallax layers.",
        "Guarantee a safe landing zone after every obstacle; never require a jump immediately after landing.",
        "Increase difficulty through speed and pattern density, not by shrinking reaction time below 0.35 s.",
    ),
    feel=(
        "Dust on landing, a small squash on jump, and a speed-line effect as the run accelerates.",
        "Add a near-miss slow-motion pulse (0.1 s) and a satisfying coin chime.",
        "Keep the player's feet visible and the obstacle silhouettes high-contrast.",
    ),
    avoid=(
        "Do not spawn obstacles off-screen at a height that is impossible to react to.",
        "Do not let the player jump infinitely or buffer a jump through death.",
        "Do not use a fixed obstacle timer that ignores the current scroll speed.",
    ),
)

_RACING = DesignSpec(
    id="racing",
    label="Arcade racing",
    category="racing",
    keywords=("racing", "race", "car", "kart", "drift", "lap", "track", "rally", "speedway", "vehicle"),
    reference_ids=(),
    inspirations=("Mario Kart", "Micro Machines", "Trackmania", "OutRun"),
    sources=(
        "https://en.wikipedia.org/wiki/Mario_Kart",
        "https://en.wikipedia.org/wiki/Micro_Machines",
        "https://en.wikipedia.org/wiki/Trackmania",
    ),
    controls=(
        "W/Up = accelerate; S/Down = brake/reverse; A/D or Left/Right = steer; Space = handbrake/drift.",
        "Touch: left/right steering zones plus gas/brake buttons; optional tilt steering with a calibration toggle.",
        "P/Escape = pause; R = restart; preventDefault() for arrows/Space.",
    ),
    physics=(
        "Fixed 1/60 s timestep; top speed 520 px/s, acceleration 600 px/s^2, brake 900 px/s^2, reverse cap 160 px/s.",
        "Steering angle scales down with speed; lateral grip 0.85 on tarmac and 0.55 on grass; handbrake reduces grip for drift.",
        "Use a simple bicycle model: heading += steer * speed * turnRate * dt; velocity = forward * speed + lateral * slip.",
        "Collision with track edges kills speed by 40% and emits sparks; never let the car tunnel through walls.",
    ),
    mechanics=(
        "Core loop: complete 3 laps, hit checkpoints in order, beat a ghost/AI time, unlock a faster car.",
        "Add drift boost: hold handbrake through a corner for 0.8 s to earn a 1.2 s speed boost.",
        "Place pickups on the racing line and obstacles off it; rubber-band the AI mildly so the race stays close.",
        "Show speed, lap, position, and best lap; countdown 3-2-1-GO before control unlocks.",
    ),
    level_design=(
        "Use a top-down track with clear edges, checkpoint gates, and a minimap; keep the camera centered on the car with look-ahead.",
        "Teach acceleration -> braking -> cornering -> drift in the first lap with wide, forgiving corners.",
        "Use visual cues (arrows, tire marks) for the racing line and brake zones.",
    ),
    feel=(
        "Tire smoke on drift, speed lines at high velocity, engine pitch tied to speed, and 2-5 px screen shake on collisions.",
        "Add a brief FOV/zoom punch on boost and a skid sound on hard braking.",
        "Keep the car sprite readable from above and show a shadow for height.",
    ),
    avoid=(
        "Do not use tank controls; steering must feel immediate at low speed and stable at high speed.",
        "Do not let the AI teleport or ignore track collisions.",
        "Do not make the camera lag so far that the car leaves the screen.",
    ),
)

_PUZZLE = DesignSpec(
    id="puzzle",
    label="Puzzle / match game",
    category="puzzle",
    keywords=("puzzle", "match", "tetris", "2048", "bejeweled", "candy", "blocks", "grid", "logic", "memory", "card", "sudoku", "minesweeper"),
    reference_ids=("tic-tac-toe", "memory-match"),
    inspirations=("Tetris", "2048", "Bejeweled", "Threes"),
    sources=(
        "https://en.wikipedia.org/wiki/Tetris",
        "https://en.wikipedia.org/wiki/2048_(video_game)",
        "https://en.wikipedia.org/wiki/Bejeweled",
    ),
    controls=(
        "Mouse/touch = select and swap/drag; keyboard arrows = move selection, Space/Enter = confirm.",
        "Touch targets must be at least 44x44 px; support tap-tap as well as drag.",
        "P/Escape = pause; R = restart; preventDefault() for arrows/Space.",
    ),
    physics=(
        "Use a fixed logical grid with animated transitions; lock input during a 120-180 ms swap/fall animation.",
        "For Tetris-like games: 7-bag randomizer, lock delay 0.5 s, DAS 0.17 s, ARR 0.05 s, ghost piece.",
        "For match-3: detect matches after the swap settles, cascade with a 0.15 s delay, and refill from the top.",
        "For 2048: slide/merge each tile once per move, then spawn a new tile; animate with easing, not instant teleport.",
    ),
    mechanics=(
        "Core loop: make a valid move -> resolve matches/merges -> score/combo -> check for no-moves -> shuffle or game over.",
        "Guarantee at least one legal move after every cascade; if none exists, shuffle with a visible animation.",
        "Add a hint after 8 s of inactivity and a clear restart button; never punish exploration.",
        "Track score, best, combo, and moves; show a satisfying cascade multiplier.",
    ),
    level_design=(
        "Center the board, keep a consistent cell size, and use color plus shape/icons so colorblind players can read it.",
        "Start with a gentle board that has an obvious first move; introduce one new mechanic every 2-3 minutes.",
        "Avoid tiny text and crowded HUD; the board is the hero.",
    ),
    feel=(
        "Tile pop/scale, particle sparkle on combos, a rising pitch per cascade, and 1-2 px screen shake on big matches.",
        "Add a subtle board shake and a 'no moves' banner before shuffling.",
        "Use easing curves for swaps and falls so the board feels physical.",
    ),
    avoid=(
        "Do not allow input during animations or double-apply a swap.",
        "Do not spawn a board with no legal moves.",
        "Do not rely on color alone to communicate tile types.",
    ),
)

_FIGHTING = DesignSpec(
    id="fighting",
    label="Fighting / beat-em-up",
    category="action",
    keywords=("fighting", "fighter", "beat em up", "beat-em-up", "combat", "punch", "kick", "combo", "street fighter", "mortal kombat", "brawler"),
    reference_ids=(),
    inspirations=("Street Fighter II", "Castle Crashers", "Streets of Rage", "Super Smash Bros."),
    sources=(
        "https://en.wikipedia.org/wiki/Street_Fighter_II",
        "https://en.wikipedia.org/wiki/Castle_Crashers",
        "https://en.wikipedia.org/wiki/Streets_of_Rage",
    ),
    controls=(
        "A/D = move, W = jump, S = crouch/block; J = light attack, K = heavy attack, L = block/parry.",
        "Touch: left virtual stick + three large buttons (light, heavy, block); never require simultaneous precision taps.",
        "P/Escape = pause; R = restart; preventDefault() for arrows/Space.",
    ),
    physics=(
        "Run combat at a fixed 60 Hz; use frame data: light 3-frame startup / 3 active / 8 recovery, heavy 7/4/14.",
        "Hitstop 50-70 ms on hit, blockstun 8-12 frames, and 6-frame input buffer for specials.",
        "Use separate hurtboxes and hitboxes; draw debug boxes behind a flag, not in the shipped game.",
        "Apply knockback with friction; clamp to the arena and never let fighters overlap.",
    ),
    mechanics=(
        "Core loop: approach -> poke -> confirm into combo -> knock down -> pressure; best of 3 rounds.",
        "Give each fighter 3 specials with clear startup telegraphs and a cooldown/resource cost.",
        "Add a parry window (3 frames) with a satisfying flash and a punish opportunity.",
        "Show health bars, round pips, combo counter, and a dramatic KO slow-motion.",
    ),
    level_design=(
        "Use a single flat arena with a clear floor line and parallax background; keep both fighters on screen.",
        "Add walls/ropes that bounce on knockback and a camera that frames both fighters.",
        "Teach one combo in the intro and show move hints on the pause screen.",
    ),
    feel=(
        "Hit sparks, impact freeze, screen shake 4-8 px, and a bass hit sound on every connect.",
        "Add a brief zoom on super moves and a slow-motion KO.",
        "Make attack animations readable: anticipation, active, recovery.",
    ),
    avoid=(
        "Do not use floaty jump arcs or allow infinite combos without scaling.",
        "Do not make blocking automatic; it must be a deliberate choice.",
        "Do not hide the hitboxes so players cannot understand why they were hit.",
    ),
)

_TOWER_DEFENSE = DesignSpec(
    id="tower-defense",
    label="Tower defense",
    category="strategy",
    keywords=("tower defense", "tower defence", "td", "waves", "creeps", "path", "strategy", "base defense", "plants vs zombies"),
    reference_ids=(),
    inspirations=("Kingdom Rush", "Plants vs. Zombies", "Bloons TD", "Desktop Tower Defense"),
    sources=(
        "https://en.wikipedia.org/wiki/Kingdom_Rush",
        "https://en.wikipedia.org/wiki/Plants_vs._Zombies",
        "https://en.wikipedia.org/wiki/Bloons_TD",
    ),
    controls=(
        "Mouse/touch: click a tower, then a valid build spot; click an enemy to inspect; Space = start next wave.",
        "Keyboard: 1-4 select tower, Esc cancel, Space start wave, P pause.",
        "Show range previews and invalid-placement feedback before committing.",
    ),
    physics=(
        "Use a fixed path with waypoints; enemies move at constant speed along the path, never cut corners.",
        "Projectiles home with a max turn rate or travel in a straight line; use swept collision.",
        "Tower range is a circle; show it while placing and when selected.",
        "Wave budget grows by 15-25% per wave; enemy HP scales faster than damage so upgrades matter.",
    ),
    mechanics=(
        "Core loop: earn gold -> build/upgrade towers -> survive a wave -> repeat; leak lives on escape.",
        "Tower roles: single-target DPS, splash, slow, support/buff; each has a clear counter-enemy.",
        "Add a wave preview, a speed-up toggle, and a sell/upgrade panel with exact numbers.",
        "Give the player a meaningful choice between economy (more gold) and defense (more damage).",
    ),
    level_design=(
        "Use one readable path with 2-3 build clusters and a clear spawn/exit; avoid maze-breaking unless the prompt asks for it.",
        "Place the first build spot near the spawn so the tutorial is immediate.",
        "Use color and silhouette to distinguish enemy armor types; show a health bar only when damaged.",
    ),
    feel=(
        "Projectile impacts, coin pops, tower upgrade flashes, and a satisfying wave-clear horn.",
        "Add a fast-forward toggle for experienced players and a pause while placing.",
        "Show floating damage/gold numbers and a clear 'wave incoming' banner.",
    ),
    avoid=(
        "Do not allow unwinnable placements with no refund; always allow sell at 70-80% value.",
        "Do not hide enemy pathing or spawn timing.",
        "Do not let one tower type dominate every wave.",
    ),
)

_ADVENTURE = DesignSpec(
    id="adventure",
    label="Top-down adventure / RPG",
    category="adventure",
    keywords=("rpg", "adventure", "zelda", "dungeon", "quest", "inventory", "explore", "open world", "stardew", "pokemon", "top down", "top-down"),
    reference_ids=(),
    inspirations=("The Legend of Zelda", "Stardew Valley", "Pokemon", "Hades"),
    sources=(
        "https://en.wikipedia.org/wiki/The_Legend_of_Zelda",
        "https://en.wikipedia.org/wiki/Stardew_Valley",
        "https://en.wikipedia.org/wiki/Hades_(video_game)",
    ),
    controls=(
        "WASD/arrows = move; Space/J = attack/interact; E = inventory; Shift = dash/run.",
        "Touch: virtual stick + action/interact buttons; tap-to-move is optional, never mandatory.",
        "P/Escape = pause/menu; preventDefault() for arrows/Space.",
    ),
    physics=(
        "Use a fixed 1/60 s timestep; walk speed 180 px/s, run 300 px/s, dash 520 px/s for 0.12 s with 0.7 s cooldown.",
        "Use tile-based collision with a small inset hitbox; slide along walls instead of sticking.",
        "Attack hitboxes are short-lived (0.1-0.15 s) and offset in the facing direction; add 40 ms hitstop.",
        "Camera follows with a dead zone and clamps to room bounds; never show outside the map.",
    ),
    mechanics=(
        "Core loop: explore -> fight -> collect key/item -> unlock shortcut/boss -> repeat.",
        "Include one NPC with a short quest, one optional treasure, and one boss with a readable pattern.",
        "Inventory with 3-5 items max; each item solves a visible problem (key, bomb, dash, heal).",
        "Save progress in a try/catch-wrapped localStorage with a version key.",
    ),
    level_design=(
        "Use one compact dungeon or village with clear landmarks; teach mechanics through layout, not text walls.",
        "Place a save/heal point before the boss and a shortcut back to the start.",
        "Use lighting/color to guide the eye toward the objective.",
    ),
    feel=(
        "Sword slash arc, hit flash, knockback, coin sparkle, and a short dungeon-clear fanfare.",
        "Add footstep dust, grass rustle, and a subtle screen shake on heavy hits.",
        "Keep the player sprite readable at small sizes and show facing direction.",
    ),
    avoid=(
        "Do not make the player walk through walls or get stuck on tile corners.",
        "Do not hide the objective with no hint; use a marker or NPC line.",
        "Do not front-load a long dialogue before the first playable moment.",
    ),
)

_ARCADE = DesignSpec(
    id="arcade",
    label="Arcade action",
    category="arcade",
    keywords=("arcade", "action", "score", "high score", "retro", "classic", "fast", "dodge", "collect"),
    reference_ids=(),
    inspirations=("Pac-Man", "Space Invaders", "Geometry Wars", "Vampire Survivors"),
    sources=(
        "https://en.wikipedia.org/wiki/Pac-Man",
        "https://en.wikipedia.org/wiki/Space_Invaders",
        "https://en.wikipedia.org/wiki/Geometry_Wars",
    ),
    controls=(
        "Arrows/WASD = move; Space/click = action; P/Escape = pause; R = restart.",
        "Touch: virtual stick or drag-to-move plus a large action button; never require a keyboard.",
        "Show the control legend on the start overlay and call preventDefault() for arrows/Space.",
    ),
    physics=(
        "Use a fixed 1/60 s timestep with delta clamping; express speeds in px/s, not px/frame.",
        "Use circle or AABB collision with a slightly forgiving player hitbox; add 0.5 s of spawn invulnerability.",
        "Clamp entities to the playfield and resolve collisions before rendering.",
        "Add a short hitstop (30-50 ms) and 2-6 px screen shake on impact.",
    ),
    mechanics=(
        "Core loop: move -> collect/avoid -> score -> escalate difficulty -> die -> instant retry.",
        "Introduce one new hazard/collectible every 20-30 s; keep the first 10 s safe and teachable.",
        "Show score, high score, and a clear game-over overlay with restart.",
        "Add a combo or multiplier so skilled play is rewarded.",
    ),
    level_design=(
        "Use a single readable arena with a strong silhouette and 2-3 parallax layers.",
        "Keep the playfield free of HUD overlap and off-screen spawns.",
        "Telegraph every hazard for at least 0.3 s.",
    ),
    feel=(
        "Particles, screen shake, pitch-rising combo sounds, and a satisfying game-over sting.",
        "Make the player the brightest object and keep enemy projectiles high-contrast.",
        "Add a brief slow-motion pulse on a big score or near miss.",
    ),
    avoid=(
        "Do not spawn hazards on top of the player.",
        "Do not use frame-dependent movement.",
        "Do not hide the restart control.",
    ),
)

_PONG = DesignSpec(
    id="pong",
    label="Paddle duel / Pong",
    category="arcade",
    keywords=("pong", "air hockey", "table tennis", "ping pong", "paddle duel"),
    reference_ids=("pong",),
    inspirations=("Pong", "Windjammers", "Curveball", "Air Hockey"),
    sources=(
        "https://en.wikipedia.org/wiki/Pong",
        "https://en.wikipedia.org/wiki/Air_hockey",
    ),
    controls=(
        "W/S or Up/Down = move paddle; mouse/touch Y-drag moves paddle directly for responsive precision.",
        "Space = serve ball / pause-resume; R = reset match; preventDefault() for arrows and Space.",
        "On touch screens, dragging anywhere on the player's half smoothly moves the paddle.",
    ),
    physics=(
        "Fixed 1/60 s timestep with delta clamping; paddle speed 480 px/s, ball starts at 360 px/s and gains +24 px/s per rally hit up to 760 px/s.",
        "Deflect ball angle (-55..+55 degrees) from normalized paddle hit offset (-1..1) plus 15% paddle velocity english.",
        "Clamp ball inside top/bottom walls and nudge outside paddle bounds after reflection so it never gets trapped inside a paddle.",
        "Use a fair CPU AI with capped max speed (340 px/s) and slight reaction smoothing instead of perfect tracking.",
    ),
    mechanics=(
        "Core loop: serve -> rally with escalating speed -> score past opponent -> first to 5 or 7 wins.",
        "Add a 0.4 s serve pause with direction indicator before each rally.",
        "Show rally counter, ball speed indicator, and crisp score display.",
    ),
    level_design=(
        "Clean 800x500 arena with dashed center line, glowing court borders, and subtle goal-zone flashes.",
        "Keep HUD outside the paddle/ball lanes so scores never obscure incoming shots.",
    ),
    feel=(
        "Ball trail proportional to speed, paddle flash + micro-squash on hit, 3 px shake on goal, and rising pitch per rally hit.",
        "Synthesize distinct wall-tick, paddle-pop, and goal-horn tones with Web Audio.",
    ),
    avoid=(
        "Do not let CPU AI teleport or match the ball infinitely without human-like speed limits.",
        "Do not allow horizontal stalemate loops; enforce minimum |vx| >= 180 px/s.",
    ),
)

_ASTEROIDS = DesignSpec(
    id="asteroids",
    label="Inertial space rock shooter",
    category="shooter",
    keywords=("asteroids", "asteroid", "thrust", "inertia", "newtonian", "space rock", "screen wrap"),
    reference_ids=(),
    inspirations=("Asteroids", "Geometry Wars", "Nova Drift", "Star Control"),
    sources=(
        "https://en.wikipedia.org/wiki/Asteroids_(video_game)",
        "https://en.wikipedia.org/wiki/Nova_Drift",
    ),
    controls=(
        "A/D or Left/Right = rotate ship; W/Up = forward thrust; Space/Click = fire; Shift/Down = hyperspace or brake.",
        "Touch: left/right steer + thrust/fire buttons, or drag-to-aim with auto-thrust.",
        "P/Escape = pause; R = restart; preventDefault() for arrows and Space.",
    ),
    physics=(
        "Fixed 1/60 s timestep; rotation rate 4.2 rad/s, forward thrust acceleration 460 px/s^2, damping 0.985/tick, max speed 440 px/s.",
        "Wrap ship, bullets, and rocks seamlessly across opposite screen edges (draw ghost copies near edges if large).",
        "Use swept segment-vs-circle collision for bullets (760 px/s, 0.9 s lifetime) and forgiving ship collision radius (75% of triangle).",
        "Splitting large asteroids spawns 2 medium rocks at +/- 35 deg with inherited + perpendicular impulse.",
    ),
    mechanics=(
        "Core loop: rotate, thrust, split large -> medium -> small rocks, dodge UFOs, clear wave with spawn-safe center check.",
        "Grant 2.0 s of invulnerability shield on respawn and never spawn a rock within 120 px of the ship.",
        "3 lives, extra life milestone every 10,000 pts, wave bonus.",
    ),
    level_design=(
        "Open 900x640 starfield arena; start Wave 1 with 4 slow large rocks far from center, scale count and speed per wave.",
    ),
    feel=(
        "Thruster flame particles, crisp vector/neon glow outlines, debris shards on rock split, and deep bass boom.",
    ),
    avoid=(
        "Do not snap velocity immediately to facing angle; preserve true momentum/drift.",
        "Do not spawn new waves directly on top of the player.",
    ),
)

_TETRIS = DesignSpec(
    id="tetris",
    label="Falling-block puzzle",
    category="puzzle",
    keywords=("tetris", "tetromino", "falling blocks", "line clear", "stacker", "block puzzle"),
    reference_ids=(),
    inspirations=("Tetris", "Tetris Effect", "Puyo Puyo Tetris", "Lumines"),
    sources=(
        "https://en.wikipedia.org/wiki/Tetris",
        "https://en.wikipedia.org/wiki/Tetris_Effect",
    ),
    controls=(
        "Left/Right = shift; Up/X = rotate CW; Z = rotate CCW; Down = soft drop; Space = hard drop; C/Shift = hold piece.",
        "Touch: swipe left/right to shift, tap to rotate, swipe down to hard drop, plus optional on-screen buttons.",
        "P/Escape = pause; R = restart; preventDefault() for arrows and Space.",
    ),
    physics=(
        "Fixed 1/60 s loop with DAS 0.17 s, ARR 0.045 s, and 0.50 s lock delay (reset up to 15 moves/rotations on ground).",
        "Use a true 7-bag randomizer so every 7 pieces contain one of each tetromino; never pure uniform random.",
        "Implement wall kicks (test offsets dx in [0, -1, +1, -2, +2]) when rotating near walls or stacks.",
        "Render a translucent ghost piece directly beneath the active piece showing exact hard-drop landing.",
    ),
    mechanics=(
        "Core loop: drop -> lock -> clear full rows (1/2/3/4 lines = Single/Double/Triple/Tetris) -> back-to-back & combo bonuses -> speed level up every 10 lines.",
        "Show Next queue (3 pieces) and Hold slot, plus score, level, lines, and high score in try/catch localStorage.",
    ),
    level_design=(
        "Standard 10x20 visible playfield (plus 2 hidden buffer rows above top) with distinct color + subtle inner bevel per piece.",
    ),
    feel=(
        "Lock flash, line-clear sweep + particle burst, subtle 2 px thud on hard drop, and ascending chord on Tetris/combo.",
    ),
    avoid=(
        "Do not lock pieces instantly on first contact without lock delay.",
        "Do not allow rotation to clip into walls or filled cells.",
    ),
)

_PHYSICS_SLINGSHOT = DesignSpec(
    id="physics-slingshot",
    label="Ballistic / physics sandbox",
    category="puzzle",
    keywords=(
        "angry birds", "slingshot", "catapult", "cannon", "trajectory", "parabolic",
        "pinball", "billiards", "pool", "golf", "mini golf", "ragdoll", "physics", "bounce",
    ),
    reference_ids=(),
    inspirations=("Angry Birds", "Peggle", "Space Cadet Pinball", "8 Ball Pool"),
    sources=(
        "https://en.wikipedia.org/wiki/Angry_Birds_(video_game)",
        "https://en.wikipedia.org/wiki/Peggle",
    ),
    controls=(
        "Pointer/touch drag-to-aim and release to launch (or click/drag cue/launcher); Space = activate mid-air ability / flippers.",
        "Keyboard fallback: Up/Down = adjust angle, Left/Right = adjust power, Space = launch.",
        "P/Escape = pause; R = reset shot/level; preventDefault() for arrows and Space.",
    ),
    physics=(
        "Fixed 1/60 s timestep with 4-8 physics sub-steps per frame so fast balls/projectiles never tunnel through thin bumpers or blocks.",
        "Semi-implicit Euler integration: v += (gravity + forces) * subDt; x += v * subDt; apply linear damping/air drag.",
        "Resolve circle-vs-circle and circle-vs-AABB/segment collisions using restitution (bounce 0.65-0.85) and positional correction (slop + percent).",
        "Draw a dotted parabolic trajectory preview (first 0.6 s of flight) while aiming.",
    ),
    mechanics=(
        "Core loop: aim -> launch -> chain impacts/combo -> settle -> evaluate star/score target -> next stage.",
        "Detect resting state (kinetic energy below threshold for 0.5 s) cleanly so turns never hang.",
    ),
    level_design=(
        "Design 3-5 handcrafted stages with breakable blocks, bouncy bumpers, and clear target silhouettes.",
    ),
    feel=(
        "Impact sparks scaled by collision impulse, camera follow on projectile, hitstop on big breaks, and pitched marimba/chime combos.",
    ),
    avoid=(
        "Do not run single-step collision on fast balls/flippers where tunneling causes ghost pass-throughs.",
        "Do not trap the turn waiting forever for a micro-jittering body to stop.",
    ),
)

_RHYTHM = DesignSpec(
    id="rhythm",
    label="Audio-synced rhythm game",
    category="arcade",
    keywords=("rhythm", "beat", "bpm", "music", "guitar hero", "ddr", "dance", "piano tiles", "tempo"),
    reference_ids=(),
    inspirations=("Guitar Hero", "Dance Dance Revolution", "OSU!", "Friday Night Funkin'"),
    sources=(
        "https://en.wikipedia.org/wiki/Rhythm_game",
        "https://en.wikipedia.org/wiki/Guitar_Hero",
    ),
    controls=(
        "D/F/J/K or Arrow keys = 4 lanes; touch/click directly on the 4 lane receptor zones on mobile.",
        "Space/Enter = start; P/Escape = pause (suspending AudioContext); R = retry song.",
        "Call preventDefault() for arrows and Space.",
    ),
    physics=(
        "Drive note positions strictly from AudioContext.currentTime (songTime = ctx.currentTime - startTime), NEVER frame counting or setInterval.",
        "Judgement windows: Perfect <= 45 ms, Great <= 90 ms, Good <= 135 ms, Miss > 150 ms.",
        "Compute note Y from hitLineY - (note.time - songTime) * scrollSpeedPxPerSec so audio and visuals never drift.",
    ),
    mechanics=(
        "Core loop: synthesize a deterministic beat pattern with Web Audio (kick, snare, synth melody) -> hit notes on beat -> build combo/multiplier -> grade screen (S/A/B/C).",
    ),
    level_design=(
        "High-contrast 4-lane highway with clear receptor line, beat bars, and color+shape/arrow differentiation.",
    ),
    feel=(
        "Receptor glow burst on hit, floating 'PERFECT!' / 'GREAT!' callouts, subtle beat-synced background pulse, and synthesized drum/melody feedback.",
    ),
    avoid=(
        "Do not desync notes from audio by advancing notes with per-frame pixel offsets.",
        "Do not start audio before a user gesture unlocks AudioContext.",
    ),
)

DESIGN_SPECS: Tuple[DesignSpec, ...] = (
    _PLATFORMER,
    _TWIN_STICK,
    _ASTEROIDS,
    _SPACE_SHOOTER,
    _SNAKE,
    _PONG,
    _BREAKOUT,
    _FLAPPY,
    _RUNNER,
    _RACING,
    _TETRIS,
    _PHYSICS_SLINGSHOT,
    _RHYTHM,
    _PUZZLE,
    _FIGHTING,
    _TOWER_DEFENSE,
    _ADVENTURE,
    _ARCADE,
)

DEFAULT_SPEC = _ARCADE
_SPEC_BY_ID = {spec.id: spec for spec in DESIGN_SPECS}
_REFERENCE_TO_SPEC = {
    ref_id: spec.id
    for spec in DESIGN_SPECS
    for ref_id in spec.reference_ids
}


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().replace("_", " ").replace("-", " ").split())


def _has_keyword(text: str, normalized_keyword: str) -> bool:
    """Match whole words/phrases so e.g. 'card' never falsely matches 'car'."""
    if not normalized_keyword:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)"
    return re.search(pattern, text) is not None


def detect_design_spec(
    prompt: str,
    category: Optional[str] = None,
    game_reference: Optional[str] = None,
) -> DesignSpec:
    """Pick the closest design brief for a prompt/category/reference.

    Scoring is intentionally simple and deterministic: explicit game references
    win, then category matches, then whole-word keyword hits.  Ties keep the
    earlier (more specific) spec in ``DESIGN_SPECS``.
    """
    if game_reference:
        ref_id = game_reference.strip().lower()
        mapped = _REFERENCE_TO_SPEC.get(ref_id)
        if mapped:
            return _SPEC_BY_ID[mapped]

    text = _normalize(f"{prompt or ''} {category or ''}")
    cat = _normalize(category or "")
    best = DEFAULT_SPEC
    best_score = 0

    for spec in DESIGN_SPECS:
        score = 0
        if cat and cat == _normalize(spec.category):
            score += 6
        for keyword in spec.keywords:
            normalized_keyword = _normalize(keyword)
            if _has_keyword(text, normalized_keyword):
                score += 3 if " " in normalized_keyword else 2
        if spec.id == "arcade":
            score -= 1  # prefer a specific genre when scores tie
        if score > best_score:
            best = spec
            best_score = score

    return best


def _bullets(items: Tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def render_design_brief(spec: DesignSpec, max_chars: int = 3600) -> str:
    """Render a compact, model-friendly brief for the prompt."""
    brief = f"""Reference genre: {spec.label}
Studied games: {', '.join(spec.inspirations)}
Use these as tuning starting points; adapt names/visuals to the user's fantasy, but keep the input contract and the feel.

CONTROLS (implement all that apply):
{_bullets(spec.controls)}

PHYSICS / TIMING:
{_bullets(spec.physics)}

CORE MECHANICS:
{_bullets(spec.mechanics)}

LEVEL / PACING:
{_bullets(spec.level_design)}

GAME FEEL:
{_bullets(spec.feel)}

QUALITY BAR — AVOID:
{_bullets(spec.avoid)}
"""
    if len(brief) > max_chars:
        brief = brief[: max_chars - 20].rstrip() + "\n- [brief truncated]\n"
    return brief


def design_spec_for_prompt(prompt: str, category: Optional[str] = None) -> DesignSpec:
    """Backward-friendly alias used by tests and callers."""
    return detect_design_spec(prompt, category)
