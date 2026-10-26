# LarchTrace render contract

RC1. The supplied renderer defines legacy behavior. Without `redaction_policy`, preserve exact stdout bytes, stderr and exit status, including one-space indentation, ASCII escapes, final newline and raw record IDs. Do not add audit fields. Keep envelope/record validation and record sorting. Unknown envelope/record fields remain ignored.

RC2. A present `redaction_policy` must be an object containing exactly `keys`: an array of distinct, nonempty strings. No trimming or case normalization; whitespace-only strings are legal exact keys. Empty array is legal. Invalid policy is fatal: exit 2, empty stdout, fixed message `error: invalid redaction_policy` on stderr. Check policy before record validation.

RC3. Within each record's `evidence`, replace the entire value of every exact, case-sensitive matching object key with `[REDACTED]`, including null, false, zero, empty strings, objects and arrays. Do not descend into a replaced subtree. Traverse all other objects and arrays. Do not redact record IDs or key names. Preserve other values and JSON types.

RC4. Policy output keeps the legacy structure and adds `redaction: {"count": N, "paths": [...]}`. Paths are JSON Pointers into the sorted output records, escaping `~` as `~0` and `/` as `~1`; array indices are zero-based. Sort paths lexicographically, count each replacement once. Never include removed values in output or diagnostics. Do not mutate the input; repeated calls are identical.
