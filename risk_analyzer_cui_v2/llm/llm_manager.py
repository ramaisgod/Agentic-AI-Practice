# llm_manager.py

from app_config import LLM_PROVIDER
from core.logger import logger

# Import all providers (safe even if some fail)
try:
    from llm.gemini_service import call_gemini_llm
except Exception:
    call_gemini_llm = None

try:
    from llm.openai_services import call_openai_llm
except Exception:
    call_openai_llm = None

try:
    from llm.llama_service import call_llama_model
except Exception:
    call_llama_model = None


def call_llm(prompt: str) -> str:
    """
    Calls the correct LLM based on app_config.LLM_PROVIDER.
    Options: "gemini", "openai", "llama".
    """

    logger.info("call_llm invoked using provider=%s", LLM_PROVIDER)

    provider = (LLM_PROVIDER or "").lower()

    if provider == "gemini":
        if call_gemini_llm:
            logger.info("Using Gemini LLM")
            return call_gemini_llm(prompt)
        logger.error("Gemini provider selected but not available")

    elif provider == "openai":
        if call_openai_llm:
            logger.info("Using OpenAI LLM")
            return call_openai_llm(prompt)
        logger.error("OpenAI provider selected but not available")

    elif provider == "llama":
        if call_llama_model:
            logger.info("Using LLaMA (RapidAPI) model")
            return call_llama_model(prompt)
        logger.error("LLaMA provider selected but not available")

    # Fallback
    logger.error("LLM_PROVIDER '%s' is invalid or unavailable", LLM_PROVIDER)
    return None
