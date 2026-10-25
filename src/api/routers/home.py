"""Home page rows: curated customer lists with their true counts and observed leaving rates."""
from __future__ import annotations

from fastapi import APIRouter

from api import artifacts
from api.serialize import item

router = APIRouter(tags=["home"])
ROW_LIMIT = 30                               # customers returned per row (the row reports the true count)


@router.get("/home/rows")
def home_rows():
    df = artifacts.people()

    def row(key: str, title: str, d, rate: bool = True) -> dict:
        return {"key": key, "title": title, "count": int(len(d)),
                "rate": float(d["Exited"].mean()) if rate and len(d) and d["Exited"].notna().any() else None,
                "items": [item(r) for r in d.head(ROW_LIMIT).itertuples(index=False)]}

    top = df.head(10)
    rows = [row("top", "Top 10 value at risk today", top)]
    countries = df.groupby("Geography")["Exited"].mean().dropna()
    if len(countries):
        hi = str(countries.idxmax())
        rest = sorted(str(c) for c in countries.index if c != hi)
        rows.append(row("country", f"{hi}, the highest leaving rate", df[df["Geography"] == hi]))
        rows.append(row("products", "Holding 3 or 4 products", df[df["NumOfProducts"] >= 3]))
        rows.append(row("staying", "Still with the bank, worth watching", df[df["Exited"] == 0], rate=False))
        rows.append(row("others", " and ".join(rest), df[df["Geography"].isin(rest)]))
    return {"rows": rows}
