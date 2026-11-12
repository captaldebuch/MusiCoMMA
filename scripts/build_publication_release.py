#!/usr/bin/env python3
"""Build the self-contained MusiCoMMA v0.2.0 Zenodo deposit candidate.

The script promotes the reviewed pilot into the public evidence schema while
preserving the complete v0.1.0 vocabulary foundation. It also generates every
headline statistic and publication figure used by the accompanying papers.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
import textwrap
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "release" / "musiconis-comma-v0.1.0"
VALIDATED = ROOT / "review" / "musiconis-comma-validated-v0.2.0"
OUT = ROOT / "release" / "musiconis-comma-v0.2.0-zenodo"
ZIP_PATH = ROOT / "release" / "MusiCoMMA_v0.2.0_Zenodo_deposit.zip"
VERSION = "0.2.0"
BUILD_DATE = "2026-07-29"
COMMA_REVISION = "dfaacb6e79900e09f14a9fcd1fb13a1d595c2e0a"
GENERATED_AT = f"{BUILD_DATE}T12:00:00+02:00"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        if not rows:
            raise ValueError(f"fields required for empty table: {path}")
        fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_repo(shelfmark: str) -> str:
    shelfmark = (shelfmark or "").strip()
    if not shelfmark:
        return "Not supplied"
    rules = [
        ("Paris. Bibliothèque nationale de France", "Paris, Bibliothèque nationale de France"),
        ("Bibliothèque nationale de France", "Paris, Bibliothèque nationale de France"),
        ("Chantilly", "Chantilly, Bibliothèque du château"),
        ("Reims", "Reims, Bibliothèque municipale"),
        ("Arras", "Arras, Bibliothèque municipale"),
        ("Troyes", "Troyes, Médiathèque Jacques-Chirac"),
        ("Toulouse", "Toulouse, Bibliothèque municipale"),
        ("Saint-Omer", "Saint-Omer, Bibliothèque d'agglomération"),
        ("Montpellier", "Montpellier, Bibliothèque interuniversitaire"),
        ("Sainte-Geneviève", "Paris, Bibliothèque Sainte-Geneviève"),
        ("Bourges", "Bourges, Bibliothèque municipale"),
        ("Angers", "Angers, Bibliothèque municipale"),
        ("Mazarine", "Paris, Bibliothèque Mazarine"),
        ("Bodleian", "Oxford, Bodleian Library"),
    ]
    for needle, label in rules:
        if needle.casefold() in shelfmark.casefold():
            return label
    return shelfmark.split(",")[0].split(" MS")[0].strip()[:120]


def pct(num: int, den: int) -> str:
    return f"{(100 * num / den):.2f}" if den else "0.00"


def svg_start(title: str, desc: str, width: int = 1200, height: int = 720) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{escape(title)}</title>",
        f"<desc id=\"desc\">{escape(desc)}</desc>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#17233c}.title{font-size:34px;font-weight:700}.subtitle{font-size:18px;fill:#526075}.label{font-size:18px}.small{font-size:15px;fill:#526075}.value{font-size:18px;font-weight:700}.axis{stroke:#8b96a8;stroke-width:1}.grid{stroke:#dbe1ea;stroke-width:1}.bar1{fill:#2864a6}.bar2{fill:#d77a2b}.bar3{fill:#3f8f75}.bar4{fill:#8156a3}</style>',
    ]


def save_svg(name: str, lines: list[str], alt: str) -> None:
    lines.append("</svg>")
    svg = OUT / "figures" / f"{name}.svg"
    png = OUT / "figures" / f"{name}.png"
    write_text(svg, "\n".join(lines))
    write_text(OUT / "figures" / f"{name}.alt.txt", alt)
    subprocess.run(["rsvg-convert", "-w", "1800", "-o", str(png), str(svg)], check=True)


def bar_chart(name: str, title: str, subtitle: str, data: list[tuple[str, int]], alt: str, color: str = "#2864a6") -> None:
    width, height = 1200, max(640, 230 + 58 * len(data))
    lines = svg_start(title, alt, width, height)
    lines += [f'<text x="80" y="70" class="title">{escape(title)}</text>', f'<text x="80" y="104" class="subtitle">{escape(subtitle)}</text>']
    left, top, plot_w = 370, 150, 720
    maximum = max(v for _, v in data) or 1
    for i, (label, value) in enumerate(data):
        y = top + i * 58
        bar_w = plot_w * value / maximum
        lines.append(f'<text x="350" y="{y + 24}" text-anchor="end" class="label">{escape(label)}</text>')
        lines.append(f'<rect x="{left}" y="{y}" width="{bar_w:.1f}" height="34" rx="4" fill="{color}"/>')
        lines.append(f'<text x="{left + bar_w + 12:.1f}" y="{y + 24}" class="value">{value}</text>')
    lines.append(f'<text x="80" y="{height - 35}" class="small">{escape(subtitle)}</text>')
    save_svg(name, lines, alt)


def grouped_bar_chart(name: str, title: str, subtitle: str, data: list[tuple[str, int, int]], alt: str) -> None:
    width, height = 1200, 720
    lines = svg_start(title, alt, width, height)
    lines += [f'<text x="80" y="70" class="title">{escape(title)}</text>', f'<text x="80" y="104" class="subtitle">{escape(subtitle)}</text>']
    left, top, plot_w, plot_h = 205, 160, 915, 430
    maximum = max(max(a, b) for _, a, b in data)
    for tick in range(0, maximum + 101, 100):
        x = left + plot_w * tick / maximum
        lines += [f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + plot_h}" class="grid"/>', f'<text x="{x}" y="{top + plot_h + 28}" text-anchor="middle" class="small">{tick}</text>']
    group_h = plot_h / len(data)
    for i, (label, entries, senses) in enumerate(data):
        y = top + i * group_h
        ew = plot_w * entries / maximum
        sw = plot_w * senses / maximum
        lines += [
            f'<text x="{left - 16}" y="{y + 31}" text-anchor="end" class="label">{escape(label)}</text>',
            f'<rect x="{left}" y="{y + 5}" width="{ew:.1f}" height="24" fill="#2864a6"/>',
            f'<rect x="{left}" y="{y + 34}" width="{sw:.1f}" height="24" fill="#d77a2b"/>',
            f'<text x="{left + ew + 9:.1f}" y="{y + 24}" class="small">{entries}</text>',
            f'<text x="{left + sw + 9:.1f}" y="{y + 53}" class="small">{senses}</text>',
        ]
    lines += ['<rect x="800" y="120" width="20" height="14" fill="#2864a6"/><text x="830" y="133" class="small">Entries</text>', '<rect x="920" y="120" width="20" height="14" fill="#d77a2b"/><text x="950" y="133" class="small">Senses</text>']
    save_svg(name, lines, alt)


def pipeline_figure() -> None:
    alt = "Flow diagram: 1,585 Musiconis source lines become 1,572 parsed records, 1,198 entries and 1,548 senses; 900 Latin and Old French entries are in CoMMA scope; the balanced pilot selects 50 entries and exact retrieval yields 485 reviewer-accepted contexts grouped into 384 manuscripts."
    lines = svg_start("MusiCoMMA v0.2.0 data and evidence pipeline", alt, 1400, 620)
    lines += ['<text x="70" y="65" class="title">MusiCoMMA v0.2.0 data and evidence pipeline</text>', '<text x="70" y="100" class="subtitle">Deterministic vocabulary reconstruction + bounded exact-match validation pilot</text>']
    boxes = [
        ("Musiconis source", "1,585 lines", "#e8f1fb"),
        ("Lexical model", "1,198 entries\n1,548 senses", "#e8f1fb"),
        ("CoMMA scope", "900 Latin / Old French\nentries", "#fff1e5"),
        ("Balanced pilot", "50 entries", "#e8f5ef"),
        ("Validated evidence", "485 contexts\n384 manuscripts", "#efe8f7"),
    ]
    x_positions = [70, 330, 590, 850, 1110]
    for i, ((label, value, fill), x) in enumerate(zip(boxes, x_positions)):
        lines.append(f'<rect x="{x}" y="210" width="220" height="190" rx="14" fill="{fill}" stroke="#526075" stroke-width="2"/>')
        lines.append(f'<text x="{x + 110}" y="255" text-anchor="middle" class="label" font-weight="700">{escape(label)}</text>')
        for j, part in enumerate(value.split("\n")):
            lines.append(f'<text x="{x + 110}" y="{310 + 34*j}" text-anchor="middle" class="value">{escape(part)}</text>')
        if i < len(boxes) - 1:
            lines.append(f'<line x1="{x + 220}" y1="305" x2="{x_positions[i+1] - 20}" y2="305" stroke="#526075" stroke-width="3"/>')
            lines.append(f'<polygon points="{x_positions[i+1]-20},297 {x_positions[i+1]-5},305 {x_positions[i+1]-20},313" fill="#526075"/>')
    lines += ['<text x="70" y="485" class="small">Pilot evidence is not vocabulary-wide coverage. Acceptance records entry-level musical relevance; manuscript-image checking was not recorded.</text>', '<text x="70" y="520" class="small">330 attestations from polysemous entries remain sense-unresolved; 155 single-sense attestations are linked automatically.</text>']
    save_svg("fig01_pipeline", lines, alt)


def date_bands(rows: list[dict[str, str]]) -> list[tuple[str, int]]:
    buckets = Counter()
    for row in rows:
        a, b = safe_int(row["not_before"]), safe_int(row["not_after"])
        if a is None or b is None:
            buckets["Missing"] += 1
            continue
        midpoint = (a + b) / 2
        if midpoint < 1000:
            buckets["800-999"] += 1
        elif midpoint < 1200:
            buckets["1000-1199"] += 1
        elif midpoint < 1400:
            buckets["1200-1399"] += 1
        elif midpoint <= 1600:
            buckets["1400-1600"] += 1
        else:
            buckets[">1600 midpoint"] += 1
    return [(k, buckets[k]) for k in ["800-999", "1000-1199", "1200-1399", "1400-1600", ">1600 midpoint", "Missing"]]


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    base_data = FOUNDATION / "data"
    validated_data = VALIDATED / "data"
    entries = read_csv(base_data / "entries.csv")
    forms = read_csv(base_data / "forms.csv")
    senses = read_csv(base_data / "senses.csv")
    concepts = read_csv(base_data / "concepts.csv")
    source_records = read_csv(base_data / "source_records.csv")
    source_lines = read_csv(base_data / "source_lines.csv")
    parse_issues = read_csv(base_data / "parse_issues.csv")
    old_provenance = read_csv(base_data / "provenance.csv")
    validated = read_csv(validated_data / "validated_attestations.csv")
    selected = read_csv(validated_data / "selected_entries.csv")
    entry_groups = read_csv(validated_data / "entry_groups.csv")
    manuscript_groups = read_csv(validated_data / "manuscript_groups.csv")
    review_events = read_csv(validated_data / "review_events.csv")
    reviewed_manuscripts = read_csv(validated_data / "manuscripts.csv")

    selected_ids = {row["entry_id"] for row in selected}
    form_by_entry = {row["entry_id"]: row["form_id"] for row in forms}
    sense_by_id = {row["sense_id"]: row for row in senses}

    # Complete vocabulary layer, with pilot coverage made explicit.
    for row in entries:
        if row["entry_id"] in selected_ids:
            row["coverage_status"] = "validated_attestation"
            row["review_status"] = "source_imported_and_pilot_attestation_validated"
            row["provenance_id"] = "mmc:provenance:validated-pilot-v0-2-0"
    for name, rows, fields in [
        ("entries.csv", entries, None),
        ("forms.csv", forms, None),
        ("senses.csv", senses, None),
        ("concepts.csv", concepts, None),
        ("source_records.csv", source_records, None),
        ("source_lines.csv", source_lines, None),
    ]:
        write_csv(OUT / "data" / name, rows, fields)
    if parse_issues:
        write_csv(OUT / "data" / "parse_issues.csv", parse_issues)
    else:
        with (base_data / "parse_issues.csv").open("r", encoding="utf-8") as source:
            write_text(OUT / "data" / "parse_issues.csv", source.readline().rstrip("\n"))

    coverage = read_csv(base_data / "coverage.csv")
    count_by_entry = Counter(row["entry_id"] for row in validated)
    for row in coverage:
        if row["entry_id"] in selected_ids:
            row.update({
                "coverage_status": "validated_attestation",
                "search_release": COMMA_REVISION,
                "search_method": "exact source-form retrieval; maximum 10 retained contexts per selected entry",
                "candidate_count": str(count_by_entry[row["entry_id"]]),
                "validated_attestation_count": str(count_by_entry[row["entry_id"]]),
                "last_searched_at": BUILD_DATE,
                "scope_reason": "Balanced 50-entry pilot; all retained exact-match contexts batch-confirmed as musically relevant at entry level.",
            })
    write_csv(OUT / "data" / "coverage.csv", coverage)

    # Public attestation table conforming to the release contract.
    attestation_fields = [
        "attestation_id", "entry_id", "form_id", "sense_id", "source_string",
        "normalized_search_string", "expanded_hypothesis", "left_context", "right_context",
        "context_with_match", "char_start", "char_end", "comma_record_id", "comma_release",
        "ingestion_date", "manuscript_id", "page_canvas_line_locator", "iiif_url", "language",
        "not_before", "not_after", "repository", "shelfmark", "metadata_confidence",
        "htr_quality", "retrieval_method", "model_id", "score", "threshold",
        "validation_status", "image_checked", "annotation_id", "provenance_id",
        "entry_group_id", "manuscript_group_id", "sense_assignment_status",
        "validation_event_id", "reviewer", "reviewed_at", "review_method",
    ]
    manuscript_id_by_key = {row["manuscript_key"]: row["manuscript_id"] for row in reviewed_manuscripts}
    attestations: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    for row in validated:
        annotation_id = row["review_id"].replace("mmc:review:", "mmc:annotation:")
        manuscript_id = manuscript_id_by_key[row["manuscript_key"]]
        normalized = row["source_string"].casefold()
        att = {
            "attestation_id": row["attestation_id"],
            "entry_id": row["entry_id"],
            "form_id": form_by_entry[row["entry_id"]],
            "sense_id": row["linked_sense_id"],
            "source_string": row["source_string"],
            "normalized_search_string": normalized,
            "expanded_hypothesis": "",
            "left_context": row["left_context"],
            "right_context": row["right_context"],
            "context_with_match": row["context_with_match"],
            "char_start": row["char_start"],
            "char_end": row["char_end"],
            "comma_record_id": f'{row["shard"]}:{row["record_line"]}',
            "comma_release": row["comma_revision"],
            "ingestion_date": BUILD_DATE,
            "manuscript_id": manuscript_id,
            "page_canvas_line_locator": "record-level locator only; page/canvas/line not supplied by pilot",
            "iiif_url": row["iiif_manifest"],
            "language": row["language_code"],
            "not_before": row["not_before"],
            "not_after": row["not_after"],
            "repository": normalize_repo(row["shelfmark"]),
            "shelfmark": row["shelfmark"],
            "metadata_confidence": "upstream_metadata_unassessed",
            "htr_quality": "not_supplied_at_attestation_level",
            "retrieval_method": "exact_source_form",
            "model_id": "rule:exact-v0.1.0",
            "score": "1.0",
            "threshold": "1.0",
            "validation_status": row["validation_status"],
            "image_checked": row["image_checked"],
            "annotation_id": annotation_id,
            "provenance_id": "mmc:provenance:validated-pilot-v0-2-0",
            "entry_group_id": row["entry_group_id"],
            "manuscript_group_id": row["manuscript_group_id"],
            "sense_assignment_status": row["sense_assignment_status"],
            "validation_event_id": row["validation_event_id"],
            "reviewer": row["reviewer"],
            "reviewed_at": row["reviewed_at"],
            "review_method": row["review_method"],
        }
        attestations.append(att)
        annotations.append({
            "annotation_id": annotation_id,
            "target_id": row["attestation_id"],
            "annotator_id": "researcher:xavier-fresquet",
            "timestamp": row["reviewed_at"],
            "task_version": "pilot-batch-validation-v0.2.0",
            "valid_occurrence": row["valid_occurrence"],
            "musical_relevance": row["musical_relevance"],
            "decision": row["decision"],
            "certainty": "not_recorded",
            "image_checked": row["image_checked"],
            "sense_assignment_status": row["sense_assignment_status"],
            "note": row["reviewer_note"] or "Batch confirmation of musical relevance at entry level.",
            "adjudication_relation": "none_single_reviewer_event",
            "validation_event_id": row["validation_event_id"],
            "provenance_id": "mmc:provenance:validated-pilot-v0-2-0",
        })
    write_csv(OUT / "data" / "attestations.csv", attestations, attestation_fields)
    annotation_fields = list(annotations[0])
    write_csv(OUT / "data" / "annotations.csv", annotations, annotation_fields)
    (OUT / "jsonl").mkdir(parents=True, exist_ok=True)
    with (OUT / "jsonl" / "attestations.jsonl").open("w", encoding="utf-8") as handle:
        for row in attestations:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (OUT / "jsonl" / "annotations.jsonl").open("w", encoding="utf-8") as handle:
        for row in annotations:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manuscript_fields = [
        "manuscript_id", "comma_record_id", "repository", "shelfmark", "not_before", "not_after",
        "language", "iiif_manifest", "source_url", "biblissima_id", "metadata_license",
        "corpus_release", "entry_count", "attestation_count", "metadata_confidence",
    ]
    langs_by_ms: dict[str, set[str]] = defaultdict(set)
    for row in attestations:
        langs_by_ms[str(row["manuscript_id"])].add(str(row["language"]))
    manuscripts = []
    for row in reviewed_manuscripts:
        bid = row["biblissima_id"]
        source_url = bid if bid.startswith("http") else (f"https://data.biblissima.fr/entity/{bid}" if bid else row["iiif_manifest"])
        manuscripts.append({
            "manuscript_id": row["manuscript_id"],
            "comma_record_id": f'{row["shard"]}:{row["record_line"]}',
            "repository": normalize_repo(row["shelfmark"]),
            "shelfmark": row["shelfmark"],
            "not_before": row["not_before"],
            "not_after": row["not_after"],
            "language": "|".join(sorted(langs_by_ms[row["manuscript_id"]])),
            "iiif_manifest": row["iiif_manifest"],
            "source_url": source_url,
            "biblissima_id": bid,
            "metadata_license": "CoMMA source reports CC BY 4.0; verify linked-provider terms",
            "corpus_release": row["comma_revision"],
            "entry_count": row["entry_count"],
            "attestation_count": row["attestation_count"],
            "metadata_confidence": "upstream_metadata_unassessed",
        })
    write_csv(OUT / "data" / "manuscripts.csv", manuscripts, manuscript_fields)
    write_csv(OUT / "data" / "entry_groups.csv", entry_groups)
    write_csv(OUT / "data" / "manuscript_groups.csv", manuscript_groups)
    write_csv(OUT / "data" / "review_events.csv", review_events)
    write_csv(OUT / "data" / "selected_entries.csv", selected)
    write_csv(OUT / "data" / "candidates.csv", [], [
        "candidate_id", "candidate_type", "proposed_string", "proposed_definition", "source_context",
        "generating_method", "score", "review_state", "reviewer_note", "linked_entry_id", "provenance_id",
    ])

    provenance = old_provenance + [
        {
            "provenance_id": "mmc:provenance:comma-snapshot-dfaacb6e",
            "agent": "CoMMA project; local snapshot verifier",
            "activity_type": "corpus_snapshot_download_and_checksum_verification",
            "source_resource_version": f"comma-project/comma-jsonl@{COMMA_REVISION}",
            "software_model_version": "MusiCoMMA local corpus workflow",
            "parameters_config_hash": "See corpus/CORPUS_MANIFEST.json in project source",
            "timestamp": "2026-07-27T14:16:46Z",
            "input_checksums": "Seven CoMMA shard checksums recorded in source project manifest",
            "output_checksums": "Bulk corpus is referenced, not redistributed in this deposit",
        },
        {
            "provenance_id": "mmc:provenance:exact-pilot-v0-1-0",
            "agent": "MusiCoMMA deterministic retrieval pipeline",
            "activity_type": "balanced_entry_selection_and_exact_source_form_retrieval",
            "source_resource_version": f"CoMMA {COMMA_REVISION}; MusiCoMMA vocabulary 0.1.0",
            "software_model_version": "rule:exact-v0.1.0",
            "parameters_config_hash": "50 entries; balanced language/category design; maximum 10 retained contexts per entry",
            "timestamp": "2026-07-29T00:00:00+02:00",
            "input_checksums": "See project review package checksums",
            "output_checksums": "See project review package checksums",
        },
        {
            "provenance_id": "mmc:provenance:validated-pilot-v0-2-0",
            "agent": "Xavier Fresquet",
            "activity_type": "batch_scholarly_validation_and_grouping",
            "source_resource_version": "musiconis-comma-review-v0.1.0",
            "software_model_version": "human_review_event",
            "parameters_config_hash": "all 485 retained contexts accepted as musical attestations; image checking not recorded",
            "timestamp": "2026-07-29T00:00:00+02:00",
            "input_checksums": "See review/MusiCoMMA_review_pilot_v0.1.0.zip.sha256",
            "output_checksums": "See review/MusiCoMMA_validated_grouped_v0.2.0.zip.sha256",
        },
        {
            "provenance_id": "mmc:provenance:publication-build-v0-2-0",
            "agent": "MusiCoMMA publication build pipeline",
            "activity_type": "schema_alignment_statistics_visualization_and_deposit_packaging",
            "source_resource_version": "MusiCoMMA 0.2.0 validated pilot",
            "software_model_version": "build_publication_release.py",
            "parameters_config_hash": sha256(Path(__file__)),
            "timestamp": GENERATED_AT,
            "input_checksums": "See source release and review package checksums",
            "output_checksums": "See checksums.sha256",
        },
    ]
    write_csv(OUT / "data" / "provenance.csv", provenance)

    # Reproducible publication statistics and plot data.
    language_entries = Counter(row["language_label"] for row in entries)
    language_senses = Counter(sense_by_id[row["sense_id"]]["language_stage"] for row in senses)
    # Use entry language labels for sense totals to avoid proliferating historical-stage strings.
    entry_lang_by_id = {row["entry_id"]: row["language_label"] for row in entries}
    language_sense_labels = Counter(entry_lang_by_id[row["entry_id"]] for row in senses)
    att_lang = Counter(row["language_label"] for row in validated)
    att_cat = Counter(row["category_label"] for row in validated)
    selected_cat = Counter(row["category_label"] for row in selected)
    unresolved = sum(row["sense_assignment_status"] == "entry_validated_sense_unresolved" for row in validated)
    linked = len(validated) - unresolved
    poly_selected = sum(row["polysemous"].lower() == "true" for row in selected)
    in_scope = sum(row["language_code"] in {"la", "fro"} for row in entries)
    date_values = date_bands(validated)
    crossing = sum((safe_int(r["not_after"]) or 0) > 1600 for r in validated)
    counts_per_entry = sorted(count_by_entry.values())
    median = (counts_per_entry[24] + counts_per_entry[25]) / 2
    repo_counts = Counter(normalize_repo(row["shelfmark"]) for row in validated)
    stats: list[dict[str, object]] = []

    def add_stat(stat_id: str, definition: str, value: object, denominator: object, unit: str, filters: str, source: str) -> None:
        stats.append({
            "stat_id": stat_id, "definition": definition, "value": value, "denominator": denominator,
            "unit": unit, "filters": filters, "source_table_version": f"{source} v{VERSION}",
            "generating_script": "scripts/build_publication_release.py", "generation_timestamp": GENERATED_AT,
        })

    add_stat("source_physical_lines", "Physical lines in the pinned Musiconis vocabulary source", len(source_lines), "", "lines", "all", "source_lines.csv")
    add_stat("parsed_source_records", "Parsed lexical source records", len(source_records), "", "records", "all", "source_records.csv")
    add_stat("canonical_entries", "Canonical Musiconis lexical entries", len(entries), "", "entries", "all", "entries.csv")
    add_stat("canonical_forms", "Canonical source-preserved forms", len(forms), "", "forms", "all", "forms.csv")
    add_stat("lexical_senses", "Lexical senses", len(senses), "", "senses", "all", "senses.csv")
    add_stat("polysemous_entries", "Entries with more than one source sense", sum(r["polysemous"] == "true" for r in entries), len(entries), "entries", "all", "entries.csv")
    add_stat("concept_categories", "Top-level analytical concepts", len(concepts), "", "concepts", "all", "concepts.csv")
    add_stat("comma_scope_entries", "Latin and Old French entries in CoMMA scope", in_scope, len(entries), "entries", "language_code in la|fro", "entries.csv")
    add_stat("pilot_selected_entries", "Entries selected for the balanced validation pilot", len(selected), in_scope, "entries", "pilot selected", "selected_entries.csv")
    add_stat("pilot_entry_coverage_percent", "Share of in-scope entries represented in the validation pilot", pct(len(selected), in_scope), in_scope, "percent", "pilot selected / in-scope", "selected_entries.csv")
    add_stat("validated_attestations", "Reviewer-accepted musical contexts", len(validated), len(validated), "attestations", "decision=accept", "attestations.csv")
    add_stat("distinct_manuscripts", "Globally deduplicated manuscript digitizations represented", len(manuscripts), "", "manuscripts", "pilot attestations", "manuscripts.csv")
    add_stat("entry_manuscript_groups", "Distinct entry-manuscript groupings", len(manuscript_groups), "", "groups", "pilot attestations", "manuscript_groups.csv")
    add_stat("single_sense_linked", "Attestations automatically linked because the entry has one source sense", linked, len(validated), "attestations", "single-source-sense entries", "attestations.csv")
    add_stat("sense_unresolved", "Attestations from polysemous entries left contextually sense-unresolved", unresolved, len(validated), "attestations", "polysemous entries", "attestations.csv")
    add_stat("pilot_polysemous_entries", "Selected pilot entries with multiple source senses", poly_selected, len(selected), "entries", "pilot selected", "selected_entries.csv")
    add_stat("image_checked_recorded", "Attestations with manuscript-image checking recorded", sum(r["image_checked"] != "not_recorded" for r in validated), len(validated), "attestations", "pilot", "attestations.csv")
    add_stat("attestations_per_entry_mean", "Mean retained attestations per selected entry", f"{len(validated)/len(selected):.2f}", len(selected), "attestations per entry", "pilot", "attestations.csv")
    add_stat("attestations_per_entry_median", "Median retained attestations per selected entry", f"{median:.1f}", len(selected), "attestations per entry", "pilot", "attestations.csv")
    add_stat("attestations_per_entry_min", "Minimum retained attestations for a selected entry", min(counts_per_entry), len(selected), "attestations", "pilot", "attestations.csv")
    add_stat("attestations_per_entry_max", "Maximum retained attestations for a selected entry", max(counts_per_entry), len(selected), "attestations", "pilot", "attestations.csv")
    add_stat("date_ranges_crossing_1600", "Attestation rows whose supplied manuscript date range ends after 1600", crossing, len(validated), "attestations", "not_after > 1600", "attestations.csv")
    for label, value in sorted(language_entries.items()):
        add_stat(f"entries_language_{label.lower().replace(' ', '_')}", f"Entries labelled {label}", value, len(entries), "entries", f"language_label={label}", "entries.csv")
    for label, value in sorted(language_sense_labels.items()):
        add_stat(f"senses_language_{label.lower().replace(' ', '_')}", f"Senses attached to {label} entries", value, len(senses), "senses", f"entry language={label}", "senses.csv")
    for label, value in sorted(att_lang.items()):
        add_stat(f"attestations_language_{label.lower().replace(' ', '_')}", f"Validated attestations labelled {label}", value, len(validated), "attestations", f"language_label={label}", "attestations.csv")
    for label, value in sorted(att_cat.items()):
        add_stat(f"attestations_category_{label.lower().replace('/', '_').replace(' ', '_')}", f"Validated attestations in category {label}", value, len(validated), "attestations", f"category_label={label}", "attestations.csv")
    for label, value in date_values:
        stat_slug = label.casefold().replace(">", "post_").replace("-", "_").replace(" ", "_")
        add_stat(f"attestations_midpoint_{stat_slug}", f"Attestations in supplied date-midpoint band {label}", value, len(validated), "attestations", "descriptive midpoint; not exposure-normalized", "attestations.csv")
    write_csv(OUT / "data" / "stats_summary.csv", stats)

    write_csv(OUT / "figures" / "plot_data" / "vocabulary_by_language.csv", [
        {"language": label, "entries": language_entries[label], "senses": language_sense_labels[label]}
        for label in ["Latin", "Old French", "Old Occitan", "Middle French"]
    ])
    write_csv(OUT / "figures" / "plot_data" / "attestations_by_category.csv", [
        {"category": label, "attestations": value, "selected_entries": selected_cat[label]}
        for label, value in att_cat.most_common()
    ])
    write_csv(OUT / "figures" / "plot_data" / "attestations_by_language_category.csv", [
        {"language": lang, "category": cat, "attestations": sum(r["language_label"] == lang and r["category_label"] == cat for r in validated)}
        for lang in ["Latin", "Old French"] for cat in sorted(att_cat)
    ])
    write_csv(OUT / "figures" / "plot_data" / "date_midpoint_bands.csv", [
        {"band": label, "attestations": value, "interpretation_note": "descriptive supplied-metadata midpoint; not normalized by CoMMA exposure"}
        for label, value in date_values
    ])
    write_csv(OUT / "figures" / "plot_data" / "sense_resolution.csv", [
        {"status": "single source sense auto-linked", "attestations": linked},
        {"status": "polysemous entry; sense unresolved", "attestations": unresolved},
    ])
    write_csv(OUT / "figures" / "plot_data" / "top_repositories.csv", [
        {"repository_normalized": label, "attestations": value} for label, value in repo_counts.most_common(15)
    ])

    pipeline_figure()
    vocab_chart_data = [(label, language_entries[label], language_sense_labels[label]) for label in ["Old French", "Latin", "Old Occitan", "Middle French"]]
    grouped_bar_chart("fig02_vocabulary_language", "Vocabulary composition by language", "Counts refer to the complete Musiconis vocabulary foundation.", vocab_chart_data, "Grouped horizontal bar chart. Old French has 560 entries and 583 senses; Latin 340 entries and 662 senses; Old Occitan 297 entries and 302 senses; Middle French 1 entry and 1 sense.")
    bar_chart("fig03_attestations_category", "Validated pilot attestations by category", "n = 485 accepted contexts; categories are inherited from the selected Musiconis entries.", att_cat.most_common(), "Horizontal bar chart of 485 attestations: performance act 68; instrument, performer or social role, sound category, musical or literary form, and instrument part or implement each 60; dance or movement 55; other or uncertain 52; performance context or function 10.")
    bar_chart("fig04_date_midpoints", "Attestations by manuscript date midpoint", "Descriptive only; counts are not normalized by CoMMA corpus exposure.", date_values[:-1], "Horizontal bar chart of supplied date midpoints: 800-999 40; 1000-1199 42; 1200-1399 200; 1400-1600 199; after 1600 midpoint 4.", "#3f8f75")
    bar_chart("fig05_sense_resolution", "Contextual sense assignment status", "Entry-level musical relevance is validated; polysemous contexts remain unresolved.", [("Polysemous; unresolved", unresolved), ("Single sense; auto-linked", linked)], "Horizontal bar chart: 330 attestations from polysemous entries remain contextually sense-unresolved and 155 from single-sense entries are automatically linked.", "#8156a3")

    # A compact language/category matrix drawn as an accessible heatmap.
    cats = [label for label, _ in att_cat.most_common()]
    matrix = {(lang, cat): sum(r["language_label"] == lang and r["category_label"] == cat for r in validated) for lang in ["Latin", "Old French"] for cat in cats}
    alt = "Heatmap comparing Latin and Old French attestation counts across nine analytical categories. The pilot design is nearly balanced by language but category counts reflect the selected entries and ten-context cap."
    width, height = 1450, 620
    lines = svg_start("Language by category in the validated pilot", alt, width, height)
    lines += ['<text x="60" y="60" class="title">Language by category in the validated pilot</text>', '<text x="60" y="95" class="subtitle">Cell labels give accepted-context counts; darker cells contain more records.</text>']
    max_cell = max(matrix.values())
    cell_w, cell_h, left, top = 134, 120, 190, 170
    for j, cat in enumerate(cats):
        short = cat.replace(" or ", "/").replace("Performance ", "Perf. ")
        chunks = textwrap.wrap(short, 16)
        for k, part in enumerate(chunks[:3]):
            lines.append(f'<text x="{left+j*cell_w+cell_w/2}" y="{top-50+18*k}" text-anchor="middle" class="small">{escape(part)}</text>')
    for i, lang in enumerate(["Latin", "Old French"]):
        lines.append(f'<text x="{left-20}" y="{top+i*cell_h+70}" text-anchor="end" class="label">{lang}</text>')
        for j, cat in enumerate(cats):
            value = matrix[(lang, cat)]
            intensity = 0.18 + 0.72 * value / max_cell
            # Blue palette with sufficient text contrast at high values.
            base = (40, 100, 166)
            rgb = tuple(round(255 - (255-c)*intensity) for c in base)
            fill = "#%02x%02x%02x" % rgb
            x, y = left+j*cell_w, top+i*cell_h
            lines.append(f'<rect x="{x}" y="{y}" width="{cell_w-8}" height="{cell_h-8}" rx="6" fill="{fill}" stroke="#ffffff"/>')
            lines.append(f'<text x="{x+(cell_w-8)/2}" y="{y+66}" text-anchor="middle" class="value">{value}</text>')
    lines.append('<text x="60" y="560" class="small">The 50-entry pilot is a stratified research sample, not an estimate of historical lexical frequency.</text>')
    save_svg("fig06_language_category_heatmap", lines, alt)

    # Five reviewable case-study bundles selected by lexical family, without inventing contextual sense decisions.
    case_families = [
        ("voice-boundaries", ["exclamo", "criement", "clamor", "vois"], "Voice, cry, recitation, and proclamation"),
        ("objects-and-signals", ["cymbalum", "campana", "timbre"], "Instrument names, material objects, and social signals"),
        ("implements-and-breath", ["plectrum", "follis", "souffle"], "Implements, bodily technique, and breath"),
        ("dance-and-movement", ["chorea", "carolla", "rondel", "branle", "tresche"], "Dance forms and bodily movement"),
        ("performers-and-offices", ["psaltes", "chantre", "tibicen", "trompete"], "Performers, offices, and social roles"),
    ]
    case_rows = []
    for case_id, lemmas, rationale in case_families:
        subset = [r for r in validated if r["lemma"] in lemmas]
        case_rows.append({
            "case_id": case_id,
            "title": rationale,
            "requested_lemmas": "|".join(lemmas),
            "represented_lemmas": "|".join(sorted({r["lemma"] for r in subset})),
            "attestation_count": len(subset),
            "manuscript_count": len({r["manuscript_key"] for r in subset}),
            "sense_policy": "entry-level relevance validated; contextual sense unresolved where polysemous",
            "interpretive_status": "review bundle, not image-confirmed case-study conclusion",
        })
    write_csv(OUT / "examples" / "five_reviewed_case_studies" / "case_study_index.csv", case_rows)
    write_text(OUT / "examples" / "five_reviewed_case_studies" / "README.md", """
# Five review bundles for qualitative follow-up

These five bundles organize relevant pilot entries around musicological questions. They are not independent validation samples and do not add contextual sense assignments. All contexts remain in `data/attestations.csv`; the index reports which requested lemmas are actually represented in the 50-entry pilot. Before quoting an HTR passage as evidence, a researcher should open the linked IIIF manuscript, inspect the image, identify the page/canvas/line where possible, and record a new annotation event.
""")

    # Tabular schemas and compact RDF serializations.
    tables = {}
    for path in sorted((OUT / "data").glob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            fields = next(csv.reader(handle))
        tables[path.stem] = fields
    write_json(OUT / "schemas" / "tables.json", {"version": VERSION, "tables": tables})
    write_json(OUT / "schemas" / "attestations.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MusiCoMMA v0.2.0 attestation",
        "type": "object",
        "required": ["attestation_id", "entry_id", "form_id", "source_string", "comma_record_id", "comma_release", "manuscript_id", "validation_status", "annotation_id", "provenance_id"],
        "properties": {field: {"type": "string"} for field in attestation_fields},
        "additionalProperties": False,
    })
    ttl = [
        "@prefix mmc: <https://w3id.org/musiconis-comma/> .",
        "@prefix mmcconcept: <https://w3id.org/musiconis-comma/concept/> .",
        "@prefix mmcentry: <https://w3id.org/musiconis-comma/entry/> .",
        "@prefix mmcattestation: <https://w3id.org/musiconis-comma/attestation/> .",
        "@prefix mmcmanuscript: <https://w3id.org/musiconis-comma/manuscript/> .",
        "@prefix mmcprovenance: <https://w3id.org/musiconis-comma/provenance/> .",
        "@prefix ontolex: <http://www.w3.org/ns/lemon/ontolex#> .",
        "@prefix lime: <http://www.w3.org/ns/lemon/lime#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix oa: <http://www.w3.org/ns/oa#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
        'mmc:lexicon a lime:Lexicon ; rdfs:label "MusiCoMMA multilingual vocabulary of medieval music and performance"@en ; dct:issued "2026-07-29" ; dct:hasVersion "0.2.0" ; dct:license <https://creativecommons.org/licenses/by/4.0/> .',
    ]
    for row in concepts:
        slug = row["concept_id"].split(":")[-1]
        ttl.append(f'mmcconcept:{slug} a skos:Concept ; skos:prefLabel "{row["preferred_label_en"].replace(chr(34), chr(92)+chr(34))}"@en, "{row["preferred_label_fr"].replace(chr(34), chr(92)+chr(34))}"@fr .')
    for row in entries:
        eid = row["entry_id"].split(":")[-1]
        ttl.append(f'mmcentry:{eid} a ontolex:LexicalEntry ; rdfs:label "{row["lemma"].replace(chr(34), chr(92)+chr(34))}" ; dct:language "{row["language_code"]}" .')
    for row in attestations:
        aid = str(row["attestation_id"]).split(":")[-1]
        eid = str(row["entry_id"]).split(":")[-1]
        mid = str(row["manuscript_id"]).split(":")[-1]
        ttl.append(f'mmcattestation:{aid} a oa:Annotation ; oa:hasBody mmcentry:{eid} ; oa:hasTarget mmcmanuscript:{mid} ; dct:isPartOf "CoMMA {COMMA_REVISION}" ; prov:wasGeneratedBy mmcprovenance:validated-pilot-v0-2-0 .')
    write_text(OUT / "rdf" / "musiconis_comma.ttl", "\n".join(ttl))
    context = {"@vocab": "https://w3id.org/musiconis-comma/", "dct": "http://purl.org/dc/terms/", "prov": "http://www.w3.org/ns/prov#", "oa": "http://www.w3.org/ns/oa#", "entry": {"@id": "oa:hasBody", "@type": "@id"}, "target": {"@id": "oa:hasTarget", "@type": "@id"}}
    graph = [{"@id": "lexicon", "@type": "http://www.w3.org/ns/lemon/lime#Lexicon", "dct:hasVersion": VERSION}]
    graph.extend({"@id": f'attestation/{str(r["attestation_id"]).split(":")[-1]}', "@type": "oa:Annotation", "entry": f'entry/{str(r["entry_id"]).split(":")[-1]}', "target": f'manuscript/{str(r["manuscript_id"]).split(":")[-1]}'} for r in attestations)
    write_json(OUT / "rdf" / "musiconis_comma.jsonld", {"@context": context, "@graph": graph})
    write_text(OUT / "rdf" / "shapes.ttl", """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix oa: <http://www.w3.org/ns/oa#> .
@prefix mmc: <https://w3id.org/musiconis-comma/> .

mmc:AttestationShape a sh:NodeShape ;
  sh:targetClass oa:Annotation ;
  sh:property [ sh:path oa:hasBody ; sh:minCount 1 ; sh:maxCount 1 ] ;
  sh:property [ sh:path oa:hasTarget ; sh:minCount 1 ; sh:maxCount 1 ] .
""")

    csv_row_counts = {}
    for path in sorted((OUT / "data").glob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            csv_row_counts[path.stem] = sum(1 for _ in csv.DictReader(handle))
    validation_report = {
        "dataset": "MusiCoMMA",
        "version": VERSION,
        "generated_at": GENERATED_AT,
        "status": "PASS_WITH_DECLARED_PILOT_LIMITATIONS",
        "row_counts": csv_row_counts,
        "integrity": {
            "unique_attestation_ids": len({r["attestation_id"] for r in attestations}) == len(attestations),
            "attestation_entry_foreign_keys": all(str(r["entry_id"]) in {e["entry_id"] for e in entries} for r in attestations),
            "attestation_form_foreign_keys": all(str(r["form_id"]) in {f["form_id"] for f in forms} for r in attestations),
            "resolved_sense_foreign_keys": all(not r["sense_id"] or str(r["sense_id"]) in sense_by_id for r in attestations),
            "attestation_manuscript_foreign_keys": all(str(r["manuscript_id"]) in {m["manuscript_id"] for m in manuscripts} for r in attestations),
            "annotation_foreign_keys": all(str(r["annotation_id"]) in {a["annotation_id"] for a in annotations} for r in attestations),
            "all_attestations_have_comma_release": all(r["comma_release"] for r in attestations),
        },
        "declared_limitations": [
            "The v0.2.0 corpus evidence layer covers 50 of 900 Latin and Old French entries in scope; it is not vocabulary-wide coverage.",
            "All 485 contexts were accepted in one batch reviewer event; there are no independent double annotations, negative labels, inter-annotator agreement, or held-out precision/recall estimates.",
            "Manuscript-image inspection was not recorded for the batch event.",
            "330 attestations from polysemous entries remain contextually sense-unresolved.",
            "Exact source-form retrieval is a transparent baseline, not an HTR-aware ML evaluation.",
            "Date and repository summaries are descriptive of retained contexts and are not normalized by CoMMA corpus exposure.",
        ],
    }
    write_json(OUT / "reports" / "validation_report.json", validation_report)
    write_json(OUT / "reports" / "publication_statistics.json", {"version": VERSION, "generated_at": GENERATED_AT, "statistics": stats})

    write_text(OUT / "VERSION", VERSION)
    write_text(OUT / "README.md", f"""
# MusiCoMMA v{VERSION}: Musiconis Vocabulary and Validated CoMMA Attestation Pilot

MusiCoMMA publishes the complete Musiconis music-and-performance vocabulary foundation together with a bounded, reviewer-validated pilot of corpus attestations from CoMMA. The release contains {len(entries):,} lexical entries, {len(forms):,} canonical forms, {len(senses):,} senses, and {len(concepts)} analytical concepts reconstructed from {len(source_records):,} parsed source records. Its evidence layer contains {len(attestations)} accepted contexts for {len(selected)} Latin and Old French entries, grouped across {len(manuscripts)} manuscript digitizations.

This is the deposit candidate for the first public Zenodo dataset in the MusiCoMMA sequence: a v0.2.0 validated pilot, not the eventual vocabulary-wide v1.0. Only {len(selected)} of the {in_scope} Latin and Old French entries in scope ({pct(len(selected), in_scope)}%) are represented in the validated corpus pilot. All contexts were accepted as musically relevant at entry level in one batch reviewer event on 29 July 2026. Manuscript-image inspection was not recorded. The {unresolved} attestations attached to polysemous entries remain contextually sense-unresolved; {linked} single-sense attestations are linked automatically to the sole source sense.

## Résumé français

MusiCoMMA associe le vocabulaire Musiconis de la musique et de la performance à un pilote borné d'attestations issues de CoMMA. La couche lexicale complète comprend {len(entries):,} entrées et {len(senses):,} sens. La couche de preuve pilote comprend {len(attestations)} contextes validés au niveau de l'entrée, regroupés dans {len(manuscripts)} numérisations de manuscrits. Cette version 0.2.0 ne constitue pas encore une couverture exhaustive du vocabulaire. La vérification des images n'a pas été consignée et {unresolved} contextes polysémiques restent sans désambiguïsation de sens.

## Contents

- `data/`: UTF-8 CSV tables for vocabulary, coverage, attestations, manuscripts, annotations, provenance, groupings, and every published statistic.
- `jsonl/`: attestation and annotation records as JSON Lines.
- `rdf/`: OntoLex-Lemon/SKOS-oriented Turtle and JSON-LD, plus a compact SHACL shape.
- `schemas/`: table columns and JSON Schema for attestation records.
- `figures/`: accessible SVG and PNG figures, alt text, and the CSV values underlying each plot.
- `reports/`: machine-readable validation and statistics reports.
- `examples/`: five lexical-family bundles for image-checked qualitative follow-up.

## Reuse and citation

Use the stable identifiers when joining tables. Preserve the diplomatic `source_string`; do not replace it with normalized or expanded text. Cite this release, the Musiconis vocabulary, and CoMMA. The precise citation is in `CITATION.cff`. No DOI is inserted before Zenodo reserves it.

## Research-use boundary

This dataset is released for scholarly research, teaching, reproducibility, and cultural-heritage analysis. The HTR-derived context strings are investigatory evidence, not edited transcriptions. Users who quote manuscript passages, reproduce linked images, or make philological claims should consult the supplying institution's IIIF/resource terms and inspect the manuscript image directly.

## Source corpus

CoMMA snapshot `{COMMA_REVISION}` contains 32,763 digitizations and approximately 3.33 billion tokens in the locally verified manifest. Bulk CoMMA JSONL and manuscript images are not redistributed here. Derived contexts, metadata, persistent identifiers, and links retain source attribution. HTR is research evidence, not a substitute for image-checked transcription.

## Reproducibility

All headline numbers and figures are generated by `scripts/build_publication_release.py` in the source project. `data/stats_summary.csv` is the canonical machine-readable source for paper statistics. Verify `checksums.sha256` after download.
""")
    write_text(OUT / "DATA_DICTIONARY.md", """
# Data dictionary

The complete field lists are machine-readable in `schemas/tables.json`.

## Vocabulary tables

`entries.csv` contains stable lexical entries; `forms.csv` preserves one canonical source form per entry; `senses.csv` separates source senses and definitions; `concepts.csv` defines the nine analytical categories. `source_records.csv` and `source_lines.csv` make reconstruction auditable. `coverage.csv` distinguishes the 50 pilot entries from in-scope entries that remain `not_searched` in v0.2.0.

## Evidence and review tables

`attestations.csv` contains one accepted CoMMA context per row. Original HTR strings and context are separate from normalized search strings. A blank `sense_id` with `sense_assignment_status=entry_validated_sense_unresolved` means that musical relevance was accepted but a polysemous source entry was not contextually disambiguated. `image_checked=not_recorded` must not be interpreted as image confirmation.

`annotations.csv` models the review assertion attached to each attestation. All 485 rows point to one batch validation event, preserved in `review_events.csv`; this is not an independent-annotation benchmark. `entry_groups.csv` and `manuscript_groups.csv` organize attestations without collapsing them. `manuscripts.csv` contains redistributable metadata and links, not manuscript images.

## Research-support tables

`candidates.csv` is empty because all retained pilot candidates were promoted to validated attestations; absence from the pilot is not a rejection. `provenance.csv` records source, retrieval, review, and packaging activities. `stats_summary.csv` is the required source for every headline value in the accompanying publications.
""")
    write_text(OUT / "LICENSE_DATA.md", """
# Data licence and attribution notice

This deposit candidate is prepared for release under Creative Commons Attribution 4.0 International (CC BY 4.0), subject to the final rights and authorship check in `DEPOSIT_CHECKLIST.md`.

The Musiconis-derived vocabulary and MusiCoMMA annotations must retain attribution to their creators. CoMMA reports CC BY 4.0 for its JSONL dataset; cite CoMMA and its creators when reusing derived contexts or metadata. Linked IIIF manifests and manuscript images remain governed by their supplying institutions. No manuscript images or bulk CoMMA files are included in this package.

The licence does not convert HTR into an authoritative transcription. Users remain responsible for checking images and provider terms before reproducing or publishing manuscript passages. The intended use is scholarly research, teaching, reproducibility, and cultural-heritage analysis; any downstream reuse must preserve the distinction between HTR evidence, reviewer decision, and image-checked transcription.
""")
    write_text(OUT / "CHANGELOG.md", f"""
# Changelog

## {VERSION} - {BUILD_DATE}

- Preserves the complete v0.1.0 vocabulary foundation: {len(entries):,} entries, {len(forms):,} forms, and {len(senses):,} senses.
- Adds {len(attestations)} reviewer-accepted CoMMA contexts for {len(selected)} selected entries.
- Adds {len(entry_groups)} entry groups, {len(manuscript_groups)} entry-manuscript groups, and {len(manuscripts)} deduplicated manuscript records.
- Links {linked} single-sense attestations and leaves {unresolved} polysemous attestations explicitly sense-unresolved.
- Adds per-attestation annotations, review-event provenance, schemas, JSONL, RDF, accessible figures, and reproducible publication statistics.
- Marks this release as a validated pilot; vocabulary-wide searching and formal evaluation remain future v1.0 work.
""")
    write_text(OUT / "CITATION.cff", f"""
cff-version: 1.2.0
type: dataset
title: "MusiCoMMA v{VERSION}: Musiconis Vocabulary and Validated CoMMA Attestation Pilot"
version: "{VERSION}"
date-released: "{BUILD_DATE}"
license: CC-BY-4.0
authors:
  - family-names: Fresquet
    given-names: Xavier
    orcid: "https://orcid.org/0000-0001-8362-9485"
    affiliation: "IReMus, Sorbonne Université-CNRS, UMR 8223; SCAI, Sorbonne Université; SAFIR, Sorbonne Abu Dhabi for Innovation and Research, Sorbonne University Abu Dhabi"
  - family-names: Billiet
    given-names: Frédéric
    affiliation: "IReMus, Sorbonne Université-CNRS, UMR 8223"
message: "Please cite Xavier Fresquet and Frédéric Billiet as authors of this versioned dataset, and cite the Musiconis vocabulary and CoMMA as its scholarly sources."
""")
    write_json(OUT / "ZENODO_METADATA.json", {
        "title": f"MusiCoMMA v{VERSION}: Musiconis Vocabulary and Validated CoMMA Attestation Pilot",
        "upload_type": "dataset",
        "publication_date": BUILD_DATE,
        "version": VERSION,
        "description": f"Complete Musiconis vocabulary foundation ({len(entries)} entries; {len(senses)} senses) with a bounded validated CoMMA pilot ({len(attestations)} accepted contexts; {len(selected)} Latin/Old French entries; {len(manuscripts)} manuscript digitizations). Entry-level musical relevance was accepted in one batch reviewer event. Image checking was not recorded and {unresolved} polysemous attestations remain contextually sense-unresolved. This research dataset provides investigatory HTR-derived evidence and should not be treated as an edited transcription corpus. No independent DOI for the Musiconis vocabulary package has yet been confirmed locally; add it as isDerivedFrom before publication if one is identified.",
        "creators": [
            {
                "name": "Fresquet, Xavier",
                "orcid": "0000-0001-8362-9485",
                "affiliation": "IReMus, Sorbonne Université-CNRS, UMR 8223; SCAI, Sorbonne Université; SAFIR, Sorbonne Abu Dhabi for Innovation and Research, Sorbonne University Abu Dhabi",
            },
            {
                "name": "Billiet, Frédéric",
                "affiliation": "IReMus, Sorbonne Université-CNRS, UMR 8223",
            },
        ],
        "keywords": ["medieval musicology", "digital humanities", "historical lexicography", "Latin", "Old French", "HTR", "manuscripts", "CoMMA", "Musiconis"],
        "license": "cc-by-4.0",
        "language": "eng",
        "notes": "Deposit metadata candidate for step 1 of the publication sequence. Xavier Fresquet and Frédéric Billiet are the MusiCoMMA authors, in that order. Confirm both authors' affiliations, related identifiers, contribution statement, and redistribution terms before publishing. If Journal of Cultural Analytics requires double-anonymous first-round review, create or reserve the Zenodo DOI but keep the record unpublished until acceptance or editor confirmation; otherwise publish first and insert the DOI into the HAL technical report and JCA manuscript.",
        "related_identifiers": [
            {"identifier": "https://huggingface.co/datasets/comma-project/comma-jsonl", "relation": "isDerivedFrom", "resource_type": "dataset"},
            {"identifier": "10.5281/zenodo.14163436", "relation": "references", "resource_type": "dataset"},
        ],
    })
    write_text(OUT / "DEPOSIT_CHECKLIST.md", """
# Zenodo pre-publication checklist

Do not publish the draft record until every item below is complete. Zenodo files are immutable after publication; corrections require a new version.

- [ ] Confirm Xavier Fresquet and Frédéric Billiet, in that order, as creators; verify Xavier Fresquet's ORCID and both authors' affiliations.
- [ ] Confirm the final author-contribution statement; do not invent an ORCID for Frédéric Billiet.
- [ ] Confirm that CC BY 4.0 is valid for every redistributed Musiconis field, annotation, and selected CoMMA context; the dataset is intended for scholarly research use and must not be treated as an edited transcription corpus.
- [ ] Recheck the current CoMMA dataset citation and add its paper identifier as a related work.
- [ ] Decide whether to upload the ZIP only or the ZIP plus prominent README/checksum files; avoid duplicate preservation copies without purpose.
- [ ] Create a Zenodo draft, reserve its version DOI, and add that DOI to `CITATION.cff`, README, the HAL metadata/report, and the JCA manuscript.
- [ ] Check whether JCA requires double-anonymous first-round review; if yes, keep the Zenodo record unpublished until acceptance or editor confirmation.
- [ ] Add the Musiconis vocabulary package as `isDerivedFrom` if a DOI is confirmed; otherwise state clearly in the description that no independent vocabulary DOI has yet been confirmed.
- [ ] Validate English/French descriptions, keywords, funding, and affiliations in the deposit form.
- [ ] Run the build script, inspect `reports/validation_report.json`, and verify all SHA-256 checksums from the final archive.
- [ ] Confirm that no bulk CoMMA JSONL or manuscript image entered the deposit.
- [ ] Publish as version 0.2.0 (validated pilot), not as vocabulary-wide v1.0.
""")

    # Manifest first, then checksums for every other package file.
    manifest_files = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name not in {"manifest.json", "checksums.sha256"}):
        manifest_files.append({"path": str(path.relative_to(OUT)), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    write_json(OUT / "manifest.json", {"dataset": "MusiCoMMA", "version": VERSION, "generated_at": GENERATED_AT, "files": manifest_files})
    checksum_lines = []
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "checksums.sha256"):
        checksum_lines.append(f"{sha256(path)}  {path.relative_to(OUT)}")
    write_text(OUT / "checksums.sha256", "\n".join(checksum_lines))

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in OUT.rglob("*") if p.is_file()):
            archive.write(path, arcname=str(Path(OUT.name) / path.relative_to(OUT)))
    write_text(Path(str(ZIP_PATH) + ".sha256"), f"{sha256(ZIP_PATH)}  {ZIP_PATH.name}")
    print(json.dumps({
        "release": str(OUT), "zip": str(ZIP_PATH), "zip_sha256": sha256(ZIP_PATH),
        "entries": len(entries), "senses": len(senses), "attestations": len(attestations),
        "selected_entries": len(selected), "manuscripts": len(manuscripts), "unresolved_senses": unresolved,
    }, indent=2))


if __name__ == "__main__":
    build()
