from collections import deque

from .agents import GeminiStageAgent
from .models import (
    DOWNSTREAM_OF,
    PROCESSING_ORDER,
    SimulationConfig,
    StageRole,
    StageSnapshot,
    StepResult,
    WeekRecord,
)


class SimulationComplete(Exception):
    pass


class StageState:
    def __init__(
        self,
        role: StageRole,
        config: SimulationConfig,
        restore: dict | None = None,
    ):
        self.role = role

        if restore is None:
            self.stock = config.initial_stock
            self.backlog = config.initial_backlog

            # Everyone is assumed to have already placed one order, one week
            # before week 1 -- so only the nearest pipeline slot is pre-filled
            # (it'll arrive in week 1); any further-out slots start empty
            # since no earlier order was placed.
            prior_order = (
                config.initial_order_placed
                if config.initial_order_placed is not None
                else config.customer_demand[0]
            )
            self.pipeline: deque[int] = deque(
                [prior_order] + [0] * (config.lead_time_weeks - 1)
            )
            self.last_order_placed: int | None = prior_order
            self.last_reasoning: str | None = None
            self.last_holding_cost = config.holding_cost_per_unit * self.stock
            self.last_stockout_cost = config.stockout_cost_per_unit * self.backlog
            self.cumulative_holding_cost = 0.0
            self.cumulative_stockout_cost = 0.0
            self.history: list[WeekRecord] = [
                WeekRecord(
                    week=0,
                    stock=self.stock,
                    backlog=self.backlog,
                    order_placed=self.last_order_placed,
                    holding_cost=self.last_holding_cost,
                    stockout_cost=self.last_stockout_cost,
                    cumulative_cost=0.0,
                )
            ]
        else:
            self.stock = restore["stock"]
            self.backlog = restore["backlog"]
            self.pipeline = deque(restore["pipeline"])
            self.last_order_placed = restore["last_order_placed"]
            self.last_reasoning = restore["last_reasoning"]
            self.last_holding_cost = restore["last_holding_cost"]
            self.last_stockout_cost = restore["last_stockout_cost"]
            self.cumulative_holding_cost = restore["cumulative_holding_cost"]
            self.cumulative_stockout_cost = restore["cumulative_stockout_cost"]
            self.history = [WeekRecord(**r) for r in restore["history"]]

        # Always a fresh chat session -- the agent's raw conversation memory
        # doesn't survive a restart, but build_recap() below feeds it the
        # true stock/backlog/cost facts each turn regardless, so its
        # decisions stay coherent even without the literal past turns.
        self.agent = GeminiStageAgent(role, config)

    def to_persisted_dict(self) -> dict:
        return {
            "stock": self.stock,
            "backlog": self.backlog,
            "pipeline": list(self.pipeline),
            "last_order_placed": self.last_order_placed,
            "last_reasoning": self.last_reasoning,
            "last_holding_cost": self.last_holding_cost,
            "last_stockout_cost": self.last_stockout_cost,
            "cumulative_holding_cost": self.cumulative_holding_cost,
            "cumulative_stockout_cost": self.cumulative_stockout_cost,
            "history": [r.model_dump() for r in self.history],
        }

    def build_recap(self) -> str | None:
        if self.last_order_placed is None:
            return None
        return (
            f"Last week you ordered {self.last_order_placed} units. You ended "
            f"last week with stock={self.stock}, backlog={self.backlog}, "
            f"incurring holding cost=${self.last_holding_cost:.2f} and stockout "
            f"cost=${self.last_stockout_cost:.2f}."
        )

    def snapshot(self) -> StageSnapshot:
        return StageSnapshot(
            role=self.role,
            stock=self.stock,
            backlog=self.backlog,
            order_placed=self.last_order_placed,
            cumulative_holding_cost=self.cumulative_holding_cost,
            cumulative_stockout_cost=self.cumulative_stockout_cost,
            cumulative_cost=self.cumulative_holding_cost + self.cumulative_stockout_cost,
            reasoning=self.last_reasoning,
        )


class SimulationEngine:
    def __init__(
        self,
        config: SimulationConfig,
        restore_stages: dict | None = None,
        current_week: int = 0,
    ):
        self.config = config
        self.current_week = current_week
        self.stages: dict[StageRole, StageState] = {
            role: StageState(
                role,
                config,
                restore=None if restore_stages is None else restore_stages[role.value],
            )
            for role in StageRole
        }

    def to_persisted_stages(self) -> dict:
        return {role.value: state.to_persisted_dict() for role, state in self.stages.items()}

    def snapshot(self) -> StepResult:
        return StepResult(
            week=self.current_week,
            total_weeks=self.config.total_weeks,
            done=self.current_week >= self.config.total_weeks,
            holding_cost_per_unit=self.config.holding_cost_per_unit,
            stockout_cost_per_unit=self.config.stockout_cost_per_unit,
            stages={role: state.snapshot() for role, state in self.stages.items()},
            history={role: state.history for role, state in self.stages.items()},
        )

    async def step(self) -> StepResult:
        if self.current_week >= self.config.total_weeks:
            raise SimulationComplete("Simulation already at its final week.")

        week = self.current_week + 1

        for role in PROCESSING_ORDER:
            stage = self.stages[role]

            recap = stage.build_recap()

            arrived = stage.pipeline.popleft()
            stage.stock += arrived
            in_transit = list(stage.pipeline)

            if role is StageRole.RETAILER:
                downstream_qty = self.config.customer_demand[week - 1]
            else:
                downstream_qty = self.stages[DOWNSTREAM_OF[role]].last_order_placed

            demand_to_fulfill = downstream_qty + stage.backlog

            decision = await stage.agent.decide_order(
                week=week,
                total_weeks=self.config.total_weeks,
                stock=stage.stock,
                backlog=stage.backlog,
                downstream_qty=downstream_qty,
                last_outcome=recap,
                in_transit=in_transit,
            )
            stage.last_order_placed = decision.order_quantity
            stage.last_reasoning = decision.reasoning

            shipped_now = min(stage.stock, demand_to_fulfill)
            stage.stock -= shipped_now
            stage.backlog = demand_to_fulfill - shipped_now

            downstream_role = DOWNSTREAM_OF[role]
            if downstream_role is not None:
                self.stages[downstream_role].pipeline.append(shipped_now)
            if role is StageRole.SUPPLIER:
                stage.pipeline.append(stage.last_order_placed)

            stage.last_holding_cost = self.config.holding_cost_per_unit * stage.stock
            stage.last_stockout_cost = (
                self.config.stockout_cost_per_unit * stage.backlog
            )
            stage.cumulative_holding_cost += stage.last_holding_cost
            stage.cumulative_stockout_cost += stage.last_stockout_cost

            stage.history.append(
                WeekRecord(
                    week=week,
                    stock=stage.stock,
                    backlog=stage.backlog,
                    order_placed=stage.last_order_placed,
                    holding_cost=stage.last_holding_cost,
                    stockout_cost=stage.last_stockout_cost,
                    cumulative_cost=stage.cumulative_holding_cost
                    + stage.cumulative_stockout_cost,
                )
            )

        self.current_week = week
        return self.snapshot()
