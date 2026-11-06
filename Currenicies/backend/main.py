from __future__ import annotations

from pathlib import Path
from typing import Any
import re

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
DATASET_STEMS = ("cleaned_currency_data.csv", "cleaned_currency_data.CSV", "cleaned_currency_data.json", "cleaned_currency_data")
app = FastAPI(title="Currency Atlas API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def norm(value: str) -> str:
    return re.sub(r"[ _-]", "", value.lower())

def choose(columns: list[str], options: tuple[str, ...]) -> str | None:
    return next((col for col in columns if norm(col) in options), None) or next((col for col in columns if any(option in norm(col) for option in options)), None)

def dataset() -> tuple[pd.DataFrame, dict[str, str | None]]:
    path = next((ROOT / name for name in DATASET_STEMS if (ROOT / name).exists()), None)
    if not path:
        raise HTTPException(404, "Dataset not found. Put cleaned_currency_data.csv in the project root.")
    frame = pd.read_json(path) if path.suffix.lower() == ".json" else pd.read_csv(path)
    cols = list(frame.columns)
    mapping = {
        "currency": choose(cols, ("quote", "quotecurrency", "currencycode", "currency", "code", "symbol")),
        "base": choose(cols, ("base", "basecurrency")),
        "country": choose(cols, ("country", "countryname", "nation")),
        "rate": choose(cols, ("exchangerate", "usdrate", "rate", "value", "close", "price")),
        "date": choose(cols, ("date", "timestamp", "time", "year")),
    }
    if not mapping["rate"] or not (mapping["currency"] or mapping["country"]):
        raise HTTPException(422, {"message": "Could not infer currency and exchange-rate columns.", "columns": cols})
    label = mapping["currency"] or mapping["country"]
    frame["currency"] = frame[label].astype(str).str.strip().str.upper()
    frame["rate"] = pd.to_numeric(frame[mapping["rate"]], errors="coerce")
    # The supplied data is USD -> quote. The UI displays one unit of the
    # selected quote currency in USD, so invert those rows before returning.
    if mapping["base"]:
        usd_base = frame[mapping["base"]].astype(str).str.strip().str.upper().eq("USD")
        frame.loc[usd_base, "rate"] = 1 / frame.loc[usd_base, "rate"]
    frame["date"] = pd.to_datetime(frame[mapping["date"]], errors="coerce") if mapping["date"] else pd.NaT
    return frame.dropna(subset=["currency", "rate"]).query("rate > 0"), mapping

def forecast(values: pd.Series) -> float:
    if len(values) < 2:
        return float(values.iloc[-1])
    model = LinearRegression().fit(pd.DataFrame({"step": range(len(values))}), values)
    horizon = min(12, max(1, round(len(values) * .15)))
    return max(0.0, float(model.predict(pd.DataFrame({"step": [len(values) + horizon]}))[0]))

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
def website() -> FileResponse:
    return FileResponse(ROOT / "index.html")

@app.get("/data-loader.js", include_in_schema=False)
def data_loader() -> FileResponse:
    return FileResponse(ROOT / "data-loader.js", media_type="application/javascript")

@app.get("/dataset.csv", include_in_schema=False)
def download_dataset() -> FileResponse:
    path = ROOT / "cleaned_currency_data.csv"
    if not path.exists():
        raise HTTPException(404, "Dataset not found")
    return FileResponse(path, media_type="text/csv", filename=path.name)

@app.get("/currencies")
def currencies() -> list[str]:
    frame, _ = dataset()
    return sorted(frame.currency.unique().tolist())

@app.get("/history/{currency}")
def history(currency: str) -> list[dict[str, Any]]:
    frame, _ = dataset()
    rows = frame[frame.currency == currency.upper()].sort_values("date")
    if rows.empty:
        raise HTTPException(404, "Currency not found")
    return [{"date": row.date.isoformat() if pd.notna(row.date) else None, "rate": float(row.rate)} for row in rows.itertuples()]

@app.get("/forecast/{currency}")
def currency_forecast(currency: str) -> dict[str, Any]:
    frame, _ = dataset()
    rows = frame[frame.currency == currency.upper()].sort_values("date")
    if rows.empty:
        raise HTTPException(404, "Currency not found")
    rates = rows.rate.reset_index(drop=True)
    current = float(rates.iloc[-1])
    projected = forecast(rates)
    return {"currency": currency.upper(), "current_rate": current, "forecast_rate": projected, "forecast_change_pct": (projected / current - 1) * 100, "observations": len(rates), "model": "linear regression trend"}

@app.get("/statistics")
def statistics() -> list[dict[str, Any]]:
    frame, _ = dataset()
    output = []
    for currency, group in frame.groupby("currency"):
        rates = group.sort_values("date").rate.reset_index(drop=True)
        output.append({"currency": currency, "observations": len(rates), "mean": float(rates.mean()), "median": float(rates.median()), "minimum": float(rates.min()), "maximum": float(rates.max()), "std_dev": float(rates.std(ddof=0)), "volatility_pct": float(rates.pct_change().std(ddof=0) * 100) if len(rates) > 1 else 0.0, "forecast": forecast(rates)})
    return sorted(output, key=lambda item: item["volatility_pct"], reverse=True)
