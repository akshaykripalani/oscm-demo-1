# Beer Distribution Game -- AI Agent Simulator

Four independent Gemini-driven agents (Supplier, Manufacturer, Distributor, Retailer)
each place weekly orders with no communication between them -- each only ever sees
its own stock/backlog and a single number: the order its immediate downstream
neighbor just placed (or customer demand, for the Retailer).

## Setup

```bash
uv sync
```

Requires a `.env` file with `GEMINI_KEY=<your Gemini API key>`.

## Run

```bash
uv run python run.py
```

Prints clickable links to the app and API docs, and shuts down cleanly on Ctrl+C.
Upload `data/sample_demand.csv` (or your own CSV in the same shape) and click
"Step forward one week" to advance the simulation.

(Alternatively, `uv run uvicorn app.main:app --reload` for auto-reload during development.)

## CSV format

```
weeks,1,2,...,N
demand,<N values>
ICH,<holding cost per unit per week>
ICO,<stockout/backlog cost per unit per week>
```
