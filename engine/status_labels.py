"""Resolve human-readable status labels beyond DEFAULT_STATUS_MAPPING."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from engine.processor import DEFAULT_STATUS_MAPPING, _map_status

_JUNK_LABELS = {"", "nan", "none", "null", "0", "1", "2", "3", "4", "5", "6", "7", "-1"}
_SOUS_CODE_SUFFIX = re.compile(r"\s*\(sous[\s\-‑–—]*code\b.*", re.IGNORECASE)


def is_meaningful_label(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = str(value).strip()
    if not text or text.casefold() in _JUNK_LABELS:
        return False
    if text.lstrip("-").isdigit():
        return False
    return True


def _status_code_text(status: pd.Series) -> pd.Series:
    codes = pd.to_numeric(status, errors="coerce")
    out = pd.Series(index=status.index, dtype=str)
    valid = codes.notna()
    out.loc[valid] = codes.loc[valid].astype(int).astype(str)
    out.loc[~valid] = status.loc[~valid].astype(str).str.strip()
    return out.replace({"": pd.NA, "nan": pd.NA})


_LIB_ALIASES: dict[str, str] = {
    "pas de collaboration": "Pas de collaboration",
    "repondeur": "Répondeur",
    "refus": "Refus",
    "injoignable": "Injoignable",
    "absent": "Absent",
    "indisponible": "Indisponible",
    "hors cible": "Hors cible",
    "ne jamais appeler": "Ne jamais appeler",
    "rappel personnel": "Rappel Personnel",
    "a relancer": "A Relancer",
    "pas decisionaire": "Pas décisionnaire",
    "pas décisionnaire": "Pas décisionnaire",
    "vente": "Vente",
}


def group_status_label(
    label: object,
    *,
    status_mapping: dict[int, str] | None = None,
) -> str:
    """Merge variants like « Répondeur (sous-code …) » into a single display name."""
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return "Autre"
    text = str(label).strip()
    if not text or text.casefold() in _JUNK_LABELS:
        return "Autre"
    text = _SOUS_CODE_SUFFIX.sub("", text).strip()
    if not text and "(" in str(label):
        raw = str(label).strip()
        if re.search(r"sous[\s\-‑–—]*code", raw, re.IGNORECASE):
            text = raw.split("(", 1)[0].strip()
    if text.startswith("Code "):
        code_part = text[5:].strip()
        mapping = status_mapping or DEFAULT_STATUS_MAPPING
        try:
            mapped = mapping.get(int(code_part))
            if mapped:
                return mapped
        except ValueError:
            pass
    mapping = status_mapping or DEFAULT_STATUS_MAPPING
    canonical = {v.casefold(): v for v in mapping.values()}
    folded = text.casefold()
    if folded in canonical:
        return canonical[folded]
    if folded in _LIB_ALIASES:
        return _LIB_ALIASES[folded]
    return text


def group_status_labels(
    series: pd.Series,
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.Series:
    return series.map(lambda value: group_status_label(value, status_mapping=status_mapping))


def group_transition_frame(
    frame: pd.DataFrame,
    columns: tuple[str, ...] = (
        "Status_Label",
        "Status_Category",
        "Prior_Status",
        "Prior_Status_Label",
    ),
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Apply grouped status names on transition/history columns."""
    out = frame.copy()
    for col in columns:
        if col in out.columns:
            out[col] = group_status_labels(out[col], status_mapping=status_mapping)
    return out


def collapse_status_table(
    df: pd.DataFrame,
    label_col: str,
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Merge rows that share the same grouped status name."""
    if df.empty or label_col not in df.columns:
        return df
    out = df.copy()
    out[label_col] = group_status_labels(out[label_col], status_mapping=status_mapping)
    sum_cols = [c for c in ("Ventes", "Transitions", "Transitions_depuis_statut") if c in out.columns]
    if not sum_cols:
        return out.drop_duplicates(subset=[label_col], keep="first")
    collapsed = out.groupby(label_col, as_index=False)[sum_cols].sum()
    if "Ventes" in collapsed.columns and "Transitions" in collapsed.columns:
        collapsed["Taux_conversion_%"] = (
            (100 * collapsed["Ventes"] / collapsed["Transitions"].replace(0, pd.NA))
            .fillna(0)
            .round(2)
        )
        total = int(collapsed["Ventes"].sum())
        collapsed["Part_des_ventes_%"] = (
            (100 * collapsed["Ventes"] / total).round(2) if total else 0.0
        )
    elif "Ventes" in collapsed.columns and "Transitions_depuis_statut" in collapsed.columns:
        collapsed["Taux_conversion_%"] = (
            (
                100
                * collapsed["Ventes"]
                / collapsed["Transitions_depuis_statut"].replace(0, pd.NA)
            )
            .fillna(0)
            .round(2)
        )
    sort_cols = [c for c in ("Ventes", "Taux_conversion_%") if c in collapsed.columns]
    if sort_cols:
        collapsed = collapsed.sort_values(sort_cols, ascending=[False] * len(sort_cols))
    return collapsed.reset_index(drop=True)


def apply_resolved_status_labels(
    frame: pd.DataFrame,
    *,
    status_col: str = "STATUS",
    status_mapping: dict[int, str] | None = None,
    target_col: str = "Status_Label",
) -> pd.Series:
    """Vectorized resolved labels for a history/client frame."""
    status_mapping = status_mapping or DEFAULT_STATUS_MAPPING
    mapped = _map_status(frame[status_col], status_mapping)
    label = mapped.copy()

    for col in ("LIB_STATUS", "LIB_DETAIL"):
        if col not in frame.columns:
            continue
        raw = frame[col]
        meaningful = raw.where(raw.apply(is_meaningful_label))
        label = label.fillna(meaningful)

    if "STATUS_STATUS" in frame.columns:
        sub_mapped = _map_status(frame["STATUS_STATUS"], status_mapping)
        fallback = sub_mapped.where(sub_mapped.notna())
        label = label.fillna(fallback)

    code_text = _status_code_text(frame[status_col])
    label = label.fillna("Code " + code_text.astype(str))
    label = label.fillna("Autre")
    return group_status_labels(label, status_mapping=status_mapping).rename(target_col)


def resolve_status_label(
    status: object,
    *,
    lib_status: object = None,
    lib_detail: object = None,
    status_status: object = None,
    status_mapping: dict[int, str] | None = None,
) -> str:
    row = pd.DataFrame(
        {
            "STATUS": [status],
            "LIB_STATUS": [lib_status],
            "LIB_DETAIL": [lib_detail],
            "STATUS_STATUS": [status_status],
        }
    )
    return str(apply_resolved_status_labels(row, status_mapping=status_mapping).iloc[0])


def build_status_code_catalog(
    frame: pd.DataFrame,
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Catalogue de tous les codes STATUS avec leurs libellés observés."""
    status_mapping = status_mapping or DEFAULT_STATUS_MAPPING
    if frame.empty or "STATUS" not in frame.columns:
        return pd.DataFrame(
            columns=[
                "Code_STATUS",
                "Libellé_résolu",
                "Dans_mapping",
                "LIB_DETAIL_principal",
                "Occurrences",
            ]
        )

    work = frame.copy()
    work["Code_STATUS"] = _status_code_text(work["STATUS"])
    work["Status_Label"] = apply_resolved_status_labels(work, status_mapping=status_mapping)
    if "LIB_DETAIL" in work.columns:
        work["_detail"] = work["LIB_DETAIL"].where(work["LIB_DETAIL"].apply(is_meaningful_label))
    else:
        work["_detail"] = pd.NA

    rows: list[dict[str, Any]] = []
    for code, group in work.groupby("Code_STATUS", dropna=False):
        if not code or pd.isna(code):
            continue
        try:
            in_map = int(code) in status_mapping
        except ValueError:
            in_map = False
        top_detail = ""
        if group["_detail"].notna().any():
            top_detail = str(group["_detail"].value_counts().index[0])
        top_label = str(group["Status_Label"].value_counts().index[0])
        rows.append(
            {
                "Code_STATUS": code,
                "Libellé_résolu": top_label,
                "Dans_mapping": "Oui" if in_map else "Non",
                "LIB_DETAIL_principal": top_detail,
                "Occurrences": len(group),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("Occurrences", ascending=False)
    return out.reset_index(drop=True)


def breakdown_autre_ventes(vente_transitions: pd.DataFrame) -> pd.DataFrame:
    """Détail des ventes classées Autre : codes et vrais noms."""
    empty = pd.DataFrame(
        columns=[
            "Code_STATUS",
            "Libellé_avant_vente",
            "LIB_DETAIL",
            "Sous_statut_STATUS_STATUS",
            "Ventes",
            "Part_%",
        ]
    )
    if vente_transitions.empty:
        return empty

    autre = vente_transitions[vente_transitions["Prior_Status"] == "Autre"].copy()
    if autre.empty:
        return empty

    autre["Code_STATUS"] = autre.get("Prior_Status_Code", pd.Series(dtype=str)).astype(str)
    autre["Libellé_avant_vente"] = autre.get(
        "Prior_Status_Label", autre["Code_STATUS"].apply(lambda c: f"Code {c}")
    )

    group_cols = ["Code_STATUS", "Libellé_avant_vente"]
    if "Prior_LIB_DETAIL" in autre.columns:
        autre["LIB_DETAIL"] = autre["Prior_LIB_DETAIL"].where(
            autre["Prior_LIB_DETAIL"].apply(is_meaningful_label)
        )
        group_cols.append("LIB_DETAIL")
    else:
        autre["LIB_DETAIL"] = pd.NA

    if "Prior_STATUS_STATUS" in autre.columns:
        autre["Sous_statut_STATUS_STATUS"] = autre["Prior_STATUS_STATUS"].apply(
            lambda v: resolve_status_label(v) if pd.notna(v) else pd.NA
        )
        group_cols.append("Sous_statut_STATUS_STATUS")
    else:
        autre["Sous_statut_STATUS_STATUS"] = pd.NA

    grouped = (
        autre.groupby(group_cols, dropna=False)
        .size()
        .reset_index(name="Ventes")
        .sort_values("Ventes", ascending=False)
    )
    total = int(grouped["Ventes"].sum())
    grouped["Part_%"] = (100 * grouped["Ventes"] / total).round(2) if total else 0.0
    return grouped.reset_index(drop=True)
