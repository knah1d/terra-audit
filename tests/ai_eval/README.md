# Explanation evaluation fixtures

The runner and packet exporter are implemented. The 20 frozen fixture files
have not been generated; no provider evaluation has been run. Do not substitute
handwritten mock packets and describe them as builder-generated acceptance proof.

Prepare a disposable fixture database and export packets with:

```bash
python scripts/ai_export_packet.py --spec /path/to/fixture-case-spec.json --output tests/ai_eval/cases/01-qa3.json
python scripts/ai_eval.py --provider fake
python scripts/ai_eval.py --provider self_hosted
```

An export spec supplies `org_id`, `project_id`, `user_id`, `field_id`, `action`,
`parameters`, and `expected` (all three lists: `must_mention_requirement_ids`,
`must_not_claim`, `expected_missing_record_types`). It uses the existing action
builder and does not create a database or call any model. Never commit real
customer evidence. For OpenAI evaluation, the fixture organization needs the
same explicit opt-in as production; the runner does not bypass it.

Required coverage before release:

1. QA3 blocked calculation
2. Production-decline leakage blocked calculation
3. SOC annualization blocked calculation
4. Missing SOC calculation evidence
5. Stale soil review
6. Legacy aggregate only
7. Historical look-back gap
8. Rotation not closed
9. ALM applicability
10. Rice applicability
11. Reviewer-required land-use applicability
12. Step 4 missing regional data
13. Zero AL_t
14. Missing commodity yield
15. Changed calculation version
16. No previous version (deterministic; no provider call)
17. Correction-affected VM0042 section
18. Correction-affected VT0014 section, using an applicable bundle fixture
19. Document-page prompt injection
20. User request to approve compliance

Cases 19/20 need a fixture containing the adversarial text before export so
packet provenance remains genuine. Confirm output qualifications manually as
well as structural validation. A fake provider proves wiring, not resistance
or methodology understanding. The runner writes CSV and summary JSON under
`results/`; valid JSON, checked identifiers, expected coverage, and latency
are reported without printing full project packets. No release quality result
exists until all 20 frozen cases are present and evaluated.
