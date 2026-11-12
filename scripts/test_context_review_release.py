"""Integrity tests for the explicit ten-window contextual review."""

import csv
import hashlib
import json
import os
import unittest
from pathlib import Path

from rdflib import Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path(os.environ.get("MUSICOMMA_DATA_ROOT", ROOT / "release/musiconis-comma-v0.2.1-zenodo"))


def rows(name):
    with (RELEASE / name).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


class ContextReviewTests(unittest.TestCase):
    def test_numbered_decisions(self):
        decisions = rows('data/context_review_decisions.csv')
        original = [r for r in rows('history/v0.2.0/attestations.csv') if r['entry_id'] == 'mmc:entry:5b48e7fd337d86e9']
        self.assertEqual([d['number'] for d in decisions], list(map(str, range(1, 11))))
        self.assertEqual([d['attestation_id'] for d in decisions], [r['attestation_id'] for r in original])
        self.assertEqual([d['number'] for d in decisions if d['decision'] == 'accept'], ['7', '8', '10'])
        self.assertTrue(all(d['image_checked'] == 'not_recorded' and d['rationale'] == 'not_supplied' for d in decisions))

    def test_partition_and_source_preservation(self):
        accepted = rows('data/attestations.csv')
        excluded = rows('data/excluded_contexts.csv')
        old = {r['attestation_id']: r for r in rows('history/v0.2.0/attestations.csv')}
        current = accepted + excluded
        self.assertEqual((len(accepted), len(excluded)), (478, 7))
        self.assertEqual(len({r['attestation_id'] for r in current}), 485)
        self.assertEqual(set(old), {r['attestation_id'] for r in current})
        reviewed = {r['attestation_id'] for r in rows('data/context_review_decisions.csv')}
        for r in current:
            self.assertEqual(r['context_with_match'], old[r['attestation_id']]['context_with_match'])
            if r['attestation_id'] not in reviewed:
                self.assertEqual(r, old[r['attestation_id']])

    def test_history_and_foreign_keys(self):
        assertions = rows('data/annotations.csv')
        self.assertEqual(assertions[:485], rows('history/v0.2.0/annotations.csv'))
        self.assertEqual(len(assertions), 495)
        self.assertEqual(len({r['annotation_id'] for r in assertions}), 495)
        events = {r['validation_event_id'] for r in rows('data/review_events.csv')}
        provenance = {r['provenance_id'] for r in rows('data/provenance.csv')}
        for r in assertions:
            self.assertIn(r['validation_event_id'], events)
            self.assertIn(r['provenance_id'], provenance)
        for r in rows('data/attestations.csv') + rows('data/excluded_contexts.csv'):
            self.assertIn(r['annotation_id'], {a['annotation_id'] for a in assertions})
        for r in assertions[485:]:
            self.assertIn(r['adjudication_relation'].removeprefix('supersedes:'), {a['annotation_id'] for a in assertions[:485]})

    def test_counts_and_group_membership(self):
        accepted = rows('data/attestations.csv')
        groups = rows('data/manuscript_groups.csv')
        manuscripts = rows('data/manuscripts.csv')
        self.assertEqual((len(groups), len(manuscripts)), (475, 378))
        self.assertEqual(sum(int(r['attestation_count']) for r in groups), 478)
        self.assertEqual({r['manuscript_id'] for r in accepted}, {r['manuscript_id'] for r in manuscripts})
        self.assertEqual(sum(r['sense_assignment_status'] == 'entry_validated_sense_unresolved' for r in accepted), 330)
        stats = {r['stat_id']: r['value'] for r in rows('data/stats_summary.csv')}
        self.assertEqual(stats['single_sense_linked'], '148')
        for group in groups:
            self.assertEqual(set(group['attestation_ids'].split('|')), {r['attestation_id'] for r in accepted if r['manuscript_group_id'] == group['manuscript_group_id']})

    def test_active_serializations(self):
        accepted = rows('data/attestations.csv')
        for name in ('attestations', 'annotations', 'excluded_contexts'):
            data = [json.loads(line) for line in (RELEASE / f'jsonl/{name}.jsonl').read_text().splitlines()]
            self.assertEqual(data, rows(f'data/{name}.csv'))
        graph = Graph().parse(RELEASE / 'rdf/musiconis_comma.ttl')
        jsonld = json.loads((RELEASE / 'rdf/musiconis_comma.jsonld').read_text())
        ids = {r['@id'].split('/')[-1] for r in jsonld['@graph'] if r['@id'].startswith('attestation/')}
        self.assertEqual(ids, {r['attestation_id'].split(':')[-1] for r in accepted})
        for r in rows('data/excluded_contexts.csv'):
            uri = URIRef('https://w3id.org/musiconis-comma/attestation/' + r['attestation_id'].split(':')[-1])
            self.assertFalse(list(graph.triples((uri, None, None))))

    def test_checksums(self):
        for line in (RELEASE / 'checksums.sha256').read_text().splitlines():
            expected, name = line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((RELEASE / name).read_bytes()).hexdigest(), expected, name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
