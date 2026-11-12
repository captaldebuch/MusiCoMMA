#!/usr/bin/env python3
"""Build the executable MusiCoMMA v0.2.0 publication-analysis notebook."""

from pathlib import Path
import os
import textwrap

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks"
RELEASE_VERSION = os.environ.get("MUSICOMMA_RELEASE_VERSION", "0.2.0")
if RELEASE_VERSION not in {"0.2.0", "0.2.1"}:
    raise ValueError("Unsupported release version")
NOTEBOOK_PATH = NOTEBOOK_DIR / f"MusiCoMMA_analysis_v{RELEASE_VERSION}.ipynb"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(textwrap.dedent(text).strip())


def code(text: str):
    return nbf.v4.new_code_cell(textwrap.dedent(text).strip())


cells = [
    markdown(
        """
        # MusiCoMMA v0.2.0: dataset analysis and publication figures

        This notebook analyzes the frozen **MusiCoMMA v0.2.0 validated pilot** and exports reusable tables and publication-ready figures for the HAL technical report and the musicology/digital-humanities article.

        **Dataset layers.** The lexical layer contains the complete current Musiconis vocabulary foundation (1,198 entries and 1,548 senses). The corpus-evidence layer is a bounded pilot: 50 of the 900 Latin and Old French entries in current CoMMA scope, producing 485 reviewer-accepted contexts.

        **Interpretive limits.** The charts are descriptive of the designed pilot, not estimates of medieval lexical frequency. All retained contexts received a positive entry-level relevance decision, so the notebook does not calculate precision, recall, F-score, or classifier performance. Contextual senses remain unresolved for polysemous entries, and manuscript-image checking was not recorded for the batch review.

        The notebook reads only the deposit-candidate tables under `release/musiconis-comma-v0.2.0-zenodo/data/`. It writes derived files under `notebooks/outputs/v0.2.0/` and does not modify the release.
        """
    ),
    markdown("## 1. Environment, paths, and publication style"),
    code(
        """
        from pathlib import Path
        import json
        import os
        import platform

        def locate_project_root():
            candidates = [Path.cwd(), *Path.cwd().parents]
            for candidate in candidates:
                if (candidate / "data/attestations.csv").exists() and (candidate / "VERSION").exists():
                    return candidate.resolve()
                release = candidate / "release" / "musiconis-comma-v0.2.0-zenodo"
                if release.exists():
                    return candidate.resolve()
            raise FileNotFoundError(
                "Run this notebook from the MusiCoMMA project or its notebooks directory."
            )

        PROJECT_ROOT = locate_project_root()
        PACKAGED_RELEASE = (PROJECT_ROOT / "data/attestations.csv").exists()
        RELEASE_DIR = PROJECT_ROOT if PACKAGED_RELEASE else PROJECT_ROOT / "release" / "musiconis-comma-v0.2.0-zenodo"
        DATA_DIR = RELEASE_DIR / "data"
        OUTPUT_DIR = PROJECT_ROOT / "analysis_outputs" if PACKAGED_RELEASE else PROJECT_ROOT / "notebooks" / "outputs" / "v0.2.0"
        FIGURE_DIR = OUTPUT_DIR / "figures"
        TABLE_DIR = OUTPUT_DIR / "tables"
        for directory in (FIGURE_DIR, TABLE_DIR):
            directory.mkdir(parents=True, exist_ok=True)

        os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / "_matplotlib_cache"))
        os.environ.setdefault("MPLBACKEND", "Agg")

        import numpy as np
        import pandas as pd
        import matplotlib
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
        import seaborn as sns
        from IPython.display import display, Markdown

        RELEASE_VERSION = (RELEASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
        assert RELEASE_VERSION == "0.2.0"

        COLORS = {
            "blue": "#2F6BAA",
            "orange": "#D67A2A",
            "green": "#4F8A70",
            "purple": "#8057A5",
            "slate": "#56657A",
            "light_blue": "#DDE9F5",
            "light_orange": "#F6E6D6",
            "light_green": "#DDEDE5",
            "light_purple": "#E9E0F1",
            "grid": "#D9DEE7",
            "text": "#17233C",
        }

        sns.set_theme(style="whitegrid", context="paper")
        plt.rcParams.update({
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "font.family": "sans-serif",
            "font.sans-serif": ["Carlito", "Arial", "DejaVu Sans"],
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.edgecolor": COLORS["grid"],
            "axes.labelcolor": COLORS["text"],
            "text.color": COLORS["text"],
            "xtick.color": COLORS["slate"],
            "ytick.color": COLORS["text"],
            "grid.color": COLORS["grid"],
            "grid.linewidth": 0.6,
            "legend.frameon": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        })

        figure_manifest = []

        def save_figure(fig, stem, title, caption, alt_text, recommended_use):
            # Save one figure in PNG, SVG, and PDF plus accessible text.
            for suffix in ("png", "svg", "pdf"):
                path = FIGURE_DIR / f"{stem}.{suffix}"
                kwargs = {"bbox_inches": "tight", "facecolor": "white"}
                if suffix == "png":
                    kwargs["dpi"] = 300
                fig.savefig(path, **kwargs)
            (FIGURE_DIR / f"{stem}.alt.txt").write_text(alt_text + "\\n", encoding="utf-8")
            figure_manifest.append({
                "file_stem": stem,
                "title": title,
                "caption": caption,
                "alt_text": alt_text,
                "recommended_use": recommended_use,
                "formats": "PNG; SVG; PDF",
            })
            display(fig)
            plt.close(fig)

        print(f"Project: {PROJECT_ROOT}")
        print(f"Release: {RELEASE_VERSION}")
        print(f"Python: {platform.python_version()}")
        print(f"pandas: {pd.__version__}; matplotlib: {matplotlib.__version__}; seaborn: {sns.__version__}")
        print(f"Derived outputs: {OUTPUT_DIR}")
        """
    ),
    markdown("## 2. Load and validate the frozen release tables"),
    code(
        """
        TABLE_NAMES = [
            "entries", "forms", "senses", "concepts", "coverage",
            "selected_entries", "attestations", "annotations",
            "entry_groups", "manuscript_groups", "manuscripts",
            "review_events", "provenance", "stats_summary",
        ]

        tables = {
            name: pd.read_csv(DATA_DIR / f"{name}.csv", dtype=str, keep_default_na=False)
            for name in TABLE_NAMES
        }

        entries = tables["entries"].copy()
        forms = tables["forms"].copy()
        senses = tables["senses"].copy()
        concepts = tables["concepts"].copy()
        coverage = tables["coverage"].copy()
        selected = tables["selected_entries"].copy()
        attestations = tables["attestations"].copy()
        annotations = tables["annotations"].copy()
        entry_groups = tables["entry_groups"].copy()
        manuscript_groups = tables["manuscript_groups"].copy()
        manuscripts = tables["manuscripts"].copy()

        numeric_columns = {
            "entries": ["source_record_count", "sense_count", "form_count"],
            "selected_entries": ["pilot_rank", "sense_count", "observed_exact_hits_capped", "observed_manuscripts_capped", "review_rows_selected"],
            "attestations": ["char_start", "char_end", "not_before", "not_after", "score", "threshold"],
            "entry_groups": ["entry_group_sequence", "sense_count", "attestation_count", "manuscript_group_count", "distinct_manuscript_count", "earliest_not_before", "latest_not_after"],
            "manuscript_groups": ["entry_group_sequence", "manuscript_group_sequence", "not_before", "not_after", "record_line", "attestation_count"],
            "manuscripts": ["not_before", "not_after", "entry_count", "attestation_count"],
        }
        for table_name, columns in numeric_columns.items():
            frame = tables[table_name]
            for column in columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")

        entries = tables["entries"]
        selected = tables["selected_entries"]
        attestations = tables["attestations"]
        entry_groups = tables["entry_groups"]
        manuscript_groups = tables["manuscript_groups"]
        manuscripts = tables["manuscripts"]

        expected_counts = {
            "entries": 1198,
            "forms": 1198,
            "senses": 1548,
            "concepts": 9,
            "coverage": 1198,
            "selected_entries": 50,
            "attestations": 485,
            "annotations": 485,
            "entry_groups": 50,
            "manuscript_groups": 482,
            "manuscripts": 384,
        }
        if RELEASE_VERSION == "0.2.1":
            expected_counts.update(attestations=478, annotations=495,
                                   manuscript_groups=475, manuscripts=378)
        observed_counts = {name: len(tables[name]) for name in expected_counts}
        assert observed_counts == expected_counts

        assert attestations["attestation_id"].is_unique
        assert set(attestations["entry_id"]) <= set(entries["entry_id"])
        assert set(attestations["form_id"]) <= set(forms["form_id"])
        assert set(attestations.loc[attestations["sense_id"] != "", "sense_id"]) <= set(senses["sense_id"])
        assert set(attestations["manuscript_id"]) <= set(manuscripts["manuscript_id"])
        assert (attestations["validation_status"] == "validated_attestation").all()
        assert (attestations["image_checked"] == "not_recorded").all()

        validation = pd.DataFrame({
            "table": list(expected_counts),
            "expected_rows": list(expected_counts.values()),
            "observed_rows": [observed_counts[name] for name in expected_counts],
        })
        validation["status"] = np.where(
            validation["expected_rows"] == validation["observed_rows"], "PASS", "FAIL"
        )
        display(validation)
        print("Foreign keys, unique attestation identifiers, validation status, and image-check state: PASS")
        """
    ),
    markdown(
        """
        ## 3. Headline statistics and scope

        The headline table distinguishes the full lexical foundation from the bounded corpus pilot. “Accepted context” means reviewer-confirmed musical relevance to the selected lexical entry; it does not imply manuscript-image verification or contextual sense disambiguation.
        """
    ),
    code(
        """
        in_scope_mask = entries["coverage_status"].isin(["not_searched", "validated_attestation"])
        unresolved_mask = attestations["sense_assignment_status"].eq("entry_validated_sense_unresolved")
        auto_linked_mask = attestations["sense_assignment_status"].eq("single_source_sense_auto_linked_after_entry_validation")

        headline = pd.DataFrame([
            ("Source physical lines", 1585, "Complete source package"),
            ("Parsed source records", 1572, "Complete source package"),
            ("Vocabulary entries", len(entries), "Complete lexical foundation"),
            ("Vocabulary senses", len(senses), "Complete lexical foundation"),
            ("Analytical concepts", len(concepts), "Complete lexical foundation"),
            ("Latin/Old French entries in CoMMA scope", int(in_scope_mask.sum()), "Current retrieval scope"),
            ("Selected pilot entries", len(selected), "Designed, capped pilot"),
            ("Accepted contexts", len(attestations), "Entry-level reviewer decision"),
            ("Distinct manuscript digitizations", attestations["manuscript_id"].nunique(), "Global deduplication"),
            ("Entry-manuscript groups", len(manuscript_groups), "Browsing and analysis grouping"),
            ("Sense-unresolved contexts", int(unresolved_mask.sum()), "Polysemous entries"),
            ("Single-sense auto-linked contexts", int(auto_linked_mask.sum()), "Entries with one source sense"),
            ("Image-checked contexts recorded", int(attestations["image_checked"].ne("not_recorded").sum()), "Batch review metadata"),
        ], columns=["metric", "value", "scope_or_definition"])

        headline["value"] = headline["value"].astype(int)
        headline.to_csv(TABLE_DIR / "headline_statistics.csv", index=False)
        display(headline.style.format({"value": "{:,}"}))

        print(f"Pilot coverage of in-scope entries: {len(selected) / in_scope_mask.sum():.2%}")
        print(f"Unresolved contextual senses: {unresolved_mask.mean():.2%}")
        print(f"Single-sense automatic links: {auto_linked_mask.mean():.2%}")
        """
    ),
    code(
        """
        coverage_matrix = (
            entries.groupby(["language_label", "coverage_status"], observed=True)
            .size()
            .unstack(fill_value=0)
            .rename(columns={
                "validated_attestation": "pilot_validated",
                "not_searched": "in_scope_not_yet_searched",
                "out_of_comma_scope": "outside_current_comma_scope",
            })
        )
        coverage_matrix["total_entries"] = coverage_matrix.sum(axis=1)
        coverage_matrix.to_csv(TABLE_DIR / "coverage_by_language.csv")
        display(coverage_matrix)
        """
    ),
    markdown("## 4. Figure 1 — evidence pipeline and validation boundary"),
    code(
        """
        stages = [
            ("Musiconis source", "1,585 lines", COLORS["light_blue"]),
            ("Lexical model", "1,198 entries\\n1,548 senses", COLORS["light_blue"]),
            ("CoMMA scope", "900 Latin / Old French\\nentries", COLORS["light_orange"]),
            ("Balanced pilot", "50 entries", COLORS["light_green"]),
            ("Accepted evidence", f"{len(attestations)} contexts\\n{len(manuscripts)} manuscripts", COLORS["light_purple"]),
        ]

        fig, ax = plt.subplots(figsize=(12, 4.2))
        ax.set_xlim(0, 12)
        ax.set_ylim(0, 4.2)
        ax.axis("off")
        x_positions = np.linspace(0.5, 9.9, len(stages))
        for index, ((label, value, fill), x) in enumerate(zip(stages, x_positions)):
            box = FancyBboxPatch(
                (x, 1.45), 1.75, 1.45,
                boxstyle="round,pad=0.08,rounding_size=0.12",
                linewidth=1.2, edgecolor=COLORS["slate"], facecolor=fill,
            )
            ax.add_patch(box)
            ax.text(x + 0.875, 2.52, label, ha="center", va="center", weight="bold", fontsize=10)
            ax.text(x + 0.875, 1.93, value, ha="center", va="center", fontsize=10)
            if index < len(stages) - 1:
                arrow = FancyArrowPatch(
                    (x + 1.78, 2.17), (x_positions[index + 1] - 0.05, 2.17),
                    arrowstyle="-|>", mutation_scale=16, linewidth=1.2, color=COLORS["slate"],
                )
                ax.add_patch(arrow)
        ax.set_title("MusiCoMMA v0.2.0 data and evidence pipeline", loc="left", pad=12)
        ax.text(
            0.5, 0.68,
            "Pilot evidence is not vocabulary-wide coverage. Acceptance records entry-level relevance; image checking was not recorded.",
            fontsize=9, color=COLORS["slate"],
        )
        ax.text(
            0.5, 0.30,
            f"{int(unresolved_mask.sum())} contexts remain sense-unresolved; {int(auto_linked_mask.sum())} single-sense contexts are auto-linked.",
            fontsize=9, color=COLORS["slate"],
        )
        save_figure(
            fig,
            "fig01_pipeline",
            "MusiCoMMA v0.2.0 data and evidence pipeline",
            "The complete vocabulary foundation and bounded corpus pilot are separate layers; accepted relevance does not imply image verification or contextual sense resolution.",
            f"Five stages link the Musiconis source and vocabulary, 900 in-scope entries, a 50-entry pilot, and {len(attestations)} accepted contexts across {len(manuscripts)} digitizations. Image checking was not recorded.",
            "HAL methods overview; journal methods overview",
        )
        """
    ),
    markdown("## 5. Figure 2 — vocabulary composition by language"),
    code(
        """
        language_order = ["Old French", "Latin", "Old Occitan", "Middle French"]
        vocabulary_language = (
            entries.groupby("language_label", observed=True)
            .agg(entries=("entry_id", "nunique"), senses=("sense_count", "sum"))
            .reindex(language_order)
            .fillna(0)
            .astype(int)
            .reset_index()
        )
        vocabulary_language.to_csv(TABLE_DIR / "vocabulary_by_language.csv", index=False)

        fig, ax = plt.subplots(figsize=(10, 5.6))
        y = np.arange(len(vocabulary_language))
        height = 0.34
        ax.barh(y - height / 2, vocabulary_language["entries"], height, label="Entries", color=COLORS["blue"])
        ax.barh(y + height / 2, vocabulary_language["senses"], height, label="Senses", color=COLORS["orange"])
        ax.set_yticks(y, vocabulary_language["language_label"])
        ax.invert_yaxis()
        ax.set_xlabel("Count")
        ax.set_title("Vocabulary composition by language", loc="left")
        ax.legend(loc="lower right")
        ax.spines[["top", "right", "left"]].set_visible(False)
        for index, row in vocabulary_language.iterrows():
            ax.text(row["entries"] + 7, index - height / 2, f'{row["entries"]:,}', va="center", fontsize=9)
            ax.text(row["senses"] + 7, index + height / 2, f'{row["senses"]:,}', va="center", fontsize=9)
        ax.set_xlim(0, max(vocabulary_language["senses"].max(), vocabulary_language["entries"].max()) * 1.10)
        save_figure(
            fig,
            "fig02_vocabulary_language",
            "Vocabulary composition by language",
            "Complete vocabulary entries and senses by historical language. The gap between entries and senses is especially pronounced for Latin.",
            "Horizontal paired bars compare entries and senses. Old French has 560 entries and 583 senses; Latin 340 and 662; Old Occitan 297 and 302; Middle French one and one.",
            "HAL dataset profile; journal materials and methods",
        )
        display(vocabulary_language)
        """
    ),
    markdown("## 6. Figures 3 and 4 — pilot design by category and language"),
    code(
        """
        attestation_enriched = attestations.merge(
            selected[["entry_id", "lemma", "language_label", "category_label", "sense_count", "polysemous"]],
            on="entry_id", how="left", validate="many_to_one"
        )
        assert attestation_enriched["category_label"].ne("").all()

        publication_category_order = [
            "Performance act",
            "Instrument",
            "Performer or social role",
            "Sound category",
            "Musical or literary form",
            "Instrument part or implement",
            "Dance or movement",
            "Other or uncertain",
            "Performance context or function",
        ]
        category_counts = (
            attestation_enriched.groupby("category_label", observed=True)
            .size().rename("accepted_contexts")
            .reindex(publication_category_order)
            .reset_index()
        )
        category_counts.to_csv(TABLE_DIR / "accepted_contexts_by_category.csv", index=False)

        fig, ax = plt.subplots(figsize=(10, 6.2))
        bars = ax.barh(category_counts["category_label"], category_counts["accepted_contexts"], color=COLORS["blue"])
        ax.invert_yaxis()
        ax.set_xlabel("Accepted contexts")
        ax.set_title("Validated pilot attestations by analytical category", loc="left")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.bar_label(bars, padding=5, fontsize=9, weight="bold")
        ax.set_xlim(0, category_counts["accepted_contexts"].max() * 1.12)
        ax.text(
            0, -0.24,
            "Designed pilot counts with a ten-context-per-entry cap; not historical prevalence.",
            fontsize=9, color=COLORS["slate"], transform=ax.transAxes,
        )
        fig.subplots_adjust(bottom=0.22)
        save_figure(
            fig,
            "fig03_attestations_category",
            "Validated pilot attestations by analytical category",
            "Accepted pilot contexts by the category inherited from each selected entry. The distribution records pilot design, not historical prevalence.",
            "Horizontal bars show 68 performance-act contexts; 60 each for instruments, performers or social roles, sound categories, musical or literary forms, and instrument parts or implements; 55 for dance or movement; 52 other or uncertain; and 10 performance context or function.",
            "HAL results; journal category-distribution results",
        )
        display(category_counts.sort_values("accepted_contexts", ascending=False))
        """
    ),
    code(
        """
        category_order = publication_category_order
        language_category = pd.crosstab(
            attestation_enriched["language_label"],
            attestation_enriched["category_label"],
        ).reindex(index=["Latin", "Old French"], columns=category_order, fill_value=0)
        language_category.to_csv(TABLE_DIR / "accepted_contexts_by_language_category.csv")

        wrapped_labels = [
            label.replace("Performance act", "Perf. act")
                 .replace("Performer or social role", "Performer/social\\nrole")
                 .replace("Musical or literary form", "Musical/literary\\nform")
                 .replace("Instrument part or implement", "Instrument\\npart/implement")
                 .replace("Dance or movement", "Dance/movement")
                 .replace("Other or uncertain", "Other/uncertain")
                 .replace("Performance context or function", "Perf. context/\\nfunction")
            for label in language_category.columns
        ]
        fig, ax = plt.subplots(figsize=(12, 3.8))
        sns.heatmap(
            language_category,
            annot=True, fmt="d", cmap=sns.light_palette(COLORS["blue"], as_cmap=True),
            cbar=False, linewidths=1, linecolor="white", ax=ax,
            annot_kws={"weight": "bold", "fontsize": 9},
        )
        ax.set_xticklabels(wrapped_labels, rotation=0, fontsize=8)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("Language by category in the validated pilot", loc="left", pad=16)
        save_figure(
            fig,
            "fig04_language_category_heatmap",
            "Language by category in the validated pilot",
            "Accepted-context counts by language and analytical category. Regular 30-count cells are effects of stratification and capping.",
            "A two-row heatmap compares Latin and Old French. Many cells contain 30 accepted contexts because three selected entries reached the ten-context cap. Latin performance acts contain 40 contexts and Old French performance acts 28. Performance context or function contains ten Old French contexts and no Latin contexts in the pilot.",
            "HAL pilot-design analysis; journal category-distribution results",
        )
        display(language_category)
        """
    ),
    markdown("## 7. Figure 5 — contextual sense assignment status"),
    code(
        """
        sense_labels = {
            "entry_validated_sense_unresolved": "Polysemous; unresolved",
            "single_source_sense_auto_linked_after_entry_validation": "Single sense; auto-linked",
        }
        sense_status = (
            attestations["sense_assignment_status"].map(sense_labels)
            .value_counts().rename_axis("sense_status").rename("contexts")
            .reindex(["Polysemous; unresolved", "Single sense; auto-linked"])
            .reset_index()
        )
        sense_status["share"] = sense_status["contexts"] / sense_status["contexts"].sum()
        sense_status.to_csv(TABLE_DIR / "contextual_sense_status.csv", index=False)

        fig, ax = plt.subplots(figsize=(9.5, 3.8))
        bars = ax.barh(sense_status["sense_status"], sense_status["contexts"], color=COLORS["purple"])
        ax.invert_yaxis()
        ax.set_xlabel("Accepted contexts")
        ax.set_title("Contextual sense assignment status", loc="left")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.bar_label(
            bars,
            labels=[f'{row.contexts:,} ({row.share:.1%})' for row in sense_status.itertuples()],
            padding=6, fontsize=9, weight="bold",
        )
        ax.set_xlim(0, sense_status["contexts"].max() * 1.18)
        save_figure(
            fig,
            "fig05_sense_resolution",
            "Contextual sense assignment status",
            "Most accepted contexts belong to polysemous entries and deliberately remain contextually sense-unresolved.",
            f"Two bars show {int(unresolved_mask.sum())} unresolved contexts ({unresolved_mask.mean():.1%}) and {int(auto_linked_mask.sum())} automatic single-source-sense links ({auto_linked_mask.mean():.1%}).",
            "HAL validation results; journal central polysemy argument",
        )
        display(sense_status.style.format({"share": "{:.2%}"}))
        """
    ),
    markdown("## 8. Figure 6 — supplied manuscript-date midpoints"),
    code(
        """
        dated = attestations.dropna(subset=["not_before", "not_after"]).copy()
        dated["date_midpoint"] = (dated["not_before"] + dated["not_after"]) / 2
        date_bins = [-np.inf, 999, 1199, 1399, 1600, np.inf]
        date_labels = ["800–999", "1000–1199", "1200–1399", "1400–1600", "After 1600"]
        dated["date_band"] = pd.cut(dated["date_midpoint"], bins=date_bins, labels=date_labels)
        date_counts = (
            dated["date_band"].value_counts(sort=False)
            .rename_axis("date_midpoint_band").rename("contexts").reset_index()
        )
        date_counts.to_csv(TABLE_DIR / "date_midpoint_bands.csv", index=False)

        fig, ax = plt.subplots(figsize=(9.5, 4.8))
        bars = ax.bar(date_counts["date_midpoint_band"].astype(str), date_counts["contexts"], color=COLORS["green"])
        ax.set_ylabel("Accepted contexts")
        ax.set_xlabel("Midpoint of supplied manuscript date range")
        ax.set_title("Accepted contexts by supplied date midpoint", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.bar_label(bars, padding=4, fontsize=9, weight="bold")
        ax.text(
            0.0, -0.30,
            "Descriptive metadata only: no denominator for corpus exposure, searchable pages, or tokens by period.",
            transform=ax.transAxes, fontsize=9, color=COLORS["slate"],
        )
        save_figure(
            fig,
            "fig06_date_midpoints",
            "Accepted contexts by supplied date midpoint",
            "Context counts by midpoint of supplied manuscript date ranges. The plot is descriptive and is not normalized by CoMMA corpus exposure.",
            "Bars show 40 contexts dated by midpoint to 800–999, 42 to 1000–1199, 200 to 1200–1399, 199 to 1400–1600, and four after 1600. The chart warns that no corpus-exposure denominator is used.",
            "HAL descriptive chronology; journal limitations and metadata discussion",
        )
        display(date_counts)
        print(f"Rows whose supplied upper date bound exceeds 1600: {(attestations['not_after'] > 1600).sum()}")
        """
    ),
    markdown("## 9. Additional exploratory figures for author review"),
    code(
        """
        entry_distribution = (
            entry_groups.groupby("attestation_count", observed=True)
            .size().rename("entries").reset_index().sort_values("attestation_count")
        )
        entry_distribution.to_csv(TABLE_DIR / "entries_by_context_count.csv", index=False)

        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        bars = ax.bar(entry_distribution["attestation_count"].astype(int).astype(str), entry_distribution["entries"], color=COLORS["blue"])
        ax.set_xlabel("Accepted contexts per selected entry")
        ax.set_ylabel("Selected entries")
        ax.set_title("Retention-cap profile across the 50 selected entries", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.bar_label(bars, padding=3, fontsize=9)
        save_figure(
            fig,
            "fig07_entry_context_distribution",
            "Retention-cap profile across selected entries",
            "Distribution of accepted-context counts per selected entry. Concentration at ten reflects the pilot retention cap.",
            "A bar chart shows how many of the 50 selected entries have each accepted-context count from two to ten. Most entries reach ten, demonstrating the influence of the retention cap rather than lexical prevalence.",
            "Author review and methods appendix; do not interpret as lexical frequency",
        )
        display(entry_distribution)
        print(f"Mean contexts per entry: {entry_groups['attestation_count'].mean():.2f}")
        print(f"Median contexts per entry: {entry_groups['attestation_count'].median():.0f}")
        print(f"Range: {entry_groups['attestation_count'].min():.0f}–{entry_groups['attestation_count'].max():.0f}")
        """
    ),
    code(
        """
        repository_summary = (
            manuscripts.assign(repository=manuscripts["repository"].replace("", "Not supplied"))
            .groupby("repository", observed=True)
            .agg(
                distinct_manuscripts=("manuscript_id", "nunique"),
                accepted_contexts=("attestation_count", "sum"),
            )
            .sort_values(["distinct_manuscripts", "accepted_contexts"], ascending=False)
            .reset_index()
        )
        repository_summary.to_csv(TABLE_DIR / "repositories.csv", index=False)
        repository_top = repository_summary.head(12).sort_values("distinct_manuscripts")

        fig, ax = plt.subplots(figsize=(10, 6.5))
        bars = ax.barh(repository_top["repository"], repository_top["distinct_manuscripts"], color=COLORS["orange"])
        ax.set_xlabel("Distinct manuscript digitizations in the pilot")
        ax.set_title("Leading repositories in the validated pilot", loc="left")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.bar_label(bars, padding=4, fontsize=9)
        ax.set_xlim(0, repository_top["distinct_manuscripts"].max() * 1.12)
        save_figure(
            fig,
            "fig08_top_repositories",
            "Leading repositories in the validated pilot",
            "Repositories ranked by distinct manuscript digitizations represented among retained contexts. This is a pilot-composition measure, not repository or corpus coverage.",
            "A horizontal bar chart ranks the twelve repositories contributing the most distinct manuscript digitizations to the validated pilot. The caption warns that the ranking reflects the retained pilot rather than repository holdings or normalized CoMMA coverage.",
            "HAL descriptive appendix; corpus-bias discussion",
        )
        display(repository_summary.head(15))
        """
    ),
    code(
        """
        manuscript_convergence = (
            manuscripts.groupby("entry_count", observed=True)
            .size().rename("manuscripts").reset_index().sort_values("entry_count")
        )
        manuscript_convergence.to_csv(TABLE_DIR / "manuscripts_by_selected_entry_count.csv", index=False)

        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        bars = ax.bar(
            manuscript_convergence["entry_count"].astype(int).astype(str),
            manuscript_convergence["manuscripts"],
            color=COLORS["purple"],
        )
        ax.set_xlabel("Distinct selected entries represented in a manuscript")
        ax.set_ylabel("Manuscripts")
        ax.set_title("Convergence of selected vocabulary within manuscripts", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        ax.bar_label(bars, padding=4, fontsize=9)
        save_figure(
            fig,
            "fig09_manuscript_convergence",
            "Convergence of selected vocabulary within manuscripts",
            "Distribution of distinct selected Musiconis entries represented per globally deduplicated manuscript in the pilot.",
            f"A bar chart counts digitizations by distinct selected entries, separately from {len(manuscript_groups)} entry-manuscript browsing groups.",
            "Journal discussion of grouping and dossier building; exploratory appendix",
        )
        display(manuscript_convergence)
        """
    ),
    markdown(
        """
        ## 10. Entry-level inspection helper

        Use `entry_profile()` to inspect a selected lemma without changing the dataset. The function returns lexical metadata, source senses, grouped manuscript evidence, and compact HTR context snippets. A returned string is research evidence, not a diplomatic transcription.
        """
    ),
    code(
        """
        def entry_profile(lemma, language_code=None, context_limit=10):
            matches = entries[entries["normalized_lemma"].str.casefold() == str(lemma).casefold()].copy()
            if language_code:
                matches = matches[matches["language_code"] == language_code]
            if matches.empty:
                raise KeyError(f"No vocabulary entry found for {lemma!r}")

            entry_ids = matches["entry_id"].tolist()
            entry_senses = senses[senses["entry_id"].isin(entry_ids)][
                ["sense_id", "entry_id", "definition_fr", "language_stage", "part_of_speech", "concept_id", "uncertainty_flag"]
            ]
            evidence = attestation_enriched[attestation_enriched["entry_id"].isin(entry_ids)].copy()
            evidence = evidence[
                ["attestation_id", "lemma", "language_label", "category_label", "source_string", "left_context", "right_context", "repository", "shelfmark", "not_before", "not_after", "iiif_url", "sense_assignment_status", "image_checked"]
            ].head(context_limit)

            display(Markdown(f"### Entry profile: `{lemma}`"))
            display(matches[["entry_id", "lemma", "language_label", "sense_count", "primary_category_id", "coverage_status", "polysemous"]])
            display(Markdown("**Source senses**"))
            display(entry_senses)
            display(Markdown(f"**Accepted evidence (first {min(context_limit, len(evidence))} rows)**"))
            display(evidence)
            return {"entries": matches, "senses": entry_senses, "evidence": evidence}

        _example = entry_profile("cymbalum", language_code="la", context_limit=5)
        """
    ),
    markdown("## 11. Export publication tables and figure manifest"),
    code(
        """
        entry_summary = entry_groups.merge(
            selected[["entry_id", "category_label", "polysemous", "selection_reason"]],
            on=["entry_id", "category_label"], how="left", validate="one_to_one"
        ).sort_values("entry_group_sequence")
        entry_summary.to_csv(TABLE_DIR / "selected_entry_summary.csv", index=False)

        manuscript_summary = manuscripts.sort_values(
            ["entry_count", "attestation_count", "repository", "shelfmark"],
            ascending=[False, False, True, True],
        )
        manuscript_summary.to_csv(TABLE_DIR / "manuscript_summary.csv", index=False)

        manifest = pd.DataFrame(figure_manifest)
        manifest.to_csv(OUTPUT_DIR / "figure_manifest.csv", index=False)
        (OUTPUT_DIR / "figure_captions_and_alt_text.md").write_text(
            "# MusiCoMMA v0.2.0 notebook figures\\n\\n" +
            "\\n\\n".join(
                f"## {row['title']}\\n\\n**Caption:** {row['caption']}\\n\\n**Alternative text:** {row['alt_text']}\\n\\n**Recommended use:** {row['recommended_use']}"
                for row in figure_manifest
            ) + "\\n",
            encoding="utf-8",
        )

        output_inventory = pd.DataFrame([
            {"path": str(path.relative_to(OUTPUT_DIR)), "bytes": path.stat().st_size}
            for path in sorted(OUTPUT_DIR.rglob("*")) if path.is_file()
        ])
        output_inventory.to_csv(OUTPUT_DIR / "output_inventory.csv", index=False)

        display(manifest[["file_stem", "title", "recommended_use"]])
        print(f"Exported {len(manifest)} figures in PNG, SVG, and PDF.")
        print(f"Exported {len(list(TABLE_DIR.glob('*.csv')))} derived CSV tables.")
        print(f"Output directory: {OUTPUT_DIR}")
        """
    ),
    markdown(
        """
        ## 12. Reporting guide

        **Supported descriptive claims**

        - Counts and composition of the reconstructed vocabulary foundation.
        - Counts of selected entries, accepted contexts, manuscript witnesses, and evidence groups.
        - Language/category composition of the designed pilot.
        - The explicit split between 330 contextually sense-unresolved and 155 single-sense auto-linked contexts.
        - Descriptive date and repository composition when accompanied by sampling and exposure caveats.

        **Claims not supported by v0.2.0**

        - Historical prevalence, diachronic lexical change, or repository representativeness.
        - Model precision, recall, F-score, calibration, or comparison with learned retrieval.
        - Vocabulary-wide CoMMA coverage: 850 in-scope entries have not yet been searched in this release.
        - Image-verified transcription or contextual sense labels for polysemous entries.
        - Inter-annotator agreement: validation was recorded as one batch reviewer event.

        These boundaries should remain visible in figure captions, methods, data availability statements, and repository metadata.
        """
    ),
    markdown(
        """
        ## 13. JCA addendum diagnostics

        This block runs the JCA addendum script and displays the review-driven tables used in the data essay: coverage states, censored inverse-probability lower bounds, category lower-bound hit distributions, manuscript-cluster bootstrap rates, full co-occurrence matrices, and formulaic-context marker data for *cymbalum*, *psallo*, and *cantus*.
        """
    ),
    code(
        """
        import subprocess
        import sys

        jca_script = PROJECT_ROOT / "scripts" / "run_jca_v0_3_analysis.py"
        run_env = os.environ.copy()
        run_env["MUSICOMMA_RELEASE_VERSION"] = RELEASE_VERSION
        run_env["MUSICOMMA_DATA_ROOT"] = str(RELEASE_DIR)
        run_env["MUSICOMMA_OUTPUT_DIR"] = str(OUTPUT_DIR)
        run_env.setdefault("MPLBACKEND", "Agg")
        result = subprocess.run(
            [sys.executable, str(jca_script)],
            cwd=PROJECT_ROOT,
            env=run_env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        print(result.stdout)

        JCA_DIR = OUTPUT_DIR / "jca_v0.3.0"
        JCA_TABLE_DIR = JCA_DIR / "tables"
        jca_tables = {
            path.stem: pd.read_csv(path)
            for path in sorted(JCA_TABLE_DIR.glob("*.csv"))
        }
        display(Markdown((JCA_DIR / "JCA_v0.3.0_analysis_summary.md").read_text(encoding="utf-8")))
        """
    ),
    markdown("## 14. Review-critical addendum tables"),
    code(
        """
        display(Markdown("### Coverage states"))
        display(jca_tables["coverage_state_summary"])
        display(jca_tables["coverage_state_by_language"])

        display(Markdown("### Censored cap diagnostics"))
        display(jca_tables["pre_review_hit_spread_by_entry"].head(12))
        display(jca_tables["pre_review_hit_lower_bounds_by_category"])

        display(Markdown("### Exposure-normalized rates with manuscript-cluster bootstrap"))
        display(jca_tables["pilot_rates_reportable_cells_for_manuscript"])

        display(Markdown("### Co-occurrence design diagnostic"))
        display(jca_tables["cooccurrence_design_diagnostic"])
        display(jca_tables["category_cooccurrence_matrix_with_diagonal_wide"])
        display(jca_tables["same_category_entry_pairs_within_digitization"])

        display(Markdown("### Formulaic-context diagnostic"))
        display(jca_tables["formulaic_marker_method"])
        display(jca_tables["formulaic_context_summary"])
        display(
            jca_tables["formulaic_context_marker_plot_data"]
            .query("lemma == 'cymbalum'")
            [[
                "attestation_id", "corinthians13_core_marker_count",
                "probable_1_cor_13_citation_fingerprint",
                "matched_core_corinthians13_markers",
            ]]
        )
        """
    ),
]

if RELEASE_VERSION == "0.2.1":
    cells[0] = markdown("""
    # MusiCoMMA v0.2.1: context-reviewed dataset and publication analysis

    The lexical foundation remains unchanged: 1,198 entries and 1,548 source-sense
    records. The original pilot retrieved 485 contexts for 50 entries. Xavier
    Fresquet's targeted re-review retained three chantre contexts and excluded
    seven, leaving 478 accepted contexts. The seven exclusions and all prior
    assertions remain in separate tables. This is same-author contextual
    selection, not independent transcription validation or a random accuracy audit.

    No image checking or corrected reading was supplied. Inclusion does not
    imply an observed singing event or a newly adjudicated lexical sense.
    The notebook reads the v0.2.1 release and writes derived outputs separately.
    """)
    for cell in cells:
        # Versioned paths and headings are mechanical substitutions, never data labels.
        cell.source = cell.source.replace("0.2.0", RELEASE_VERSION)
        cell.source = cell.source.replace("330 contextually sense-unresolved and 155 single-sense auto-linked", "330 contextually sense-unresolved and 148 single-sense auto-linked")
        cell.source = cell.source.replace("Inter-annotator agreement: validation was recorded as one batch reviewer event.", "Inter-annotator agreement: both the batch decision and targeted re-review were supplied by the same author.")
    cells.extend([
        markdown("""## 15. Targeted chantre selection review

        This table reproduces the ten explicit include/exclude decisions. Seven
        exclusions are selection decisions, not confirmed HTR corrections.
        Do not calculate an accuracy rate from this deliberately targeted review.
        The original assertions remain available in the history tables.
        """),
        code("""
        decisions = pd.read_csv(DATA_DIR / "context_review_decisions.csv", dtype=str, keep_default_na=False)
        excluded = pd.read_csv(DATA_DIR / "excluded_contexts.csv", dtype=str, keep_default_na=False)
        assert len(decisions) == 10 and len(excluded) == 7
        assert decisions.loc[decisions.decision.eq("accept"), "number"].tolist() == ["7", "8", "10"]
        assert set(excluded.attestation_id).isdisjoint(attestations.attestation_id)
        assert len(annotations) == 485 + 10
        assert decisions.image_checked.eq("not_recorded").all()
        decisions.to_csv(TABLE_DIR / "chantre_context_review.csv", index=False)
        display(decisions[["number", "shelfmark", "decision", "rationale", "image_checked"]])
        print("478 accepted + 7 excluded = 485 original contexts; 485 prior + 10 new assertions = 495 annotation assertions.")
        """),
    ])

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3",
            "mimetype": "text/x-python",
            "codemirror_mode": {"name": "ipython", "version": 3},
            "pygments_lexer": "ipython3",
            "nbconvert_exporter": "python",
            "file_extension": ".py",
        },
        "title": f"MusiCoMMA v{RELEASE_VERSION} dataset analysis and publication figures",
    },
)

NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, NOTEBOOK_PATH)
print(NOTEBOOK_PATH)
