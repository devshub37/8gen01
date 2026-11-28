"""Game refinement and iteration pipeline."""

from typing import Callable, Optional
from eightgen.config.settings import Settings
from eightgen.core.extractor import HTMLExtractor
from eightgen.core.validator import GameValidator, ValidationResult
from eightgen.llm.base import LLMProvider
from eightgen.llm.prompt_builder import PromptBuilder
from eightgen.plugins.manager import get_plugin_manager
from eightgen.utils.logger import get_logger

import asyncio
import inspect

logger = get_logger("eightgen.refiner")


class RefinementError(Exception):
    """Raised when game refinement fails all retries."""
    pass


class GameRefiner:
    """Modifies and iterates on existing games using instructions."""

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

    async def refine(
        self,
        game_id: str,
        existing_html: str,
        instruction: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        design_brief: str = "",
    ) -> str:
        """Apply user modifications to existing game code."""
        await self.plugins.trigger_pre_refine(game_id, instruction)

        messages = self.prompt_builder.build_refine_messages(
            existing_html, instruction, design_brief=design_brief
        )
        max_attempts = max(1, self.settings.max_retries)
        last_errors = []
        raw_output = ""

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Refinement attempt {attempt}/{max_attempts}...")

            if attempt > 1:
                messages = self.prompt_builder.build_fix_messages(
                    raw_output, last_errors, design_brief=design_brief
                )

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

            html_code = HTMLExtractor.extract(raw_output)
            if not html_code:
                last_errors = ["Failed to extract valid HTML code block from LLM response."]
                await self.plugins.trigger_on_validate_error(raw_output, last_errors)
                continue

            val_result: ValidationResult = await asyncio.to_thread(
                GameValidator.validate,
                html_code,
                check_js=self.settings.js_syntax_check,
            )
            if val_result.is_valid:
                logger.info("Refinement validation passed successfully!")
                await self.plugins.trigger_post_refine(game_id, html_code)
                return html_code

            logger.warning(f"Refinement validation failed (attempt {attempt}): {val_result.errors}")
            last_errors = val_result.errors
            await self.plugins.trigger_on_validate_error(html_code, last_errors)

        # Never return invalid refined HTML: persist the failed draft so the
        # user can inspect it, then fail loudly instead of silently shipping a
        # broken game.
        if html_code:
            draft_path = self._save_failed_draft(game_id, html_code, instruction)
            logger.warning(
                f"Max retries reached; invalid refined draft saved to {draft_path} "
                f"(errors: {last_errors})."
            )

        raise RefinementError(
            f"Failed to refine game after {max_attempts} attempts: {last_errors}"
            + (
                f". The invalid draft was kept at {draft_path}."
                if html_code and draft_path
                else ""
            )
        )

    def _save_failed_draft(self, game_id: str, html_code: str, instruction: str) -> Optional[str]:
        """Persist an invalid refinement draft under ``<output_dir>/failed_drafts``."""
        try:
            import time
            from pathlib import Path

            draft_dir = Path(self.settings.output_dir) / "failed_drafts"
            draft_dir.mkdir(parents=True, exist_ok=True)
            slug = "".join(c if c.isalnum() else "-" for c in instruction.lower())[:40].strip("-")
            draft_path = draft_dir / f"{game_id}-{slug or 'refine'}-{int(time.time())}.html"
            draft_path.write_text(html_code, encoding="utf-8")
            return str(draft_path)
        except Exception as exc:  # pragma: no cover - draft saving is best effort
            logger.warning(f"Could not save failed refinement draft: {exc}")
            return None
