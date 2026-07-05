from google import genai
from google.genai import types

from .config import settings
from .models import OrderDecision, STAGE_DISPLAY_NAME, SimulationConfig, StageRole

DOWNSTREAM_DESCRIPTION: dict[StageRole, str] = {
    StageRole.RETAILER: "the number of units end customers demanded",
    StageRole.DISTRIBUTOR: "the number of units the Retailer ordered from you",
    StageRole.MANUFACTURER: "the number of units the Distributor ordered from you",
    StageRole.SUPPLIER: "the number of units the Manufacturer ordered from you",
}

UPSTREAM_DESCRIPTION: dict[StageRole, str] = {
    StageRole.RETAILER: "the Distributor",
    StageRole.DISTRIBUTOR: "the Manufacturer",
    StageRole.MANUFACTURER: "the Supplier",
    StageRole.SUPPLIER: "your own raw-material source",
}


def build_system_instruction(role: StageRole, config: SimulationConfig) -> str:
    name = STAGE_DISPLAY_NAME[role]
    downstream_desc = DOWNSTREAM_DESCRIPTION[role]
    upstream_desc = UPSTREAM_DESCRIPTION[role]

    supplier_note = ""
    if role is StageRole.SUPPLIER:
        supplier_note = (
            "\nSpecial note: your own upstream supply is unconstrained -- whatever "
            "quantity you order will always arrive in full after the lead time, "
            "with no capacity limit.\n"
        )

    return (
        f"You are the {name} in a 4-stage beer distribution supply chain "
        "(Supplier -> Manufacturer -> Distributor -> Retailer -> End Customer).\n\n"
        "You are operating completely independently. You cannot communicate with, "
        "message, or see the internal state, reasoning, stock, backlog, or identity "
        f"of any other stage in this chain. Each week you are told exactly one "
        f"external number: {downstream_desc}. That is the ONLY information you "
        "receive about anything downstream of you.\n\n"
        f"Your job each week is to decide how many units to order from your "
        f"upstream source ({upstream_desc}). Orders you place now will arrive "
        f"after a fixed lead time of {config.lead_time_weeks} weeks -- this lead "
        "time covers both placing the order and the goods physically arriving. "
        f"You will not see any effect of an order you place until "
        f"{config.lead_time_weeks} weeks from now.\n"
        f"{supplier_note}\n"
        "Costs you are trying to minimize over the course of the simulation:\n"
        f"- Holding cost: ${config.holding_cost_per_unit:.2f} per unit of "
        "inventory you are holding at the end of each week.\n"
        f"- Stockout / backlog cost: ${config.stockout_cost_per_unit:.2f} per "
        "unit of unmet demand that remains backlogged at the end of each week. "
        "Unmet demand carries forward until fulfilled, accruing this cost every "
        "week it remains open.\n\n"
        "Every week you will be given your current on-hand stock, your current "
        "backlog, the single downstream number you're allowed to observe, and a "
        "recap of what happened last week. Respond ONLY with the required "
        "structured JSON output: an `order_quantity` (a non-negative integer) "
        "and a short `reasoning` string (1-2 sentences) explaining your decision."
    )


def build_turn_prompt(
    role: StageRole,
    *,
    week: int,
    total_weeks: int,
    stock: int,
    backlog: int,
    downstream_qty: int,
    last_outcome: str | None,
) -> str:
    downstream_desc = DOWNSTREAM_DESCRIPTION[role]
    lines = [
        f"Week {week} of {total_weeks}.",
        f"Your current on-hand stock (after this week's incoming shipment "
        f"arrived): {stock} units.",
        f"Your current backlog (unmet demand still owed downstream): {backlog} units.",
        f"{downstream_desc.capitalize()} this week: {downstream_qty} units.",
    ]
    if last_outcome:
        lines.append(last_outcome)
    else:
        lines.append("This is your first turn -- you have no prior history yet.")
    lines.append("Decide how many units to order from your upstream source this week.")
    return "\n".join(lines)


_RETRY_MESSAGE = (
    "Your previous response could not be parsed as valid JSON matching the "
    "required schema. Respond again with ONLY a JSON object of the form "
    '{"order_quantity": <non-negative integer>, "reasoning": "<short text>"}.'
)


class GeminiStageAgent:
    # NOTE: uses the SDK's `client.aio` (async) chat session, not the sync one.
    # The sync `client.chats` session raises "Cannot send a request, as the
    # client has been closed" when called from inside a running asyncio event
    # loop (which FastAPI always has) -- the async client is the SDK's
    # intended way to call it from an async server.
    def __init__(self, role: StageRole, config: SimulationConfig):
        self.role = role
        # Keep a strong reference to the client for this agent's lifetime --
        # if it's a local variable that goes out of scope when __init__
        # returns, it gets garbage-collected immediately (CPython refcounting)
        # and its async httpx client is torn down with it, which then raises
        # "Cannot send a request, as the client has been closed" on first use.
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._chat = self._client.aio.chats.create(
            model=settings.model_name,
            config=types.GenerateContentConfig(
                system_instruction=build_system_instruction(role, config),
                thinking_config=types.ThinkingConfig(
                    thinking_budget=settings.thinking_budget
                ),
                response_mime_type="application/json",
                response_schema=OrderDecision,
            ),
        )

    async def decide_order(
        self,
        *,
        week: int,
        total_weeks: int,
        stock: int,
        backlog: int,
        downstream_qty: int,
        last_outcome: str | None,
    ) -> OrderDecision:
        prompt = build_turn_prompt(
            self.role,
            week=week,
            total_weeks=total_weeks,
            stock=stock,
            backlog=backlog,
            downstream_qty=downstream_qty,
            last_outcome=last_outcome,
        )
        decision = await self._try_send(prompt)
        if decision is not None:
            return decision

        decision = await self._try_send(_RETRY_MESSAGE)
        if decision is not None:
            return decision

        return OrderDecision(
            order_quantity=downstream_qty, reasoning="[fallback: parse failure]"
        )

    async def _try_send(self, message: str) -> OrderDecision | None:
        try:
            response = await self._chat.send_message(message)
        except Exception:
            return None
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, OrderDecision) and parsed.order_quantity >= 0:
            return parsed
        return None
