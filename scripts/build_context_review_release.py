#!/usr/bin/env python3
"""Build v0.2.1 from the frozen pilot and explicit contextual review decisions."""

import argparse
import json
import shutil
import statistics
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef

from build_publication_release import read_csv, write_csv, write_json, write_text, sha256, date_bands

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "release/musiconis-comma-v0.2.0-zenodo"
BASE_ZIP = ROOT / "release/MusiCoMMA_v0.2.0_Zenodo_deposit.zip"
BASE_SHA256 = "fa44b1faaa23528b18b3d88ca231587fa35f5b880d3a6068e91b4a785eefb763"
OUT = ROOT / "release/musiconis-comma-v0.2.1-zenodo"
REVIEW = ROOT / "review/chantre_2026-09-12"
VERSION = "0.2.1"
DATE = "2026-09-12"
PROV = "mmc:provenance:context-review-2026-09-12"
TITLE = "MusiCoMMA v0.2.1: Musiconis Vocabulary and Context-Reviewed CoMMA Pilot"


def verify_manifest(root):
    for line in (root / "checksums.sha256").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        if sha256(root / name) != expected:
            raise ValueError(f"Input checksum mismatch: {name}")


def finalize():
    files = [p for p in sorted(OUT.rglob("*")) if p.is_file()
             and p.name not in {"manifest.json", "checksums.sha256"}]
    write_json(OUT / "manifest.json", {
        "dataset": "MusiCoMMA", "version": VERSION, "build_date": DATE,
        "files": [{"path": str(p.relative_to(OUT)), "size_bytes": p.stat().st_size,
                   "sha256": sha256(p)} for p in files],
    })
    write_text(OUT / "checksums.sha256", "\n".join(
        f"{sha256(p)}  {p.relative_to(OUT)}" for p in sorted(OUT.rglob("*"))
        if p.is_file() and p.name != "checksums.sha256"))
    verify_manifest(OUT)
    archive = OUT.parent / f"MusiCoMMA_v{VERSION}_Zenodo_deposit.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                info = zipfile.ZipInfo(str(Path(OUT.name) / p.relative_to(OUT)), (2026, 9, 12, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, p.read_bytes())
    write_text(Path(str(archive) + ".sha256"), f"{sha256(archive)}  {archive.name}")
    print(archive)


def build():
    verify_manifest(BASE)
    event = json.loads((REVIEW / "decisions.json").read_text())
    original = read_csv(BASE / "data/attestations.csv")
    target = [r for r in original if r["entry_id"] == event["entry_id"]]
    decisions = event["decisions"]
    if [d["attestation_id"] for d in decisions] != [r["attestation_id"] for r in target]:
        raise ValueError("Review order does not match the ten presented contexts")
    if [d["number"] for d in decisions] != list(range(1, 11)):
        raise ValueError("Missing or duplicate review number")
    if any(d["decision"] not in {"accept", "exclude"} for d in decisions):
        raise ValueError("Unsupported decision")
    if sum(d["decision"] == "accept" for d in decisions) != 3:
        raise ValueError("Expected the three explicit user acceptances")
    by_id = {d["attestation_id"]: d for d in decisions}
    rejected_ids = {k for k, d in by_id.items() if d["decision"] == "exclude"}
    # Only the new generated maintenance directory is replaced on a rerun.
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(BASE, OUT)
    shutil.rmtree(OUT / "figures")
    history = OUT / "history/v0.2.0"
    history.mkdir(parents=True)
    for name in ("attestations", "annotations", "review_events", "stats_summary"):
        shutil.copy2(BASE / f"data/{name}.csv", history / f"{name}.csv")
    shutil.copytree(REVIEW, OUT / "review")
    write_json(OUT / "reports/input_provenance.json", {
        "baseline_archive": BASE_ZIP.name, "sha256": BASE_SHA256,
        "decisions_sha256": sha256(REVIEW / "decisions.json"),
        "note": "Frozen ZIP used because the unpacked directory has later checklist edits; all source data CSVs compared byte-for-byte before rebuild.",
    })

    annotations = read_csv(BASE / "data/annotations.csv")
    old_annotations = {r["target_id"]: r for r in annotations}
    all_rows = []
    review_rows = []
    for source in original:
        r = dict(source)
        aid = r["attestation_id"]
        if aid in by_id:
            d = by_id[aid]
            annotation_id = f"mmc:annotation:2026-09-12-{aid.rsplit(':', 1)[1]}"
            annotations.append({
                "annotation_id": annotation_id, "target_id": aid,
                "annotator_id": "researcher:xavier-fresquet", "timestamp": DATE,
                "task_version": "targeted-context-selection-v0.2.1",
                "valid_occurrence": "not_reassessed",
                "musical_relevance": "retained_for_pilot" if d["decision"] == "accept" else "excluded_from_pilot",
                "decision": d["decision"], "certainty": "not_recorded",
                "image_checked": "not_recorded", "sense_assignment_status": "not_reassessed",
                "note": f"User decision {d['number']}: {d['user_decision']}. No rationale or corrected reading supplied.",
                "adjudication_relation": "supersedes:" + old_annotations[aid]["annotation_id"],
                "validation_event_id": event["event_id"], "provenance_id": PROV,
            })
            r.update(annotation_id=annotation_id, validation_event_id=event["event_id"],
                     reviewer=event["reviewer"], reviewed_at=DATE, review_method=event["method"],
                     provenance_id=PROV)
            if d["decision"] == "exclude":
                r.update(validation_status="excluded_by_context_review", sense_id="",
                         sense_assignment_status="not_applicable_excluded")
            review_rows.append({**d, "previous_annotation_id": old_annotations[aid]["annotation_id"],
                               "annotation_id": annotation_id, "reviewer": event["reviewer"],
                               "reviewed_at": DATE, "image_checked": "not_recorded",
                               "rationale": "not_supplied", "corrected_reading": "",
                               "shelfmark": r["shelfmark"], "iiif_url": r["iiif_url"],
                               "context_with_match": r["context_with_match"]})
        all_rows.append(r)
    accepted = [r for r in all_rows if r["attestation_id"] not in rejected_ids]
    excluded = [r for r in all_rows if r["attestation_id"] in rejected_ids]
    write_csv(OUT / "data/attestations.csv", accepted)
    write_csv(OUT / "data/excluded_contexts.csv", excluded)
    write_csv(OUT / "data/context_review_decisions.csv", review_rows)
    write_csv(OUT / "data/annotations.csv", annotations)
    for name, rows in (("attestations", accepted), ("excluded_contexts", excluded), ("annotations", annotations)):
        write_text(OUT / f"jsonl/{name}.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    events = read_csv(BASE / "data/review_events.csv")
    events.append({**{k: "" for k in events[0]}, "validation_event_id": event["event_id"],
                   "target_dataset": "musiconis-comma-v0.2.0-zenodo", "target_scope": event["entry_id"],
                   "reviewer": event["reviewer"], "reviewed_at": DATE, "review_method": event["method"],
                   "decision": "3_accept_7_exclude", "decision_note": event["scope"],
                   "attestation_count": "10", "entry_group_count": "1",
                   "comma_revision": original[0]["comma_release"]})
    write_csv(OUT / "data/review_events.csv", events)

    for table, key in (("entry_groups", "entry_id"), ("manuscript_groups", "manuscript_group_id"),
                       ("manuscripts", "manuscript_id")):
        groups = []
        for row in read_csv(BASE / f"data/{table}.csv"):
            members = [r for r in accepted if r[key] == row[key]]
            if not members:
                continue
            row["attestation_count"] = str(len(members))
            if table == "entry_groups":
                row["manuscript_group_count"] = str(len({r["manuscript_group_id"] for r in members}))
                row["distinct_manuscript_count"] = str(len({r["manuscript_id"] for r in members}))
                row["earliest_not_before"] = str(min(int(r["not_before"]) for r in members))
                row["latest_not_after"] = str(max(int(r["not_after"]) for r in members))
                if row[key] == event["entry_id"]:
                    row["validation_event_id"] = event["event_id"]
            elif table == "manuscript_groups":
                row["attestation_ids"] = "|".join(r["attestation_id"] for r in members)
            else:
                row["entry_count"] = str(len({r["entry_id"] for r in members}))
                row["language"] = "|".join(sorted({r["language"] for r in members}))
            groups.append(row)
        write_csv(OUT / f"data/{table}.csv", groups)
    coverage = read_csv(BASE / "data/coverage.csv")
    for row in coverage:
        if row["entry_id"] == event["entry_id"]:
            row["validated_attestation_count"] = "3"
            row["scope_reason"] = "10 retained candidates; contextual re-review: 3 included, 7 excluded. Original search count/date unchanged."
    write_csv(OUT / "data/coverage.csv", coverage)
    provenance = read_csv(BASE / "data/provenance.csv")
    provenance.append({**{k: "" for k in provenance[0]}, "provenance_id": PROV,
                       "agent": event["reviewer"], "activity_type": "targeted_context_selection_review",
                       "source_resource_version": "MusiCoMMA 0.2.0", "software_model_version": "human_review_event",
                       "parameters_config_hash": sha256(REVIEW / "decisions.json"), "timestamp": DATE,
                       "input_checksums": sha256(BASE / "data/attestations.csv"),
                       "output_checksums": "See context_review_decisions.csv and checksums.sha256"})
    write_csv(OUT / "data/provenance.csv", provenance)

    entries = read_csv(BASE / "data/entries.csv")
    entry_by_id = {r["entry_id"]: r for r in entries}
    selected = read_csv(BASE / "data/selected_entries.csv")
    selected_by_id = {r["entry_id"]: r for r in selected}
    ms = read_csv(OUT / "data/manuscripts.csv")
    mg = read_csv(OUT / "data/manuscript_groups.csv")
    count_by_entry = Counter(r["entry_id"] for r in accepted)
    languages = Counter(entry_by_id[r["entry_id"]]["language_label"] for r in accepted)
    categories = Counter(selected_by_id[r["entry_id"]]["category_label"] for r in accepted)
    bands = dict(date_bands(accepted))
    unresolved = sum(r["sense_assignment_status"] == "entry_validated_sense_unresolved" for r in accepted)
    linked = len(accepted) - unresolved
    updates = {
        "validated_attestations": len(accepted), "distinct_manuscripts": len(ms),
        "entry_manuscript_groups": len(mg), "single_sense_linked": linked,
        "sense_unresolved": unresolved, "attestations_per_entry_mean": f"{len(accepted)/len(selected):.2f}",
        "attestations_per_entry_median": f"{statistics.median(count_by_entry.values()):.1f}",
        "attestations_per_entry_min": min(count_by_entry.values()),
        "attestations_per_entry_max": max(count_by_entry.values()),
        "date_ranges_crossing_1600": sum(int(r["not_after"]) > 1600 for r in accepted),
    }
    for label, value in languages.items():
        updates["attestations_language_" + label.lower().replace(" ", "_")] = value
    for label, value in categories.items():
        updates["attestations_category_" + label.lower().replace("/", "_").replace(" ", "_")] = value
    for label, value in bands.items():
        updates["attestations_midpoint_" + label.casefold().replace(">", "post_").replace("-", "_").replace(" ", "_")] = value
    stats = read_csv(BASE / "data/stats_summary.csv")
    for row in stats:
        if row["stat_id"] in updates:
            row["value"] = str(updates[row["stat_id"]])
        if row["denominator"] == "485":
            row["denominator"] = str(len(accepted))
        row["source_table_version"] = row["source_table_version"].replace("v0.2.0", "v0.2.1")
        row["generating_script"] = "scripts/build_context_review_release.py"
        row["generation_timestamp"] = DATE
    write_csv(OUT / "data/stats_summary.csv", stats)
    write_json(OUT / "reports/publication_statistics.json", {"version": VERSION, "statistics": stats})

    # Remove excluded assertions from the active graph, retaining them in the review history tables.
    graph = Graph().parse(BASE / "rdf/musiconis_comma.ttl", format="turtle")
    dct = Namespace("http://purl.org/dc/terms/")
    prov = Namespace("http://www.w3.org/ns/prov#")
    lexicon = URIRef("https://w3id.org/musiconis-comma/lexicon")
    graph.set((lexicon, dct.hasVersion, Literal(VERSION)))
    graph.set((lexicon, dct.issued, Literal(DATE)))
    for aid, decision in by_id.items():
        uri = URIRef("https://w3id.org/musiconis-comma/attestation/" + aid.rsplit(":", 1)[1])
        if decision["decision"] == "exclude":
            graph.remove((uri, None, None))
        else:
            graph.set((uri, prov.wasGeneratedBy, URIRef("https://w3id.org/musiconis-comma/provenance/context-review-2026-09-12")))
    graph.serialize(OUT / "rdf/musiconis_comma.ttl", format="turtle")
    linked_data = json.loads((BASE / "rdf/musiconis_comma.jsonld").read_text())
    suffixes = {"attestation/" + aid.rsplit(":", 1)[1] for aid in rejected_ids}
    linked_data["@graph"] = [r for r in linked_data["@graph"] if r["@id"] not in suffixes]
    linked_data["@graph"][0]["dct:hasVersion"] = VERSION
    for row in linked_data["@graph"]:
        aid = "mmc:attestation:" + row["@id"].removeprefix("attestation/")
        if aid in by_id:
            row["prov:wasGeneratedBy"] = {"@id": "https://w3id.org/musiconis-comma/provenance/context-review-2026-09-12"}
    write_json(OUT / "rdf/musiconis_comma.jsonld", linked_data)
    examples = read_csv(BASE / "examples/five_reviewed_case_studies/case_study_index.csv")
    for row in examples:
        lemmas = row["requested_lemmas"].split("|")
        subset = [r for r in accepted if entry_by_id[r["entry_id"]]["lemma"] in lemmas]
        row["attestation_count"] = str(len(subset))
        row["manuscript_count"] = str(len({r["manuscript_id"] for r in subset}))
    write_csv(OUT / "examples/five_reviewed_case_studies/case_study_index.csv", examples)
    tables = {p.stem: list(read_csv(p)[0]) if read_csv(p) else
              json.loads((BASE / "schemas/tables.json").read_text())["tables"][p.stem]
              for p in sorted((OUT / "data").glob("*.csv"))}
    write_json(OUT / "schemas/tables.json", {"version": VERSION, "tables": tables})
    schema = json.loads((OUT / "schemas/attestations.schema.json").read_text())
    schema["title"] = "MusiCoMMA v0.2.1 accepted context"
    write_json(OUT / "schemas/attestations.schema.json", schema)
    checks = {
        "review_numbers_map_to_original_order": True,
        "accepted_plus_excluded_equal_original_ids": {r["attestation_id"] for r in all_rows} == {r["attestation_id"] for r in original},
        "accepted_excluded_disjoint": not ({r["attestation_id"] for r in accepted} & rejected_ids),
        "accepted_count": len(accepted) == 478, "excluded_count": len(excluded) == 7,
        "original_annotations_preserved": annotations[:485] == read_csv(BASE / "data/annotations.csv"),
        "annotation_count": len(annotations) == 495,
        "source_text_unchanged": all(r["context_with_match"] == o["context_with_match"] for r, o in zip(all_rows, original)),
        "remaining_475_records_unchanged": all(r == o for r, o in zip(all_rows, original) if r["attestation_id"] not in by_id),
        "image_check_not_invented": all(r["image_checked"] == "not_recorded" for r in all_rows),
        "manuscript_group_totals": sum(int(r["attestation_count"]) for r in mg) == len(accepted),
        "manuscript_totals": sum(int(r["attestation_count"]) for r in ms) == len(accepted),
        "annotation_foreign_keys": all(r["annotation_id"] in {a["annotation_id"] for a in annotations} for r in all_rows),
    }
    if not all(checks.values()):
        raise AssertionError(checks)
    row_counts = {p.stem: len(read_csv(p)) for p in sorted((OUT / "data").glob("*.csv"))}
    write_json(OUT / "reports/validation_report.json", {
        "version": VERSION, "build_date": DATE, "status": "PASS_WITH_DECLARED_PILOT_LIMITATIONS",
        "row_counts": row_counts, "integrity": checks,
        "limitations": ["Targeted same-author contextual review; not a random accuracy sample.",
                        "No image inspection or corrected reading supplied.",
                        "Seven exclusions have no author-supplied individual rationale.",
                        "Source-sense links are automatic, not newly adjudicated contextual senses."],
    })
    summary = {"accepted": len(accepted), "excluded": len(excluded), "manuscripts": len(ms),
               "entry_manuscript_groups": len(mg), "annotations": len(annotations),
               "linked": linked, "unresolved": unresolved, "languages": dict(languages),
               "categories": dict(categories), "date_bands": bands, "statistics_updates": updates}
    write_json(OUT / "reports/context_review_summary.json", summary)
    write_text(OUT / "VERSION", VERSION)
    description = (f"MusiCoMMA combines the Musiconis vocabulary (1,198 entries; 1,548 source-sense records) "
                   f"with a bounded CoMMA pilot covering 50 Latin/Old French entries. Version 0.2.1 retains "
                   f"{len(accepted)} contexts across {len(ms)} manuscript digitizations after Xavier Fresquet's "
                   "targeted contextual review of ten chantre windows: three retained and seven excluded. "
                   "The seven exclusions, all ten new decisions, and the original 485 annotation assertions are "
                   f"preserved separately. {unresolved} contexts remain sense-unresolved; {linked} are "
                   "automatically linked to a single source sense. No image inspection, corrected readings, "
                   "independent annotation or population-level accuracy estimate is claimed. "
                   "Musiconis, Sorbonne Université, is credited to Frédéric Billiet and Xavier Fresquet. "
                   "CoMMA is credited to Thibault Clérice, Simon Gabay, Malamatenia Vlachou-Efstathiou, "
                   "Ariane Pinche and Benoît Sagot (2025), HAL hal-05299220v2. No manuscript images or "
                   "bulk CoMMA files are redistributed.")
    write_text(OUT / "README.md", f"""# {TITLE}

{description}

## Reading the release

`data/attestations.csv` is the current accepted set. `data/excluded_contexts.csv`
contains seven excluded rows; do not merge them back into the accepted set.
`data/context_review_decisions.csv` records the ten numbered decisions.
`data/annotations.csv` preserves 485 prior assertions and appends ten superseding
assertions, for 495 annotation events, not 495 accepted contexts.
`history/v0.2.0/` preserves the historical tables verbatim. Stable context IDs and
HTR strings are unchanged. `data/selected_entries.csv` and retrieval counts
describe the original sampling operation and are not rewritten as acceptance counts.

## Interpretation

The author retained Troyes Ms. 521, Tournai Ms. 43 and Arras Ms. 226. The seven
other chantre rows are excluded by selection decision, not labelled as proven
HTR errors. No exclusion rationale or corrected word was supplied. Pierre le
Chantre is discussed as a possible author-name use in the manuscript; that
interpretation is not a new human sense annotation. Image checking remains
`not_recorded`, including for the retained rows. The review was prompted by
suspected problems, so 3/10 is not a precision estimate for chantre or CoMMA.

## Files, rights and citation

CSV tables are authoritative; JSONL and the active RDF graph contain the
corresponding representations. Source locators remain record-level, not verified
page or folio references. Data and documentation: CC BY 4.0. Executable code and
notebooks: MIT where `LICENSE-CODE` applies. See `review/RIGHTS_AND_APPROVAL.md`
for the source-owner authorization and coauthor deposit approval relayed by Xavier.
CoMMA paper: https://inria.hal.science/hal-05299220v2 .
CoMMA data: https://huggingface.co/datasets/comma-project/comma-jsonl .
No independent Musiconis vocabulary DOI has been confirmed. The Zenodo DOI is
not yet reserved; this is a local release candidate, not a published dataset.

The intended use is research and teaching; this is not an extra non-commercial
restriction. No image-reproduction permission or source-institution endorsement
is implied. HTR excerpts are not critical-edition transcriptions.
""")
    write_text(OUT / "DATA_DICTIONARY.md", """# Data dictionary: v0.2.1

Complete columns are listed in `schemas/tables.json`. Vocabulary tables retain
their v0.2.0 fields and identifiers. `attestations.csv` contains the accepted
set only; `excluded_contexts.csv` retains the seven excluded contexts and latest
decision provenance. Their `sense_id` is blank and the status is
`not_applicable_excluded`, not an alternative lexical sense.

`annotations.csv` is append-only event history, not one current label per row.
The ten new annotation IDs are linked to their predecessors by
`adjudication_relation=supersedes:<annotation_id>`. The accepted/excluded tables
point to the current assertion. `valid_occurrence=not_reassessed` in the new
events means that an include/exclude decision did not independently verify the
HTR word. `image_checked=not_recorded` is never an image confirmation.

`context_review_decisions.csv` preserves the numbered user response, with
`rationale=not_supplied` and blank `corrected_reading`. `review_events.csv`
contains the batch review and the later targeted review. Original annotation
targets remain recoverable in `history/v0.2.0/attestations.csv`.

`manuscripts.csv`, `manuscript_groups.csv` and `entry_groups.csv` summarize the
current accepted set. Original IDs and sequence values are not renumbered.
`coverage.csv` retains retrieval candidate counts but updates the accepted
count for chantre. Empty `candidates.csv` denotes the unused new-lexical-entry
proposal table; it does not mean that there are no excluded attestation contexts.
""")
    write_text(OUT / "CHANGELOG.md", f"""# Version 0.2.1 - {DATE}

- Applies the ten explicit decisions of Xavier Fresquet; three retained, seven excluded.
- Current evidence: {len(accepted)} contexts, {len(ms)} digitizations, {len(mg)} entry-manuscript groups.
- Preserves all original annotations and appends ten events; all vocabulary data and HTR strings are unchanged.
- Retains {unresolved} unresolved contexts and {linked} automatic single-source-sense links.
- Records Musiconis redistribution authorization and Frédéric Billiet's deposit agreement, relayed by Xavier.
- Credits Musiconis/Sorbonne Université, Frédéric Billiet and Xavier Fresquet; adds CoMMA's five authors and HAL version 2.
- Does not claim image verification, corrected readings, independent review, or journal acceptance.
""")
    write_text(OUT / "LICENSE_DATA.md", """# Data licence and source attribution

Data and documentation are prepared for release under CC BY 4.0:
https://creativecommons.org/licenses/by/4.0/ .

Musiconis, Sorbonne Université: Frédéric Billiet and Xavier Fresquet.
Redistribution authorization was confirmed by Xavier on 12 September 2026;
public accessibility alone is not the basis of this authorization.

CoMMA: Thibault Clérice, Simon Gabay, Malamatenia Vlachou-Efstathiou,
Ariane Pinche, Benoît Sagot (2025). *CoMMA, a Large-scale Corpus of Multilingual
Medieval Archives*, HAL hal-05299220v2, https://inria.hal.science/hal-05299220v2 .
Dataset: https://huggingface.co/datasets/comma-project/comma-jsonl , CC BY 4.0.
Changes: context extraction, vocabulary matching, restructuring and selection review.

No manuscript images or bulk CoMMA files are included. Source-institution rights
and notices are not replaced by this licence. No endorsement is implied.
Code is separately MIT-licensed where LICENSE-CODE applies.
""")
    cff = (BASE / "CITATION.cff").read_text().replace("0.2.0", VERSION).replace("2026-07-29", DATE)
    cff = cff.replace("Musiconis Vocabulary and Validated CoMMA Attestation Pilot", "Musiconis Vocabulary and Context-Reviewed CoMMA Pilot")
    write_text(OUT / "CITATION.cff", cff)
    metadata = json.loads((BASE / "ZENODO_METADATA.json").read_text())
    metadata.update(title=TITLE, version=VERSION, publication_date=DATE, description=description,
                    notes="Local candidate; no DOI yet. Deposit approval relayed by Xavier Fresquet. Context review is not image verification. No journal acceptance or publication claimed.")
    metadata["related_identifiers"] = [r for r in metadata["related_identifiers"] if r["identifier"] != "10.5281/zenodo.14163436"]
    metadata["related_identifiers"].append({"identifier": "https://inria.hal.science/hal-05299220v2", "relation": "references", "resource_type": "publication-preprint"})
    metadata["references"] = ["Clérice, T.; Gabay, S.; Vlachou-Efstathiou, M.; Pinche, A.; Sagot, B. (2025). CoMMA, a Large-scale Corpus of Multilingual Medieval Archives. HAL hal-05299220v2.", "Musiconis, Sorbonne Université. Frédéric Billiet and Xavier Fresquet. Source vocabulary; no independent DOI confirmed."]
    write_json(OUT / "ZENODO_METADATA.json", metadata)
    write_text(OUT / "DEPOSIT_CHECKLIST.md", """# Current deposit checklist

- [x] Ten numbered contextual decisions recorded; previous assertions preserved.
- [x] Musiconis redistribution authorization recorded from Xavier Fresquet.
- [x] Frédéric Billiet's agreement to deposit recorded as relayed by Xavier.
- [x] Both MusiCoMMA authors and distinct Musiconis/CoMMA source credits included.
- [x] CoMMA dataset CC BY 4.0 checked against its dataset card; paper version supplied by author.
- [ ] Execute the updated notebook and add its outputs to the final package.
- [ ] Reserve the Zenodo DOI, add it to citations and metadata, then verify the final archive.
- [ ] Confirm final display of affiliations/contributions and any funding declaration.
- [ ] Check current JCA anonymous-review/data-sharing instructions; anonymity alone does not establish a prepublication ban.
- [ ] Publish only after reviewing this candidate and confirming the final form.
""")
    finalize()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize", action="store_true", help="Refresh checksums/archive after adding verified outputs")
    parser.add_argument("--baseline-zip", type=Path, default=BASE_ZIP)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--review-dir", type=Path, default=REVIEW)
    args = parser.parse_args()
    BASE_ZIP = args.baseline_zip.resolve()
    OUT = args.output.resolve()
    REVIEW = args.review_dir.resolve()
    if args.finalize:
        finalize()
    else:
        if sha256(BASE_ZIP) != BASE_SHA256:
            raise ValueError("Frozen baseline archive changed")
        with tempfile.TemporaryDirectory(prefix="musicomma-baseline-") as tmp:
            with zipfile.ZipFile(BASE_ZIP) as archive:
                if any(Path(n).is_absolute() or ".." in Path(n).parts for n in archive.namelist()):
                    raise ValueError("Unsafe archive member")
                archive.extractall(tmp)
            frozen = Path(tmp) / BASE.name
            for source in (frozen / "data").glob("*.csv"):
                if BASE.exists() and source.read_bytes() != (BASE / "data" / source.name).read_bytes():
                    raise ValueError(f"Unpacked data differ from archive: {source.name}")
            BASE = frozen
            build()
