"""Acceptance tests for policy-driven redaction: contract rules RC1-RC4."""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import typing
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
MARKER = "[REDACTED]"


def _run(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run the CLI without writing .pyc files, capturing raw bytes."""
    return subprocess.run(
        [sys.executable, "-B", "app.py", *arguments],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )


def _render(fixture: str) -> dict[str, typing.Any]:
    result = _run("--input", fixture)
    if result.returncode != 0:
        raise AssertionError(f"unexpected failure: {result.stderr!r}")
    return json.loads(result.stdout)


def _run_payload(payload: typing.Any) -> subprocess.CompletedProcess[bytes]:
    """Write a synthetic payload to a temporary fixture and run the CLI on it."""
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return _run("--input", str(path))


def _evidence(result: dict[str, typing.Any]) -> list[dict[str, typing.Any]]:
    """Return [{record_id: evidence}] in rendered (sorted) order."""
    return [{record["record_id"]: record["evidence"]} for record in result["records"]]


class LegacyGoldenTest(unittest.TestCase):
    """RC1: with no policy, output must stay byte-for-byte identical."""

    def testLegacy_whenNoPolicy_preservesCapturedBytes(self) -> None:
        result = _run("--input", "inputs/legacy.json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, (GOLDEN / "legacy.stderr").read_bytes())
        self.assertEqual(result.stdout, (GOLDEN / "legacy.stdout").read_bytes())
        self.assertNotIn(b'"redaction"', result.stdout)

    def testLegacy_whenNoPolicy_keepsOddRecordIdOrdering(self) -> None:
        result = _render("inputs/legacy.json")
        order = [record["record_id"] for record in result["records"]]
        self.assertEqual(order, [" L02 ", "L01"])


class PrimaryFixtureTest(unittest.TestCase):
    """RC3/RC4 against inputs/primary.json (policy: token, password)."""

    def testPrimary_whenPolicySupplied_redactsExactKeys(self) -> None:
        result = _render("inputs/primary.json")
        self.assertEqual(sorted(result), ["records", "redaction", "summary"])
        self.assertEqual(result["summary"], {"records": 8})
        self.assertEqual(
            _evidence(result),
            [
                {"R01": {"Token": "case-visible", "password": MARKER, "token": MARKER}},
                {"R02": {"nested": {"safe": {"count": 0, "enabled": False}, "token": MARKER},
                         "note": "operator-visible"}},
                {"R03": {"attempts": [{"password": MARKER}, {"status": 200, "token": MARKER}],
                         "tokenized": "public-tokenized"}},
                {"R04": {"password": MARKER, "safe": None, "token": MARKER}},
                {"R05": {"status": "ok", "token": MARKER}},
                {"R06": {"a/b": {"~meta": {"password": MARKER}}, "host": "api.example.test"}},
                {"R07": {"list": [[{"password": MARKER}], None, 2.5], "unicode": "café"}},
                {"R08": {"empty": [], "message": "token text is ordinary", "status": "done"}},
            ],
        )

    def testPrimary_whenPolicySupplied_reportsTenSortedPaths(self) -> None:
        result = _render("inputs/primary.json")
        self.assertEqual(result["redaction"]["count"], 10)
        self.assertEqual(
            result["redaction"]["paths"],
            [
                "/records/0/evidence/password",
                "/records/0/evidence/token",
                "/records/1/evidence/nested/token",
                "/records/2/evidence/attempts/0/password",
                "/records/2/evidence/attempts/1/token",
                "/records/3/evidence/password",
                "/records/3/evidence/token",
                "/records/4/evidence/token",
                "/records/5/evidence/a~1b/~0meta/password",
                "/records/6/evidence/list/0/0/password",
            ],
        )

    def testPrimary_whenPolicySupplied_leaksNoSyntheticMarkers(self) -> None:
        result = _run("--input", "inputs/primary.json")
        self.assertNotIn(b"DEMO-", result.stdout)
        self.assertNotIn(b"DEMO-", result.stderr)


class SecondaryFixtureTest(unittest.TestCase):
    """Same renderer, refreshed policy (RC2-RC4): no key list is hardcoded."""

    def testSecondary_whenPolicyChanges_followsSuppliedKeys(self) -> None:
        result = _render("inputs/secondary.json")
        self.assertEqual(
            _evidence(result),
            [
                {"R01": {"Token": "case-visible", "password": "public-password-field",
                         "session": MARKER, "token": MARKER}},
                {"R02": {"nested": {"safe": {"count": 0, "enabled": False}, "token": MARKER},
                         "note": "review-visible"}},
                {"R03": {"attempts": [{"password": "public-sample"}, {"status": 200, "token": MARKER}],
                         "tokenized": "public-tokenized"}},
                {"R04": {"password": False, "safe": None, "token": MARKER}},
                {"R05": {"status": "ok", "token": MARKER}},
                {"R06": {"a/b": {"~meta": {"session": MARKER}}, "host": "api.example.test"}},
                {"R07": {"list": [[{"session": MARKER}], None, 2.5], "unicode": "café"}},
                {"R08": {"empty": [], "message": "token text is ordinary", "note": "retained-note",
                         "status": "done"}},
            ],
        )
        self.assertEqual(result["redaction"]["count"], 8)
        self.assertEqual(
            result["redaction"]["paths"],
            [
                "/records/0/evidence/session",
                "/records/0/evidence/token",
                "/records/1/evidence/nested/token",
                "/records/2/evidence/attempts/1/token",
                "/records/3/evidence/token",
                "/records/4/evidence/token",
                "/records/5/evidence/a~1b/~0meta/session",
                "/records/6/evidence/list/0/0/session",
            ],
        )
        self.assertNotIn(b"DEMO-", _run("--input", "inputs/secondary.json").stdout)


class ValueTypeTest(unittest.TestCase):
    """RC3: matching depends on the key, never on value truthiness or type."""

    def testRedaction_whenValuesAreFalsyOrContainers_replacesEachWhole(self) -> None:
        payload = {
            "records": [{"record_id": "T1", "evidence": {
                "s": "secret", "e": "", "f": False, "z": 0, "n": None,
                "o": {"password": "child", "safe": "sibling"}, "a": ["x"],
            }}],
            "redaction_policy": {"keys": ["s", "e", "f", "z", "n", "o", "a"]},
        }
        result = json.loads(_run_payload(payload).stdout)
        self.assertEqual(result["records"][0]["evidence"], {
            "s": MARKER, "e": MARKER, "f": MARKER, "z": MARKER, "n": MARKER, "o": MARKER, "a": MARKER,
        })
        # Replaced containers are not inspected: exactly one path per key.
        self.assertEqual(result["redaction"]["count"], 7)
        self.assertEqual(result["redaction"]["paths"], [
            "/records/0/evidence/a", "/records/0/evidence/e", "/records/0/evidence/f",
            "/records/0/evidence/n", "/records/0/evidence/o", "/records/0/evidence/s",
            "/records/0/evidence/z",
        ])


class PolicyValidationTest(unittest.TestCase):
    """RC2: strict validation, fixed diagnostic, policy checked before records."""

    INVALID: list[typing.Any] = [
        None,
        {},
        {"keys": "token"},
        {"keys": ["token", "token"]},
        {"keys": [""]},
        {"keys": [123]},
        {"keys": [["token"]]},
        {"keys": ["token"], "extra": True},
        {"keys": None},
        [],
        "token",
    ]

    VALID: list[typing.Any] = [
        {"keys": []},
        {"keys": [" "]},
        {"keys": ["token", "Token"]},
    ]

    def testPolicy_whenInvalid_failsSafelyBeforeRecords(self) -> None:
        for policy in self.INVALID:
            with self.subTest(policy=policy):
                result = _run_payload({"records": [{"record_id": 1}], "redaction_policy": policy})
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr.decode(), "error: invalid redaction_policy\n")
                self.assertNotIn("Traceback", result.stderr.decode())

    def testPolicy_whenValidButRecordsBroken_reportsRecordError(self) -> None:
        for policy in self.VALID:
            with self.subTest(policy=policy):
                result = _run_payload({"records": [{"record_id": 1}], "redaction_policy": policy})
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn("invalid redaction_policy", result.stderr.decode())

    def testPolicy_whenEmptyKeyList_stillEmitsZeroCountAudit(self) -> None:
        result = json.loads(_run_payload({
            "records": [{"record_id": "E1", "evidence": {"token": "visible"}}],
            "redaction_policy": {"keys": []},
        }).stdout)
        self.assertEqual(result["records"][0]["evidence"], {"token": "visible"})
        self.assertEqual(result["redaction"], {"count": 0, "paths": []})

    def testPolicy_whenRecordsEmpty_rendersEmptyAudit(self) -> None:
        result = json.loads(_run_payload({
            "records": [], "redaction_policy": {"keys": ["token"]},
        }).stdout)
        self.assertEqual(result["records"], [])
        self.assertEqual(result["summary"], {"records": 0})
        self.assertEqual(result["redaction"], {"count": 0, "paths": []})


class BoundaryTest(unittest.TestCase):
    """Constructed boundaries: whitespace keys, single space vs two spaces."""

    def testPolicy_whenWhitespaceKey_matchesOnlyExactWhitespace(self) -> None:
        result = json.loads(_run_payload({
            "records": [{"record_id": "W1", "evidence": {" ": "one", "  ": "two", "x": "three"}}],
            "redaction_policy": {"keys": [" "]},
        }).stdout)
        self.assertEqual(result["records"][0]["evidence"], {" ": MARKER, "  ": "two", "x": "three"})
        self.assertEqual(result["redaction"]["paths"], ["/records/0/evidence/ "])

    def testPolicy_whenRecordIdsCarrySpaces_doesNotRedactIds(self) -> None:
        result = json.loads(_run_payload({
            "records": [
                {"record_id": " token ", "evidence": {"token": "x"}},
                {"record_id": "A", "evidence": {"Token": "x"}},
            ],
            "redaction_policy": {"keys": ["token"]},
        }).stdout)
        # Legacy quirk kept: " token " sorts first because a leading space is below "A".
        order = [record["record_id"] for record in result["records"]]
        self.assertEqual(order, [" token ", "A"])
        self.assertEqual(result["records"][1]["evidence"], {"Token": "x"})
        self.assertEqual(result["redaction"]["paths"], ["/records/0/evidence/token"])


class InputImmutabilityTest(unittest.TestCase):
    """RC4: never mutate the caller's payload; repeated calls are identical."""

    def testRender_whenCalledTwice_leavesInputAndOutputUntouched(self) -> None:
        sys.path.insert(0, str(ROOT))
        try:
            import app
        finally:
            sys.path.pop(0)

        payload = json.loads((ROOT / "inputs" / "primary.json").read_text(encoding="utf-8"))
        original = copy.deepcopy(payload)
        arguments = app.argparse.Namespace(input="unused")
        first = app.render_evidence(payload, arguments)
        second = app.render_evidence(payload, arguments)
        self.assertEqual(payload, original)
        self.assertEqual(first, second)
        self.assertEqual(first["redaction"]["count"], 10)


if __name__ == "__main__":
    unittest.main()
