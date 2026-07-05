from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class StageRole(str, Enum):
    SUPPLIER = "supplier"
    MANUFACTURER = "manufacturer"
    DISTRIBUTOR = "distributor"
    RETAILER = "retailer"


# Chain topology: who each stage ships to / whose order each stage observes as
# its own demand. Retailer's downstream is the end customer (None).
DOWNSTREAM_OF: dict[StageRole, StageRole | None] = {
    StageRole.SUPPLIER: StageRole.MANUFACTURER,
    StageRole.MANUFACTURER: StageRole.DISTRIBUTOR,
    StageRole.DISTRIBUTOR: StageRole.RETAILER,
    StageRole.RETAILER: None,
}

# Downstream stages must decide first so the upstream neighbor can observe
# their just-placed order within the same week's step.
PROCESSING_ORDER: list[StageRole] = [
    StageRole.RETAILER,
    StageRole.DISTRIBUTOR,
    StageRole.MANUFACTURER,
    StageRole.SUPPLIER,
]

STAGE_DISPLAY_NAME: dict[StageRole, str] = {
    StageRole.SUPPLIER: "Supplier",
    StageRole.MANUFACTURER: "Manufacturer",
    StageRole.DISTRIBUTOR: "Distributor",
    StageRole.RETAILER: "Retailer",
}


class SimulationConfig(BaseModel):
    total_weeks: int
    customer_demand: list[int]
    holding_cost_per_unit: float
    stockout_cost_per_unit: float
    lead_time_weeks: int = 2
    initial_stock: int = 0
    initial_backlog: int = 0


class OrderDecision(BaseModel):
    order_quantity: int = Field(ge=0)
    reasoning: str


class StageSnapshot(BaseModel):
    role: StageRole
    stock: int
    backlog: int
    order_placed: int | None
    cumulative_holding_cost: float
    cumulative_stockout_cost: float
    cumulative_cost: float
    reasoning: str | None


class StepResult(BaseModel):
    week: int
    total_weeks: int
    done: bool
    holding_cost_per_unit: float
    stockout_cost_per_unit: float
    stages: dict[StageRole, StageSnapshot]
