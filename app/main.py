import csv
import io
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .csv_parser import CsvParseError, build_default_config, parse_csv
from .engine import SimulationComplete
from .models import StageRole, StepResult
from .state_store import store


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.restore_from_db()
    yield


app = FastAPI(title="Beer Distribution Game Simulator", lifespan=lifespan)


@app.post("/api/upload-csv", response_model=StepResult)
async def upload_csv(file: UploadFile):
    raw = await file.read()
    try:
        config = parse_csv(raw)
    except CsvParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    engine = store.load(config)
    return engine.snapshot()


@app.post("/api/use-default-data", response_model=StepResult)
async def use_default_data():
    engine = store.load(build_default_config())
    return engine.snapshot()


@app.post("/api/step", response_model=StepResult)
async def step():
    if store.engine is None:
        raise HTTPException(status_code=400, detail="No simulation loaded yet. Upload a CSV first.")
    try:
        result = await store.engine.step()
    except SimulationComplete as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    store.persist_current()
    return result


@app.get("/api/state", response_model=StepResult)
async def get_state():
    if store.engine is None:
        raise HTTPException(status_code=400, detail="No simulation loaded yet. Upload a CSV first.")
    return store.engine.snapshot()


@app.post("/api/reset", response_model=StepResult)
async def reset():
    try:
        engine = store.reset()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return engine.snapshot()


@app.get("/api/history/{role}/csv")
async def history_csv(role: StageRole):
    if store.engine is None:
        raise HTTPException(status_code=400, detail="No simulation loaded yet. Upload a CSV first.")

    history = store.engine.stages[role].history
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "week",
            "stock",
            "backlog",
            "order_placed",
            "holding_cost",
            "stockout_cost",
            "cumulative_cost",
        ]
    )
    for r in history:
        writer.writerow(
            [
                r.week,
                r.stock,
                r.backlog,
                r.order_placed,
                r.holding_cost,
                r.stockout_cost,
                r.cumulative_cost,
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={role.value}_history.csv"},
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
