#!/usr/bin/env python3
"""Check a rendered application against an adversarial pass condition.

Unit tests prove the renderer's rules in isolation. This checks a real run:
given an output folder and the capabilities the profile deliberately does not
contain, it asserts the obvious things a human would otherwise have to eyeball
every time.

    python3 tests/check_adversarial.py \\
        career/outputs/<folder> \\
        --profile career/profile.md \\
        --forbid Python SQL RAG Docker MCP embedding

Checks:
  1. no forbidden capability appears in 104-application.md
  2. every forbidden capability is surfaced in gaps.md
  3. every evidence-map row cites at least one ID and shows a source
  4. every ID cited anywhere in the evidence map exists in profile.md
  5. injecting a fake ID and a misspelled section into claims.json still
     makes the renderer exit 2 (with --claims)

Exit 0 if every check passes, 1 otherwise. Judgment calls — whether a kept
claim is genuinely transferable rather than quietly overreaching — are still
yours; this only catches what a machine can be sure about.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "twcareer" / "scripts"))
import render_application  # noqa: E402

RENDERER = Path(render_application.__file__)
ID_RE = re.compile(r"\b(?:EXP|SKILL|PROJ|CERT|EDU)-\d+\b")


class Report:
    def __init__(self):
        self.failures = []

    def check(self, ok, label, detail=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            if detail:
                print(f"        {detail}")
            self.failures.append(label)


def evidence_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("區塊", "---"):
            continue
        if set(cells[0]) <= {"-"}:
            continue
        rows.append(cells)
    return rows


def run_injection(claims_path, profile, mutate, label, report):
    doc = json.loads(claims_path.read_text(encoding="utf-8"))
    mutate(doc)
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "claims.json"
        target.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(RENDERER), str(target), "--profile", str(profile)],
            capture_output=True,
            text=True,
        )
        rendered = list(Path(tmp).glob("*.md"))
    report.check(
        proc.returncode == 2 and not rendered,
        label,
        f"exit {proc.returncode}, {len(rendered)} files written",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", help="folder holding the rendered .md files")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--forbid", nargs="*", default=[], help="capabilities the profile does not contain")
    ap.add_argument("--claims", help="claims.json, to also run the injection checks")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    profile_path = Path(args.profile)

    if not outdir.is_dir():
        sibling = outdir.parent
        print(f"error: {outdir} does not exist.", file=sys.stderr)
        if outdir.name in ("FOLDER", "<folder>", "folder"):
            print(
                "That looks like the placeholder. Replace it with the folder "
                "twcareer actually created.",
                file=sys.stderr,
            )
        if sibling.is_dir():
            found = sorted(p.name for p in sibling.iterdir() if p.is_dir())
            print(
                f"Folders in {sibling}: {', '.join(found) if found else '(none)'}",
                file=sys.stderr,
            )
        else:
            print(
                f"{sibling} does not exist either — nothing has been rendered yet. "
                "Run /twcareer:cv first; this checker inspects its output.",
                file=sys.stderr,
            )
        return 1

    missing = [n for n in ("104-application.md", "gaps.md", "evidence-map.md") if not (outdir / n).is_file()]
    if missing:
        print(
            f"error: {outdir} is missing {', '.join(missing)}. "
            "Either the render failed or this is not an application output folder.",
            file=sys.stderr,
        )
        return 1

    if not profile_path.is_file():
        print(f"error: no such profile: {profile_path}", file=sys.stderr)
        return 1

    if args.claims and not Path(args.claims).is_file():
        print(f"error: no such claims file: {args.claims}", file=sys.stderr)
        return 1

    application = (outdir / "104-application.md").read_text(encoding="utf-8")
    gaps = (outdir / "gaps.md").read_text(encoding="utf-8")
    evidence = (outdir / "evidence-map.md").read_text(encoding="utf-8")
    profile_ids = set(render_application.parse_profile(profile_path.read_text(encoding="utf-8")))

    report = Report()

    print("\nForbidden capabilities absent from the application")
    for term in args.forbid:
        hits = [l for l in application.splitlines() if term.lower() in l.lower()]
        report.check(not hits, f"{term} not in 104-application.md", hits[0] if hits else "")

    print("\nForbidden capabilities surfaced as gaps")
    for term in args.forbid:
        report.check(term.lower() in gaps.lower(), f"{term} appears in gaps.md")

    print("\nEvidence map integrity")
    rows = evidence_rows(evidence)
    report.check(bool(rows), "evidence map has rows")
    unsourced = [r[1][:30] for r in rows if not r[3]]
    report.check(not unsourced, "every row shows a source", "; ".join(unsourced[:3]))
    idless = [r[1][:30] for r in rows if not ID_RE.search(r[2])]
    report.check(not idless, "every row cites at least one ID", "; ".join(idless[:3]))
    cited = {i for r in rows for i in ID_RE.findall(" ".join(r))}
    unknown = sorted(cited - profile_ids)
    report.check(not unknown, "every cited ID exists in profile.md", ", ".join(unknown))

    if args.claims:
        print("\nInjection checks")
        claims_path = Path(args.claims)

        def fake_id(doc):
            doc.setdefault("summary", []).append(
                {"text": "injected", "state": "SUPPORTED", "evidence_ids": ["EXP-999999"]}
            )

        def typo_section(doc):
            doc["experiencee"] = doc.get("experience", [])

        run_injection(claims_path, profile_path, fake_id, "EXP-999999 rejected", report)
        run_injection(claims_path, profile_path, typo_section, "`experiencee` rejected", report)

    print()
    if report.failures:
        print(f"{len(report.failures)} check(s) failed:")
        for f in report.failures:
            print(f"  - {f}")
        return 1
    print("All checks passed. Human judgment still required on whether the kept")
    print("claims are genuinely transferable rather than quietly overreaching.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
