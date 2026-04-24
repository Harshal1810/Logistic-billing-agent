import httpx


class LLMClientError(Exception):
    pass


def generate_grounded_text_openai(
    *,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "input": prompt,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers=headers,
                json=body,
            )
    except Exception as exc:  # pragma: no cover
        raise LLMClientError(f"Failed to call LLM API: {exc}") from exc

    if response.status_code >= 400:
        raise LLMClientError(
            f"LLM API error status={response.status_code}: {response.text[:400]}"
        )

    payload = response.json()
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    output = payload.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            content = item.get("content") if isinstance(item, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") in {"output_text", "text"}:
                    block_text = block.get("text")
                    if isinstance(block_text, str) and block_text.strip():
                        parts.append(block_text.strip())
        if parts:
            return "\n".join(parts)

    raise LLMClientError("LLM API response missing output text")


def generate_grounded_text_groq(
    *,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=body,
            )
    except Exception as exc:  # pragma: no cover
        raise LLMClientError(f"Failed to call Groq API: {exc}") from exc

    if response.status_code >= 400:
        raise LLMClientError(
            f"Groq API error status={response.status_code}: {response.text[:400]}"
        )

    payload = response.json()
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()

    raise LLMClientError("Groq API response missing output text")


# Backward-compatible alias used in tests and service imports.
def generate_grounded_text(
    *,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    return generate_grounded_text_openai(
        api_key=api_key,
        model=model,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
    )
