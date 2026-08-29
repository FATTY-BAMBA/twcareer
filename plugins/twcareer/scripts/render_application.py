#!/usr/bin/env python3
"""Render a Taiwan job application from an evidence-tagged claims file.

The point of this script is the filter: a claim that is not SUPPORTED or
USER_CONFIRMED cannot reach the application. That rule lives here, in code,
rather than in an instruction a model may or may not follow.

Usage:
    python3 render_application.py path/to/claims.json

Exit codes:
    0  rendered
    1  file / IO problem
    2  validation failure
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ACCEPTED = ("SUPPORTED", "USER_CONFIRMED")
VALID_STATES = ACCEPTED + ("UNSUPPORTED",)


def plugin_version():
    """Read the version from the plugin manifest next to this script.

    Printed on every run so a rendered file can always be traced to the exact
    build that produced it. Without this you cannot tell whether a bug you are
    chasing exists in the code you just committed.
    """
    manifest = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version", "unknown")
    except Exception:
        return "unknown"


class ValidationError(Exception):
    pass


# ---------------------------------------------------------------- validation


def validate_claim(claim, where):
    if not isinstance(claim, dict):
        raise ValidationError(f"{where}: claim must be an object, got {type(claim).__name__}")

    text = claim.get("text")
    if not text or not str(text).strip():
        raise ValidationError(f"{where}: claim has no text")

    state = claim.get("state")
    if state not in VALID_STATES:
        raise ValidationError(
            f"{where}: state must be one of {', '.join(VALID_STATES)} (got {state!r}). "
            "An untagged claim cannot be rendered."
        )

    if state == "SUPPORTED" and not str(claim.get("evidence_id") or "").strip():
        raise ValidationError(
            f"{where}: SUPPORTED claim has no evidence_id. "
            "Either point it at a profile ID or downgrade it."
        )

    if state == "USER_CONFIRMED" and not str(claim.get("note") or "").strip():
        raise ValidationError(
            f"{where}: USER_CONFIRMED claim has no note recording what the user said."
        )

    return claim


def validate(doc):
    if not isinstance(doc, dict):
        raise ValidationError("top level of claims.json must be an object")

    if doc.get("schema_version") != 1:
        raise ValidationError(f"unsupported schema_version {doc.get('schema_version')!r}; expected 1")

    meta = doc.get("meta") or {}
    for field in ("company", "role"):
        if not str(meta.get(field) or "").strip():
            raise ValidationError(f"meta.{field} is required")

    for section in ("summary", "skills", "autobiography", "motivation"):
        for i, claim in enumerate(doc.get(section) or []):
            validate_claim(claim, f"{section}[{i}]")

    for j, job in enumerate(doc.get("experience") or []):
        if not isinstance(job, dict):
            raise ValidationError(f"experience[{j}] must be an object")
        for i, claim in enumerate(job.get("bullets") or []):
            validate_claim(claim, f"experience[{j}].bullets[{i}]")

    for j, proj in enumerate(doc.get("projects") or []):
        if not isinstance(proj, dict):
            raise ValidationError(f"projects[{j}] must be an object")
        for i, claim in enumerate(proj.get("bullets") or []):
            validate_claim(claim, f"projects[{j}].bullets[{i}]")

    return doc


# ------------------------------------------------------------------- filter


def partition(claims):
    """Split claims into (kept, dropped). This is the enforcement point."""
    kept, dropped = [], []
    for claim in claims or []:
        (kept if claim.get("state") in ACCEPTED else dropped).append(claim)
    return kept, dropped


def render_claim(claim):
    line = f"- {claim['text']}"
    en = str(claim.get("text_en") or "").strip()
    if en:
        line += f"\n  - {en}"
    return line


def empty_note(out, heading, had_candidates):
    """Say why a section is absent instead of silently omitting it.

    A section that vanishes without explanation reads as a bug. A section that
    says it found no evidence reads as the product working.
    """
    out.append(f"## {heading}")
    out.append("")
    if had_candidates:
        out.append("> 目前缺乏可驗證證據，未自動產生。相關敘述已移至 `gaps.md`。")
        out.append("> No verifiable evidence for this section — see `gaps.md`.")
    else:
        out.append("> 目前沒有可用的內容。")
        out.append("> Nothing available for this section yet.")
    out.append("")


# ------------------------------------------------------------------ sections


def build_application(doc, dropped_sink):
    meta = doc.get("meta") or {}
    out = []
    out.append(f"# 104 應徵包 — {meta.get('company')} / {meta.get('role')}")
    out.append("")
    out.append("> 每個區塊可直接複製貼上到 104 對應欄位。")
    out.append("> Each block below pastes directly into the matching 104 field.")
    out.append("")

    summary, d = partition(doc.get("summary"))
    dropped_sink += [("個人簡介", c) for c in d]
    if summary:
        out.append("## ① 個人簡介")
        out.append("")
        out.extend(render_claim(c) for c in summary)
        out.append("")
    else:
        empty_note(out, "① 個人簡介", bool(doc.get("summary")))

    experience = doc.get("experience") or []
    rendered_any_job = False
    if experience:
        out.append("## ② 工作經歷")
        out.append("")
        for job in experience:
            bullets, d = partition(job.get("bullets"))
            dropped_sink += [("工作經歷", c) for c in d]
            if not bullets:
                continue
            header = f"### {job.get('company', '')} — {job.get('role', '')}"
            out.append(header)
            meta_bits = [b for b in (job.get("dates"), job.get("employment_type")) if b]
            if meta_bits:
                out.append(" | ".join(str(b) for b in meta_bits))
            out.append("")
            out.extend(render_claim(c) for c in bullets)
            out.append("")
            rendered_any_job = True
    if not rendered_any_job:
        empty_note(out, "② 工作經歷", bool(experience))

    skills, d = partition(doc.get("skills"))
    dropped_sink += [("專長技能", c) for c in d]
    if skills:
        out.append("## ③ 專長技能")
        out.append("")
        out.extend(render_claim(c) for c in skills)
        out.append("")
    else:
        empty_note(out, "③ 專長技能", bool(doc.get("skills")))

    projects = doc.get("projects") or []
    rendered_projects = []
    for proj in projects:
        bullets, d = partition(proj.get("bullets"))
        dropped_sink += [("專案成就", c) for c in d]
        if bullets:
            rendered_projects.append((proj.get("name", ""), bullets))
    if rendered_projects:
        out.append("## ④ 專案成就")
        out.append("")
        for name, bullets in rendered_projects:
            out.append(f"### {name}")
            out.append("")
            out.extend(render_claim(c) for c in bullets)
            out.append("")
    else:
        empty_note(out, "④ 專案成就", bool(projects))

    auto, d = partition(doc.get("autobiography"))
    dropped_sink += [("自傳", c) for c in d]
    if auto:
        out.append("## ⑤ 自傳")
        out.append("")
        for claim in auto:
            out.append(claim["text"])
            out.append("")
            en = str(claim.get("text_en") or "").strip()
            if en:
                out.append(f"*{en}*")
                out.append("")
    else:
        empty_note(out, "⑤ 自傳", bool(doc.get("autobiography")))

    motivation, d = partition(doc.get("motivation"))
    dropped_sink += [("應徵動機", c) for c in d]
    if motivation:
        out.append("## ⑥ 應徵動機")
        out.append("")
        for claim in motivation:
            out.append(claim["text"])
            out.append("")
    else:
        empty_note(out, "⑥ 應徵動機", bool(doc.get("motivation")))

    cond = doc.get("conditions") or {}
    if any(str(v or "").strip() for v in cond.values()):
        out.append("## ⑦ 求職條件")
        out.append("")
        labels = [
            ("expected_salary", "期望待遇"),
            ("notice_period", "可到職日 / 預告期"),
            ("location", "希望工作地點"),
            ("notes", "備註"),
        ]
        for key, label in labels:
            val = str(cond.get(key) or "").strip()
            if val:
                out.append(f"- **{label}**：{val}")
        out.append("")
        out.append("> 期望待遇為討論起點。收到面試邀約不代表這個數字已被接受，")
        out.append("> 實際條件仍會在面試與薪資核定過程中決定。")
        out.append("")
    else:
        empty_note(out, "⑦ 求職條件", False)

    return "\n".join(out).rstrip() + "\n"


def build_evidence_map(doc):
    out = ["# 證據對照表 / Evidence map", ""]
    out.append("每一句寫進履歷的話，都對應到一筆你真實的經歷。")
    out.append("Every line in the application traces back to something you actually have.")
    out.append("")

    rows = []

    def collect(section_label, claims):
        for claim in claims or []:
            if claim.get("state") not in ACCEPTED:
                continue
            rows.append(
                (
                    section_label,
                    claim["text"],
                    claim.get("state"),
                    claim.get("evidence_id") or claim.get("note") or "",
                    claim.get("source") or "",
                )
            )

    collect("個人簡介", doc.get("summary"))
    for job in doc.get("experience") or []:
        collect(f"工作經歷 / {job.get('company', '')}", job.get("bullets"))
    collect("專長技能", doc.get("skills"))
    for proj in doc.get("projects") or []:
        collect(f"專案 / {proj.get('name', '')}", proj.get("bullets"))
    collect("自傳", doc.get("autobiography"))
    collect("應徵動機", doc.get("motivation"))

    supported = sum(1 for r in rows if r[2] == "SUPPORTED")
    confirmed = sum(1 for r in rows if r[2] == "USER_CONFIRMED")
    out.append(f"**{len(rows)} 項主張** — {supported} 項來自原履歷，{confirmed} 項為你本次補充。")
    out.append("")

    out.append("| 區塊 | 主張 | 狀態 | 依據 | 出處 |")
    out.append("|---|---|---|---|---|")
    for section, text, state, ref, source in rows:
        mark = "✓ 原履歷" if state == "SUPPORTED" else "✓ 使用者補充"
        cells = [
            section,
            text.replace("|", "\\|"),
            mark,
            str(ref).replace("|", "\\|"),
            str(source).replace("|", "\\|"),
        ]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    return "\n".join(out)


def build_gaps(doc, dropped):
    out = ["# 缺口與面試風險 / Gaps and interview risks", ""]
    out.append("這些內容**沒有**寫進履歷，因為找不到證據。這不是失敗 —— 這是面試前該準備的清單。")
    out.append("These were kept out of the application because there was no evidence for them.")
    out.append("")

    declared = doc.get("gaps") or []
    if declared:
        out.append("## JD 要求但目前無證據")
        out.append("")
        for gap in declared:
            out.append(f"### {gap.get('requirement', '')}  ({gap.get('importance', '')})")
            if gap.get("note"):
                out.append(f"- 現況：{gap['note']}")
            if gap.get("interview_risk"):
                out.append(f"- 面試風險：{gap['interview_risk']}")
            out.append("")

    if dropped:
        out.append("## 被系統移除的主張")
        out.append("")
        out.append("以下敘述在產出時被自動移除，因為它們沒有標記為有證據：")
        out.append("")
        for section, claim in dropped:
            out.append(f"- **[{section}]** {claim.get('text', '')}  — `{claim.get('state')}`")
        out.append("")

    if not declared and not dropped:
        out.append("目前沒有偵測到缺口。")
        out.append("")

    return "\n".join(out)


# ---------------------------------------------------------------------- main


def main(argv):
    version = plugin_version()

    if len(argv) == 2 and argv[1] in ("--version", "-v"):
        print(f"twcareer {version}")
        print(f"renderer: {Path(__file__).resolve()}")
        return 0

    if len(argv) != 2:
        print("usage: render_application.py path/to/claims.json", file=sys.stderr)
        return 1

    print(f"twcareer {version} — renderer {Path(__file__).resolve()}")

    path = Path(argv[1])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: {path} is not valid JSON — {exc}", file=sys.stderr)
        return 2

    try:
        validate(doc)
    except ValidationError as exc:
        print(f"validation failed — {exc}", file=sys.stderr)
        print("Nothing was rendered. Fix claims.json; do not hand-write the output.", file=sys.stderr)
        return 2

    out_dir = path.parent
    dropped = []

    application = build_application(doc, dropped)
    evidence = build_evidence_map(doc)
    gaps = build_gaps(doc, dropped)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    footer = (
        f"\n---\n*Generated {stamp} by twcareer v{version}. "
        "Evidence-filtered: unsupported claims removed in code.*\n"
    )

    written = []
    for name, body in (
        ("104-application.md", application + footer),
        ("evidence-map.md", evidence + footer),
        ("gaps.md", gaps + footer),
    ):
        target = out_dir / name
        target.write_text(body, encoding="utf-8")
        size = target.stat().st_size
        if size == 0:
            print(f"error: wrote {target} but it is empty", file=sys.stderr)
            return 1
        written.append((target, size))

    total_dropped = len(dropped)
    print(f"Rendered {len(written)} files into {out_dir}")
    for target, size in written:
        print(f"  {target.name}  ({size} bytes)")
    print(f"Claims dropped for lack of evidence: {total_dropped}")
    if total_dropped:
        print("  (see gaps.md — these are interview prep, not failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
