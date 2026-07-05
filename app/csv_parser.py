import csv
import io

from .config import settings
from .models import SimulationConfig


class CsvParseError(ValueError):
    pass


DEFAULT_DEMAND_CSV = (
    "weeks," + ",".join(str(i) for i in range(1, 36)) + "\n"
    "demand," + ",".join(["7"] * 5 + ["14"] * 30) + "\n"
    "ICH,1\n"
    "ICO,2\n"
).encode("utf-8")


def build_default_config() -> SimulationConfig:
    """35 weeks, demand=7 for weeks 1-5 then 14 for weeks 6-35, ICH=1, ICO=2 --
    used when no CSV is uploaded."""
    return parse_csv(DEFAULT_DEMAND_CSV)


def parse_csv(file_bytes: bytes) -> SimulationConfig:
    """Parses the transposed/ragged CSV shape:

        weeks,1,2,...,35
        demand,7,7,...,14
        ICH,1
        ICO,2

    Row labels are matched case-insensitively; ICH/ICO rows must carry
    exactly one constant value each.
    """
    text = file_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows: dict[str, list[str]] = {}
    for row in reader:
        if not row or not row[0].strip():
            continue
        label = row[0].strip().lower()
        values = [cell.strip() for cell in row[1:] if cell.strip() != ""]
        rows[label] = values

    for required in ("weeks", "demand", "ich", "ico"):
        if required not in rows:
            raise CsvParseError(f"CSV is missing required row: '{required}'")

    weeks_raw = rows["weeks"]
    demand_raw = rows["demand"]
    ich_raw = rows["ich"]
    ico_raw = rows["ico"]

    if len(weeks_raw) == 0:
        raise CsvParseError("'weeks' row has no values.")
    if len(weeks_raw) != len(demand_raw):
        raise CsvParseError(
            f"'weeks' row has {len(weeks_raw)} values but 'demand' row has "
            f"{len(demand_raw)} values; they must match."
        )
    if len(ich_raw) != 1:
        raise CsvParseError(
            f"'ICH' row must have exactly one constant value, found {len(ich_raw)}."
        )
    if len(ico_raw) != 1:
        raise CsvParseError(
            f"'ICO' row must have exactly one constant value, found {len(ico_raw)}."
        )

    try:
        weeks = [int(float(w)) for w in weeks_raw]
    except ValueError as e:
        raise CsvParseError(f"'weeks' row contains a non-numeric value: {e}") from e

    expected_weeks = list(range(1, len(weeks) + 1))
    if weeks != expected_weeks:
        raise CsvParseError(
            "'weeks' row must be a contiguous sequence starting at 1 "
            f"(got {weeks[:5]}{'...' if len(weeks) > 5 else ''})."
        )

    try:
        demand = [int(float(d)) for d in demand_raw]
    except ValueError as e:
        raise CsvParseError(f"'demand' row contains a non-numeric value: {e}") from e
    if any(d < 0 for d in demand):
        raise CsvParseError("'demand' values must be non-negative.")

    try:
        ich = float(ich_raw[0])
        ico = float(ico_raw[0])
    except ValueError as e:
        raise CsvParseError(f"'ICH'/'ICO' must be numeric: {e}") from e

    return SimulationConfig(
        total_weeks=len(weeks),
        customer_demand=demand,
        holding_cost_per_unit=ich,
        stockout_cost_per_unit=ico,
        lead_time_weeks=settings.lead_time_weeks,
        initial_stock=settings.initial_stock,
        initial_backlog=settings.initial_backlog,
        initial_order_placed=settings.initial_order_placed,
    )
