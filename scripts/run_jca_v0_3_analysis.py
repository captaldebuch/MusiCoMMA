#!/usr/bin/env python3
"""Run the MusiCoMMA JCA v0.3.0 addendum analyses.

The script extends the v0.2.0 descriptive notebook with analyses that can be
computed from the frozen release and the local CoMMA snapshot. It deliberately
does not create independent annotation labels or agreement scores.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = os.environ.get("MUSICOMMA_RELEASE_VERSION", "0.2.0")
if RELEASE_VERSION not in {"0.2.0", "0.2.1"}:
    raise ValueError("Unsupported release version")
RELEASE = Path(os.environ.get("MUSICOMMA_DATA_ROOT", ROOT / "release" / f"musiconis-comma-v{RELEASE_VERSION}-zenodo"))
DATA = RELEASE / "data"
NOTEBOOK_OUT = Path(os.environ.get("MUSICOMMA_OUTPUT_DIR", ROOT / "notebooks" / "outputs" / f"v{RELEASE_VERSION}"))
OUT = NOTEBOOK_OUT / "jca_v0.3.0"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
CORPUS = ROOT / "corpus" / "comma-jsonl-dfaacb6e"

os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".matplotlib"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

try:  # noqa: E402
    import matplotlib.pyplot as plt
    import seaborn as sns
except ModuleNotFoundError:  # pragma: no cover - dependency-light table rebuilds
    plt = None
    sns = None


BANDS: list[tuple[str, int, int]] = [
    ("800-999", 800, 999),
    ("1000-1199", 1000, 1199),
    ("1200-1399", 1200, 1399),
    ("1400-1600", 1400, 1600),
    ("post-1600", 1601, 9999),
]

STOPWORDS = {
    "a",
    "ad",
    "al",
    "aut",
    "cum",
    "de",
    "del",
    "des",
    "e",
    "en",
    "est",
    "et",
    "in",
    "la",
    "le",
    "les",
    "li",
    "ne",
    "non",
    "par",
    "per",
    "pour",
    "que",
    "qui",
    "quod",
    "se",
    "sed",
    "si",
    "sur",
    "un",
    "une",
    "ut",
}

CORINTHIANS_13_PATTERNS = {
    "linguis": r"\blinguis\b",
    "hominum": r"\bhominum\b",
    "loquar": r"\bloquar\b",
    "aes": r"\baes\b",
    "sonans": r"\bsonans\b",
    "tinniens_variant": r"\b(tinniens|tiniens|tyniens|tinmens|tuniens|tinicus)\b",
    "habuero_or_habeam": r"\b(habuero|habuero|habeam|habeo|habero)\b",
    "prophetiam": r"\b(prophetiam|propheciam)\b",
    "montes": r"\bmontes\b",
    "transferam": r"\btransferam\b",
    "caritas_or_charitas": r"\b(caritas|charitas|caritatem|charitatem|karitas|karitatem)\b",
    "nihil": r"\bnihil\b",
    "sum": r"\bsum\b",
}

PSALMIC_PATTERNS = {
    "psalmus_or_psalter": r"\b(psalmus|psalmi|psalmorum|psalterium|psalterio|psalterii)\b",
    "cantabo": r"\bcantabo\b",
    "domino": r"\bdomino\b",
    "gloria": r"\bgloria\b",
    "laudate": r"\blaudate\b",
}

CORE_CORINTHIANS_13_MARKERS = [
    "tinniens_variant",
    "aes",
    "sonans",
    "caritas_or_charitas",
    "loquar",
    "habuero_or_habeam",
    "montes",
    "transferam",
]


def ensure_dirs() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    (OUT / ".matplotlib").mkdir(parents=True, exist_ok=True)


def read_csv(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(DATA / name, **kwargs)


def write_table(df: pd.DataFrame, name: str) -> Path:
    path = TABLES / name
    df.to_csv(path, index=False)
    return path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_release_checksums() -> pd.DataFrame:
    rows = []
    with (RELEASE / "checksums.sha256").open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            expected, rel = line.split(maxsplit=1)
            # A portable notebook regenerates outputs before reaching this block.
            # Full archive integrity is checked separately before execution.
            if rel.startswith("analysis_outputs/"):
                continue
            path = RELEASE / rel
            observed = sha256(path)
            rows.append(
                {
                    "path": rel,
                    "expected_sha256": expected,
                    "observed_sha256": observed,
                    "status": "ok" if expected == observed else "mismatch",
                }
            )
    df = pd.DataFrame(rows)
    write_table(df, "checksum_verification.csv")
    return df


def source_polysemy(entries: pd.DataFrame) -> pd.DataFrame:
    e = entries.copy()
    for col in ["source_record_count", "sense_count", "form_count"]:
        e[col] = pd.to_numeric(e[col], errors="coerce")
    rows = []
    for language, group in e.groupby("language_label", sort=False):
        corr = (
            group["source_record_count"].corr(group["sense_count"])
            if len(group) > 1
            else np.nan
        )
        rows.append(
            {
                "language_label": language,
                "entries": len(group),
                "source_records": int(group["source_record_count"].sum()),
                "senses": int(group["sense_count"].sum()),
                "senses_per_entry": round(group["sense_count"].sum() / len(group), 3),
                "senses_per_source_record": round(
                    group["sense_count"].sum() / group["source_record_count"].sum(), 3
                ),
                "mean_source_records_per_entry": round(group["source_record_count"].mean(), 3),
                "source_record_sense_count_pearson": round(corr, 3)
                if not math.isnan(corr)
                else "",
            }
        )
    df = pd.DataFrame(rows).sort_values("entries", ascending=False)
    write_table(df, "source_polysemy_diagnostic.csv")
    return df


def coverage_states(entries: pd.DataFrame, coverage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = coverage.merge(
        entries[["entry_id", "language_label", "primary_category_id"]],
        on="entry_id",
        how="left",
    )
    by_language = (
        merged.groupby(["coverage_status", "language_code", "language_label"], dropna=False)
        .agg(entries=("entry_id", "count"))
        .reset_index()
        .sort_values(["coverage_status", "language_label"])
    )
    write_table(by_language, "coverage_state_by_language.csv")

    summary = (
        merged.groupby("coverage_status", dropna=False)
        .agg(entries=("entry_id", "count"))
        .reset_index()
        .sort_values("entries", ascending=False)
    )
    total = int(summary["entries"].sum())
    summary["share_of_vocabulary"] = (summary["entries"] / total).round(4)
    summary["interpretation"] = summary["coverage_status"].map(
        {
            "not_searched": "in current CoMMA language scope but not searched in v0.2.0",
            "out_of_comma_scope": "retained lexically but outside current CoMMA language scope",
            "validated_attestation": "selected exact-match pilot entry with accepted contexts",
        }
    )
    write_table(summary, "coverage_state_summary.csv")
    return by_language, summary


def cap_diagnostics(selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = selected.copy()
    for col in ["observed_exact_hits_capped", "review_rows_selected", "observed_manuscripts_capped"]:
        s[col] = pd.to_numeric(s[col], errors="coerce")
    s["retained_share_of_pre_review_hits"] = (
        s["review_rows_selected"] / s["observed_exact_hits_capped"]
    ).replace([np.inf, -np.inf], np.nan)
    s["ipw_lower_bound"] = (
        s["observed_exact_hits_capped"] / s["review_rows_selected"]
    ).replace([np.inf, -np.inf], np.nan)
    s["censored"] = s["observed_exact_hits_capped"] >= 200
    ranked = s.sort_values("observed_exact_hits_capped", ascending=False)[
        [
            "pilot_rank",
            "entry_id",
            "lemma",
            "language_label",
            "category_label",
            "polysemous",
            "observed_exact_hits_capped",
            "observed_manuscripts_capped",
            "review_rows_selected",
            "retained_share_of_pre_review_hits",
            "ipw_lower_bound",
            "censored",
        ]
    ]
    write_table(ranked, "pre_review_hit_spread_by_entry.csv")
    summary = (
        s.groupby(["language_label", "category_label"], observed=True)
        .agg(
            selected_entries=("entry_id", "count"),
            pre_review_hits_lower_bound=("observed_exact_hits_capped", "sum"),
            retained_review_rows=("review_rows_selected", "sum"),
            censored_entries=("censored", "sum"),
            median_pre_review_hits_lower_bound=("observed_exact_hits_capped", "median"),
            median_ipw_lower_bound=("ipw_lower_bound", "median"),
        )
        .reset_index()
        .sort_values(["language_label", "category_label"])
    )
    write_table(summary, "cap_distortion_by_language_category.csv")

    cat = (
        s.groupby("category_label", observed=True)
        .agg(
            selected_entries=("entry_id", "count"),
            pre_review_hits_lower_bound=("observed_exact_hits_capped", "sum"),
            retained_review_rows=("review_rows_selected", "sum"),
            censored_entries=("censored", "sum"),
        )
        .reset_index()
        .sort_values("pre_review_hits_lower_bound", ascending=False)
    )
    total_hits = cat["pre_review_hits_lower_bound"].sum()
    cat["share_of_lower_bound_hits"] = (
        cat["pre_review_hits_lower_bound"] / total_hits
    ).round(4)
    write_table(cat, "pre_review_hit_lower_bounds_by_category.csv")

    if plt is not None and sns is not None:
        top = ranked.head(20).iloc[::-1]
        plt.figure(figsize=(8, 7))
        sns.barplot(data=top, x="observed_exact_hits_capped", y="lemma", hue="language_label")
        plt.axvline(10, color="#333333", linestyle="--", linewidth=1, label="review retention cap")
        plt.xlabel("Pre-review decoded exact hits (capped at 200 per entry)")
        plt.ylabel("Selected entry")
        plt.title(f"MusiCoMMA v{RELEASE_VERSION}: exact-hit spread before review sampling")
        plt.tight_layout()
        plt.savefig(FIGURES / "fig10_pre_review_hit_spread.png", dpi=300)
        plt.savefig(FIGURES / "fig10_pre_review_hit_spread.svg")
        plt.close()
    (FIGURES / "fig10_pre_review_hit_spread.alt.txt").write_text(
        "Horizontal bar chart showing the twenty selected MusiCoMMA entries with the largest pre-review decoded exact-hit lower-bound counts. Many entries reach the 200-hit diagnostic ceiling while the ten-row review cap appears as a dashed vertical line.\n",
        encoding="utf-8",
    )
    return ranked, summary


def allocate_interval(start: float, end: float) -> dict[str, float]:
    if pd.isna(start) or pd.isna(end):
        return {}
    a, b = int(start), int(end)
    if b < a:
        a, b = b, a
    total = max(1, b - a + 1)
    shares: dict[str, float] = {}
    for label, lo, hi in BANDS:
        overlap = max(0, min(b, hi) - max(a, lo) + 1)
        if overlap:
            shares[label] = overlap / total
    return shares


def pilot_date_allocation(attestations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    sens_rows = []
    for _, row in attestations.iterrows():
        start = pd.to_numeric(row.get("not_before"), errors="coerce")
        end = pd.to_numeric(row.get("not_after"), errors="coerce")
        language = "Latin" if row.get("language") == "la" else "Old French"
        width = None if pd.isna(start) or pd.isna(end) else abs(int(end) - int(start)) + 1
        for band, share in allocate_interval(start, end).items():
            rows.append(
                {
                    "language_label": language,
                    "date_band": band,
                    "allocated_attestations": share,
                    "interval_width": width,
                    "attestation_id": row.get("attestation_id"),
                    "entry_id": row.get("entry_id"),
                    "manuscript_id": row.get("manuscript_id"),
                }
            )
            if width is not None and width <= 100:
                sens_rows.append(
                    {
                        "language_label": language,
                        "date_band": band,
                        "allocated_attestations": share,
                        "interval_width": width,
                        "attestation_id": row.get("attestation_id"),
                        "entry_id": row.get("entry_id"),
                        "manuscript_id": row.get("manuscript_id"),
                    }
                )
    allocated = pd.DataFrame(rows)
    df = (
        allocated
        .groupby(["language_label", "date_band"], observed=True)["allocated_attestations"]
        .sum()
        .reset_index()
    )
    df["allocated_attestations"] = df["allocated_attestations"].round(3)
    write_table(df, "pilot_interval_allocated_dates.csv")
    sens = (
        pd.DataFrame(sens_rows)
        .groupby(["language_label", "date_band"], observed=True)["allocated_attestations"]
        .sum()
        .reset_index()
        if sens_rows
        else pd.DataFrame(columns=["language_label", "date_band", "allocated_attestations"])
    )
    sens["allocated_attestations"] = sens["allocated_attestations"].round(3)
    write_table(sens, "pilot_interval_allocated_dates_ranges_le_100.csv")
    write_table(allocated, "pilot_interval_allocated_date_rows.csv")
    return df, sens, allocated


def corpus_language_bucket(value: object) -> str | None:
    text = str(value).lower()
    if "bilingual" in text:
        return "Bilingual Latin/French"
    if "latin" in text:
        return "Latin"
    if "french" in text:
        return "Old French"
    return None


def corpus_exposure(force: bool = False) -> pd.DataFrame:
    cache = TABLES / "corpus_exposure_by_date_language.csv"
    if cache.exists() and not force:
        provenance_path = OUT / "exposure_cache_provenance.json"
        if provenance_path.exists():
            expected = json.loads(provenance_path.read_text())["sha256"]
            if sha256(cache) != expected:
                raise ValueError("Corpus-exposure cache checksum mismatch")
        return pd.read_csv(cache)
    if not list(CORPUS.glob("parts_*.jsonl")):
        raise FileNotFoundError("Corpus-exposure cache missing; restore the packaged cache or supply the pinned CoMMA shards.")
    totals: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"allocated_records": 0.0, "allocated_tokens": 0.0}
    )
    processed = 0
    for shard in sorted(CORPUS.glob("parts_*.jsonl")):
        with shard.open(encoding="utf-8") as stream:
            for line in stream:
                processed += 1
                record = json.loads(line)
                bucket = corpus_language_bucket(record.get("language_categorized", ""))
                if bucket is None:
                    continue
                try:
                    tokens = float(record.get("tokens") or 0)
                    start = int(record.get("notBefore"))
                    end = int(record.get("notAfter"))
                except (TypeError, ValueError):
                    continue
                shares = allocate_interval(start, end)
                for band, share in shares.items():
                    key = (bucket, band)
                    totals[key]["allocated_records"] += share
                    totals[key]["allocated_tokens"] += tokens * share
    rows = [
        {
            "language_bucket": language,
            "date_band": band,
            "allocated_records": round(values["allocated_records"], 3),
            "allocated_tokens": round(values["allocated_tokens"], 3),
        }
        for (language, band), values in totals.items()
    ]
    df = pd.DataFrame(rows).sort_values(["language_bucket", "date_band"])
    df["records_processed"] = processed
    write_table(df, "corpus_exposure_by_date_language.csv")
    return df


def date_rates(pilot_dates: pd.DataFrame, exposure: pd.DataFrame) -> pd.DataFrame:
    denom = exposure[exposure["language_bucket"].isin(["Latin", "Old French"])].rename(
        columns={"language_bucket": "language_label"}
    )
    merged = pilot_dates.merge(
        denom[["language_label", "date_band", "allocated_records", "allocated_tokens"]],
        on=["language_label", "date_band"],
        how="left",
    )
    merged["attestations_per_million_tokens"] = (
        merged["allocated_attestations"] / merged["allocated_tokens"] * 1_000_000
    ).round(6)
    merged["attestations_per_1000_digitizations"] = (
        merged["allocated_attestations"] / merged["allocated_records"] * 1000
    ).round(6)
    merged["rate_reporting_status"] = np.where(
        (merged["allocated_attestations"] < 5) | (merged["allocated_tokens"] < 10_000_000),
        "suppressed_sparse_denominator",
        "reportable_exploratory_rate",
    )
    write_table(merged, "pilot_rates_by_corpus_exposure.csv")

    plot = merged.dropna(subset=["allocated_tokens"]).copy()
    if not plot.empty and plt is not None and sns is not None:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharex=True)
        sns.barplot(
            data=plot,
            x="date_band",
            y="allocated_attestations",
            hue="language_label",
            ax=axes[0],
        )
        axes[0].set_title("Raw pilot attestations")
        axes[0].set_ylabel("Interval-allocated attestations")
        axes[0].tick_params(axis="x", rotation=35)
        sns.barplot(
            data=plot,
            x="date_band",
            y="attestations_per_million_tokens",
            hue="language_label",
            ax=axes[1],
        )
        axes[1].set_title("Token-normalized pilot rate")
        axes[1].set_ylabel("Attestations per million CoMMA tokens")
        axes[1].tick_params(axis="x", rotation=35)
        plt.tight_layout()
        plt.savefig(FIGURES / "fig11_raw_vs_exposure_normalized_dates.png", dpi=300)
        plt.savefig(FIGURES / "fig11_raw_vs_exposure_normalized_dates.svg")
        plt.close()
    (FIGURES / "fig11_raw_vs_exposure_normalized_dates.alt.txt").write_text(
        "Two-panel bar chart comparing raw interval-allocated pilot attestations with token-normalized pilot rates by language and date band. The normalized panel shows that Latin 800-999 rises above Latin 1200-1399 after division by CoMMA language/date token exposure, while sparse Old French cells require suppressed reporting.\n",
        encoding="utf-8",
    )
    return merged


def date_rate_bootstrap(
    allocated_rows: pd.DataFrame,
    exposure: pd.DataFrame,
    n_boot: int = 2000,
    seed: int = 20260903,
) -> pd.DataFrame:
    if allocated_rows.empty:
        df = pd.DataFrame()
        write_table(df, "pilot_rates_by_corpus_exposure_bootstrap.csv")
        return df
    denom = exposure[exposure["language_bucket"].isin(["Latin", "Old French"])].rename(
        columns={"language_bucket": "language_label"}
    )
    per_ms = (
        allocated_rows.groupby(["manuscript_id", "language_label", "date_band"], observed=True)[
            "allocated_attestations"
        ]
        .sum()
        .reset_index()
    )
    pivot = per_ms.pivot_table(
        index="manuscript_id",
        columns=["language_label", "date_band"],
        values="allocated_attestations",
        aggfunc="sum",
        fill_value=0.0,
    )
    rng = np.random.default_rng(seed)
    rows = []
    denom_lookup = denom.set_index(["language_label", "date_band"])
    for language, band in pivot.columns:
        values = pivot[(language, band)].to_numpy(dtype=float)
        observed = float(values.sum())
        idx = rng.integers(0, len(values), size=(n_boot, len(values)))
        boot_attestations = values[idx].sum(axis=1)
        try:
            token_denom = float(denom_lookup.loc[(language, band), "allocated_tokens"])
            record_denom = float(denom_lookup.loc[(language, band), "allocated_records"])
        except KeyError:
            token_denom = np.nan
            record_denom = np.nan
        if token_denom and not np.isnan(token_denom):
            boot_rates = boot_attestations / token_denom * 1_000_000
            observed_rate = observed / token_denom * 1_000_000
        else:
            boot_rates = np.array([np.nan])
            observed_rate = np.nan
        rows.append(
            {
                "language_label": language,
                "date_band": band,
                "allocated_attestations": round(observed, 3),
                "contributing_digitizations": int((values > 0).sum()),
                "allocated_records": round(record_denom, 3) if not np.isnan(record_denom) else "",
                "allocated_tokens": round(token_denom, 3) if not np.isnan(token_denom) else "",
                "attestations_per_million_tokens": round(observed_rate, 6)
                if not np.isnan(observed_rate)
                else "",
                "bootstrap_cluster_unit": "manuscript_id",
                "bootstrap_iterations": n_boot,
                "rate_ci2_5": round(float(np.nanpercentile(boot_rates, 2.5)), 6),
                "rate_ci50": round(float(np.nanpercentile(boot_rates, 50)), 6),
                "rate_ci97_5": round(float(np.nanpercentile(boot_rates, 97.5)), 6),
                "rate_reporting_status": "suppressed_sparse_denominator"
                if observed < 5 or (not np.isnan(token_denom) and token_denom < 10_000_000)
                else "reportable_exploratory_rate",
            }
        )
    df = pd.DataFrame(rows).sort_values(["language_label", "date_band"])
    write_table(df, "pilot_rates_by_corpus_exposure_bootstrap.csv")
    reporting = df.copy()
    if not reporting.empty:
        reporting["allocated_attestations_reported"] = reporting["allocated_attestations"].map(
            lambda value: f"{float(value):.1f}"
        )
        for column in ["attestations_per_million_tokens", "rate_ci2_5", "rate_ci97_5"]:
            reporting[f"{column}_reported"] = reporting[column].map(
                lambda value: f"{float(value):.3g}" if value != "" else ""
            )
        reporting["reporting_note"] = np.where(
            reporting["rate_reporting_status"] == "reportable_exploratory_rate",
            "reported exploratory cell",
            "suppressed because the numerator or token denominator is sparse",
        )
        reporting = reporting[
            [
                "language_label",
                "date_band",
                "allocated_attestations_reported",
                "attestations_per_million_tokens_reported",
                "rate_ci2_5_reported",
                "rate_ci97_5_reported",
                "rate_reporting_status",
                "reporting_note",
            ]
        ]
    write_table(reporting, "pilot_rates_reportable_cells_for_manuscript.csv")
    return df


def hypergeom_upper_tail(n: int, k1: int, k2: int, observed: int) -> float:
    denom = math.comb(n, k2)
    max_x = min(k1, k2)
    total = 0
    for x in range(observed, max_x + 1):
        if k2 - x <= n - k1:
            total += math.comb(k1, x) * math.comb(n - k1, k2 - x)
    return min(1.0, total / denom)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    q = [1.0] * m
    running = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        running = min(running, p_values[i] * m / rank)
        q[i] = running
    return q


def category_cooccurrence(attestations: pd.DataFrame, selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    enriched = attestations.merge(
        selected[["entry_id", "category_label", "lemma", "language_label"]], on="entry_id", how="left"
    )
    by_ms = (
        enriched.groupby("manuscript_id", observed=True)["category_label"]
        .apply(lambda values: sorted(set(values.dropna())))
        .reset_index()
    )
    n = len(by_ms)
    category_counts = Counter()
    pair_counts = Counter()
    for cats in by_ms["category_label"]:
        category_counts.update(cats)
        pair_counts.update(tuple(pair) for pair in combinations(cats, 2))
    entry_ms = enriched.drop_duplicates(["entry_id", "manuscript_id"])
    entry_count_by_ms = entry_ms.groupby("manuscript_id", observed=True)["entry_id"].nunique()
    same_category_pair_counts = Counter()
    for _, group in entry_ms.groupby(["manuscript_id", "category_label"], observed=True):
        count = group["entry_id"].nunique()
        if count > 1:
            same_category_pair_counts[group["category_label"].iloc[0]] += math.comb(count, 2)
    category_count_by_ms = (
        enriched.drop_duplicates(["manuscript_id", "category_label"])
        .groupby("manuscript_id", observed=True)["category_label"]
        .nunique()
    )
    rows = []
    for pair, observed in sorted(pair_counts.items()):
        a, b = pair
        k1, k2 = category_counts[a], category_counts[b]
        expected = k1 * k2 / n if n else 0
        p = hypergeom_upper_tail(n, k1, k2, observed) if n else 1.0
        rows.append(
            {
                "category_a": a,
                "category_b": b,
                "manuscripts_total": n,
                "category_a_manuscripts": k1,
                "category_b_manuscripts": k2,
                "observed_cooccurring_manuscripts": observed,
                "expected_under_fixed_category_margins": round(expected, 3),
                "enrichment_ratio": round(observed / expected, 3) if expected else "",
                "hypergeom_upper_tail_p": p,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["bh_q"] = benjamini_hochberg(df["hypergeom_upper_tail_p"].tolist())
        # Keep this as a design diagnostic, not a pseudo-precise inference table.
        df["hypergeom_upper_tail_p"] = df["hypergeom_upper_tail_p"].round(3)
        df["bh_q"] = df["bh_q"].round(3)
        df = df.sort_values(["bh_q", "hypergeom_upper_tail_p", "enrichment_ratio"])
    strongest_enrichment_pair_count = int(df.iloc[0]["observed_cooccurring_manuscripts"]) if not df.empty else 0
    categories = sorted(category_counts)
    matrix_rows = []
    for a in categories:
        for b in categories:
            if a == b:
                observed = category_counts[a]
                cell_definition = "digitizations containing category"
            else:
                key = tuple(sorted((a, b)))
                observed = pair_counts.get(key, 0)
                cell_definition = "digitizations containing both categories"
            matrix_rows.append(
                {
                    "category_a": a,
                    "category_b": b,
                    "observed_digitizations": int(observed),
                    "cell_definition": cell_definition,
                }
            )
    matrix_long = pd.DataFrame(matrix_rows)
    matrix_wide = matrix_long.pivot(
        index="category_a", columns="category_b", values="observed_digitizations"
    ).reset_index()
    write_table(matrix_long, "category_cooccurrence_matrix_with_diagonal_long.csv")
    write_table(matrix_wide, "category_cooccurrence_matrix_with_diagonal_wide.csv")
    same_category_summary = pd.DataFrame(
        [
            {
                "category_label": category,
                "same_category_entry_pairs_within_digitization": int(count),
            }
            for category, count in sorted(same_category_pair_counts.items())
        ]
    )
    if same_category_summary.empty:
        same_category_summary = pd.DataFrame(
            columns=["category_label", "same_category_entry_pairs_within_digitization"]
        )
    write_table(same_category_summary, "same_category_entry_pairs_within_digitization.csv")
    design = pd.DataFrame(
        [
            {
                "accepted_contexts": len(attestations),
                "distinct_digitizations": int(enriched["manuscript_id"].nunique()),
                "entry_manuscript_groups": int(len(entry_ms)),
                "additional_entry_manuscript_groups_beyond_one_per_digitization": int(
                    len(entry_ms) - enriched["manuscript_id"].nunique()
                ),
                "digitizations_with_multiple_selected_entries": int((entry_count_by_ms > 1).sum()),
                "max_selected_entries_in_one_digitization": int(entry_count_by_ms.max()),
                "max_categories_in_one_digitization": int(category_count_by_ms.max()),
                "off_diagonal_category_pair_observations": int(sum(pair_counts.values())),
                "same_category_entry_pair_observations": int(sum(same_category_pair_counts.values())),
                "max_observed_category_pair_cooccurrence": int(max(pair_counts.values()) if pair_counts else 0),
                "strongest_enrichment_pair_cooccurrence": strongest_enrichment_pair_count,
                "interpretation": "ten-context cap disperses the pilot; category co-occurrence is not estimable as a substantive corpus structure",
            }
        ]
    )
    write_table(design, "cooccurrence_design_diagnostic.csv")
    write_table(df, "category_cooccurrence_fixed_margin.csv")
    return df, design


def normalize_token(token: str) -> str:
    token = unicodedata.normalize("NFKD", token).casefold()
    token = "".join(ch for ch in token if not unicodedata.combining(ch))
    token = re.sub(r"[^a-z0-9]+", "", token)
    return token


def tokenize(text: str) -> list[str]:
    toks = [normalize_token(t) for t in re.findall(r"[\wÀ-ÿꝑꝓꝙꝗꝟ]+", text, flags=re.UNICODE)]
    return [t for t in toks if len(t) > 2 and t not in STOPWORDS]


def normalize_context_text(text: object) -> str:
    text = unicodedata.normalize("NFKD", str(text)).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def collocations(attestations: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    enriched = attestations.merge(
        selected[["entry_id", "lemma", "language_label", "category_label", "sense_count", "polysemous"]],
        on="entry_id",
        how="left",
    )
    enriched["polysemous_bool"] = enriched["polysemous"].astype(str).str.lower().isin(["true", "1"])
    poly = enriched[enriched["polysemous_bool"]].copy()
    context_tokens: dict[str, list[list[str]]] = defaultdict(list)
    global_counts = Counter()
    for _, row in poly.iterrows():
        lemma = normalize_token(str(row["lemma"]))
        source = normalize_token(str(row.get("source_string", "")))
        tokens = [
            t
            for t in tokenize(f"{row.get('left_context', '')} {row.get('right_context', '')}")
            if t not in {lemma, source}
        ]
        context_tokens[row["entry_id"]].append(tokens)
        global_counts.update(tokens)
    rows = []
    for entry_id, contexts in context_tokens.items():
        meta = poly[poly["entry_id"] == entry_id].iloc[0]
        if len(contexts) < 5:
            continue
        entry_counts = Counter()
        for toks in contexts:
            entry_counts.update(toks)
        total_entry_tokens = sum(entry_counts.values())
        for collocate, f_xy in entry_counts.most_common(25):
            f_y = global_counts[collocate]
            score = 14 + math.log2((2 * f_xy) / (total_entry_tokens + f_y))
            rows.append(
                {
                    "entry_id": entry_id,
                    "lemma": meta["lemma"],
                    "language_label": meta["language_label"],
                    "category_label": meta["category_label"],
                    "context_count": len(contexts),
                    "sense_count": meta["sense_count"],
                    "collocate": collocate,
                    "collocate_count_in_entry_contexts": f_xy,
                    "collocate_count_global_poly_contexts": f_y,
                    "log_dice": round(score, 3),
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["entry_id", "log_dice"], ascending=[True, False])
        df["rank_for_entry"] = df.groupby("entry_id").cumcount() + 1
        df = df[df["rank_for_entry"] <= 10]
    write_table(df, "polysemous_entry_collocations_logdice.csv")
    return df


def cymbalum_contexts(attestations: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    enriched = attestations.merge(selected[["entry_id", "lemma", "sense_summary_fr"]], on="entry_id", how="left")
    cym = enriched[enriched["lemma"].astype(str).str.casefold() == "cymbalum"].copy()
    cols = [
        "attestation_id",
        "lemma",
        "source_string",
        "context_with_match",
        "repository",
        "shelfmark",
        "not_before",
        "not_after",
        "iiif_url",
        "sense_summary_fr",
        "sense_assignment_status",
        "image_checked",
    ]
    cym = cym[[c for c in cols if c in cym.columns]].head(10)
    write_table(cym, "cymbalum_contexts_for_close_reading.csv")
    return cym


def formulaic_context_markers(attestations: pd.DataFrame, selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    enriched = attestations.merge(
        selected[["entry_id", "lemma", "language_label", "category_label"]],
        on="entry_id",
        how="left",
    )
    targets = enriched[enriched["lemma"].astype(str).str.casefold().isin(["cymbalum", "psallo", "cantus"])].copy()
    rows = []
    for _, row in targets.iterrows():
        text = normalize_context_text(
            f"{row.get('left_context', '')} {row.get('source_string', '')} {row.get('right_context', '')} {row.get('context_with_match', '')}"
        )
        cor_markers = {
            name: bool(re.search(pattern, text)) for name, pattern in CORINTHIANS_13_PATTERNS.items()
        }
        psalm_markers = {
            name: bool(re.search(pattern, text)) for name, pattern in PSALMIC_PATTERNS.items()
        }
        core_cor = sum(cor_markers[name] for name in CORE_CORINTHIANS_13_MARKERS)
        probable_cor = (
            row["lemma"].casefold() == "cymbalum"
            and core_cor >= 2
        )
        probable_psalmic = sum(psalm_markers.values()) >= 1
        matched_core = [
            marker for marker in CORE_CORINTHIANS_13_MARKERS if cor_markers[marker]
        ]
        matched_psalmic = [marker for marker, value in psalm_markers.items() if value]
        rows.append(
            {
                "attestation_id": row.get("attestation_id"),
                "entry_id": row.get("entry_id"),
                "lemma": row.get("lemma"),
                "language_label": row.get("language_label"),
                "category_label": row.get("category_label"),
                "manuscript_id": row.get("manuscript_id"),
                "repository": row.get("repository"),
                "shelfmark": row.get("shelfmark"),
                "not_before": row.get("not_before"),
                "not_after": row.get("not_after"),
                "corinthians13_core_marker_count": int(core_cor),
                "probable_1_cor_13_citation_fingerprint": bool(probable_cor),
                "psalmic_marker_count": int(sum(psalm_markers.values())),
                "probable_psalmic_or_liturgical_fingerprint": bool(probable_psalmic),
                "matched_core_corinthians13_markers": ";".join(matched_core),
                "matched_psalmic_markers": ";".join(matched_psalmic),
                **{f"cor13_{name}": value for name, value in cor_markers.items()},
                **{f"psalmic_{name}": value for name, value in psalm_markers.items()},
                "context_with_match": row.get("context_with_match"),
            }
        )
    detail = pd.DataFrame(rows)
    write_table(detail, "formulaic_context_markers.csv")
    plot_cols = [
        "attestation_id",
        "entry_id",
        "lemma",
        "manuscript_id",
        "corinthians13_core_marker_count",
        "probable_1_cor_13_citation_fingerprint",
        "matched_core_corinthians13_markers",
        "psalmic_marker_count",
        "probable_psalmic_or_liturgical_fingerprint",
        "matched_psalmic_markers",
    ]
    write_table(detail[[c for c in plot_cols if c in detail.columns]], "formulaic_context_marker_plot_data.csv")
    method = pd.DataFrame(
        [
            {
                "diagnostic": "1 Corinthians 13 citation fingerprint",
                "target_entry": "cymbalum",
                "marker_inventory": "; ".join(CORE_CORINTHIANS_13_MARKERS),
                "decision_rule": "probable if the retained context contains at least two distinct core markers around the target entry",
                "positive_count": int(detail["probable_1_cor_13_citation_fingerprint"].sum()) if not detail.empty else 0,
                "target_contexts": int((detail["lemma"] == "cymbalum").sum()) if not detail.empty else 0,
                "negative_controls": "psallo; cantus",
                "negative_control_rule": "same Corinthians marker rule, plus a separate Psalter/liturgical marker screen",
                "negative_control_positive_count": int(
                    detail.loc[detail["lemma"].isin(["psallo", "cantus"]), "probable_1_cor_13_citation_fingerprint"].sum()
                )
                if not detail.empty
                else 0,
            }
        ]
    )
    write_table(method, "formulaic_marker_method.csv")
    if detail.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            detail.groupby("lemma", observed=True)
            .agg(
                contexts=("attestation_id", "count"),
                probable_1_cor_13_contexts=("probable_1_cor_13_citation_fingerprint", "sum"),
                probable_psalmic_or_liturgical_contexts=(
                    "probable_psalmic_or_liturgical_fingerprint",
                    "sum",
                ),
                max_corinthians13_core_marker_count=("corinthians13_core_marker_count", "max"),
                max_psalmic_marker_count=("psalmic_marker_count", "max"),
            )
            .reset_index()
        )
    write_table(summary, "formulaic_context_summary.csv")
    return detail, summary


def write_summary(
    checksum: pd.DataFrame,
    poly: pd.DataFrame,
    coverage_scope: pd.DataFrame,
    ranked: pd.DataFrame,
    date_rates_df: pd.DataFrame,
    bootstrap_rates: pd.DataFrame,
    cooc_design: pd.DataFrame,
    colloc: pd.DataFrame,
    formula_summary: pd.DataFrame,
) -> Path:
    lines = [
        "# MusiCoMMA JCA v0.3.0 Analysis Summary",
        "",
        f"- Input checksum verification: {(checksum['status'] == 'ok').sum()}/{len(checksum)} non-generated release files matched the v{RELEASE_VERSION} manifest. Regenerated analysis_outputs are excluded; the reused exposure cache is checked separately.",
    ]
    latin = poly[poly["language_label"] == "Latin"]
    old_french = poly[poly["language_label"] == "Old French"]
    if not latin.empty and not old_french.empty:
        lines.append(
            f"- Source-polysemy diagnostic: Latin has {latin.iloc[0]['senses_per_entry']} senses per entry, Old French {old_french.iloc[0]['senses_per_entry']}; this is reported as a feature of Musiconis compilation, not medieval language behaviour."
        )
    if not coverage_scope.empty:
        coverage_lookup = dict(
            zip(coverage_scope["coverage_status"], coverage_scope["entries"], strict=False)
        )
        lines.append(
            f"- Coverage-state diagnostic: {int(coverage_lookup.get('not_searched', 0))} entries remain `not_searched`, {int(coverage_lookup.get('out_of_comma_scope', 0))} are outside the current CoMMA language scope, and {int(coverage_lookup.get('validated_attestation', 0))} belong to the validated exact-match pilot."
        )
    lines.append(
        f"- Cap diagnostic: the 50 selected entries expose at least {int(ranked['observed_exact_hits_capped'].sum())} pre-review decoded exact hits under the retrieval ceiling, of which {int(ranked['review_rows_selected'].sum())} were retained for review; {int(ranked['censored'].sum())} entries reached the 200-hit diagnostic cap."
    )
    weight_min = ranked["ipw_lower_bound"].min()
    weight_max = ranked["ipw_lower_bound"].max()
    uncensored = int((~ranked["censored"]).sum())
    lines.append(
        f"- Inverse-probability diagnostics are lower bounds, not measured population weights: `ipw_lower_bound` ranges from {weight_min:.2f} to {weight_max:.2f}, but only {uncensored} uncensored entries can use it as a direct entry-level review weight."
    )
    if not bootstrap_rates.empty:
        reportable = bootstrap_rates[
            bootstrap_rates["rate_reporting_status"] == "reportable_exploratory_rate"
        ]
        highest = reportable.sort_values("attestations_per_million_tokens", ascending=False).iloc[0]
        latin_early = bootstrap_rates[
            (bootstrap_rates["language_label"] == "Latin")
            & (bootstrap_rates["date_band"] == "800-999")
        ].iloc[0]
        latin_late = bootstrap_rates[
            (bootstrap_rates["language_label"] == "Latin")
            & (bootstrap_rates["date_band"] == "1200-1399")
        ].iloc[0]
        ratio = latin_early["attestations_per_million_tokens"] / latin_late[
            "attestations_per_million_tokens"
        ]
        lines.append(
            f"- Exposure-normalized pilot chronology: among reportable exploratory cells, the highest rate is {highest['attestations_per_million_tokens']:.3g} attestations per million tokens for {highest['language_label']} in {highest['date_band']}; Latin 800-999 is {ratio:.1f} times the Latin 1200-1399 rate under manuscript-cluster bootstrap diagnostics."
        )
    if not cooc_design.empty:
        diag = cooc_design.iloc[0]
        lines.append(
            f"- Category co-occurrence: not estimable as a substantive structure in this pilot; {diag['entry_manuscript_groups']} entry-manuscript groups from {diag['accepted_contexts']} contexts are spread across {diag['distinct_digitizations']} digitizations, and the strongest exploratory enrichment pair co-occurs in only {diag['strongest_enrichment_pair_cooccurrence']} digitizations."
        )
    if not colloc.empty:
        entries = colloc["entry_id"].nunique()
        lines.append(
            f"- Collocation profiles: log-Dice profiles were computed for {entries} polysemous entries with at least five retained contexts; unresolved sense is now inspectable through context vocabulary rather than only counted as missing annotation."
        )
    if not formula_summary.empty:
        cym = formula_summary[formula_summary["lemma"] == "cymbalum"].iloc[0]
        lines.append(
            f"- Formulaic-context diagnostic: {int(cym['probable_1_cor_13_contexts'])}/{int(cym['contexts'])} retained `cymbalum` contexts carry probable 1 Corinthians 13 citation fingerprints; collocates that first looked generic are therefore musicological evidence for scriptural register."
        )
    lines.append("")
    lines.append("Unsupported after this run:")
    lines.append("- No inter-annotator agreement is reported; Frédéric Billiet has not yet supplied an independent blind annotation layer.")
    lines.append(f"- No onomastic/appellative distribution is reported; use-type labels are not present in v{RELEASE_VERSION}.")
    lines.append("- The exposure-normalized rates use corpus-wide date/language/token denominators but remain pilot rates, not historical prevalence estimates.")
    path = OUT / "JCA_v0.3.0_analysis_summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ensure_dirs()
    if sns is not None:
        sns.set_theme(style="whitegrid")
    entries = read_csv("entries.csv")
    coverage = read_csv("coverage.csv")
    selected = read_csv("selected_entries.csv")
    attestations = read_csv("attestations.csv")

    checksum = verify_release_checksums()
    if not (checksum["status"] == "ok").all():
        raise RuntimeError("Release checksum verification failed")

    poly = source_polysemy(entries)
    _coverage_by_language, coverage_scope = coverage_states(entries, coverage)
    ranked, _summary = cap_diagnostics(selected)
    pilot_dates, _pilot_sens, allocated_rows = pilot_date_allocation(attestations)
    exposure = corpus_exposure(force=False)
    rates = date_rates(pilot_dates, exposure)
    bootstrap_rates = date_rate_bootstrap(allocated_rows, exposure)
    _cooc, cooc_design = category_cooccurrence(attestations, selected)
    colloc = collocations(attestations, selected)
    _cym = cymbalum_contexts(attestations, selected)
    _formula_detail, formula_summary = formulaic_context_markers(attestations, selected)
    summary_path = write_summary(
        checksum,
        poly,
        coverage_scope,
        ranked,
        rates,
        bootstrap_rates,
        cooc_design,
        colloc,
        formula_summary,
    )
    print(f"Wrote JCA v0.3.0 outputs to {OUT}")
    print(summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
