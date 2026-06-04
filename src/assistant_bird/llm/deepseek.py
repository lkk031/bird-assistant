"""DeepSeek Chat model factory via langchain-deepseek."""

from langchain_deepseek import ChatDeepSeek

from assistant_bird.config import get_settings


def create_deepseek_model() -> ChatDeepSeek:
    """Create a configured ChatDeepSeek instance.

    Returns a ChatDeepSeek model configured with:
    - Streaming enabled for token-by-token output
    - Temperature from settings
    - Max tokens from settings
    - Retry on failure (max 2 retries)
    """
    settings = get_settings()

    if not settings.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Please configure it in your .env file. "
            "You can get an API key from https://platform.deepseek.com/"
        )

    return ChatDeepSeek(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_api_base,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=True,
        max_retries=2,
    )
