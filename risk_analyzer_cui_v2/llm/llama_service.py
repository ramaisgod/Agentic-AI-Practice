# llm/llama_service.py

import requests
from app_config import RAPID_API_KEY
from core.logger import logger


LLAMA_URL = "https://open-ai21.p.rapidapi.com/conversationllama"


def _preview(text: str, limit: int = 200) -> str:
    """Utility: safe preview for logging."""
    if not isinstance(text, str):
        return str(text)
    return text if len(text) <= limit else text[:limit] + "..."


def call_llama_model(prompt: str):
    logger.info("call_llama_model invoked")
    logger.debug("Prompt preview: %s", _preview(prompt))

    # Mask RapidAPI key in logs
    try:
        masked_key = RAPID_API_KEY[:4] + "****" if RAPID_API_KEY else "None"
        logger.debug("Using RapidAPI key=%s", masked_key)
    except Exception:
        logger.exception("Failed while masking RAPID_API_KEY")

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "web_access": False
    }

    headers = {
        "x-rapidapi-key": RAPID_API_KEY,
        "x-rapidapi-host": "open-ai21.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    logger.info("Sending request to LLaMA API endpoint: %s", LLAMA_URL)

    try:
        response = requests.post(LLAMA_URL, json=payload, headers=headers)

        logger.debug("LLaMA API HTTP status=%s", response.status_code)

        response.raise_for_status()

        # Log response preview
        try:
            resp_json = response.json()
            logger.debug("LLaMA response JSON preview: %s", _preview(str(resp_json)))
        except Exception:
            logger.exception("Failed to parse JSON from LLaMA response")
            return None

        result = resp_json.get("result")
        logger.info("LLaMA call succeeded (result_length=%d)", len(result) if isinstance(result, str) else 0)

        return result

    except requests.HTTPError as http_err:
        logger.error("LLaMA HTTP error: %s | Status=%s", http_err, getattr(http_err.response, 'status_code', '?'))
        logger.debug("HTTP error details:", exc_info=True)
        return None

    except Exception as e:
        logger.error("LLaMA API Error: %s", e)
        logger.debug("Exception details:", exc_info=True)
        return None
