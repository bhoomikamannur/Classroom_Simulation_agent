"""Small Ollama client with configurable timeouts and clear failure types."""
import os

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "qwen3:1.7b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "240"))
OLLAMA_CONNECT_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "10"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "1024"))


class LLMTimeoutError(TimeoutError):
    """Raised when Ollama does not complete a generation in time."""


def generate(prompt: str, num_predict: int | None = None) -> str:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"num_predict": num_predict or OLLAMA_NUM_PREDICT, "temperature": 0.1},
            },
            timeout=(OLLAMA_CONNECT_TIMEOUT_SECONDS, OLLAMA_TIMEOUT_SECONDS),
        )
    except requests.exceptions.Timeout as exc:
        raise LLMTimeoutError(
            f"Ollama model '{MODEL_NAME}' did not respond within "
            f"{OLLAMA_TIMEOUT_SECONDS:g} seconds. Try again or use a smaller prompt/model."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Could not connect to Ollama at the configured local endpoint. "
            "Check that Ollama is running and the model is available."
        ) from exc

    response.raise_for_status()
    data = response.json()
    result = data.get("response")
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("Ollama returned an empty or invalid response.")
    return result
