# Extend an existing evidence renderer

This is one Software Engineer Intern assessment with a **24-hour** window. Your recruiter assigns one exercise from the bank. Your 24 hours start when you click **Start** on the link in your invitation email; the exercise zip becomes available at that moment. Send your submission back within 24 hours of clicking Start. You are not expected to work for the full 24 hours: organize your own working time and breaks within the window. There are no surprise messages or overnight availability requirements, and hours worked are not scored. Follow-through and verification matter more than hours or volume.

The fictional LarchTrace scanning platform has a working nested-evidence renderer. At the scenario snapshot, **2026-12-09 09:00 UTC+00:00**, another team requests explicit redaction before sharing rendered evidence. Extend their code while keeping existing no-policy output byte-identical. The scenario date is separate from your submission clock. All `DEMO-` values are nonfunctional synthetic markers.

All companies, tenants, assets and product behavior here are **fictional assessment facts**. The supplied fixtures are the authoritative universe. Outside research is optional and cannot affect marks. Do not contact real systems, send real messages, publish, or use production credentials.

## Supplied inputs and setup

You need basic Python, JSON, CLI use, tests, recursive objects/arrays and familiarity with reading unfamiliar code. A golden test compares complete captured output bytes. Python **3.10 or later**, its standard library and a local editor are sufficient; no packages, accounts, paid tools, web access or company framework are needed.

- [Existing renderer](app.py): working legacy behavior; it currently ignores the new policy field.
- [Render contract](inputs/render-contract.md): authoritative RC1–RC4 policy, paths, validation and compatibility rules.
- [Primary fixture](inputs/primary.json): eight structured evidence records and the initial policy.
- [Legacy fixture](inputs/legacy.json): no policy; capture its current output before editing.
- [Second fixture](inputs/secondary.json): a refreshed policy and new evidence, using the same schema.
- [Malformed input](inputs/malformed-input.txt): deliberately truncated JSON for error handling.
- [Starter smoke checks](tests/app_test.py): four infrastructure checks, **not feature acceptance tests**.

From the exported `candidate/` directory:

```sh
python3 --version
python3 -B app.py --help
python3 -B -m unittest discover -s tests -p '*_test.py' -v
python3 -B app.py --input inputs/legacy.json
python3 -B app.py --input inputs/primary.json
python3 -B app.py --input inputs/secondary.json
```

The smoke suite initially passes. All three fixture commands already exit **0** with JSON and empty stderr, but the primary and secondary commands currently leave sensitive values visible and have no redaction audit. This is intentional unfinished feature behavior, not a setup failure. Malformed JSON or a missing file returns **2**, no stdout and a readable stderr diagnostic; **3** is reserved for a starter placeholder and is unused here. Preserve `--input`, its default and those exit conventions.

## Core task and observable acceptance criteria

Build a usable extension implementing RC1–RC4. Use JSON on stdout for success and diagnostics on stderr for fatal errors. Explain assumptions without silently changing rules.

1. **Characterize first.** Before editing, capture the full no-policy stdout, stderr and exit status in reusable golden tests and show they pass against the starter. Preserve odd formatting, ASCII escaping and raw record IDs. Record suspected legacy bugs instead of fixing them during this extension.
2. Add explicit policy validation and recursive redaction within evidence, using exact case-sensitive object keys. Arrays may contain more arrays and objects. A matched key replaces its entire value with `[REDACTED]` regardless of type or truthiness; do not inspect or audit descendants of a replaced value. Keep all unrelated JSON values, types and array positions.
3. With policy present, add the exact count and sorted JSON-pointer path audit defined in RC4. Keep record sorting and generate paths using the sorted output positions. Without policy, add nothing. Invalid policies must produce the fixed safe diagnostic and exit 2 before record validation, without echoing supplied values.
4. Build meaningful automated tests that assert golden bytes, recursive results, escaped pointer segments, exact-key controls, empty/false/zero/null replacements, an entire matched container, invalid policy handling and unchanged input across repeated calls. Include a constructed boundary case and an executed failure/refinement. Search serialized success output and diagnostics for sensitive test sentinels; testing just the displayed evidence is insufficient.
5. Apply the same renderer and tests **unchanged to the second fixture**. Reconcile each affected path, explain changed and unchanged behavior under the refreshed policy, and record any refinement with a primary regression rerun. A static answer table without reusable code and assertions is incomplete.

Primary self-check after implementation: **8 records, 10 replacements**. R04's false password and zero token both become the marker. R05's whole token object becomes one marker, counted once. `Token`, `tokenized` and ordinary text containing “token” stay unchanged. No original `DEMO-` value from either policy fixture may appear anywhere in serialized output. Counts alone are insufficient: check the specific paths and retained controls.

Keep envelope/record validation from the working renderer; do not add a second conflicting interpretation. Test empty records and empty key lists. Document the limit: exact key policy cannot identify secrets under unknown keys or in ordinary text. Do not claim complete sanitization or real-world scanner coverage.

After implementation, repeat the fixture and smoke commands above. Legacy bytes must match the capture, policy fixtures must match RC1–RC4, and invalid cases must have no partial stdout. A clear, tested core earns full marks. Optional stretch: add one useful test or local developer aid; no stretch is necessary. A service, database, large framework or public deployment is outside the core scope.

## Time and AI use

Plan your own time within the 24-hour window. Prioritize the core contract and leave time for verification instead of adding features.

**AI is allowed and encouraged** for coding, explanation, test generation, critique and optional research. Tool choice is not graded. No AI tool is provided; you may use any AI tool you already have, and no purchase is required. Free/offline tools and completing the exercise without AI are supported. Check AI output against the rules, input rows and executed tests. Submit a short AI-use note with one concrete accepted, corrected or rejected output and how you checked it; if you did not use AI, state that. Do not invent an AI failure or share complete prompt histories, private account access, or secrets.

## Submission

Submit an archive or repository containing runnable source, tests, the supplied inputs, and:

1. A short run guide with exact commands for all fixtures and the meaningful checks; include representative outputs or assertions with record IDs and redaction paths.
2. A concise decision/work log: priorities and what you deferred; one obstacle and response; one validation/refinement; known limits and next step. Cite record IDs or JSON paths as evidence, and note odd existing behavior you preserved.
3. The AI-use note described above.
4. A 3–5 minute walkthrough recording **or equivalent accessible text** explaining the core workflow, one edge case, and evidence of execution.

You do not need a public repository, deployment, PDF or proprietary tools. Document incomplete behavior honestly. Do not submit only a design or report: the runnable feature and reproducible tests are the primary deliverables.

Published scoring: **usable result 40, accuracy/verification 25, prioritization 20, communication/handoff 15**. Full marks are available on the core alone. Tool choice, AI-detector judgments, prose polish, hours worked and sheer output volume are not scored.
