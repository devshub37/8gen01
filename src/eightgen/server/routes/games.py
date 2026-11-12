"""Games REST API routes."""

import re
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent
from eightgen.core.engine.archetypes import (
    build_space_shooter_game,
    build_brick_breaker_game,
    build_cyber_snake_game,
    build_flappy_drone_game,
)
from eightgen.storage.models import Game

router = APIRouter(prefix="/api/games", tags=["games"])

_EMBED_CONTROL_SCRIPT = """<script>
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
    try {
      Object.defineProperty(window.performance, "now", {
        configurable: true,
        value: function () { return (pAt !== null ? pAt : oPNow()) - offset; }
      });
    } catch (e) {}
  }
  var AC = window.AudioContext || window.webkitAudioContext;
  if (AC) {
    var WAC = function () { var c = new AC(); audioCtxs.push(c); return c; };
    WAC.prototype = AC.prototype;
    try {
      if (window.AudioContext) window.AudioContext = WAC;
      if (window.webkitAudioContext) window.webkitAudioContext = WAC;
    } catch (e) {}
  }
  function scheduleVirtualRaf(id, cb) {
    if (paused) {
      queuedIds.push(id);
      return;
    }
    var realId = oRaf(function (ts) {
      var entry = rafState.get(id);
      if (!entry || entry.cancelled) { rafState.delete(id); return; }
      if (paused) {
        entry.realId = null;
        queuedIds.push(id);
        return;
      }
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
    if (entry) {
      entry.cancelled = true;
      if (entry.realId !== null) oCRaf(entry.realId);
      rafState.delete(id);
    } else {
      oCRaf(id);
    }
  };
  window.setInterval = function (fn, ms) {
    var args = Array.prototype.slice.call(arguments, 2);
    var id = iid++;
    var realId = oSI(function () { if (!paused && typeof fn === "function") fn.apply(window, args); }, ms);
    intervals.set(id, realId);
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
      ids.forEach(function (id) {
        var entry = rafState.get(id);
        if (entry && !entry.cancelled) scheduleVirtualRaf(id, entry.cb);
      });
    },
    isPaused: function () { return paused; }
  };
})();
</script>"""


def _with_embed_controls(html: str, ctrl: bool) -> str:
    if not ctrl:
        return html
    head_match = re.search(r"<head\b[^>]*>", html, re.IGNORECASE)
    if head_match:
        idx = head_match.end()
        return html[:idx] + "\n" + _EMBED_CONTROL_SCRIPT + html[idx:]
    html_match = re.search(r"<html\b[^>]*>", html, re.IGNORECASE)
    if html_match:
        idx = html_match.end()
        return html[:idx] + "\n<head>" + _EMBED_CONTROL_SCRIPT + "</head>\n" + html[idx:]
    return _EMBED_CONTROL_SCRIPT + "\n" + html


def get_agent() -> Agent:
    return Agent(get_settings())


@router.get("/archetype/{name}", response_class=HTMLResponse)
def get_archetype_html(name: str, ctrl: bool = False):
    """Serve a guaranteed playable arcade archetype instantly."""
    n = name.lower()
    if "shooter" in n or "space" in n:
        html = build_space_shooter_game("Neon Space Defender")
    elif "snake" in n:
        html = build_cyber_snake_game("Cyber Snake 2099")
    elif "brick" in n or "breaker" in n:
        html = build_brick_breaker_game("Quantum Breakout")
    elif "drone" in n or "flappy" in n:
        html = build_flappy_drone_game("Aero Drone Odyssey")
    else:
        html = build_space_shooter_game("Neon Space Defender")
    return HTMLResponse(content=_with_embed_controls(html, ctrl))


class RefineRequest(BaseModel):
    instruction: str


@router.get("", response_model=List[dict])
def list_games(tag: Optional[str] = None, agent: Agent = Depends(get_agent)):
    """List all games."""
    games = agent.list_games(tag=tag)
    return [g.model_dump(mode="json") for g in games]


@router.get("/{game_id}")
def get_game(game_id: str, agent: Agent = Depends(get_agent)):
    """Get single game metadata."""
    game = agent.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.model_dump(mode="json")


@router.get("/{game_id}/play", response_class=HTMLResponse)
def play_game(
    game_id: str,
    version: Optional[int] = None,
    ctrl: bool = False,
    agent: Agent = Depends(get_agent),
):
    """Serve the raw game HTML for in-browser or iframe playing."""
    game = agent.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if version is not None:
        for v in game.versions:
            if v.version == version:
                return HTMLResponse(content=_with_embed_controls(v.html_content, ctrl))

    return HTMLResponse(content=_with_embed_controls(game.latest_html, ctrl))


@router.get("/{game_id}/download")
def download_game(game_id: str, agent: Agent = Depends(get_agent)):
    """Download game as HTML file."""
    game = agent.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.file_path.is_file():
        return FileResponse(
            path=game.file_path,
            filename=game.file_path.name,
            media_type="text/html",
        )
    return Response(
        content=game.latest_html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{game.file_path.name}"'},
    )


@router.post("/{game_id}/refine")
async def refine_game(game_id: str, payload: RefineRequest, agent: Agent = Depends(get_agent)):
    """Refine an existing game."""
    try:
        updated = await agent.refine_game(
            game_id=game_id,
            instruction=payload.instruction,
            auto_open=False,
        )
        return updated.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{game_id}")
def delete_game(game_id: str, agent: Agent = Depends(get_agent)):
    """Delete a game."""
    success = agent.delete_game(game_id)
    if not success:
        raise HTTPException(status_code=404, detail="Game not found or could not be deleted")
    return {"status": "deleted", "id": game_id}
