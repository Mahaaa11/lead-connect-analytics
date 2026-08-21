"""Daily per-agent PDF reports: conversion origins + Pas de collab / Refus / Onoff."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO

import pandas as pd

from engine.agent_analytics import _normalize_agent_label
from engine.dashboard import SALE_STATUS_CODE
from engine.processor import (
    _clean_tel_db,
    _format_duration,
    _normalize_columns,
    last_onoff_call_durations,
    merge_onoff_calls,
    read_onoff_calls,
)
from engine.status_labels import apply_resolved_status_labels, group_status_label

# Matplotlib needs a writable config dir in some sandboxed / headless envs.
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplconfig")

PRIOR_KEYS = (
    "Répondeur",
    "Sans contact précédent",
    "Rappel Personnel",
    "RELANCE",
    "Pas de collaboration",
    "Refus",
    "Raccroche au nez",
    "Autre",
)

# Last-status mix shown in PDF 2 (order = table / stacked chart).
OUTCOME_KEYS = (
    "Répondeur",
    "Pas de collaboration",
    "Raccroche au nez",
    "Rappel Personnel",
    "RELANCE",
    "Refus",
    "Vente",
    "Faux Numéro",
    "Injoignable",
    "Hors cible",
)

PRIOR_COLORS = {
    "Répondeur": "#3B82F6",
    "Sans contact précédent": "#94A3B8",
    "Rappel Personnel": "#F59E0B",
    "RELANCE": "#22C55E",
    "Pas de collaboration": "#F97316",
    "Refus": "#EF4444",
    "Raccroche au nez": "#A855F7",
    "Vente": "#16A34A",
    "Faux Numéro": "#78716C",
    "Injoignable": "#64748B",
    "Hors cible": "#0EA5E9",
    "Autre": "#94A3B8",
}


def _fold_agent(label: str) -> str:
    """Collapse duplicated first-name TV labels (e.g. 'Camille Camille' → 'Camille')."""
    text = _normalize_agent_label(label)
    if text == "Non renseigné":
        return text
    parts = text.split()
    if len(parts) >= 2 and parts[0].casefold() == parts[1].casefold():
        return parts[0]
    return text


def _fmt_moy(seconds: float | int | None) -> str:
    if seconds is None or (isinstance(seconds, float) and pd.isna(seconds)):
        return "—"
    sec = int(round(float(seconds)))
    if sec < 60:
        return f"{sec}s"
    minutes, secs = divmod(sec, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _prepare_day_histo(histo: pd.DataFrame) -> pd.DataFrame:
    if histo is None or histo.empty:
        return pd.DataFrame()
    df = histo.copy()
    if "TEL" not in df.columns and "TEL_DB" in df.columns:
        df["TEL"] = df["TEL_DB"]
    df["TEL"] = _clean_tel_db(df["TEL"].astype(str))
    agent_col = "TV" if "TV" in df.columns else None
    if agent_col is None:
        for cand in ("STATUS_USER", "AGENT"):
            if cand in df.columns:
                agent_col = cand
                break
    if agent_col:
        df["Agent"] = df[agent_col].map(_fold_agent)
    else:
        df["Agent"] = "Non renseigné"
    if "Status_Label" not in df.columns:
        df["Status_Label"] = apply_resolved_status_labels(df)
    df["Status_Group"] = df["Status_Label"].map(group_status_label)
    if "DATETIME" not in df.columns:
        df["DATETIME"] = pd.NaT
    if "HEURE" in df.columns:
        df["_h"] = pd.to_numeric(df["HEURE"], errors="coerce").fillna(0)
    else:
        df["_h"] = 0
    return df


def _prepare_client(client: pd.DataFrame | None) -> pd.DataFrame:
    if client is None or client.empty:
        return pd.DataFrame()
    df = _normalize_columns(client.copy())
    if "TEL" not in df.columns:
        return pd.DataFrame()
    df["TEL"] = _clean_tel_db(df["TEL"].astype(str))
    agent_col = "TV" if "TV" in df.columns else None
    if agent_col:
        df["Agent"] = df[agent_col].map(_fold_agent)
    else:
        df["Agent"] = "Non renseigné"
    return df


def _load_onoff_calls(onoff_sources: list[Any] | None) -> pd.DataFrame:
    if not onoff_sources:
        return pd.DataFrame()
    sources = list(onoff_sources)
    try:
        if len(sources) == 1:
            return read_onoff_calls(sources[0])
        calls, _totals, _stats = merge_onoff_calls(sources)
        return calls
    except Exception:
        parts: list[pd.DataFrame] = []
        for src in sources:
            try:
                if hasattr(src, "seek"):
                    src.seek(0)
                parts.append(read_onoff_calls(src))
            except Exception:
                continue
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _prior_from_history(
    vente_tels: pd.DataFrame,
    store_history: pd.DataFrame | None,
    day_histo: pd.DataFrame,
) -> pd.DataFrame:
    """Last non-vente status before each vente TEL."""
    rows: list[dict[str, Any]] = []
    hist = pd.DataFrame()
    if store_history is not None and not store_history.empty:
        hist = store_history.copy()
        hist = _normalize_columns(hist) if "TEL" not in hist.columns else hist
        if "TEL" in hist.columns:
            hist["TEL"] = _clean_tel_db(hist["TEL"].astype(str))
            if "Status_Label" not in hist.columns:
                hist["Status_Label"] = apply_resolved_status_labels(hist)
            hist["Status_Group"] = hist["Status_Label"].map(group_status_label)
            if "DATETIME" not in hist.columns and "DATE" in hist.columns:
                dcol = hist["DATE"].astype(str).str.replace(r"\.0$", "", regex=True)
                hcol = (
                    hist["HEURE"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
                    if "HEURE" in hist.columns
                    else "0000"
                )
                hist["DATETIME"] = pd.to_datetime(
                    dcol + hcol + "00",
                    format="%Y%m%d%H%M%S",
                    errors="coerce",
                )

    for _, row in vente_tels.iterrows():
        tel = str(row["TEL"])
        agent = str(row.get("Agent") or "Non renseigné")
        prior = "Sans contact précédent"
        if not hist.empty:
            g = hist[hist["TEL"] == tel].sort_values("DATETIME")
            is_vente = pd.to_numeric(g.get("STATUS", pd.Series(dtype=float)), errors="coerce") == int(
                SALE_STATUS_CODE
            )
            vg = g[is_vente]
            if not vg.empty:
                t0 = vg.iloc[0]["DATETIME"]
                before = g[
                    (g["DATETIME"] < t0)
                    & (pd.to_numeric(g["STATUS"], errors="coerce") != int(SALE_STATUS_CODE))
                ]
                if not before.empty:
                    prior = str(before.iloc[-1]["Status_Group"])
        if prior == "Sans contact précédent" and not day_histo.empty:
            gh = day_histo[day_histo["TEL"] == tel].sort_values(["DATETIME", "_h"])
            is_v = pd.to_numeric(gh.get("STATUS", pd.Series(dtype=float)), errors="coerce") == int(
                SALE_STATUS_CODE
            )
            if is_v.any():
                idx = is_v[is_v].index[0]
                before = gh.loc[:idx].iloc[:-1]
                before = before[
                    pd.to_numeric(before.get("STATUS", pd.Series(dtype=float)), errors="coerce")
                    != int(SALE_STATUS_CODE)
                ]
                if not before.empty:
                    prior = str(before.iloc[-1]["Status_Group"])
        rows.append({"TEL": tel, "Agent": agent, "Prior": prior})
    return pd.DataFrame(rows)


@dataclass
class DailyAgentReport:
    day_label: str
    ventes_total: int = 0
    prior_total: dict[str, int] = field(default_factory=dict)
    agents: list[dict[str, Any]] = field(default_factory=list)
    vente_details: pd.DataFrame = field(default_factory=pd.DataFrame)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def compute_daily_agent_report(
    *,
    histo: pd.DataFrame,
    data_client: pd.DataFrame | None = None,
    onoff_sources: list[Any] | None = None,
    store_history: pd.DataFrame | None = None,
    day_label: str | None = None,
) -> DailyAgentReport:
    """Build per-agent conversion origins + Pas de collab / Refus / Onoff metrics."""
    day = day_label or datetime.now().strftime("%d/%m/%Y")
    day_histo = _prepare_day_histo(histo)
    client = _prepare_client(data_client)

    if day_histo.empty and client.empty:
        return DailyAgentReport(day_label=day)

    # Last status per TEL from histo
    if not day_histo.empty:
        last = (
            day_histo.sort_values(["DATETIME", "_h"])
            .groupby("TEL", as_index=False)
            .tail(1)
            .copy()
        )
    else:
        last = pd.DataFrame(columns=["TEL", "Agent", "Status_Group"])

    # Ventes: prefer data client STATUS=1, else histo
    if not client.empty and "STATUS" in client.columns:
        ventes = client[pd.to_numeric(client["STATUS"], errors="coerce") == int(SALE_STATUS_CODE)][
            ["TEL", "Agent"]
        ].drop_duplicates("TEL")
    else:
        ventes = last[last["Status_Group"] == "Vente"][["TEL", "Agent"]].drop_duplicates("TEL")
        if ventes.empty and not day_histo.empty:
            codes = pd.to_numeric(day_histo["STATUS"], errors="coerce")
            ventes = (
                day_histo[codes == int(SALE_STATUS_CODE)][["TEL", "Agent"]]
                .drop_duplicates("TEL")
            )

    vente_tels = set(ventes["TEL"].astype(str)) if not ventes.empty else set()
    if not last.empty:
        last = last.copy()
        last.loc[last["TEL"].isin(vente_tels), "Status_Group"] = "Vente"
        # Prefer agent from vente/client when available
        if not ventes.empty:
            agent_map = dict(zip(ventes["TEL"].astype(str), ventes["Agent"]))
            last["Agent"] = last["TEL"].map(lambda t: agent_map.get(str(t), None)).fillna(
                last["Agent"]
            )

    priors = (
        _prior_from_history(ventes, store_history, day_histo)
        if not ventes.empty
        else pd.DataFrame(columns=["TEL", "Agent", "Prior"])
    )
    prior_total = (
        priors["Prior"].value_counts().to_dict() if not priors.empty else {}
    )

    onoff = _load_onoff_calls(onoff_sources)
    dur_map: dict[str, int] = {}
    tot_map: dict[str, int] = {}
    if not onoff.empty and "TEL" in onoff.columns:
        onoff = onoff.copy()
        onoff["TEL"] = _clean_tel_db(onoff["TEL"].astype(str))
        last_dur = last_onoff_call_durations(onoff)
        if not last_dur.empty:
            dur_map = dict(
                zip(
                    last_dur["TEL"].astype(str),
                    pd.to_numeric(last_dur["Duree_Dernier_Appel_Sec"], errors="coerce")
                    .fillna(0)
                    .astype(int),
                )
            )
        if "Duration_Seconds" in onoff.columns:
            tot_map = (
                onoff.groupby("TEL")["Duration_Seconds"]
                .sum()
                .astype(int)
                .to_dict()
            )

    agents: list[dict[str, Any]] = []
    if last.empty:
        agent_names = sorted(set(ventes["Agent"].tolist())) if not ventes.empty else []
        frame_by_agent = {a: pd.DataFrame() for a in agent_names}
    else:
        frame_by_agent = {a: g for a, g in last.groupby("Agent")}

    all_agents = sorted(
        {a for a in frame_by_agent if a != "Non renseigné"}
        | ({a for a in ventes["Agent"].tolist() if a != "Non renseigné"} if not ventes.empty else set())
    )

    for ag in all_agents:
        g = frame_by_agent.get(ag, pd.DataFrame())
        tel_n = int(g["TEL"].nunique()) if not g.empty else 0
        vtels = set(priors.loc[priors["Agent"] == ag, "TEL"].astype(str)) if not priors.empty else set()
        n_ventes = len(vtels)
        if tel_n == 0 and n_ventes:
            tel_n = n_ventes
        pc = g[g["Status_Group"] == "Pas de collaboration"] if not g.empty else pd.DataFrame()
        rf = g[g["Status_Group"] == "Refus"] if not g.empty else pd.DataFrame()
        pc_secs = [dur_map[t] for t in pc["TEL"].astype(str) if t in dur_map] if not pc.empty else []
        rf_secs = [dur_map[t] for t in rf["TEL"].astype(str) if t in dur_map] if not rf.empty else []
        all_secs = (
            [tot_map[t] for t in g["TEL"].astype(str) if t in tot_map] if not g.empty else []
        )
        agent_priors = (
            priors.loc[priors["Agent"] == ag, "Prior"].value_counts().to_dict()
            if not priors.empty
            else {}
        )
        outcomes_raw = (
            g["Status_Group"].value_counts().to_dict() if not g.empty else {}
        )
        # Ensure vente count matches data-client ventes when override applied
        if n_ventes:
            outcomes_raw["Vente"] = n_ventes
        outcomes = {str(k): int(v) for k, v in outcomes_raw.items()}
        other_outcomes = sum(
            v for k, v in outcomes.items() if k not in OUTCOME_KEYS
        )
        agents.append(
            {
                "Agent": ag,
                "TEL": tel_n,
                "Ventes": n_ventes,
                "Taux": round(100 * n_ventes / max(tel_n, 1), 2),
                "priors": {str(k): int(v) for k, v in agent_priors.items()},
                "outcomes": outcomes,
                "outcomes_autre": int(other_outcomes),
                "Pas_de_collab": int(outcomes.get("Pas de collaboration", 0)),
                "Refus": int(outcomes.get("Refus", 0)),
                "Repondeur": int(outcomes.get("Répondeur", 0)),
                "Raccroche": int(outcomes.get("Raccroche au nez", 0)),
                "Rappel_Pers": int(outcomes.get("Rappel Personnel", 0)),
                "Relance": int(outcomes.get("RELANCE", 0)),
                "Onoff_PasCollab_match": len(pc_secs),
                "Onoff_PasCollab_moy_sec": round(sum(pc_secs) / len(pc_secs), 1) if pc_secs else None,
                "Onoff_PasCollab_tot_sec": int(sum(pc_secs)) if pc_secs else 0,
                "Onoff_Refus_match": len(rf_secs),
                "Onoff_Refus_moy_sec": round(sum(rf_secs) / len(rf_secs), 1) if rf_secs else None,
                "Onoff_Refus_tot_sec": int(sum(rf_secs)) if rf_secs else 0,
                "Onoff_agent_tot_sec": int(sum(all_secs)),
                "Onoff_agent_tot_fmt": _format_duration(int(sum(all_secs))),
                "Onoff_agent_match": len(all_secs),
            }
        )

    agents = sorted(agents, key=lambda x: (-x["Ventes"], -x["TEL"], x["Agent"]))
    return DailyAgentReport(
        day_label=day,
        ventes_total=int(len(priors)) if not priors.empty else int(len(vente_tels)),
        prior_total={str(k): int(v) for k, v in prior_total.items()},
        agents=agents,
        vente_details=priors,
    )


def _setup_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    return plt


def build_conversion_origins_pdf(report: DailyAgentReport) -> bytes:
    """PDF 1 — what each agent converted (prior status → vente)."""
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages

    plt = _setup_matplotlib()
    agents = [a for a in report.agents if a["Ventes"] > 0]
    buf = BytesIO()
    day = report.day_label

    with PdfPages(buf) as pdf:
        # Page 1 overview
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.suptitle(
            f"Ce que chaque agent a converti — {day}",
            fontsize=15,
            fontweight="bold",
            y=0.97,
        )
        fig.text(
            0.5,
            0.93,
            "Dernier statut non-vente du TEL avant la conversion",
            ha="center",
            fontsize=9,
            color="#64748B",
        )

        prior_items = sorted(report.prior_total.items(), key=lambda x: -x[1])
        if not prior_items:
            fig.text(0.5, 0.5, "Aucune vente ce jour", ha="center", fontsize=14)
            pdf.savefig(fig, dpi=150)
            plt.close(fig)
        else:
            axk = fig.add_axes([0.06, 0.82, 0.88, 0.08])
            axk.axis("off")
            repond = report.prior_total.get("Répondeur", 0)
            pct = round(100 * repond / max(report.ventes_total, 1))
            kpis = [
                (str(report.ventes_total), "Ventes"),
                (str(repond), "Issues de Répondeur"),
                (f"{pct} %", "Depuis Répondeur"),
                (str(len(agents)), "Agents avec ≥1 vente"),
            ]
            for i, (v, lab) in enumerate(kpis):
                x = 0.02 + i * 0.25
                axk.text(
                    x + 0.1,
                    0.65,
                    v,
                    ha="center",
                    fontsize=18,
                    fontweight="bold",
                    transform=axk.transAxes,
                )
                axk.text(
                    x + 0.1,
                    0.15,
                    lab,
                    ha="center",
                    fontsize=8,
                    color="#64748B",
                    transform=axk.transAxes,
                )

            names = [n for n, _ in prior_items]
            vals = [v for _, v in prior_items]
            cols = [PRIOR_COLORS.get(n, "#64748B") for n in names]

            ax1 = fig.add_axes([0.05, 0.28, 0.38, 0.48])
            ax1.pie(
                vals,
                colors=cols,
                startangle=90,
                autopct=lambda p: f"{p:.0f}%" if p >= 5 else "",
                pctdistance=0.65,
                wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
                textprops=dict(fontsize=8, color="white", fontweight="bold"),
            )
            ax1.set_title("Origine globale des ventes", fontsize=11)
            ax1.text(
                0,
                0,
                f"{report.ventes_total}\nventes",
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
            )
            ax1.legend(names, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=7, frameon=False)

            ax2 = fig.add_axes([0.52, 0.38, 0.42, 0.38])
            short = [n if len(n) < 16 else n[:14] + "…" for n in names]
            bars = ax2.bar(short, vals, color=cols, width=0.65)
            for b, v in zip(bars, vals):
                ax2.text(
                    b.get_x() + b.get_width() / 2,
                    b.get_height() + 0.2,
                    str(v),
                    ha="center",
                    fontsize=9,
                    fontweight="bold",
                )
            ax2.set_ylabel("Nombre de ventes")
            ax2.set_title("Ventes par statut précédent", fontsize=11)
            ax2.tick_params(axis="x", labelsize=8)
            ax2.set_ylim(0, max(vals) * 1.25)

            fig.text(
                0.06,
                0.08,
                "Sans contact précédent = aucun statut non-vente trouvé avant la vente "
                "(historique store ou histo du jour).",
                fontsize=8,
                color="#475569",
            )
            fig.text(
                0.06,
                0.04,
                f"Source : data client + histo + historique persisté · généré {report.generated_at}",
                fontsize=7,
                color="#94A3B8",
            )
            pdf.savefig(fig, dpi=150)
            plt.close(fig)

        # Page 2 stacked + ventes
        if agents:
            fig = plt.figure(figsize=(11.69, 8.27))
            fig.suptitle(f"Ventes et origines par agent — {day}", fontsize=14, fontweight="bold", y=0.97)
            names = [a["Agent"] for a in agents]
            ventes = [a["Ventes"] for a in agents]

            ax1 = fig.add_axes([0.08, 0.55, 0.86, 0.35])
            bars = ax1.bar(names, ventes, color="#22C55E", width=0.7)
            for b, v in zip(bars, ventes):
                ax1.text(
                    b.get_x() + b.get_width() / 2,
                    b.get_height() + 0.05,
                    str(v),
                    ha="center",
                    fontsize=9,
                    fontweight="bold",
                )
            ax1.set_ylabel("Ventes")
            ax1.set_title("Nombre de ventes par agent", fontsize=11)
            ax1.tick_params(axis="x", labelsize=8, rotation=20)
            ax1.set_ylim(0, max(ventes) + 1)

            ax2 = fig.add_axes([0.08, 0.08, 0.86, 0.38])
            x = np.arange(len(names))
            bottom = np.zeros(len(names))
            keys_used = [k for k in PRIOR_KEYS if any(a["priors"].get(k, 0) for a in agents)]
            extra = sorted(
                {
                    k
                    for a in agents
                    for k in a["priors"]
                    if k not in PRIOR_KEYS and a["priors"][k]
                }
            )
            for key in keys_used + extra:
                vals_k = np.array([a["priors"].get(key, 0) for a in agents], dtype=float)
                ax2.bar(
                    x,
                    vals_k,
                    bottom=bottom,
                    color=PRIOR_COLORS.get(key, "#64748B"),
                    label=key,
                    width=0.7,
                )
                bottom += vals_k
            ax2.set_xticks(x)
            ax2.set_xticklabels(names, rotation=20, fontsize=8)
            ax2.set_ylabel("Ventes")
            ax2.set_title("Origine des ventes par agent (empilé)", fontsize=11)
            ax2.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
            pdf.savefig(fig, dpi=150)
            plt.close(fig)

            # Page 3 table
            fig = plt.figure(figsize=(11.69, 8.27))
            fig.suptitle(f"Tableau origines des ventes — {day}", fontsize=14, fontweight="bold", y=0.96)
            ax = fig.add_axes([0.06, 0.12, 0.88, 0.78])
            ax.axis("off")
            headers = ["Agent", "TEL", "Ventes", "Taux %", "Répondeur", "Sans contact", "Rappel", "RELANCE", "Autre"]
            rows = []
            for a in report.agents:
                other = sum(
                    v
                    for k, v in a["priors"].items()
                    if k
                    not in {
                        "Répondeur",
                        "Sans contact précédent",
                        "Rappel Personnel",
                        "RELANCE",
                    }
                )
                rows.append(
                    [
                        a["Agent"],
                        str(a["TEL"]),
                        str(a["Ventes"]),
                        f"{a['Taux']:.2f}",
                        str(a["priors"].get("Répondeur", 0)),
                        str(a["priors"].get("Sans contact précédent", 0)),
                        str(a["priors"].get("Rappel Personnel", 0)),
                        str(a["priors"].get("RELANCE", 0)),
                        str(other),
                    ]
                )
            table = ax.table(
                cellText=rows,
                colLabels=headers,
                loc="center",
                cellLoc="center",
                colColours=["#E2E8F0"] * len(headers),
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.45)
            for (r, c), cell in table.get_celld().items():
                cell.set_edgecolor("#CBD5E1")
                if r == 0:
                    cell.set_text_props(fontweight="bold")
                elif r > 0 and report.agents[r - 1]["Ventes"] >= 3:
                    cell.set_facecolor("#ECFDF5")
                elif r > 0 and report.agents[r - 1]["Ventes"] == 0:
                    if c == 0:
                        cell.set_text_props(color="#DC2626", fontweight="bold")
            fig.text(
                0.06,
                0.04,
                "Sans contact précédent = aucun historique non-vente avant la vente.",
                fontsize=7,
                color="#94A3B8",
            )
            pdf.savefig(fig, dpi=150)
            plt.close(fig)

    return buf.getvalue()


def build_agent_enriched_pdf(report: DailyAgentReport) -> bytes:
    """PDF 2 — mix de tous les statuts + Pas de collab / Refus + durées Onoff."""
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages

    plt = _setup_matplotlib()
    agents = report.agents
    buf = BytesIO()
    day = report.day_label

    def _outcome(a: dict[str, Any], key: str) -> int:
        return int((a.get("outcomes") or {}).get(key, 0))

    outcome_keys_used = [
        k
        for k in OUTCOME_KEYS
        if any(_outcome(a, k) for a in agents)
    ]
    extra_keys = sorted(
        {
            k
            for a in agents
            for k in (a.get("outcomes") or {})
            if k not in OUTCOME_KEYS and (a.get("outcomes") or {}).get(k, 0)
        }
    )
    all_outcome_keys = outcome_keys_used + extra_keys

    with PdfPages(buf) as pdf:
        # —— Page 1: overview + stacked status mix ——
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.suptitle(
            f"Analyse agents — {day}\nMix des statuts, Pas de collab / Refus & Onoff",
            fontsize=14,
            fontweight="bold",
            y=0.97,
        )
        tot_pc = sum(a["Pas_de_collab"] for a in agents)
        tot_rf = sum(a["Refus"] for a in agents)
        tot_rep = sum(_outcome(a, "Répondeur") for a in agents)
        axk = fig.add_axes([0.06, 0.86, 0.88, 0.07])
        axk.axis("off")
        for i, (v, lab) in enumerate(
            [
                (str(report.ventes_total), "Ventes"),
                (str(tot_rep), "Répondeur"),
                (str(tot_pc), "Pas de collab"),
                (str(tot_rf), "Refus"),
            ]
        ):
            x = 0.02 + i * 0.25
            axk.text(x + 0.1, 0.65, v, ha="center", fontsize=16, fontweight="bold", transform=axk.transAxes)
            axk.text(x + 0.1, 0.1, lab, ha="center", fontsize=8, color="#64748B", transform=axk.transAxes)

        if agents:
            names = [a["Agent"] for a in agents]
            x = np.arange(len(names))

            ax1 = fig.add_axes([0.08, 0.38, 0.86, 0.42])
            bottom = np.zeros(len(names))
            for key in all_outcome_keys:
                vals_k = np.array([_outcome(a, key) for a in agents], dtype=float)
                if vals_k.sum() == 0:
                    continue
                ax1.bar(
                    x,
                    vals_k,
                    bottom=bottom,
                    color=PRIOR_COLORS.get(key, "#94A3B8"),
                    label=key,
                    width=0.72,
                )
                bottom += vals_k
            ax1.set_xticks(x)
            ax1.set_xticklabels(names, rotation=22, fontsize=8)
            ax1.set_ylabel("Nb TEL (dernier statut du jour)")
            ax1.set_title("Tous les statuts posés par agent (empilé)", fontsize=11)
            ax1.legend(loc="upper right", fontsize=6.5, frameon=False, ncol=3)

            by_pc = sorted(agents, key=lambda a: -a["Pas_de_collab"])
            by_rf = sorted(agents, key=lambda a: -a["Refus"])
            by_v = sorted(agents, key=lambda a: -a["Ventes"])
            lines = ["Lecture clé"]
            if by_pc:
                top = by_pc[0]
                lines.append(
                    f"• {top['Agent']} : {top['Pas_de_collab']} Pas de collab "
                    f"(Ø Onoff {_fmt_moy(top['Onoff_PasCollab_moy_sec'])})."
                )
            if by_rf and by_rf[0]["Refus"]:
                top = by_rf[0]
                lines.append(
                    f"• {top['Agent']} : {top['Refus']} Refus "
                    f"(Ø Onoff {_fmt_moy(top['Onoff_Refus_moy_sec'])})."
                )
            if by_v and by_v[0]["Ventes"]:
                top = by_v[0]
                lines.append(
                    f"• Top ventes : {top['Agent']} ({top['Ventes']} ventes, taux {top['Taux']}%)."
                )
            zero = [a["Agent"] for a in agents if a["Ventes"] == 0]
            if zero:
                lines.append(f"• 0 vente : {', '.join(zero)}.")
            fig.text(0.06, 0.05, "\n".join(lines), fontsize=8.5, color="#0F172A", va="bottom")
        else:
            fig.text(0.5, 0.5, "Aucune donnée agent pour ce jour", ha="center", fontsize=14)

        pdf.savefig(fig, dpi=150)
        plt.close(fig)

        # —— Page 2: full status counts table + Onoff ——
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.suptitle(f"Mix des statuts + Onoff par agent — {day}", fontsize=14, fontweight="bold", y=0.96)
        ax = fig.add_axes([0.02, 0.10, 0.96, 0.82])
        ax.axis("off")

        short_headers = {
            "Répondeur": "Répond.",
            "Pas de collaboration": "Pas collab",
            "Raccroche au nez": "Raccroche",
            "Rappel Personnel": "Rappel P.",
            "RELANCE": "RELANCE",
            "Refus": "Refus",
            "Vente": "Vente",
            "Faux Numéro": "Faux N°",
            "Injoignable": "Injoign.",
            "Hors cible": "Hors cib.",
        }
        status_cols = [k for k in OUTCOME_KEYS if any(_outcome(a, k) for a in agents)]
        # Always keep core quality cols even if 0 for readability of Onoff section
        for must in ("Pas de collaboration", "Refus", "Vente", "Répondeur"):
            if must not in status_cols:
                status_cols.insert(0 if must == "Répondeur" else len(status_cols), must)
        # de-dupe preserve order
        seen: set[str] = set()
        status_cols = [k for k in status_cols if not (k in seen or seen.add(k))]

        headers = (
            ["Agent", "TEL", "Taux%"]
            + [short_headers.get(k, k[:8]) for k in status_cols]
            + ["Autre", "Ø PC", "Ø Refus", "Σ Onoff"]
        )
        rows = []
        for a in agents:
            row = [
                a["Agent"],
                str(a["TEL"]),
                f"{a['Taux']:.2f}",
            ]
            for k in status_cols:
                row.append(str(_outcome(a, k)))
            row.extend(
                [
                    str(a.get("outcomes_autre", 0)),
                    _fmt_moy(a["Onoff_PasCollab_moy_sec"]) if a["Pas_de_collab"] else "—",
                    _fmt_moy(a["Onoff_Refus_moy_sec"]) if a["Refus"] else "—",
                    a["Onoff_agent_tot_fmt"],
                ]
            )
            rows.append(row)

        if rows:
            table = ax.table(
                cellText=rows,
                colLabels=headers,
                loc="center",
                cellLoc="center",
                colColours=["#E2E8F0"] * len(headers),
            )
            table.auto_set_font_size(False)
            table.set_fontsize(6.8)
            table.scale(1, 1.5)
            pc_idx = 3 + status_cols.index("Pas de collaboration") if "Pas de collaboration" in status_cols else None
            rf_idx = 3 + status_cols.index("Refus") if "Refus" in status_cols else None
            for (r, c), cell in table.get_celld().items():
                cell.set_edgecolor("#CBD5E1")
                if r == 0:
                    cell.set_text_props(fontweight="bold", fontsize=6.5)
                else:
                    a = agents[r - 1]
                    if a["Ventes"] >= 3:
                        cell.set_facecolor("#ECFDF5")
                    if a["Ventes"] == 0 and c == 0:
                        cell.set_text_props(color="#DC2626", fontweight="bold")
                    if pc_idx is not None and c == pc_idx and a["Pas_de_collab"] >= 40:
                        cell.set_facecolor("#FEE2E2")
                    if rf_idx is not None and c == rf_idx and a["Refus"] >= 4:
                        cell.set_facecolor("#FEE2E2")

        fig.text(
            0.02,
            0.04,
            "Colonnes statut = dernier statut du jour par TEL. Autre = statuts hors liste principale. "
            "Ø PC / Ø Refus = durée moy. Onoff du dernier appel sur ces TEL. "
            f"Généré {report.generated_at}",
            fontsize=6.5,
            color="#64748B",
        )
        pdf.savefig(fig, dpi=150)
        plt.close(fig)

        # —— Page 3: PC/Refus focus + Onoff durations ——
        if agents:
            fig = plt.figure(figsize=(11.69, 8.27))
            fig.suptitle(
                f"Pas de collab / Refus & durées Onoff — {day}",
                fontsize=14,
                fontweight="bold",
                y=0.96,
            )
            names = [a["Agent"] for a in agents]
            x = np.arange(len(names))
            w = 0.38

            ax1 = fig.add_axes([0.08, 0.55, 0.55, 0.35])
            ax1.bar(x - w / 2, [a["Pas_de_collab"] for a in agents], width=w, color="#F59E0B", label="Pas de collab")
            ax1.bar(x + w / 2, [a["Refus"] for a in agents], width=w, color="#EF4444", label="Refus")
            ax1.set_xticks(x)
            ax1.set_xticklabels(names, rotation=25, fontsize=8)
            ax1.set_ylabel("Nb TEL")
            ax1.set_title("Pas de collab & Refus", fontsize=11)
            ax1.legend(frameon=False, fontsize=8)

            ax2 = fig.add_axes([0.70, 0.55, 0.26, 0.35])
            moy = [a["Onoff_PasCollab_moy_sec"] or 0 for a in agents]
            colors = [
                "#DC2626" if (a["Onoff_PasCollab_moy_sec"] or 999) < 30 else "#3B82F6"
                for a in agents
            ]
            ax2.barh(names[::-1], moy[::-1], color=colors[::-1])
            ax2.set_xlabel("sec")
            ax2.set_title("Ø Onoff Pas de collab", fontsize=10)
            ax2.axvline(30, color="#94A3B8", ls="--", lw=1)
            ax2.tick_params(axis="y", labelsize=7)

            ax3 = fig.add_axes([0.08, 0.10, 0.84, 0.35])
            pc_tot = [a["Onoff_PasCollab_tot_sec"] / 60 for a in agents]
            rf_tot = [a["Onoff_Refus_tot_sec"] / 60 for a in agents]
            ax3.bar(x - w / 2, pc_tot, width=w, color="#F59E0B", label="Pas de collab (min)")
            ax3.bar(x + w / 2, rf_tot, width=w, color="#EF4444", label="Refus (min)")
            ax3.set_xticks(x)
            ax3.set_xticklabels(names, rotation=25, fontsize=8)
            ax3.set_ylabel("Minutes Onoff cumulées")
            ax3.set_title("Temps Onoff sur TEL Pas de collab / Refus", fontsize=11)
            ax3.legend(frameon=False, fontsize=8)
            for i, a in enumerate(agents):
                if a["Pas_de_collab"]:
                    ax3.text(i - w / 2, pc_tot[i] + 0.3, str(a["Pas_de_collab"]), ha="center", fontsize=7)
                if a["Refus"]:
                    ax3.text(i + w / 2, rf_tot[i] + 0.3, str(a["Refus"]), ha="center", fontsize=7)

            pdf.savefig(fig, dpi=150)
            plt.close(fig)

    return buf.getvalue()


def generate_daily_agent_pdfs(
    *,
    histo: pd.DataFrame,
    data_client: pd.DataFrame | None = None,
    onoff_sources: list[Any] | BinaryIO | None = None,
    store_history: pd.DataFrame | None = None,
    day_label: str | None = None,
) -> dict[str, Any]:
    """Compute report and return both PDF payloads + summary metrics."""
    if onoff_sources is not None and not isinstance(onoff_sources, list):
        onoff_sources = [onoff_sources]
    report = compute_daily_agent_report(
        histo=histo,
        data_client=data_client,
        onoff_sources=onoff_sources,
        store_history=store_history,
        day_label=day_label,
    )
    pdf1 = build_conversion_origins_pdf(report)
    pdf2 = build_agent_enriched_pdf(report)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    day_slug = (report.day_label or "jour").replace("/", "")
    return {
        "report": report,
        "pdf_conversions": pdf1,
        "pdf_enriched": pdf2,
        "filename_conversions": f"conversions_agents_{day_slug}_{stamp}.pdf",
        "filename_enriched": f"analyse_agents_pas_collab_refus_{day_slug}_{stamp}.pdf",
        "agents": report.agents,
        "ventes_total": report.ventes_total,
        "prior_total": report.prior_total,
    }
