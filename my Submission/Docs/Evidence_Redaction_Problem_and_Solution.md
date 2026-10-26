# Structured Evidence Redaction — Problem and Solution


This document describes the solution I intend to deliver for the fictional LarchTrace assessment. The examples describe the required behavior; they are not a record of development history. The supplied render contract (RC1–RC4) remains the authoritative specification.

## 1. The problem

The existing Python application reads a JSON file containing scanner evidence, validates the records, sorts them by their IDs, and prints formatted JSON. Evidence can contain nested objects and arrays.

The problem is that the renderer currently prints sensitive values unchanged. Even when the input supplies a redaction policy, the starter ignores it. A team sharing the rendered evidence could therefore expose values that the policy explicitly identifies for removal.

My task is to extend the renderer so that it replaces values under configured keys with `[REDACTED]` and reports where those replacements occurred.

```text
BEFORE
Input JSON + policy --> Existing renderer --> Formatted evidence
                         policy ignored       sensitive values visible

AFTER
Input JSON + policy --> Extended renderer --> Redacted evidence
                         policy enforced      + count and affected paths
```

This is an exact-key JSON transformation. It does not infer which values are secrets, search ordinary text, or use an AI model.

## 2. What is provided

| File | Role |
| --- | --- |
| `app.py` | Working renderer to extend. |
| `inputs/render-contract.md` | Rules for compatibility, validation, redaction and audit. |
| `inputs/primary.json` | Eight records with a `token` / `password` policy. |
| `inputs/secondary.json` | Eight records with a refreshed `token` / `session` policy. |
| `inputs/legacy.json` | No-policy fixture used to protect existing behavior. |
| `inputs/malformed-input.txt` | Truncated JSON for testing error handling. |
| `tests/app_test.py` | Starter smoke checks; these do not prove feature correctness. |
| `README.md` | Assessment requirements, submission instructions and scoring. |

## 3. The behavior I need to preserve

The extension must remain compatible with existing callers. Without `redaction_policy`, the output must be identical to the starter, including its bytes, stderr and exit status.

That means preserving:

- One-space indentation, ASCII escaping and the final newline.
- Record sorting by raw `record_id`, including surrounding whitespace.
- Existing envelope and record validation.
- Array order, JSON types and unrelated values.
- The existing `--input` option and its default, `inputs/primary.json`.
- Ignoring unknown envelope and record fields.
- No redaction audit when a policy is absent.

For example, `" L02 "` sorts before `"L01"` because it starts with a space. I will preserve this behavior rather than trim the identifier.

## 4. Solution overview

I will keep the existing renderer and add three focused responsibilities: policy validation, recursive replacement and audit collection.

```text
Read file and parse JSON
          |
          v
Check that the envelope is an object
          |
          v
Is redaction_policy present?
          |
     +----+-----------------------+
     | No                         | Yes
     v                            v
Use legacy mode             Validate policy
     |                            |
     |                       +----+----------+
     |                       | Valid         | Invalid
     |                       v               v
     |                 Use policy mode   stderr: fixed error
     |                       |           stdout: empty
     |                       |           exit: 2
     +-----------+-----------+
                 |
                 v
        Validate and sort records
                 |
                 v
       Copy each record's evidence
       (redact only in policy mode)
                 |
                 v
       Add audit only in policy mode
                 |
                 v
       Print JSON to stdout; exit 0
```

Policy validation happens before record validation. If both are invalid, the policy error must be reported first.

### Function responsibilities

| Function | Responsibility |
| --- | --- |
| `main()` | Read input, check the envelope, serialize output and handle fatal errors. |
| `validate_records()` | Preserve the existing record-validation rules. |
| `render_value()` | Preserve the original recursive copy behavior for no-policy inputs. |
| `validate_policy()` | Accept only the policy structure defined by RC2. |
| `escape_pointer_segment()` | Escape object-key segments for JSON Pointer paths. |
| `redact_value()` | Copy nested evidence, replace matching values and collect paths. |
| `render_evidence()` | Coordinate validation, record sorting, rendering and the audit. |

## 5. Policy validation

A valid policy is an object containing exactly `keys`, whose value is an array of distinct, nonempty strings.

```json
{
  "redaction_policy": {
    "keys": ["token", "password"]
  }
}
```

Keys are used exactly as supplied. I will not trim whitespace or change letter case.

| Policy value | Result |
| --- | --- |
| `{"keys": ["token", "password"]}` | Valid. |
| `{"keys": []}` | Valid; produces an audit with zero replacements. |
| `{"keys": [" "]}` | Valid; matches an object key consisting of one space. |
| `{"keys": ["token", "Token"]}` | Valid; these are distinct keys. |
| `null` | Invalid; present is different from absent. |
| `{}` | Invalid; missing `keys`. |
| `{"keys": "token"}` | Invalid; the value must be an array. |
| `{"keys": [""]}` | Invalid; empty strings are forbidden. |
| `{"keys": ["token", "token"]}` | Invalid; duplicates are forbidden. |
| `{"keys": [123]}` | Invalid; all entries must be strings. |
| `{"keys": ["token"], "extra": true}` | Invalid; additional properties are forbidden. |

Every invalid policy must produce exactly this diagnostic, followed by a newline:

```text
error: invalid redaction_policy
```

The exit status is `2` and stdout is empty. The diagnostic must not echo supplied policy values.

## 6. Before and after: complete example

### Input

```json
{
  "records": [
    {
      "record_id": "R01",
      "evidence": {
        "password": "DEMO-P01",
        "token": "DEMO-T01",
        "Token": "case-visible"
      }
    }
  ],
  "redaction_policy": {
    "keys": ["token", "password"]
  }
}
```

### Before: starter output

The policy is ignored, so both sensitive values remain visible.

```json
{
 "records": [
  {
   "evidence": {
    "Token": "case-visible",
    "password": "DEMO-P01",
    "token": "DEMO-T01"
   },
   "record_id": "R01"
  }
 ],
 "summary": {
  "records": 1
 }
}
```

### After: required output

```json
{
 "records": [
  {
   "evidence": {
    "Token": "case-visible",
    "password": "[REDACTED]",
    "token": "[REDACTED]"
   },
   "record_id": "R01"
  }
 ],
 "redaction": {
  "count": 2,
  "paths": [
   "/records/0/evidence/password",
   "/records/0/evidence/token"
  ]
 },
 "summary": {
  "records": 1
 }
}
```

`Token` is retained because it does not exactly match `token`. The key names and record ID are unchanged. The removed values do not appear in the audit.

## 7. Recursive replacement and edge cases

The decision is based on the object key, never on whether its value is truthy.

```text
redact(value, path)
 |
 +-- Object
 |    |
 |    +-- For each key:
 |         |
 |         +-- Key matches policy?
 |              |
 |              +-- YES: replace entire value
 |              |        record this path once
 |              |        STOP for this subtree
 |              |
 |              +-- NO: recurse into its value
 |
 +-- Array: recurse into each element using its index
 |
 +-- Primitive: return unchanged
```

### False, zero, null and empty values

With `{"keys": ["password", "token"]}`:

| Before | After |
| --- | --- |
| `{"password": false}` | `{"password": "[REDACTED]"}` |
| `{"token": 0}` | `{"token": "[REDACTED]"}` |
| `{"token": null}` | `{"token": "[REDACTED]"}` |
| `{"token": ""}` | `{"token": "[REDACTED]"}` |
| `{"token": []}` | `{"token": "[REDACTED]"}` |
| `{"token": {}}` | `{"token": "[REDACTED]"}` |
| `{"safe": false}` | Unchanged. |
| `{"Token": "visible"}` | Unchanged. |
| `{"tokenized": "visible"}` | Unchanged. |
| `{"message": "token text is ordinary"}` | Unchanged. |

### Whole-container replacement: R05

```text
BEFORE                               AFTER

evidence                             evidence
+-- token                            +-- token: "[REDACTED]"
|   +-- password: DEMO-hidden-child   +-- status: "ok"
|   +-- safe: DEMO-hidden-sibling
+-- status: "ok"
```

The `token` key matches, so its whole object is removed. This is one replacement, even though several values disappear. Descendants are neither visited nor separately audited.

### Nested arrays: R07

```text
evidence
+-- list
    +-- [0]
    |   +-- [0]
    |       +-- password: "[REDACTED]"
    +-- [1]: null
    +-- [2]: 2.5

Audit: /records/6/evidence/list/0/0/password
```

Array positions remain unchanged. The safe `null` and numeric value remain unchanged too.

## 8. Audit paths and sorting

A path points into the sorted output, not the original input order.

```text
INPUT ORDER                      SORTED OUTPUT
R03                              index 0: R01
R01           -- sort IDs -->    index 1: R02
R02                              index 2: R03
...

R03 token path: /records/2/evidence/attempts/1/token
```

Object-key segments use JSON Pointer escaping:

| Original segment | Escaped segment |
| --- | --- |
| `a/b` | `a~1b` |
| `~meta` | `~0meta` |
| `~/` | `~0~1` |

I will escape `~` first and `/` second, then sort the complete paths lexicographically. The audit count equals the number of paths.

Lexicographic order is string order: if indices reach two digits, `/records/10/...` sorts before `/records/2/...`. The paths must still identify the correct numeric output positions.

## 9. Expected results for both supplied policies

The same code must handle both fixtures without hardcoded field names or record-specific branches.

| Record | Primary: token/password | Secondary: token/session |
| --- | --- | --- |
| R01 | Password and token replaced: 2. | Session and token replaced: 2; password retained. |
| R02 | Nested token replaced: 1. | Nested token replaced: 1. |
| R03 | Attempt password and empty token replaced: 2. | Empty token replaced: 1; password retained. |
| R04 | False password and zero token replaced: 2. | Zero token replaced: 1; false password retained. |
| R05 | Whole token object replaced: 1. | Whole token object replaced: 1. |
| R06 | Password under escaped keys replaced: 1. | Session under escaped keys replaced: 1. |
| R07 | Password inside nested arrays replaced: 1. | Session inside nested arrays replaced: 1. |
| R08 | No replacements. | No replacements. |
| **Total** | **8 records, 10 replacements.** | **8 records, 8 replacements.** |

For both policy fixtures, no original `DEMO-` value may appear anywhere in serialized success output or diagnostics. Counts alone are insufficient: evidence values, retained controls and exact paths must also match.

## 10. Implementation and verification plan

1. **Capture the baseline before editing.** Save the starter's complete legacy stdout and stderr, and assert exit status `0`. The supplied legacy output is 303 bytes. A golden test must compare raw bytes, not only parsed JSON.
2. **Add acceptance tests.** Express the expected primary and secondary evidence, exact paths and invalid-policy behavior. Run feature tests against the starter to demonstrate the missing feature.
3. **Implement strict policy validation.** Check policy presence explicitly and reject invalid policies before validating records.
4. **Implement recursive copying and redaction.** Build new objects and arrays, stop at matched keys, and preserve other values and types.
5. **Integrate the audit.** Sort records first, use their output indices, escape pointer segments and sort the final paths.
6. **Run regressions.** Verify the legacy baseline and both fixtures with the same implementation. Repeat calls on the same input and confirm that neither call changes it.
7. **Document real findings.** Record actual failed checks, corrections and reruns. Do not invent development failures or AI mistakes.

### Test checklist

- [ ] Legacy stdout bytes, stderr and exit status match the starter.
- [ ] Primary and secondary evidence and audit paths match exact expectations.
- [ ] Matching is case-sensitive and does not trim keys.
- [ ] False, zero, null, empty strings, objects and arrays are replaced.
- [ ] Replaced containers produce one path and no descendant paths.
- [ ] Nested arrays preserve positions and unrelated JSON types.
- [ ] Pointer segments containing `~` and `/` are escaped correctly.
- [ ] Absent policy and valid empty policy behave differently.
- [ ] Empty records and whitespace-only policy keys are supported.
- [ ] Invalid policies produce the fixed diagnostic before record errors.
- [ ] Fatal cases have no partial stdout.
- [ ] Successful policy fixtures have empty stderr and no sensitive sentinels in either stream.
- [ ] Repeated calls return equal results without modifying input.

## 11. Running and handing over the solution

Use Python 3.10 or later. Run commands from the directory containing `app.py`:

```sh
python3 --version
python3 -B app.py --help
python3 -B -m unittest discover -s tests -p '*_test.py' -v
python3 -B app.py --input inputs/legacy.json
python3 -B app.py --input inputs/primary.json
python3 -B app.py --input inputs/secondary.json
python3 -B app.py --input inputs/malformed-input.txt
python3 -B app.py --input inputs/does-not-exist.json
```

The final two commands are deliberate failure checks. They should return exit `2`, empty stdout and readable stderr. Exit `3` remains reserved and unused, as in the starter.

The submission should contain runnable source, tests, the supplied inputs, a concise run guide, a decision/work log, an honest AI-use note and a 3–5 minute walkthrough recording or equivalent accessible text. Generated Python cache files are not needed.

## 12. Limits

This feature only hides values under explicitly configured keys inside evidence. It does not identify unknown secrets, redact ordinary text, or modify record IDs and key names. Unknown envelope and record fields remain ignored by the existing renderer.

The audit records locations, not removed values. The feature is not encryption and does not guarantee complete sanitization of arbitrary data.

My goal is a small, verifiable extension that follows RC1–RC4 and preserves the original behavior for existing users.
