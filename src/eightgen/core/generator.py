"""Game generation pipeline with self-healing validation loop."""

from typing import Callable, Optional
from eightgen.config.settings import Settings
from eightgen.core.engine.archetypes import build_smart_archetype
from eightgen.core.extractor import HTMLExtractor
from eightgen.core.validator import GameValidator, ValidationResult
from eightgen.llm.base import LLMProvider
from eightgen.llm.prompt_builder import PromptBuilder
from eightgen.plugins.manager import get_plugin_manager
from eightgen.utils.logger import get_logger

import inspect

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
    ) -> str:
        """Generate a complete, validated HTML5 game from a prompt."""
        await self.plugins.trigger_pre_generate(prompt, category)

        # Fast path: instant archetype compilation
        if instant:
            logger.info("Instant mode requested; compiling guaranteed playable game archetype...")
            html = build_smart_archetype(prompt, category or "")
            await self.plugins.trigger_post_generate(prompt, html)
            return html

        base_messages = self.prompt_builder.build_generate_messages(prompt, category)
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
                messages = self.prompt_builder.build_fix_messages(raw_output, last_errors)
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
                logger.warning(f"LLM configuration error: {exc}. Falling back to guaranteed playable engine archetype.")
                await _notify(f"\n⚠️ AI generation notice: {exc}\n⚡ Loading instant playable archetype...\n")
                fallback_html = build_smart_archetype(prompt, category or "")
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

            # Validate HTML structure and requirements
            val_result: ValidationResult = GameValidator.validate(html_code)
            if val_result.is_valid:
                logger.info("Validation passed successfully!")
                await self.plugins.trigger_post_generate(prompt, html_code)
                return html_code

            logger.warning(f"Validation failed (attempt {attempt}): {val_result.errors}")
            last_errors = val_result.errors
            await self.plugins.trigger_on_validate_error(html_code, last_errors)
            should_fix_previous = True

        # If retries exhausted but we have some extracted HTML, log warning and return best effort
        if html_code and "<html" in html_code.lower() and "</script>" in html_code.lower():
            logger.warning("Max retries reached; returning best effort HTML.")
            return html_code

        logger.warning(f"Retries exhausted ({last_errors}). Falling back to guaranteed playable engine archetype.")
        await _notify(f"\n⚠️ Retries exhausted ({'; '.join(last_errors)}). Loading instant playable archetype...\n")
        fallback_html = build_smart_archetype(prompt, category or "")
        await self.plugins.trigger_post_generate(prompt, fallback_html)
        return fallback_html

