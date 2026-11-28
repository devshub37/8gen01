"""Online game-research learner for controls, physics, and mechanics.

Queries public, zero-key endpoints (Wikipedia MediaWiki API and GitHub public
repository search) to learn how similar games on the internet handle controls,
physics, and core loops.  Results are distilled into concise design notes and
cached locally so repeated prompts work offline with zero added latency.

All network calls are bounded by a tight timeout and fail silently to the
curated offline ``design_knowledge`` corpus when offline or rate-limited.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import quote, urlparse

import httpx

from eightgen.core.engine.design_knowledge import DesignSpec, detect_design_spec
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.web_learner")

ALLOWED_HOSTS = frozenset({"en.wikipedia.org", "api.github.com"})
DEFAULT_CACHE_TTL_SECONDS = 7 * 24 * 3600
_USER_AGENT = "8Gen-GameLearner/1.0 (+https://github.com/8gen)"

_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "build", "by", "can", "create",
        "for", "from", "game", "games", "generate", "html", "html5", "in", "instant",
        "is", "it", "like", "make", "me", "modern", "neon", "new", "of", "on", "or",
        "play", "playable", "please", "retro", "simple", "style", "styled", "that",
        "the", "to", "using", "with", "you", "your",
    }
)

_CONTROL_HINTS = (
    "control", "keyboard", "arrow", "wasd", "mouse", "touch", "swipe", "tap",
    "drag", "button", "joystick", "steer", "jump", "dash", "shoot", "fire",
    "aim", "paddle", "flap", "move", "rotate", "turn", "hold", "press",
)

_PHYSICS_HINTS = (
    "physics", "gravity", "velocity", "momentum", "inertia", "thrust", "bounce",
    "rebound", "deflect", "collision", "hitbox", "hurtbox", "speed", "accelerat",
    "friction", "drag", "drift", "grid", "tile", "angle", "trajectory", "arc",
    "parabol", "orbit", "wrap", "lock delay", "coyote", "buffer", "timestep",
    "frame", "knockback", "ricochet", "elastic", "restitution",
)

_MECHANIC_HINTS = (
    "score", "point", "combo", "multiplier", "wave", "level", "stage", "power-up",
    "powerup", "health", "life", "lives", "enemy", "enemies", "obstacle", "boss",
    "checkpoint", "upgrade", "spawn", "timer", "goal", "win", "lose", "difficulty",
    "clear", "match", "merge", "chain", "cascade",
)


@dataclass(frozen=True)
class LearnedGameKnowledge:
    """Distilled controls, physics, and mechanics learned from internet games."""

    query: str
    references: tuple[tuple[str, str], ...] = ()
    controls_notes: tuple[str, ...] = ()
    physics_notes: tuple[str, ...] = ()
    mechanics_notes: tuple[str, ...] = ()
    open_source_patterns: tuple[str, ...] = ()
    from_cache: bool = False

    @property
    def has_findings(self) -> bool:
        return bool(
            self.references
            or self.controls_notes
            or self.physics_notes
            or self.mechanics_notes
            or self.open_source_patterns
        )

    def render_brief(self, max_chars: int = 1400) -> str:
        """Render learned internet findings as a compact prompt section."""
        if not self.has_findings:
            return ""
        lines: list[str] = [f"Internet research query: {self.query}"]
        if self.references:
            refs = ", ".join(f"{title} ({url})" for title, url in self.references[:4])
            lines.append(f"Similar games studied online: {refs}")
        if self.controls_notes:
            lines.append("Observed control patterns from similar games:")
            lines.extend(f"- {note}" for note in self.controls_notes[:4])
        if self.physics_notes:
            lines.append("Observed physics & movement patterns:")
            lines.extend(f"- {note}" for note in self.physics_notes[:5])
        if self.mechanics_notes:
            lines.append("Observed core loop & progression patterns:")
            lines.extend(f"- {note}" for note in self.mechanics_notes[:4])
        if self.open_source_patterns:
            lines.append("Open-source HTML5 implementation ideas:")
            lines.extend(f"- {pat}" for pat in self.open_source_patterns[:3])

        text = "\n".join(lines).strip()
        if len(text) > max_chars:
            text = text[: max_chars - 24].rstrip() + "\n- [research truncated]"
        return text


def _is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.lower() in ALLOWED_HOSTS


def _build_search_query(
    prompt: str,
    spec: DesignSpec,
    category: Optional[str] = None,
) -> str:
    """Extract clean, focused game-search terms from the user prompt and spec."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{1,24}", (prompt or "").lower())
    meaningful = [tok for tok in tokens if tok not in _STOPWORDS]
    if meaningful:
        base = " ".join(meaningful[:5])
    elif spec.inspirations:
        base = spec.inspirations[0]
    elif category:
        base = f"{category} arcade"
    else:
        base = spec.label
    return base[:80].strip()


def _split_sentences(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return []
    parts = re.split(r"(?<=[.!?])\s+", clean)
    result: list[str] = []
    for part in parts:
        sentence = part.strip()
        if 25 <= len(sentence) <= 240:
            result.append(sentence)
    return result


def _classify_sentences(
    sentences: Iterable[str],
) -> tuple[list[str], list[str], list[str]]:
    controls: list[str] = []
    physics: list[str] = []
    mechanics: list[str] = []
    seen: set[str] = set()

    for sentence in sentences:
        low = sentence.lower()
        key = low[:80]
        if key in seen:
            continue
        matched = False
        if any(hint in low for hint in _PHYSICS_HINTS):
            physics.append(sentence)
            matched = True
        elif any(hint in low for hint in _CONTROL_HINTS):
            controls.append(sentence)
            matched = True
        elif any(hint in low for hint in _MECHANIC_HINTS):
            mechanics.append(sentence)
            matched = True
        if matched:
            seen.add(key)

    return controls[:4], physics[:5], mechanics[:4]


async def _safe_get_json(
    client: httpx.AsyncClient,
    url: str,
    params: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    if not _is_allowed_url(url):
        return None
    try:
        resp = await client.get(url, params=params, follow_redirects=False)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception as exc:
        logger.debug("Web learner HTTP error for %s: %s", url, exc)
        return None


async def _fetch_wikipedia_insights(
    client: httpx.AsyncClient,
    query: str,
    inspirations: Sequence[str],
) -> tuple[list[tuple[str, str]], list[str], list[str], list[str]]:
    """Search Wikipedia for matching video games and distill gameplay sentences."""
    wiki_url = "https://en.wikipedia.org/w/api.php"
    search_terms = [f"{query} video game"]
    if inspirations:
        search_terms.append(f"{inspirations[0]} video game")

    titles: list[str] = []
    for term in search_terms:
        data = await _safe_get_json(
            client,
            wiki_url,
            params={
                "action": "query",
                "list": "search",
                "srsearch": term,
                "srlimit": 2,
                "format": "json",
            },
        )
        hits = ((data or {}).get("query") or {}).get("search") or []
        for hit in hits:
            title = str(hit.get("title") or "").strip()
            if title and title not in titles:
                titles.append(title)
        if len(titles) >= 2:
            break

    if not titles:
        return [], [], [], []

    extract_data = await _safe_get_json(
        client,
        wiki_url,
        params={
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "exchars": "5000",
            "titles": "|".join(titles[:2]),
            "format": "json",
        },
    )
    pages = ((extract_data or {}).get("query") or {}).get("pages") or {}
    refs: list[tuple[str, str]] = []
    all_sentences: list[str] = []
    for page in pages.values():
        if not isinstance(page, dict) or "missing" in page:
            continue
        title = str(page.get("title") or "").strip()
        extract = str(page.get("extract") or "")
        if title:
            refs.append((title, f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"))
        all_sentences.extend(_split_sentences(extract))

    controls, physics, mechanics = _classify_sentences(all_sentences)
    return refs, controls, physics, mechanics


async def _fetch_github_patterns(
    client: httpx.AsyncClient,
    query: str,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Search public GitHub HTML5 game repos for implementation & control patterns."""
    gh_url = "https://api.github.com/search/repositories"
    data = await _safe_get_json(
        client,
        gh_url,
        params={
            "q": f"{query} html5 canvas game",
            "sort": "stars",
            "order": "desc",
            "per_page": 3,
        },
    )
    items = (data or {}).get("items") or []
    refs: list[tuple[str, str]] = []
    patterns: list[str] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("full_name") or "").strip()
        html_url = str(item.get("html_url") or "").strip()
        desc = re.sub(r"\s+", " ", str(item.get("description") or "")).strip()
        topics = [str(t) for t in (item.get("topics") or [])[:5] if t]
        if name and html_url.startswith("https://github.com/"):
            refs.append((name, html_url))
        if desc or topics:
            topic_str = f" [topics: {', '.join(topics)}]" if topics else ""
            patterns.append(f"{name}: {desc[:140]}{topic_str}".strip())
    return refs, patterns


def _cache_key(query: str, spec_id: str) -> str:
    raw = f"{spec_id}:{query}".lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _load_cached(
    cache_path: Optional[Path],
    key: str,
    ttl_seconds: int,
) -> Optional[LearnedGameKnowledge]:
    if not cache_path or not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        entry = payload.get(key)
        if not isinstance(entry, dict):
            return None
        if time.time() - float(entry.get("ts", 0)) > ttl_seconds:
            return None
        data = entry.get("data") or {}
        return LearnedGameKnowledge(
            query=str(data.get("query") or ""),
            references=tuple((str(a), str(b)) for a, b in data.get("references", [])),
            controls_notes=tuple(str(x) for x in data.get("controls_notes", [])),
            physics_notes=tuple(str(x) for x in data.get("physics_notes", [])),
            mechanics_notes=tuple(str(x) for x in data.get("mechanics_notes", [])),
            open_source_patterns=tuple(str(x) for x in data.get("open_source_patterns", [])),
            from_cache=True,
        )
    except Exception:
        return None


def _save_cached(
    cache_path: Optional[Path],
    key: str,
    knowledge: LearnedGameKnowledge,
) -> None:
    if not cache_path or not knowledge.has_findings:
        return
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict[str, Any] = {}
        if cache_path.is_file():
            try:
                existing = json.loads(cache_path.read_text(encoding="utf-8"))
                if not isinstance(existing, dict):
                    existing = {}
            except Exception:
                existing = {}
        # Keep the cache bounded to 100 recent lookups.
        if len(existing) >= 100:
            oldest_keys = sorted(
                existing.keys(),
                key=lambda k: float(existing[k].get("ts", 0)) if isinstance(existing[k], dict) else 0,
            )[: len(existing) - 99]
            for old_k in oldest_keys:
                existing.pop(old_k, None)
        serializable = asdict(knowledge)
        serializable.pop("from_cache", None)
        existing[key] = {"ts": time.time(), "data": serializable}
        cache_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("Could not persist learned game cache: %s", exc)


async def learn_from_similar_games(
    prompt: str,
    category: Optional[str] = None,
    game_reference: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    timeout: float = 3.0,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
) -> LearnedGameKnowledge:
    """Research similar games online and distill controls/physics/mechanics.

    Checks the local JSON cache first; on a miss, queries Wikipedia and GitHub
    in parallel with a bounded timeout.  Never raises on network errors.
    """
    spec = detect_design_spec(prompt, category, game_reference)
    query = _build_search_query(prompt, spec, category)
    key = _cache_key(query, spec.id)
    cache_path = (Path(cache_dir) / "learned_games.json") if cache_dir else None

    cached = _load_cached(cache_path, key, ttl_seconds)
    if cached is not None:
        return cached

    bounded_timeout = max(0.5, min(float(timeout), 10.0))
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=bounded_timeout, headers=headers) as client:
            wiki_task = _fetch_wikipedia_insights(client, query, spec.inspirations)
            gh_task = _fetch_github_patterns(client, query)
            wiki_res, gh_res = await asyncio.gather(
                wiki_task, gh_task, return_exceptions=True
            )
    except Exception as exc:
        logger.debug("Web learning aborted: %s", exc)
        return LearnedGameKnowledge(query=query)

    refs: list[tuple[str, str]] = []
    controls: list[str] = []
    physics: list[str] = []
    mechanics: list[str] = []
    patterns: list[str] = []

    if isinstance(wiki_res, tuple) and len(wiki_res) == 4:
        w_refs, controls, physics, mechanics = wiki_res
        refs.extend(w_refs)
    if isinstance(gh_res, tuple) and len(gh_res) == 2:
        g_refs, patterns = gh_res
        refs.extend(g_refs)

    knowledge = LearnedGameKnowledge(
        query=query,
        references=tuple(refs[:5]),
        controls_notes=tuple(controls),
        physics_notes=tuple(physics),
        mechanics_notes=tuple(mechanics),
        open_source_patterns=tuple(patterns),
        from_cache=False,
    )
    _save_cached(cache_path, key, knowledge)
    return knowledge
