import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen3:1.7b"


def generate(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "think": False,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()
    return data["response"]