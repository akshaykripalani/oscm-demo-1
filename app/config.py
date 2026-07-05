import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    gemini_api_key: str = os.environ["GEMINI_KEY"]
    model_name: str = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")
    thinking_budget: int = int(os.getenv("GEMINI_THINKING_BUDGET", "512"))
    lead_time_weeks: int = int(os.getenv("LEAD_TIME_WEEKS", "2"))
    initial_stock: int = int(os.getenv("INITIAL_STOCK", "14"))
    initial_backlog: int = int(os.getenv("INITIAL_BACKLOG", "0"))
    # None => derive from the first week's demand at config-build time.
    initial_order_placed: int | None = (
        int(os.environ["INITIAL_ORDER_PLACED"])
        if os.getenv("INITIAL_ORDER_PLACED")
        else None
    )


settings = Settings()
