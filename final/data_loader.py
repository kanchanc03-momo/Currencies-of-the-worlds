"""Schema-aware loader for the uploaded currency CSV. No external packages required."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
CANDIDATES = [
    PROJECT_ROOT / "data" / "cleaned_currency_data.csv",
    BACKEND_DIR / "data" / "cleaned_currency_data.csv",
    PROJECT_ROOT / "cleaned_currency_data.csv",
]

class DatasetLoadError(RuntimeError): pass
def clean(value: str) -> str: return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())
def choose(columns: list[str], names: tuple[str, ...]) -> str | None:
    normal = {clean(column): column for column in columns}
    for name in names:
        if name in normal: return normal[name]
    for column in columns:
        if any(name in clean(column) for name in names): return column
    return None
def parse_date(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value: return None
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError: pass
    for form in ("%Y-%m-%d","%d-%m-%Y","%m-%d-%Y","%d/%m/%Y","%m/%d/%Y","%Y/%m/%d","%d.%m.%Y","%Y%m%d"):
        try: return datetime.strptime(value, form)
        except ValueError: continue
    return None
def numeric(value: Any) -> float | None:
    try:
        result = float(str(value).strip().replace(",", "").replace("$", "").replace("%", ""))
        return result if result > 0 else None
    except (TypeError, ValueError): return None
@dataclass
class LoadedDataset:
    path: Path; detected_columns: list[str]; mapping: dict[str, str | None]; rows: list[dict[str, Any]]; total_rows: int; invalid_rate_rows: int; invalid_date_rows: int; searched: list[str]
    def summary(self) -> dict[str, Any]:
        dates = [row["date"] for row in self.rows if row["date"]]
        bases = sorted({row["base"] for row in self.rows})
        quotes = sorted({row["quote"] for row in self.rows})
        return {"resolved_dataset_path": str(self.path), "searched_locations": self.searched, "detected_columns": self.detected_columns, "column_mapping": self.mapping, "total_rows": self.total_rows, "valid_rows": len(self.rows), "invalid_rate_rows": self.invalid_rate_rows, "invalid_date_rows": self.invalid_date_rows, "earliest_date": min(dates).date().isoformat() if dates else None, "latest_date": max(dates).date().isoformat() if dates else None, "available_base_currencies": bases, "available_quote_currencies": quotes, "usd_inr_latest": latest_pair(self, "USD", "INR")}
def locate() -> tuple[Path, list[str]]:
    searched = [str(path) for path in CANDIDATES]
    for path in CANDIDATES:
        if path.is_file(): return path, searched
    csv_files = sorted(PROJECT_ROOT.rglob("*.csv")) + sorted(PROJECT_ROOT.rglob("*.CSV"))
    searched.append(f"recursive CSV search under {PROJECT_ROOT}")
    preferred = [path for path in csv_files if "cleaned" in path.name.lower() and "currency" in path.name.lower()]
    if preferred: return preferred[0], searched
    if len(csv_files) == 1: return csv_files[0], searched
    found = [str(path) for path in csv_files]
    raise DatasetLoadError(f"No unambiguous currency CSV found. Searched: {searched}. CSV files detected: {found}")
def load_dataset() -> LoadedDataset:
    path, searched = locate()
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        raw_columns = reader.fieldnames or []
        columns = [str(column).strip() for column in raw_columns]
        raw_rows = list(reader)
    if not columns: raise DatasetLoadError(f"Dataset {path} has no header row. Searched: {searched}")
    date_col = choose(columns, ("date","datetime","timestamp","time","observationdate","recorddate"))
    base_col = choose(columns, ("basecurrency","base","fromcurrency","sourcecurrency"))
    quote_col = choose(columns, ("quotecurrency","quote","tocurrency","targetcurrency","currencycode","currency","code","symbol"))
    rate_col = choose(columns, ("exchangerate","rate","usdrate","close","price","value","fxrate"))
    mapping = {"date": date_col, "base": base_col or "<inferred USD>", "quote": quote_col, "rate": rate_col}
    if not quote_col or not rate_col:
        raise DatasetLoadError(f"Could not map quote currency and rate columns. Detected columns: {columns}. Mapping: {mapping}. Searched: {searched}")
    rows=[]; invalid_rate=invalid_date=0
    for raw in raw_rows:
        row = {str(k).strip(): v for k, v in raw.items() if k is not None}
        value = numeric(row.get(rate_col))
        if value is None: invalid_rate += 1; continue
        date = parse_date(row.get(date_col, "")) if date_col else None
        if date_col and date is None: invalid_date += 1
        base = str(row.get(base_col, "USD") if base_col else "USD").strip().upper()
        quote = str(row.get(quote_col, "")).strip().upper()
        if not base or not quote: invalid_rate += 1; continue
        rows.append({"date": date, "base": base, "quote": quote, "rate": value})
    if not rows: raise DatasetLoadError(f"No valid rows after parsing {path}. Detected columns: {columns}; mapping: {mapping}; invalid_rate_rows={invalid_rate}; invalid_date_rows={invalid_date}")
    rows.sort(key=lambda row: row["date"] or datetime.min)
    return LoadedDataset(path, columns, mapping, rows, len(raw_rows), invalid_rate, invalid_date, searched)
def latest_pair(dataset: LoadedDataset, base: str, quote: str) -> dict[str, Any] | None:
    direct = [row for row in dataset.rows if row["base"] == base and row["quote"] == quote]
    if direct:
        row = direct[-1]; return {"base": base, "quote": quote, "rate": row["rate"], "observation_date": row["date"].date().isoformat() if row["date"] else None, "inverted": False}
    reverse = [row for row in dataset.rows if row["base"] == quote and row["quote"] == base]
    if reverse:
        row = reverse[-1]; return {"base": base, "quote": quote, "rate": 1 / row["rate"], "observation_date": row["date"].date().isoformat() if row["date"] else None, "inverted": True}
    return None
