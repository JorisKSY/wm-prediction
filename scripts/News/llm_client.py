from config import OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL


class MissingApiKeyError(ValueError):
    pass


def get_llm_client():
    if not OPENAI_API_KEY:
        raise MissingApiKeyError("OPENAI_API_KEY fehlt. Bitte in config.py setzen.")

    from openai import OpenAI

    return OpenAI(
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
    )


def ask_llm(
    messages,
    max_tokens: int = 300,
    temperature: float = 0.7,
    stream_output: bool = True,
) -> str:
    client = get_llm_client()

    if stream_output:
        stream = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        answer_parts = []
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                answer_parts.append(content)
                print(content, end="", flush=True)

        print()
        return "".join(answer_parts)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=False,
    )

    return response.choices[0].message.content or ""