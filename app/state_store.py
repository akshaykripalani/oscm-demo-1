from . import db
from .engine import SimulationEngine
from .models import SimulationConfig


class StateStore:
    def __init__(self):
        self.engine: SimulationEngine | None = None
        self.last_config: SimulationConfig | None = None

    def load(self, config: SimulationConfig) -> SimulationEngine:
        self.last_config = config
        self.engine = SimulationEngine(config)
        self.persist_current()
        return self.engine

    def reset(self) -> SimulationEngine:
        if self.last_config is None:
            raise ValueError("No simulation has been loaded yet.")
        self.engine = SimulationEngine(self.last_config)
        self.persist_current()
        return self.engine

    def persist_current(self) -> None:
        if self.engine is not None:
            db.save_snapshot(
                self.engine.config,
                self.engine.current_week,
                self.engine.to_persisted_stages(),
            )

    def restore_from_db(self) -> None:
        loaded = db.load_snapshot()
        if loaded is None:
            return
        config, current_week, stages = loaded
        self.last_config = config
        self.engine = SimulationEngine(config, restore_stages=stages, current_week=current_week)


store = StateStore()
