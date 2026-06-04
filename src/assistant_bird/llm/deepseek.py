"""DeepSeek Chat model factory via langchain-deepseek."""

import time

from langchain_deepseek import ChatDeepSeek

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # seconds between retries, doubles each attempt
RETRYABLE_ERRORS = (
    "rate_limit",
    "timeout",
    "connection",
    "internal_server_error",
    "service_unavailable",
)


def create_deepseek_model() -> ChatDeepSeek:
    """Create a configured ChatDeepSeek instance.

    Returns a ChatDeepSeek model configured with:
    - Streaming enabled for token-by-token output
    - Temperature and max tokens from settings
    - Retry on failure with exponential backoff (max 3 retries)

    Raises:
        ValueError: If DEEPSEEK_API_KEY is not configured.
    """
    settings = get_settings()

    if not settings.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Please configure it in your .env file.\n"
            "You can get a free API key from https://platform.deepseek.com/"
        )

    model = ChatDeepSeek(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_api_base,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=True,
        max_retries=MAX_RETRIES,
        timeout=60.0,
    )

    logger.info(
        "create_deepseek_model: model created",
        model=settings.deepseek_model,
        temperature=settings.llm_temperature,
    )
    return model


def is_retryable_error(error: Exception) -> bool:
    """Check if an error from DeepSeek API is retryable.

    Args:
        error: The exception to check.

    Returns:
        True if the error type suggests a retry might succeed.
    """
    error_str = str(error).lower()
    return any(msg in error_str for msg in RETRYABLE_ERRORS)


def retry_call(func, *args, max_retries: int = MAX_RETRIES, **kwargs):
    """Call a function with exponential backoff retry on failure.

    Args:
        func: The async function to call.
        *args: Positional arguments.
        max_retries: Maximum retry attempts.
        **kwargs: Keyword arguments.

    Returns:
        The function's return value.

    Raises:
        The last error if all retries are exhausted.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries and is_retryable_error(e):
                wait = RETRY_BACKOFF * (2 ** attempt)
                logger.warning(
                    "retry_call: retrying",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    wait=wait,
                    error=str(e)[:100],
                )
                time.sleep(wait)
            else:
                raise
    raise last_error  # type: ignore[misc]
