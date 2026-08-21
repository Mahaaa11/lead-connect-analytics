"""Suivi quotidien : évolution d'une cohorte baseline + ventes vs statut d'origine."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO

import pandas as pd

from engine.dashboard import SALE_STATUS_CODE
from engine.processor import (
    STATUS_ALIASES,
    TEL_ALIASES,
    _clean_tel_db,
    _clean_tel_hist_initial,
    _find_column,
    _normalize_columns,
    _read_excel,
)
from engine.status_labels import apply_resolved_status_labels
from engine.vente_tracking import NOT_FOUND_LABEL, extract_ventes_from_client_exports

DEFAULT_COHORT_STATUS_CODES = [99]
DEFAULT_COHORT_LABELS = ["Injoignable"]
NOT_IN_DAILY_HISTO_LABEL = "Non appelé ce jour (absent export histo)"


def baseline_from_client_upload(df: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible alias — implementation lives in vente_tracking."""
    from engine.vente_tracking import baseline_from_client_upload as _fn

    return _fn(df)


def parse_day_label_from_filename(name: str) -> str:
    """Extract a human day label from export filenames."""
    lower = name.lower()
    for pattern, label in (
        (r"(\d{2})[-_]?(\d{2})[-_]?(\d{4})", None),
        (r"(\d{8})", None),
    ):
        match = re.search(pattern, lower)
        if not match:
            continue
        if len(match.groups()) == 3:
            d, m, y = match.groups()
            return f"{d}/{m}/{y}"
        raw = match.group(1)
        if len(raw) == 8:
            return f"{raw[6:8]}/{raw[4:6]}/{raw[0:4]}"
    stem = name.rsplit(".", 1)[0]
    return stem[-10:] if len(stem) >= 10 else stem


def load_histo_export(source: str | BinaryIO | BytesIO) -> pd.DataFrame:
    """Load and normalize a daily history export."""
    if hasattr(source, "seek"):
        source.seek(0)
    df = _read_excel(source, is_history=True)
    df = _normalize_columns(df)
    tel_col = _find_column(df, TEL_ALIASES)
    if tel_col not in (df.columns if tel_col else []) and "TEL" in df.columns:
        tel_col = "TEL"
    if not tel_col or tel_col not in df.columns:
        name = getattr(source, "name", source)
        raise ValueError(
            f"Colonne TEL introuvable dans « {name} ». "
            "Utilisez l'export historique du jour — pas le fichier b2b/Onoff."
        )
    df = df.rename(columns={tel_col: "TEL_RAW"})
    df["TEL_DB"] = _clean_tel_db(df["TEL_RAW"].astype(str))
    df["TEL"] = _clean_tel_hist_initial(df["TEL_RAW"].astype(str))
    if "DATE" in df.columns:
        dates = pd.to_datetime(df["DATE"].astype(str), format="%Y%m%d", errors="coerce")
        if dates.isna().all():
            dates = pd.to_datetime(df["DATE"], errors="coerce")
        hours = df["HEURE"].astype(str).str.zfill(4) if "HEURE" in df.columns else "0000"
        df["DATETIME"] = pd.to_datetime(
            dates.dt.strftime("%Y-%m-%d")
            + " "
            + hours.str[:2]
            + ":"
            + hours.str[2:],
            errors="coerce",
        )
    else:
        df["DATETIME"] = pd.NaT
    df["Status_Label"] = apply_resolved_status_labels(df)
    return df


def load_histo_exports(sources: list[tuple[Any, str]]) -> pd.DataFrame:
    """Merge one or more daily history exports."""
    parts: list[pd.DataFrame] = []
    for source, _day in sources:
        parts.append(load_histo_export(source))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def extract_ventes_from_histo_exports(
    sources: list[tuple[Any, str]],
) -> pd.DataFrame:
    """Extract unique daily sales (STATUS=1) from history exports."""
    histo = load_histo_exports(sources)
    if histo.empty:
        return pd.DataFrame(
            columns=["TEL", "Jour_Vente", "DATE", "HEURE", "LIB_STATUS", "Source"]
        )

    codes = pd.to_numeric(histo["STATUS"], errors="coerce")
    ventes = histo[codes == int(SALE_STATUS_CODE)].copy()
    if ventes.empty and "LIB_STATUS" in histo.columns:
        ventes = histo[
            histo["LIB_STATUS"].astype(str).str.upper().str.strip() == "VENTE"
        ].copy()

    if ventes.empty:
        return pd.DataFrame(
            columns=["TEL", "Jour_Vente", "DATE", "HEURE", "LIB_STATUS", "Source"]
        )

    ventes = ventes.sort_values("DATETIME").groupby("TEL_DB", as_index=False).tail(1)
    ventes["TEL"] = ventes["TEL_DB"]
    ventes["Source"] = "historique"
    if sources:
        ventes["Jour_Vente"] = sources[0][1]
    else:
        ventes["Jour_Vente"] = datetime.now().strftime("%d/%m/%Y")
    keep = ["TEL", "Jour_Vente", "Source"]
    for col in ("DATE", "HEURE", "LIB_STATUS", "DATETIME"):
        if col in ventes.columns:
            keep.append(col)
    return ventes[keep].reset_index(drop=True)


def merge_daily_vente_sources(
    histo_sources: list[tuple[Any, str]] | None,
    client_sources: list[tuple[Any, str]] | None,
) -> pd.DataFrame:
    """Combine ventes from history and client exports (unique TEL per day)."""
    parts: list[pd.DataFrame] = []
    if histo_sources:
        parts.append(extract_ventes_from_histo_exports(histo_sources))
    if client_sources:
        client = extract_ventes_from_client_exports(client_sources)
        if not client.empty:
            client = client.copy()
            client["Source"] = "data_client"
            parts.append(client)
    if not parts:
        return pd.DataFrame(
            columns=["TEL", "Jour_Vente", "DATE", "HEURE", "LIB_STATUS", "Source"]
        )
    merged = pd.concat(parts, ignore_index=True)
    return merged.drop_duplicates(subset=["TEL", "Jour_Vente"], keep="first").reset_index(
        drop=True
    )


def filter_baseline_cohort(
    baseline: pd.DataFrame,
    *,
    status_codes: list[int] | None = None,
    status_labels: list[str] | None = None,
) -> pd.DataFrame:
    """Keep baseline rows matching status codes and/or labels."""
    if baseline.empty:
        return baseline
    from engine.dashboard import EXTENDED_STATUS_MAPPING
    from engine.processor import DEFAULT_STATUS_MAPPING

    codes = status_codes if status_codes is not None else DEFAULT_COHORT_STATUS_CODES
    labels = list(status_labels) if status_labels is not None else list(DEFAULT_COHORT_LABELS)
    # Snapshot baseline often stores Statut text only — map codes → labels.
    if codes:
        mapping = {**DEFAULT_STATUS_MAPPING, **EXTENDED_STATUS_MAPPING}
        for code in codes:
            label = mapping.get(int(code))
            if label and label not in labels:
                labels.append(label)
    out = baseline.copy()
    mask = pd.Series(False, index=out.index)
    if "Status_Code" in out.columns and codes:
        mask |= pd.to_numeric(out["Status_Code"], errors="coerce").isin(codes)
    if labels and "Statut" in out.columns:
        statut = out["Statut"].astype(str).str.strip()
        for label in labels:
            mask |= statut.str.casefold() == label.casefold()
    if not codes and not labels:
        return out
    return out[mask].copy()


def _agent_from_histo_row(row: pd.Series) -> str:
    from engine.agent_analytics import _normalize_agent_label

    for col in ("TV", "STATUS_USER", "Status_User"):
        if col in row.index:
            label = _normalize_agent_label(row.get(col))
            if label != "Non renseigné":
                # "SOLANGE SOLANGE" → "SOLANGE"
                parts = label.split()
                if len(parts) >= 2 and parts[0].casefold() == parts[1].casefold():
                    return parts[0]
                return label
    return "Non renseigné"


def _onoff_duration_by_tel(
    onoff_sources: list[Any] | None,
) -> dict[str, tuple[int, str]]:
    """Map TEL → (duration_seconds, formatted) from Onoff/b2b last call."""
    from engine.processor import (
        _format_duration,
        last_onoff_call_durations,
        merge_onoff_calls,
    )

    sources: list[Any] = []
    if onoff_sources:
        sources.extend(onoff_sources)
    if not sources:
        try:
            from engine import database as _db

            stored = _db.load_onoff_calls()
            if stored is not None and not stored.empty:
                last = last_onoff_call_durations(stored)
                out: dict[str, tuple[int, str]] = {}
                for _, row in last.iterrows():
                    tel = str(row["TEL"])
                    sec = int(row["Duree_Dernier_Appel_Sec"])
                    out[tel] = (sec, str(row["Duree_Dernier_Appel"]))
                return out
        except Exception:
            return {}
        return {}

    calls, _totals, _stats = merge_onoff_calls(sources)
    if calls.empty:
        return {}
    last = last_onoff_call_durations(calls)
    out = {}
    for _, row in last.iterrows():
        tel = str(row["TEL"])
        sec = int(row["Duree_Dernier_Appel_Sec"])
        out[tel] = (sec, str(row.get("Duree_Dernier_Appel") or _format_duration(sec)))
    return out


def compute_cohort_evolution(
    baseline: pd.DataFrame,
    histo: pd.DataFrame,
    *,
    cohort_status_codes: list[int] | None = None,
    cohort_status_labels: list[str] | None = None,
    data_client: pd.DataFrame | None = None,
    onoff_sources: list[Any] | None = None,
    cohort_name: str = "Cohorte",
) -> dict[str, Any]:
    """
    Track a baseline cohort (e.g. Injoignable 99) and report latest status in history.
    Duration comes from Onoff/b2b (dernier appel), not histo DUREE.
    """
    cohort = filter_baseline_cohort(
        baseline,
        status_codes=cohort_status_codes,
        status_labels=cohort_status_labels,
    )
    empty_detail = pd.DataFrame(
        columns=[
            "TEL",
            "Statut_baseline",
            "Couleur_baseline",
            "Status_Code_baseline",
            "contacts_histo",
            "dernier_contact",
            "devenu_histo",
            "devenu_data",
            "Agent",
            "Duree",
            "Duree_sec",
            "Duree_source",
            "appele_ce_jour",
        ]
    )
    if cohort.empty:
        return {
            "cohort_name": cohort_name,
            "cohort_size": 0,
            "detail": empty_detail,
            "still_same_detail": empty_detail,
            "summary": pd.DataFrame(columns=["Statut_devenu", "Nombre", "Taux_%"]),
            "still_same_count": 0,
            "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        }

    if histo.empty:
        return {
            "cohort_name": cohort_name,
            "cohort_size": len(cohort),
            "detail": empty_detail,
            "still_same_detail": empty_detail,
            "summary": pd.DataFrame(columns=["Statut_devenu", "Nombre", "Taux_%"]),
            "still_same_count": 0,
            "analyzed_at": datetime.now().isoformat(timespec="seconds"),
        }

    histo = histo.sort_values("DATETIME")
    onoff_durations = _onoff_duration_by_tel(onoff_sources)
    data_map: dict[str, str] = {}
    if data_client is not None and not data_client.empty:
        dc = _normalize_columns(data_client.copy())
        tel_col = _find_column(dc, TEL_ALIASES)
        if not tel_col or tel_col not in dc.columns:
            raise ValueError(
                "Colonne TEL introuvable dans l'export data client. "
                "Ne pas uploader le fichier b2b/Onoff dans cet emplacement."
            )
        dc = dc.rename(columns={tel_col: "TEL"})
        dc["TEL"] = _clean_tel_db(dc["TEL"].astype(str))
        dc["Status_Label"] = apply_resolved_status_labels(dc)
        data_map = dc.set_index("TEL")["Status_Label"].to_dict()

    rows: list[dict[str, Any]] = []
    cohort_tels = cohort.drop_duplicates("TEL", keep="first")
    for _, base_row in cohort_tels.iterrows():
        tel = str(base_row["TEL"])
        sub = histo[(histo["TEL_DB"] == tel) | (histo["TEL"].astype(str) == tel)]
        onoff_hit = onoff_durations.get(tel)
        if onoff_hit:
            duree_sec, duree_disp = onoff_hit
            duree_source = "onoff"
        else:
            duree_sec, duree_disp, duree_source = None, "—", None

        if sub.empty:
            devenu_data = data_map.get(tel, "Absent data")
            # Export histo « par-jour » = appels du jour seulement ; pas d'activité → absent du fichier.
            devenu_histo = NOT_IN_DAILY_HISTO_LABEL
            if devenu_data not in ("Absent data", ""):
                devenu_histo = f"{NOT_IN_DAILY_HISTO_LABEL} · data: {devenu_data}"
            rows.append(
                {
                    "TEL": tel,
                    "Statut_baseline": base_row.get("Statut"),
                    "Couleur_baseline": base_row.get("Couleur"),
                    "Status_Code_baseline": base_row.get("Status_Code"),
                    "contacts_histo": 0,
                    "dernier_contact": None,
                    "devenu_histo": devenu_histo,
                    "devenu_data": devenu_data,
                    "Agent": None,
                    "Duree": duree_disp,
                    "Duree_sec": duree_sec,
                    "Duree_source": duree_source,
                    "appele_ce_jour": False,
                }
            )
            continue
        latest = sub.iloc[-1]
        devenu = latest["Status_Label"]
        rows.append(
            {
                "TEL": tel,
                "Statut_baseline": base_row.get("Statut"),
                "Couleur_baseline": base_row.get("Couleur"),
                "Status_Code_baseline": base_row.get("Status_Code"),
                "contacts_histo": len(sub),
                "dernier_contact": latest.get("DATETIME"),
                "devenu_histo": devenu,
                "devenu_data": data_map.get(tel, "Absent data"),
                "Agent": _agent_from_histo_row(latest),
                "Duree": duree_disp,
                "Duree_sec": duree_sec,
                "Duree_source": duree_source,
                "appele_ce_jour": True,
            }
        )

    detail = pd.DataFrame(rows)
    # Synthèse : regrouper le libellé long « non appelé… »
    summary_key = detail["devenu_histo"].str.replace(
        rf" · data:.*", "", regex=True
    )
    summary = (
        summary_key.value_counts()
        .rename_axis("Statut_devenu")
        .reset_index(name="Nombre")
    )
    total = len(detail)
    summary["Taux_%"] = (100 * summary["Nombre"] / total).round(1) if total else 0.0

    baseline_label = str(cohort.iloc[0].get("Statut", cohort_name))
    still_mask = detail["devenu_histo"].astype(str) == baseline_label
    still_same = int(still_mask.sum())
    still_same_detail = detail.loc[still_mask].copy()
    if not still_same_detail.empty:
        still_cols = [
            c
            for c in [
                "TEL",
                "Agent",
                "Duree",
                "Duree_sec",
                "Duree_source",
                "dernier_contact",
                "Statut_baseline",
                "devenu_histo",
                "contacts_histo",
            ]
            if c in still_same_detail.columns
        ]
        still_same_detail = still_same_detail[still_cols].sort_values(
            ["Agent", "Duree_sec"], ascending=[True, False], na_position="last"
        )

    return {
        "cohort_name": cohort_name,
        "cohort_size": len(detail),
        "detail": detail,
        "still_same_detail": still_same_detail,
        "summary": summary,
        "still_same_count": still_same,
        "baseline_label": baseline_label,
        "onoff_matched": int(detail["Duree_source"].eq("onoff").sum()) if not detail.empty else 0,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
    }


def export_daily_tracking_workbook(
    *,
    vente_result: dict[str, Any] | None,
    cohort_result: dict[str, Any] | None,
) -> bytes:
    """Build a multi-sheet Excel report for daily tracking."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        if cohort_result:
            detail = cohort_result.get("detail", pd.DataFrame())
            summary = cohort_result.get("summary", pd.DataFrame())
            still = cohort_result.get("still_same_detail", pd.DataFrame())
            if not detail.empty:
                detail.to_excel(writer, sheet_name="Cohorte_detail", index=False)
            if not summary.empty:
                summary.to_excel(writer, sheet_name="Cohorte_synthese", index=False)
            if still is not None and not still.empty:
                still.to_excel(writer, sheet_name="Toujours_meme_statut", index=False)
        if vente_result:
            from engine.vente_tracking import tracking_detail_for_export

            detail = tracking_detail_for_export(vente_result)
            if not detail.empty:
                detail.to_excel(writer, sheet_name="Ventes_detail", index=False)
            by_origin = vente_result.get("summary_by_origin", pd.DataFrame())
            if not by_origin.empty:
                by_origin.to_excel(writer, sheet_name="Ventes_origine", index=False)
            by_day = vente_result.get("summary_by_day", pd.DataFrame())
            if not by_day.empty:
                by_day.to_excel(writer, sheet_name="Ventes_jour", index=False)
    return buffer.getvalue()
