from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from .csv_parser import CsvParseError, build_default_config, parse_csv
from .engine import SimulationComplete
from .models import StepResult
from .state_store import store

app = FastAPI(title="Beer Distribution Game Simulator")


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
        return await store.engine.step()
    except SimulationComplete as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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


app.mount("/", StaticFiles(directory="static", html=True), name="static")
