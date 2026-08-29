#!/usr/bin/env python3
"""Tests for the twcareer renderer.

The renderer is the product's trust layer, so these tests assert behaviour a
user could be harmed by if it regressed:

  * an unevidenced claim never reaches the application
  * a well-formed pointer to a profile entry that does not exist is rejected
  * the evidence source comes from the profile, not from the claims file

Run:  python3 -m unittest discover tests
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RENDERER = REPO / "plugins" / "twcareer" / "scripts" / "render_application.py"
PROFILE = Path(__file__).resolve().parent / "fixtures" / "profile.md"

OUTPUTS = ("104-application.md", "evidence-map.md", "gaps.md")


def claim(text, state="SUPPORTED", **kw):
    obj = {"text": text, "state": state}
    obj.update(kw)
    return obj


def document(**overrides):
    doc = {
        "schema_version": 2,
        "meta": {"company": "某某科技", "role": "行銷企劃"},
        "summary": [claim("規劃並執行品牌社群內容", evidence_ids=["EXP-01"])],
    }
    doc.update(overrides)
    return doc


class RendererTestCase(unittest.TestCase):
    def render(self, doc, profile=PROFILE):
        """Run the renderer in a scratch dir. Returns (exit_code, stderr, dir)."""
        tmp = tempfile.mkdtemp()
        claims_path = Path(tmp) / "claims.json"
        claims_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

        cmd = [sys.executable, str(RENDERER), str(claims_path)]
        if profile is not None:
            cmd += ["--profile", str(profile)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr, Path(tmp)

    def read(self, out_dir, name):
        return (out_dir / name).read_text(encoding="utf-8")

    def assertNothingRendered(self, out_dir):
        for name in OUTPUTS:
            self.assertFalse(
                (out_dir / name).exists(),
                f"{name} was written despite validation failing",
            )


class TestHappyPath(RendererTestCase):
    def test_supported_claim_renders(self):
        code, log, out = self.render(document())
        self.assertEqual(code, 0, log)
        self.assertIn("規劃並執行品牌社群內容", self.read(out, "104-application.md"))
        self.assertIn("EXP-01", self.read(out, "evidence-map.md"))

    def test_outputs_are_non_empty(self):
        _, _, out = self.render(document())
        for name in OUTPUTS:
            self.assertGreater((out / name).stat().st_size, 0, name)

    def test_user_confirmed_renders_with_note(self):
        doc = document(
            skills=[
                claim(
                    "SQL",
                    state="USER_CONFIRMED",
                    note="使用者於 2026-08-28 表示：在前公司做月報，用 SQL 從內部資料庫撈訂單資料",
                )
            ]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        self.assertIn("SQL", self.read(out, "104-application.md"))
        self.assertIn("撈訂單資料", self.read(out, "evidence-map.md"))

    def test_multiple_evidence_ids_all_resolve(self):
        """A claim drawing on two entries shows both, with both profile sources."""
        doc = document(
            summary=[claim("結合社群經營與成效分析", evidence_ids=["EXP-01", "SKILL-01"])]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        evidence = self.read(out, "evidence-map.md")
        self.assertIn("EXP-01", evidence)
        self.assertIn("SKILL-01", evidence)
        self.assertIn("工作經歷 #1", evidence)
        self.assertIn("專長技能", evidence)


class TestEvidenceFilter(RendererTestCase):
    def test_unsupported_claim_is_dropped_not_rendered(self):
        doc = document(
            skills=[claim("管理 50 萬粉絲社群", state="UNSUPPORTED")],
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        self.assertNotIn("50 萬粉絲", self.read(out, "104-application.md"))
        self.assertIn("50 萬粉絲", self.read(out, "gaps.md"))

    def test_everything_unsupported_refuses_to_render(self):
        doc = document(summary=[claim("管理 50 萬粉絲社群", state="UNSUPPORTED")])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("would be empty", log)
        self.assertNothingRendered(out)


class TestEvidenceResolution(RendererTestCase):
    def test_nonexistent_evidence_id_is_rejected(self):
        """The brand promise, as a test."""
        doc = document(
            summary=[claim("Led a 20-person engineering team", evidence_ids=["EXP-999999"])]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("EXP-999999", log)
        self.assertIn("do not exist in profile.md", log)
        self.assertNothingRendered(out)

    def test_one_bad_id_among_good_ones_is_rejected(self):
        doc = document(
            summary=[claim("結合兩段經歷", evidence_ids=["EXP-01", "EXP-02"])]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("EXP-02", log)
        self.assertNothingRendered(out)

    def test_duplicate_evidence_ids_are_rejected(self):
        doc = document(summary=[claim("某項成就", evidence_ids=["EXP-01", "EXP-01"])])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("repeats", log)
        self.assertIn("EXP-01", log)
        self.assertNothingRendered(out)

    def test_cited_entry_without_source_line_is_rejected(self):
        """An entry with no provenance must fail loudly, not render as unknown."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(
                "# Career Profile\n\nSchema version: 1\n\n"
                "## Experience\n\n### EXP-01 — 某公司 / 某職位\nDates: 2024\n"
                "Responsibilities:\n  - 做了一些事\n"
            )
            thin_profile = Path(fh.name)
        code, log, out = self.render(document(), profile=thin_profile)
        self.assertEqual(code, 2, log)
        self.assertIn("Source", log)
        self.assertIn("EXP-01", log)
        self.assertNothingRendered(out)

    def test_uncited_entry_without_source_does_not_block(self):
        """Only cited entries are checked; a half-filled entry is not a build error."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(
                PROFILE.read_text(encoding="utf-8")
                + "\n### EXP-09 — 尚未填完的公司 / 職位\nDates:\n"
            )
            padded = Path(fh.name)
        code, log, _ = self.render(document(), profile=padded)
        self.assertEqual(code, 0, log)

    def test_supported_without_evidence_ids_is_rejected(self):
        doc = document(summary=[claim("某項成就")])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("no evidence_ids", log)
        self.assertNothingRendered(out)

    def test_missing_profile_blocks_supported_claims(self):
        code, log, out = self.render(document(), profile=None)
        self.assertEqual(code, 2, log)
        self.assertIn("no profile.md", log)
        self.assertNothingRendered(out)

    def test_source_comes_from_profile_not_claims(self):
        doc = document(summary=[claim("規劃並執行品牌社群內容", evidence_ids=["EXP-01"])])
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        self.assertIn("source-resume.pdf — 工作經歷 #1", self.read(out, "evidence-map.md"))

    def test_user_confirmed_source_vocabulary_is_recognised(self):
        """A Source: line written as the skill actually writes it is self-reported.

        Regression for a live defect: profile.md entries created by /twcareer:cv
        read `Source: USER_CONFIRMED <date> — 使用者本人陳述：…`, which matched none
        of the recognised markers. The claim therefore rendered as 原始文件 while
        its own 出處 column printed USER_CONFIRMED beside it — the application
        overstating its provenance by one tier.
        """
        doc = document(summary=[claim("以 Python 呼叫 OpenAI API",
                                      state="USER_CONFIRMED",
                                      note="2026-08-29 使用者本人陳述",
                                      evidence_ids=["SKILL-07"])])
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        evidence = self.read(out, "evidence-map.md")
        self.assertIn("使用者補充", evidence)
        self.assertNotIn("✓ 原始文件", evidence)
        self.assertIn("0 項來自原始文件", evidence)

    def test_supported_claim_citing_self_reported_entry_is_rejected(self):
        """Derive-and-reject: a declared state that overstates provenance fails.

        Silently relabelling would leave a wrong `state` sitting in claims.json
        looking valid to everything downstream. The build should say so instead.
        """
        doc = document(summary=[claim("以 Python 呼叫 OpenAI API", evidence_ids=["SKILL-07"])])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("declared provenance does not match", log)
        self.assertIn("SKILL-07", log)
        self.assertNothingRendered(out)

    def test_mixed_provenance_supported_claim_is_rejected(self):
        """One résumé ID plus one user-supplied ID cannot be declared SUPPORTED."""
        doc = document(
            motivation=[claim("我把流程模板化，也自行以 Python 呼叫 OpenAI API。",
                              evidence_ids=["EXP-01", "SKILL-07"])]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("SKILL-07", log)
        self.assertNotIn("EXP-01", log.split("does not match")[-1].split(".")[0])
        self.assertNothingRendered(out)

    def test_mixed_provenance_claim_takes_the_weaker_tier(self):
        """One résumé ID plus one user-supplied ID is user-supplied, not 原始文件.

        A paragraph fusing a documented fact with something said in conversation
        must not inherit the stronger label: the moment the self-reported entry is
        corrected, a claim marked 原始文件 keeps asserting it.
        """
        doc = document(
            motivation=[claim("我把流程模板化，也自行以 Python 呼叫 OpenAI API。",
                              state="USER_CONFIRMED",
                              note="2026-08-29 使用者本人陳述",
                              evidence_ids=["EXP-01", "SKILL-07"])]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        evidence = self.read(out, "evidence-map.md")
        self.assertIn("使用者補充", evidence)
        self.assertIn("1 項來自原始文件", evidence)

    def test_provenance_label_is_not_printed_twice(self):
        """A row with no evidence IDs shows its label once, not doubled."""
        doc = document(
            motivation=[claim("我的實作深度尚未涵蓋 RAG 與部署維運。",
                              state="USER_CONFIRMED",
                              note="2026-08-29 使用者本人陳述其技術範圍界線")]
        )
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        evidence = self.read(out, "evidence-map.md")
        self.assertNotIn("✓ 使用者補充　✓ 使用者補充", evidence)

    def test_self_reported_profile_entry_is_labelled_as_such(self):
        """A SUPPORTED claim backed by a conversation-sourced entry is not 原始文件."""
        doc = document(summary=[claim("SQL 資料撈取",
                                      state="USER_CONFIRMED",
                                      note="2026-08-28 使用者本人陳述",
                                      evidence_ids=["SKILL-04"])])
        code, log, out = self.render(doc)
        self.assertEqual(code, 0, log)
        evidence = self.read(out, "evidence-map.md")
        self.assertIn("使用者補充", evidence)
        self.assertIn("0 項來自原始文件", evidence)


class TestSchemaStrictness(RendererTestCase):
    def test_invalid_state_is_rejected(self):
        doc = document(summary=[claim("某項成就", state="PROBABLY")])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertNothingRendered(out)

    def test_unknown_top_level_field_is_rejected(self):
        doc = document()
        doc["experiencee"] = []
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("experiencee", log)
        self.assertNothingRendered(out)

    def test_unknown_claim_field_is_rejected(self):
        doc = document(summary=[claim("某項成就", evidence_ids=["EXP-01"], confidence="high")])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("confidence", log)
        self.assertNothingRendered(out)

    def test_legacy_evidence_id_gives_migration_message(self):
        doc = document(summary=[{"text": "某項成就", "state": "SUPPORTED", "evidence_id": "EXP-01"}])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("evidence_ids", log)
        self.assertNothingRendered(out)

    def test_model_written_source_field_is_rejected(self):
        doc = document(
            summary=[claim("某項成就", evidence_ids=["EXP-01"])],
        )
        doc["summary"][0]["source"] = "source-resume.pdf — 我說的"
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("derived from profile.md", log)
        self.assertNothingRendered(out)

    def test_schema_version_1_gives_migration_message(self):
        doc = document()
        doc["schema_version"] = 1
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("schema_version 1", log)
        self.assertNothingRendered(out)

    def test_wrong_type_for_section_is_rejected(self):
        doc = document(skills="Python, SQL")
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("must be a list", log)
        self.assertNothingRendered(out)

    def test_malformed_gap_entry_is_rejected_cleanly(self):
        doc = document(gaps=["SQL"])
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("expected an object", log)
        self.assertNotIn("Traceback", log)
        self.assertNothingRendered(out)

    def test_missing_meta_role_is_rejected(self):
        doc = document(meta={"company": "某某科技"})
        code, log, out = self.render(doc)
        self.assertEqual(code, 2, log)
        self.assertIn("meta.role", log)
        self.assertNothingRendered(out)


class TestProfileSchemaVersion(RendererTestCase):
    def write_profile(self, header):
        body = PROFILE.read_text(encoding="utf-8").replace("Schema version: 1\n", header)
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(body)
        return Path(fh.name)

    def test_missing_profile_schema_version_is_rejected(self):
        code, log, out = self.render(document(), profile=self.write_profile(""))
        self.assertEqual(code, 2, log)
        self.assertIn("Schema version", log)
        self.assertNothingRendered(out)

    def test_future_profile_schema_version_is_rejected(self):
        profile = self.write_profile("Schema version: 7\n")
        code, log, out = self.render(document(), profile=profile)
        self.assertEqual(code, 2, log)
        self.assertIn("schema version 7", log)
        self.assertNothingRendered(out)


class TestProfileParser(RendererTestCase):
    def setUp(self):
        sys.path.insert(0, str(RENDERER.parent))
        import render_application

        self.mod = render_application

    def test_parses_all_id_kinds(self):
        entries = self.mod.parse_profile(PROFILE.read_text(encoding="utf-8"))
        for expected in ("EXP-01", "EXP-03", "SKILL-01", "SKILL-04", "PROJ-01", "EDU-01"):
            self.assertIn(expected, entries)

    def test_does_not_invent_ids_from_cross_references(self):
        """`SKILL-01 ... — evidence: EXP-01` must not register a second EXP-01 entry."""
        entries = self.mod.parse_profile("- SKILL-09 foo — evidence: EXP-77 | Source: x")
        self.assertIn("SKILL-09", entries)
        self.assertNotIn("EXP-77", entries)

    def test_gaps_in_numbering_are_preserved(self):
        entries = self.mod.parse_profile(PROFILE.read_text(encoding="utf-8"))
        self.assertNotIn("EXP-02", entries)


if __name__ == "__main__":
    unittest.main()
