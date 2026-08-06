import instructor

from backend.core.config import config


def get_llm_client(model_name="deepseek/deepseek-v4-flash"):
    or_client = instructor.from_provider(
        model_name,
        api_key=config.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        async_client=False,
    )
    return or_client
