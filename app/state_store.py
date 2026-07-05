from .engine import SimulationEngine
from .models import SimulationConfig


class StateStore:
    def __init__(self):
        self.engine: SimulationEngine | None = None
        self.last_config: SimulationConfig | None = None

    def load(self, config: SimulationConfig) -> SimulationEngine:
        self.last_config = config
        self.engine = SimulationEngine(config)
        return self.engine

    def reset(self) -> SimulationEngine:
        if self.last_config is None:
            raise ValueError("No simulation has been loaded yet.")
        self.engine = SimulationEngine(self.last_config)
        return self.engine


store = StateStore()
