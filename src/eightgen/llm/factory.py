"""LLM provider factory."""

from eightgen.config.settings import GEMINI_ALIASES, OLLAMA_ALIASES, Settings
from eightgen.llm.base import LLMProvider
from eightgen.llm.ollama import OllamaProvider
from eightgen.llm.gemini import GeminiProvider
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.llm.factory")


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Create the configured LLM provider.

    An explicitly selected provider is always honored (and fails loudly when
    it is misconfigured). With the default ``auto`` selection, Gemini is used
    only when credentials are present; otherwise the local Ollama runtime is
    used, so an unset API key can never silently change providers.
    """
    name = settings.provider.strip().lower()
    has_gemini_credentials = bool(settings.gemini_api_key or settings.gemini_proxy_url)

    if name in GEMINI_ALIASES:
        if not has_gemini_credentials:
            raise ValueError(
                "Provider 'gemini' is explicitly selected but no API key is configured. "
                "Set EIGHTGEN_GEMINI_API_KEY (or GEMINI_API_KEY), or switch to the local "
                "provider with EIGHTGEN_PROVIDER=ollama."
            )
        logger.info(f"Using Gemini Provider (Model: {settings.gemini_model})")
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            proxy_url=settings.gemini_proxy_url,
            timeout=settings.timeout,
        )

    if name in OLLAMA_ALIASES:
        logger.info(f"Using local Ollama Provider (Model: {settings.model})")
        return OllamaProvider(
            base_url=settings.ollama_url,
            model=settings.model,
            timeout=settings.timeout,
        )

    # Auto-detection (default): Gemini only when credentials exist, else Ollama.
    if has_gemini_credentials:
        logger.info(
            f"Provider auto-detected: Gemini (Model: {settings.gemini_model}, key present)"
        )
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            proxy_url=settings.gemini_proxy_url,
            timeout=settings.timeout,
        )

    logger.info(
        f"Provider auto-detected: local Ollama (Model: {settings.model}; "
        "no Gemini API key configured)"
    )
    return OllamaProvider(
        base_url=settings.ollama_url,
        model=settings.model,
        timeout=settings.timeout,
    )
