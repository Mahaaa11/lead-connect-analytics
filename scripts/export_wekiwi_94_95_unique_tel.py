#!/usr/bin/env python3
"""Build WeKiwi unique-TEL export: 94/95 in a given year, no vente after, DB mask.

STATUS / LIB_STATUS in the output are NOT the DB fiche values.
They are the latest histo status AFTER the first 94/95 of that year,
excluding vente (STATUS=1 / LIB Vente).

Example:
  python3 scripts/export_wekiwi_94_95_unique_tel.py \\
    --db ~/Downloads/export_db_wekiwi_01012025-31072025_consentement_05082025-net.xlsx \\
    --histo ~/Downloads/export_db_histo_wekiwi_01012025-31072025_consentement_05082025-net.xlsx \\
    --year 2025 \\
    --out ~/Downloads/wekiwi_94_95_2025_unique_TEL.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Allow running from repo root or scripts/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from engine.processor import DEFAULT_STATUS_MAPPING
except ImportError:  # standalone fallback
    DEFAULT_STATUS_MAPPING = {
        94: "Rappel Personnel",
        95: "A Relancer",
        6: "Pas décisionnaire",
        4: "Pas de collaboration",
        2: "Refus",
        5: "Ne jamais appeler",
        93: "Répondeur",
        92: "Absent",
        96: "Indisponible",
        99: "Injoignable",
        3: "Hors cible",
        14: "Raccroche au nez",
    }

STATUS_LABELS: dict[int, str] = {
    **DEFAULT_STATUS_MAPPING,
    1: "Vente",
    91: "Wrong Number System",
    8: "Ne fais rien par telephone",
    9: "DETTES",
    10: "BLOCTEL",
    12: "Code 12",
    13: "Code 13",
    0: "Code 0",
}


def _code_series(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def _label_for_code(code: str) -> str:
    try:
        return STATUS_LABELS.get(int(code), f"Code {code}")
    except ValueError:
        return str(code) if code else ""


def _fmt_status_date(row: pd.Series) -> str:
    raw = str(row.get("Status_Date") or "").strip().replace(".0", "")
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[6:8]}/{raw[4:6]}/{raw[0:4]}"
    dt = row.get("_dt")
    return dt.strftime("%d/%m/%Y") if pd.notna(dt) else ""


def build_export(
    *,
    db_path: Path,
    histo_path: Path,
    year: int,
    out_path: Path,
) -> pd.DataFrame:
    year_s = str(year)
    print(f"Loading histo: {histo_path}")
    hi = pd.read_excel(histo_path, sheet_name=0, dtype=str)
    print(f"Loading DB:    {db_path}")
    db = pd.read_excel(db_path, sheet_name=0, dtype=str)

    ss = _code_series(hi["Status_Status"])
    st = _code_series(hi["STATUS"])
    lib = hi["LIB_STATUS"].fillna("").astype(str).str.strip()
    lib_u = lib.str.upper()

    hi = hi.copy()
    hi["_event"] = ss.where(ss.ne(""), st)
    hi["TEL"] = hi["TEL"].fillna("").astype(str).str.strip()
    hi["LIB_STATUS"] = lib
    hi = hi[hi["TEL"].ne("") & ~hi["TEL"].str.lower().isin(["nan", "none"])].copy()

    sd = _code_series(hi["Status_Date"])
    stt = (
        hi["Status_StartTime"]
        .fillna("0")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )
    hi["_year"] = sd.str.slice(0, 4)
    hi["_dt"] = pd.to_datetime(sd + stt, format="%Y%m%d%H%M%S", errors="coerce")

    is_vente = hi["_event"].eq("1") | lib_u.reindex(hi.index).eq("VENTE")
    is_9495_year = hi["_event"].isin(["94", "95"]) & hi["_year"].eq(year_s)
    tels_9495 = set(hi.loc[is_9495_year, "TEL"])
    print(f"TEL with 94/95 in {year}: {len(tels_9495):,}")

    sub = hi[hi["TEL"].isin(tels_9495)].copy()
    first_year = (
        sub.loc[is_9495_year.reindex(sub.index).fillna(False)]
        .groupby("TEL")["_dt"]
        .min()
    )

    # Exclude TEL with a vente after the first 94/95 of that year
    converted: set[str] = set()
    ventes = sub.loc[is_vente.reindex(sub.index).fillna(False), ["TEL", "_dt"]]
    for tel, vdt in zip(ventes["TEL"], ventes["_dt"]):
        t0 = first_year.get(tel)
        if pd.isna(t0) or pd.isna(vdt) or vdt > t0:
            converted.add(tel)

    db = db.copy()
    db["TEL"] = db["TEL"].fillna("").astype(str).str.strip()
    db_st = _code_series(db["STATUS"])
    db_lib = db["LIB_STATUS"].fillna("").astype(str).str.upper().str.strip()
    db_vente = set(db.loc[db_st.eq("1") | db_lib.eq("VENTE"), "TEL"])

    keep = tels_9495 - converted - db_vente
    print(f"Excluded vente after 94/95: {len(converted & tels_9495):,}")
    print(f"Excluded current DB vente:  {len((tels_9495 - converted) & db_vente):,}")
    print(f"Keep: {len(keep):,}")

    # Latest NON-vente histo status after first 94/95
    latest_rows: list[dict] = []
    subk = hi[hi["TEL"].isin(keep)].copy()
    for tel, g in subk.groupby("TEL", sort=False):
        t0 = first_year.get(tel)
        g = g.sort_values("_dt", kind="mergesort")
        after = g[g["_dt"].notna() & (g["_dt"] > t0)] if pd.notna(t0) else g.iloc[0:0]
        after_nv = after.loc[~is_vente.reindex(after.index).fillna(False)]
        if not after_nv.empty:
            last = after_nv.iloc[-1]
            src = "after_94_95"
        else:
            g9495 = g.loc[is_9495_year.reindex(g.index).fillna(False)]
            last = g9495.iloc[-1] if not g9495.empty else g.iloc[-1]
            src = "94_95_itself"

        code = str(last["_event"]).strip()
        if code == "1" or str(last.get("LIB_STATUS", "")).upper().strip() == "VENTE":
            earlier = g.loc[~is_vente.reindex(g.index).fillna(False)]
            if earlier.empty:
                continue
            last = earlier.iloc[-1]
            code = str(last["_event"]).strip()
            src = "fallback_non_vente"

        latest_rows.append(
            {
                "TEL": tel,
                "STATUS": code,
                "LIB_STATUS": _label_for_code(code),
                "LIB_DETAIL": str(last.get("LIB_DETAIL") or "")
                if "LIB_DETAIL" in last.index
                else "",
                "_status_src": src,
            }
        )

    st_df = pd.DataFrame(latest_rows)
    print("Status sources:\n", st_df["_status_src"].value_counts().to_string())
    assert int(st_df["STATUS"].eq("1").sum()) == 0

    # 94/95 summary columns
    ev = hi.loc[
        is_9495_year & hi["TEL"].isin(set(st_df["TEL"])),
        ["TEL", "_event", "_dt", "Status_Date"],
    ].copy()
    ev = ev.sort_values(["TEL", "_dt"], kind="mergesort")

    def summarize(g: pd.DataFrame) -> pd.Series:
        codes = sorted(set(g["_event"].tolist()))
        label = "94" if codes == ["94"] else ("95" if codes == ["95"] else "94+95")
        last, first = g.iloc[-1], g.iloc[0]
        return pd.Series(
            {
                "Statut_94_95": label,
                "Date_94_95": _fmt_status_date(last),
                "Date_premier_94_95": _fmt_status_date(first),
                "Had_94": "94" in codes,
                "Had_95": "95" in codes,
            }
        )

    summary = ev.groupby("TEL", sort=False).apply(summarize, include_groups=False).reset_index()

    # DB mask rows (one per TEL), overwrite STATUS/LIB from histo
    final = db[db["TEL"].isin(set(st_df["TEL"]))].copy()
    final["_d"] = pd.to_numeric(final.get("DATE"), errors="coerce")
    final["_h"] = pd.to_numeric(final.get("HEURE"), errors="coerce")
    final = (
        final.sort_values(["_d", "_h"], kind="mergesort")
        .drop_duplicates("TEL", keep="last")
        .drop(columns=["_d", "_h"])
        .reset_index(drop=True)
    )
    final = final.drop(
        columns=[c for c in ("STATUS", "LIB_STATUS", "LIB_DETAIL") if c in final.columns],
        errors="ignore",
    )
    final = final.merge(st_df[["TEL", "STATUS", "LIB_STATUS", "LIB_DETAIL"]], on="TEL", how="left")
    final = final.merge(summary, on="TEL", how="left")

    final = final[
        _code_series(final["STATUS"]).ne("1")
        & ~final["LIB_STATUS"].fillna("").astype(str).str.upper().str.strip().eq("VENTE")
    ].copy()

    cols = list(final.columns)
    for c in ("Statut_94_95", "Date_94_95", "Date_premier_94_95", "Had_94", "Had_95"):
        if c in cols:
            cols.remove(c)
    i = cols.index("TEL") + 1
    for j, c in enumerate(
        ("Statut_94_95", "Date_94_95", "Date_premier_94_95", "Had_94", "Had_95")
    ):
        cols.insert(i + j, c)
    final = final[cols].reset_index(drop=True)

    print(f"Final rows: {len(final):,}  ·  STATUS=1: {(final['STATUS']=='1').sum()}")
    print("STATUS top:\n", final["STATUS"].value_counts().head(12).to_string())
    print("LIB_STATUS top:\n", final["LIB_STATUS"].value_counts().head(12).to_string())

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        final.to_excel(writer, sheet_name="Sheet1", index=False)
        wb, ws = writer.book, writer.sheets["Sheet1"]
        fmt = wb.add_format({"num_format": "@"})
        for col in (
            "TEL",
            "TEL2",
            "STATUS",
            "Statut_94_95",
            "Date_94_95",
            "Date_premier_94_95",
            "PDL",
            "PCE",
            "IBAN",
        ):
            if col in final.columns:
                idx = list(final.columns).index(col)
                ws.set_column(idx, idx, 18, fmt)
    print(f"WROTE {out_path}")
    return final


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, required=True, help="DB WeKiwi Excel (mask source)")
    p.add_argument("--histo", type=Path, required=True, help="Histo WeKiwi Excel")
    p.add_argument("--year", type=int, default=2025, help="Year filter for 94/95 (default 2025)")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output xlsx (default: wekiwi_94_95_<year>_unique_TEL.xlsx in cwd)",
    )
    args = p.parse_args()
    out = args.out or Path(f"wekiwi_94_95_{args.year}_unique_TEL.xlsx")
    build_export(db_path=args.db, histo_path=args.histo, year=args.year, out_path=out)


if __name__ == "__main__":
    main()
