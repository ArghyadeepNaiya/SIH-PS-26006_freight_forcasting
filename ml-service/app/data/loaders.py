"""Load rate history. Prefers the real CSV, falls back to scaffolding."""
import pandas as pd
from app.config import RAW
from app.data.synthetic import generate

CSV = RAW / "baltic_indices.csv"


def load_rates():
    """Return (dataframe, source_label, is_real)."""
    if CSV.exists():
        df = pd.read_csv(CSV)
        cols = {c.lower().strip(): c for c in df.columns}
        datecol = cols.get("date") or list(df.columns)[0]
        df = df.rename(columns={datecol: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=False)
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        for c in df.columns:
            if c != "date":
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df, f"data/raw/baltic_indices.csv ({len(df)} rows)", True
    df = generate()
    return df, "SCAFFOLDING - synthetic series, not real market data", False
