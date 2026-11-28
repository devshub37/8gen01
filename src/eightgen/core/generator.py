"""Game generation pipeline with self-healing validation loop."""

from typing import Callable, Optional
from eightgen.config.settings import Settings
from eightgen.core.engine.archetypes import build_smart_archetype
from eightgen.core.engine.references import build_simple_reference_game
from eightgen.core.engine.web_learner import learn_from_similar_games
from eightgen.core.extractor import HTMLExtractor
from eightgen.core.validator import GameValidator, ValidationResult
from eightgen.llm.base import LLMProvider
from eightgen.llm.prompt_builder import PromptBuilder
from eightgen.plugins.manager import get_plugin_manager
from eightgen.utils.logger import get_logger

import asyncio
import inspect
import os

logger = get_logger("eightgen.generator")


class GenerationError(Exception):
    """Raised when game generation fails all retries."""
    pass


class GameGenerator:
    """Manages LLM interaction, extraction, validation, and self-healing."""

    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: PromptBuilder,
        settings: Settings,
    ):
        self.provider = provider
        self.prompt_builder = prompt_builder
        self.settings = settings
        self.plugins = get_plugin_manager()

    async def generate(
        self,
        prompt: str,
        category: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        instant: bool = False,
        game_reference: Optional[str] = None,
    ) -> str:
        """Generate a complete, validated HTML5 game from a prompt."""
        await self.plugins.trigger_pre_generate(prompt, category)

        def _build_instant_or_fallback() -> str:
            if game_reference:
                ref_html = build_simple_reference_game(game_reference)
                if ref_html:
                    return ref_html
            return build_smart_archetype(prompt, category or "")

        # Fast path: instant reference/archetype compilation
        if instant:
            logger.info("Instant mode requested; compiling guaranteed playable game...")
            html = _build_instant_or_fallback()
            await self.plugins.trigger_post_generate(prompt, html)
            return html

        learned_context = ""
        if self.settings.learn_from_web:
            try:
                learned = await learn_from_similar_games(
                    prompt=prompt,
                    category=category,
                    game_reference=game_reference,
                    cache_dir=self.settings.output_dir / ".cache",
                    timeout=self.settings.web_learn_timeout,
                )
                learned_context = learned.render_brief()
                if learned_context:
                    logger.info(
                        "Loaded internet game research for '%s' (%s).",
                        learned.query,
                        "cache" if learned.from_cache else "live",
                    )
            except Exception as exc:
                logger.debug("Skipping internet game research: %s", exc)

        base_messages = self.prompt_builder.build_generate_messages(
            prompt,
            category,
            game_reference=game_reference,
            learned_context=learned_context,
        )
        design_brief = self.prompt_builder.design_brief(prompt, category, game_reference)
        if learned_context:
            design_brief = f"{design_brief.rstrip()}\n\n{learned_context.strip()}"
        messages = base_messages
        max_attempts = max(1, self.settings.max_retries)
        last_errors = []
        raw_output = ""
        html_code = ""
        should_fix_previous = False

        async def _notify(text: str) -> None:
            if not stream_callback:
                return
            try:
                if inspect.iscoroutinefunction(stream_callback):
                    await stream_callback(text)
                else:
                    stream_callback(text)
            except Exception:
                pass

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Generation attempt {attempt}/{max_attempts}...")

            if attempt > 1 and should_fix_previous:
                # Self-healing debug attempt
                messages = self.prompt_builder.build_fix_messages(
                    raw_output, last_errors, design_brief=design_brief
                )
            else:
                messages = base_messages

            should_fix_previous = False
            try:
                raw_chunks = []
                if stream_callback:
                    async for chunk in self.provider.stream(messages, temperature=self.settings.temperature):
                        raw_chunks.append(chunk)
                        if inspect.iscoroutinefunction(stream_callback):
                            await stream_callback(chunk)
                        else:
                            stream_callback(chunk)
                    raw_output = "".join(raw_chunks)
                else:
                    response = await self.provider.generate(messages, temperature=self.settings.temperature)
                    raw_output = response.content
            except ValueError as exc:
                # Configuration error (e.g., missing API key) - don't retry uselessly
                logger.warning(f"LLM configuration error: {exc}. Falling back to guaranteed playable game.")
                await _notify(f"\n⚠️ AI generation notice: {exc}\n⚡ Loading instant playable game...\n")
                fallback_html = _build_instant_or_fallback()
                await self.plugins.trigger_post_generate(prompt, fallback_html)
                return fallback_html
            except Exception as exc:
                logger.warning(f"LLM attempt {attempt} failed: {exc}")
                last_errors = [str(exc)]
                if attempt < max_attempts:
                    await _notify(f"\n⚠️ Retrying with backup model ({exc})...\n")
                continue

            # Extract clean HTML
            html_code = HTMLExtractor.extract(raw_output)
            if not html_code:
                last_errors = ["Failed to extract valid HTML code block from LLM response."]
                await self.plugins.trigger_on_validate_error(raw_output, last_errors)
                should_fix_previous = True
                continue

            # Validate HTML structure and requirements. ``validate`` shells out
            # to ``node --check`` and can take seconds, so keep it off the
            # event loop.
            val_result: ValidationResult = await asyncio.to_thread(
                GameValidator.validate,
                html_code,
                check_js=self.settings.js_syntax_check,
            )
            if val_result.is_valid:
                # Optional headless smoke test: run the game once in a real
                # browser when enabled (EIGHTGEN_SMOKE_TEST=1 / smoke_test=true).
                smoke_enabled = self.settings.smoke_test or os.getenv(
                    "EIGHTGEN_SMOKE_TEST", ""
                ).strip().lower() in ("1", "true", "yes", "on")
                if smoke_enabled:
                    smoke_error = await asyncio.to_thread(GameValidator.smoke_test, html_code)
                    if smoke_error:
                        logger.warning(f"Smoke test failed (attempt {attempt}): {smoke_error}")
                        last_errors = [smoke_error]
                        await self.plugins.trigger_on_validate_error(html_code, last_errors)
                        should_fix_previous = True
                        continue
                logger.info("Validation passed successfully!")
                await self.plugins.trigger_post_generate(prompt, html_code)
                return html_code

            logger.warning(f"Validation failed (attempt {attempt}): {val_result.errors}")
            last_errors = val_result.errors
            await self.plugins.trigger_on_validate_error(html_code, last_errors)
            should_fix_previous = True

        # Retries exhausted: never return invalid best-effort HTML as a playable
        # game. Persist the failed draft for inspection, then fall back to the
        # guaranteed playable game.
        if html_code:
            draft_path = self._save_failed_draft(html_code, prompt)
            logger.warning(
                f"Max retries reached; invalid draft saved to {draft_path} "
                f"(errors: {last_errors})."
            )

        logger.warning(f"Retries exhausted ({last_errors}). Falling back to guaranteed playable game.")
        await _notify(f"\n⚠️ Retries exhausted ({'; '.join(last_errors)}). Loading instant playable game...\n")
        fallback_html = _build_instant_or_fallback()
        await self.plugins.trigger_post_generate(prompt, fallback_html)
        return fallback_html

    def _save_failed_draft(self, html_code: str, prompt: str) -> Optional[str]:
        """Persist an invalid generation draft under ``<output_dir>/failed_drafts``."""
        try:
            import time
            from pathlib import Path

            draft_dir = Path(self.settings.output_dir) / "failed_drafts"
            draft_dir.mkdir(parents=True, exist_ok=True)
            slug = "".join(c if c.isalnum() else "-" for c in prompt.lower())[:40].strip("-")
            draft_path = draft_dir / f"{slug or 'draft'}-{int(time.time())}.html"
            draft_path.write_text(html_code, encoding="utf-8")
            return str(draft_path)
        except Exception as exc:  # pragma: no cover - draft saving is best effort
            logger.warning(f"Could not save failed draft: {exc}")
            return None

