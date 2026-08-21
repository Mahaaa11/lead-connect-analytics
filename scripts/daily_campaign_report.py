#!/usr/bin/env python3
"""Daily recyclage campaign report (status × color × outcomes).

Example:
  python3 scripts/daily_campaign_report.py \\
    --dc ~/Downloads/DC-10-08.xlsx \\
    --day 2026-08-10 \\
    --out-dir ~/Downloads

Uses the app store history/onoff by default.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config_env import bootstrap_env

bootstrap_env()

from engine import daily_campaign_analysis as dca
from engine import database


def main() -> int:
    p = argparse.ArgumentParser(description="Daily recyclage campaign analysis")
    p.add_argument("--dc", required=True, help="DC / Data Client Excel of the day")
    p.add_argument(
        "--day",
        required=True,
        help="Campaign day YYYY-MM-DD or YYYYMMDD or DD/MM/YYYY",
    )
    p.add_argument(
        "--out-dir",
        default=str(Path.home() / "Downloads"),
        help="Output folder (default: ~/Downloads)",
    )
    p.add_argument("--target-size", type=int, default=None, help="Target file size for mix reco")
    p.add_argument("--short-sec", type=int, default=60, help="Error threshold seconds (Onoff)")
    p.add_argument("--no-charts", action="store_true", help="Skip PDF charts")
    args = p.parse_args()

    dc_path = Path(args.dc).expanduser()
    if not dc_path.exists():
        print(f"DC file not found: {dc_path}", file=sys.stderr)
        return 1

    day = dca._parse_day(args.day)
    print(f"Loading DC: {dc_path}")
    dc = dca.load_dc_file(dc_path)
    print(f"  TEL uniques: {len(dc):,}")

    print("Loading store history…")
    hist = database.load_history()
    onoff = database.load_onoff_calls()
    print(f"  hist={len(hist):,}  onoff={len(onoff):,}")

    result = dca.compute_daily_campaign(
        dc,
        hist,
        day=day,
        onoff=onoff,
        short_sec=args.short_sec,
        target_size=args.target_size,
    )
    k = result["kpis"]
    print(
        f"\n{k['day_label']}: DC={k['dc_tels']} called={k['called']} "
        f"clearance={k['clearance_pct']}% ventes={k['ventes']} taux={k['taux_pct']}% "
        f"err<1min={k['errors_lt_1min']}"
    )

    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = day.strftime("%Y%m%d")
    xlsx = out_dir / f"Campagne_Recyclage_{stamp}.xlsx"
    dca.export_daily_campaign_excel(result, xlsx)
    print(f"Wrote {xlsx}")

    if not args.no_charts:
        pdf = out_dir / f"Campagne_Recyclage_{stamp}.pdf"
        got = dca.export_daily_campaign_charts(result, pdf)
        if got:
            print(f"Wrote {got}")
        else:
            print("Charts skipped (matplotlib unavailable)")

    # quick top buckets
    mix = result["mix"].head(8)
    if not mix.empty:
        print("\nTop buckets:")
        for _, r in mix.iterrows():
            print(
                f"  {r['Status_Category']}/{r['Color']}: n={int(r['TEL'])} "
                f"appelés={int(r['Appeles'])} clearance={r['Clearance_%']}% "
                f"ventes={int(r['Ventes'])} taux={r['Taux_vente_%']}%"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
