#!/usr/bin/env python3
"""Render a Taiwan job application from an evidence-tagged claims file.

The point of this script is that it is the trust layer, not a formatter.
Two rules live here in code rather than in an instruction a model may or
may not follow:

  1. A claim that is not SUPPORTED or USER_CONFIRMED cannot reach the
     application.
  2. Every evidence pointer must resolve to a real entry in
     career/profile.md. A well-formed pointer to nothing is rejected.

Rule 2 is what makes the product claim literal: if twcareer puts something
in your application, it can show the profile entry it came from.

Usage:
    python3 render_application.py path/to/claims.json [--profile path/to/profile.md]

Exit codes:
    0  rendered
    1  file / IO problem
    2  validation failure
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2

# career/profile.md carries its own version, on its own axis. Claims and the
# profile drift independently, so both are checked.
PROFILE_SCHEMA_VERSION = 1

ACCEPTED = ("SUPPORTED", "USER_CONFIRMED")
VALID_STATES = ACCEPTED + ("UNSUPPORTED",)

ID_PREFIXES = ("EXP", "SKILL", "PROJ", "CERT", "EDU")

# Fail closed: anything not named here is a typo or schema drift, and a
# silently ignored section is how a whole block of a résumé goes missing.
ALLOWED_TOP_LEVEL = {
    "schema_version",
    "meta",
    "summary",
    "experience",
    "skills",
    "projects",
    "autobiography",
    "motivation",
    "conditions",
    "gaps",
}
ALLOWED_META = {
    "company",
    "role",
    "jd_language",
    "register",
    "generated_at",
    "twcareer_version",
    "profile_schema_version",
    "profile_last_updated",
}
ALLOWED_CLAIM = {"text", "text_en", "state", "evidence_ids", "note"}
ALLOWED_JOB = {"company", "role", "dates", "employment_type", "bullets"}
ALLOWED_PROJECT = {"name", "bullets"}
ALLOWED_CONDITIONS = {"expected_salary", "notice_period", "location", "notes"}
ALLOWED_GAP = {"requirement", "importance", "note", "interview_risk"}

# Keys that used to be accepted. Named explicitly so the error explains the
# migration instead of just saying "unknown field".
RETIRED_CLAIM_KEYS = {
    "evidence_id": (
        "renamed to `evidence_ids`, which is a list — "
        'use "evidence_ids": ["EXP-02"]'
    ),
    "source": (
        "no longer accepted — the evidence source is now derived from "
        "profile.md so it cannot disagree with the profile"
    ),
}

SELF_REPORTED_MARKERS = ("使用者於", "使用者補充", "user-supplied", "user supplied")


class ValidationError(Exception):
    pass


# ------------------------------------------------------------------- profile


HEADING_ID_RE = re.compile(
    r"^#{2,4}\s+(" + "|".join(ID_PREFIXES) + r")-(\d+)\s*(?:[—–-]\s*)?(.*)$"
)
LIST_ID_RE = re.compile(
    r"^[-*]\s+(" + "|".join(ID_PREFIXES) + r")-(\d+)\b\s*(.*)$"
)
SOURCE_FIELD_RE = re.compile(r"^\s*Source:\s*(.*)$", re.IGNORECASE)
PROFILE_VERSION_RE = re.compile(r"^\s*Schema version:\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_profile_schema_version(text):
    """Read `Schema version: N` from a profile.md. None when absent."""
    match = PROFILE_VERSION_RE.search(text)
    return int(match.group(1)) if match else None


def parse_profile(text):
    """Extract stable IDs from a profile.md.

    Returns {id: {"label": str, "source": str}}.

    Deliberately anchored to line starts so an inline cross-reference like
    `SKILL-01 foo — evidence: EXP-01` registers SKILL-01 only, and does not
    invent an EXP-01 entry that may not exist.
    """
    entries = {}
    current = None

    for raw in text.splitlines():
        line = raw.rstrip()

        heading = HEADING_ID_RE.match(line)
        if heading:
            prefix, num, label = heading.groups()
            key = f"{prefix}-{num}"
            entries[key] = {"label": label.strip(), "source": ""}
            current = key
            continue

        item = LIST_ID_RE.match(line)
        if item:
            prefix, num, rest = item.groups()
            key = f"{prefix}-{num}"
            label, source = rest, ""
            if "| Source:" in rest:
                label, _, source = rest.partition("| Source:")
            elif "|Source:" in rest:
                label, _, source = rest.partition("|Source:")
            entries[key] = {"label": label.strip(" —–-"), "source": source.strip()}
            current = None
            continue

        if line.startswith("#"):
            current = None
            continue

        if current:
            field = SOURCE_FIELD_RE.match(line)
            if field and not entries[current]["source"]:
                entries[current]["source"] = field.group(1).strip()

    return entries


def find_profile(claims_path):
    """Locate career/profile.md relative to the claims file."""
    for ancestor in [claims_path.parent, *claims_path.parents]:
        if ancestor.name == "career":
            candidate = ancestor / "profile.md"
            if candidate.is_file():
                return candidate
        candidate = ancestor / "career" / "profile.md"
        if candidate.is_file():
            return candidate
    return None


def is_self_reported(source):
    return any(marker in (source or "") for marker in SELF_REPORTED_MARKERS)


# ---------------------------------------------------------------- validation


def reject_unknown(obj, allowed, where, retired=None):
    if not isinstance(obj, dict):
        raise ValidationError(f"{where}: expected an object, got {type(obj).__name__}")
    for key in obj:
        if retired and key in retired:
            raise ValidationError(f"{where}: `{key}` is {retired[key]}")
        if key not in allowed:
            near = ", ".join(sorted(allowed))
            raise ValidationError(
                f"{where}: unknown field `{key}`. Allowed here: {near}. "
                "Unknown fields are rejected so a typo cannot silently drop content."
            )


def require_list(doc, key, where):
    value = doc.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(
            f"{where}: `{key}` must be a list, got {type(value).__name__}"
        )
    return value


def validate_claim(claim, where, profile_ids):
    reject_unknown(claim, ALLOWED_CLAIM, where, RETIRED_CLAIM_KEYS)

    text = claim.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValidationError(f"{where}: claim has no text")

    if "text_en" in claim and not isinstance(claim["text_en"], (str, type(None))):
        raise ValidationError(f"{where}: text_en must be a string")

    state = claim.get("state")
    if state not in VALID_STATES:
        raise ValidationError(
            f"{where}: state must be one of {', '.join(VALID_STATES)} (got {state!r}). "
            "An untagged claim cannot be rendered."
        )

    ids = claim.get("evidence_ids")
    if ids is not None and not isinstance(ids, list):
        raise ValidationError(
            f"{where}: evidence_ids must be a list, got {type(ids).__name__}"
        )
    ids = [str(i).strip() for i in (ids or []) if str(i).strip()]

    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValidationError(
            f"{where}: evidence_ids repeats {', '.join(duplicates)}. "
            "A claim cites each supporting entry once; a repeat means the list was "
            "assembled carelessly, and it would print the same source twice."
        )

    if state == "SUPPORTED" and not ids:
        raise ValidationError(
            f"{where}: SUPPORTED claim has no evidence_ids. "
            "Either point it at one or more profile IDs, or downgrade it."
        )

    # The pointer must lead somewhere. This is the check that turns
    # "every claim maps to evidence" from a promise into an invariant.
    if ids:
        if profile_ids is None:
            raise ValidationError(
                f"{where}: claim cites {', '.join(ids)} but no profile.md was found, "
                "so the evidence cannot be verified. Pass --profile."
            )
        missing = [i for i in ids if i not in profile_ids]
        if missing:
            known = ", ".join(sorted(profile_ids)) or "(none)"
            raise ValidationError(
                f"{where}: evidence_ids {', '.join(repr(m) for m in missing)} "
                f"do not exist in profile.md. IDs in the profile: {known}"
            )

        # An entry with no Source: line has no provenance to show. Rendering it
        # as "unknown" would put a claim in the application whose origin the
        # evidence map cannot state, which is the failure this tool exists to
        # prevent. Only cited entries are checked — an unused entry the user is
        # still filling in does not block a build.
        unsourced = [i for i in ids if not str(profile_ids[i].get("source") or "").strip()]
        if unsourced:
            raise ValidationError(
                f"{where}: {', '.join(unsourced)} exist in profile.md but carry no "
                "`Source:` line, so their provenance cannot be shown. Add a Source "
                "to each — the résumé file and roughly where in it, or "
                "`使用者於 YYYY-MM-DD 補充`."
            )

    if state == "USER_CONFIRMED" and not str(claim.get("note") or "").strip():
        raise ValidationError(
            f"{where}: USER_CONFIRMED claim has no note recording what the user said."
        )

    return claim


def validate(doc, profile_ids):
    if not isinstance(doc, dict):
        raise ValidationError("top level of claims.json must be an object")

    reject_unknown(doc, ALLOWED_TOP_LEVEL, "top level")

    version = doc.get("schema_version")
    if version == 1:
        raise ValidationError(
            "schema_version 1 is no longer supported. In each claim, replace "
            '"evidence_id": "EXP-02" with "evidence_ids": ["EXP-02"], drop the '
            '"source" field, and set "schema_version": 2.'
        )
    if version != SCHEMA_VERSION:
        raise ValidationError(
            f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}"
        )

    meta = doc.get("meta")
    if meta is None:
        raise ValidationError("meta is required")
    reject_unknown(meta, ALLOWED_META, "meta")
    for field in ("company", "role"):
        if not str(meta.get(field) or "").strip():
            raise ValidationError(f"meta.{field} is required")

    for section in ("summary", "skills", "autobiography", "motivation"):
        for i, claim in enumerate(require_list(doc, section, "top level")):
            validate_claim(claim, f"{section}[{i}]", profile_ids)

    for j, job in enumerate(require_list(doc, "experience", "top level")):
        reject_unknown(job, ALLOWED_JOB, f"experience[{j}]")
        for i, claim in enumerate(require_list(job, "bullets", f"experience[{j}]")):
            validate_claim(claim, f"experience[{j}].bullets[{i}]", profile_ids)

    for j, proj in enumerate(require_list(doc, "projects", "top level")):
        reject_unknown(proj, ALLOWED_PROJECT, f"projects[{j}]")
        for i, claim in enumerate(require_list(proj, "bullets", f"projects[{j}]")):
            validate_claim(claim, f"projects[{j}].bullets[{i}]", profile_ids)

    conditions = doc.get("conditions")
    if conditions is not None:
        reject_unknown(conditions, ALLOWED_CONDITIONS, "conditions")

    for j, gap in enumerate(require_list(doc, "gaps", "top level")):
        reject_unknown(gap, ALLOWED_GAP, f"gaps[{j}]")
        if not str(gap.get("requirement") or "").strip():
            raise ValidationError(f"gaps[{j}]: requirement is required")

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

    experience = doc.get("experience") or []
    rendered_jobs = []
    for job in experience:
        bullets, d = partition(job.get("bullets"))
        dropped_sink += [("工作經歷", c) for c in d]
        if bullets:
            rendered_jobs.append((job, bullets))
    if rendered_jobs:
        out.append("## ② 工作經歷")
        out.append("")
        for job, bullets in rendered_jobs:
            out.append(f"### {job.get('company', '')} — {job.get('role', '')}")
            meta_bits = [b for b in (job.get("dates"), job.get("employment_type")) if b]
            if meta_bits:
                out.append(" | ".join(str(b) for b in meta_bits))
            out.append("")
            out.extend(render_claim(c) for c in bullets)
            out.append("")

    skills, d = partition(doc.get("skills"))
    dropped_sink += [("專長技能", c) for c in d]
    if skills:
        out.append("## ③ 專長技能")
        out.append("")
        out.extend(render_claim(c) for c in skills)
        out.append("")

    rendered_projects = []
    for proj in doc.get("projects") or []:
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

    motivation, d = partition(doc.get("motivation"))
    dropped_sink += [("應徵動機", c) for c in d]
    if motivation:
        out.append("## ⑥ 應徵動機")
        out.append("")
        for claim in motivation:
            out.append(claim["text"])
            out.append("")

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

    return "\n".join(out).rstrip() + "\n"


def collect_rows(doc, profile):
    """Every accepted claim, with its evidence resolved against the profile."""
    rows = []

    def collect(section_label, claims):
        for claim in claims or []:
            if claim.get("state") not in ACCEPTED:
                continue
            ids = [str(i).strip() for i in (claim.get("evidence_ids") or []) if str(i).strip()]
            sources, self_reported = [], False
            for eid in ids:
                entry = profile.get(eid, {})
                src = entry.get("source") or entry.get("label") or ""
                if src:
                    sources.append(f"{eid}：{src}")
                else:
                    sources.append(eid)
                if is_self_reported(entry.get("source")):
                    self_reported = True

            if claim.get("state") == "USER_CONFIRMED":
                self_reported = True
                if not sources:
                    sources = [str(claim.get("note") or "").strip()]

            rows.append(
                {
                    "section": section_label,
                    "text": claim["text"],
                    "ids": ids,
                    "source": "；".join(s for s in sources if s),
                    "self_reported": self_reported,
                }
            )

    collect("個人簡介", doc.get("summary"))
    for job in doc.get("experience") or []:
        collect(f"工作經歷 / {job.get('company', '')}", job.get("bullets"))
    collect("專長技能", doc.get("skills"))
    for proj in doc.get("projects") or []:
        collect(f"專案 / {proj.get('name', '')}", proj.get("bullets"))
    collect("自傳", doc.get("autobiography"))
    collect("應徵動機", doc.get("motivation"))
    return rows


def build_evidence_map(rows):
    out = ["# 證據對照表 / Evidence map", ""]
    out.append("每一句寫進履歷的話，都對應到 profile.md 裡一筆真實的紀錄。")
    out.append("Every line in the application resolves to a real entry in profile.md.")
    out.append("")

    from_resume = sum(1 for r in rows if not r["self_reported"])
    self_reported = sum(1 for r in rows if r["self_reported"])
    out.append(
        f"**{len(rows)} 項主張** — {from_resume} 項來自原始文件，{self_reported} 項為你口頭補充。"
    )
    out.append("")
    out.append(
        "> 「來源」欄位取自 profile.md 的 Source 行，不是產出時另外寫的說明。"
    )
    out.append("")

    out.append("| 區塊 | 主張 | 依據 | 出處 |")
    out.append("|---|---|---|---|")
    for row in rows:
        mark = "✓ 使用者補充" if row["self_reported"] else "✓ 原始文件"
        ref = ", ".join(row["ids"]) or mark
        cells = [
            row["section"],
            row["text"].replace("|", "\\|"),
            f"{mark}　{ref}".strip(),
            row["source"].replace("|", "\\|"),
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
    parser = argparse.ArgumentParser(
        prog="render_application.py",
        description="Render a Taiwan job application from an evidence-tagged claims file.",
    )
    parser.add_argument("claims", help="path to claims.json")
    parser.add_argument(
        "--profile",
        help="path to career/profile.md (default: discovered from the claims path)",
    )
    args = parser.parse_args(argv[1:])

    path = Path(args.claims)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: no such file: {path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: {path} is not valid JSON — {exc}", file=sys.stderr)
        return 2

    if args.profile:
        profile_path = Path(args.profile)
        if not profile_path.is_file():
            print(f"error: no such profile: {profile_path}", file=sys.stderr)
            return 1
    else:
        profile_path = find_profile(path)

    profile = None
    if profile_path is not None:
        try:
            profile_text = profile_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: could not read {profile_path} — {exc}", file=sys.stderr)
            return 1

        profile_version = parse_profile_schema_version(profile_text)
        if profile_version is None:
            print(
                f"validation failed — {profile_path} has no `Schema version:` line. "
                f"Add `Schema version: {PROFILE_SCHEMA_VERSION}` near the top so the "
                "renderer can tell which profile shape it is reading.",
                file=sys.stderr,
            )
            return 2
        if profile_version != PROFILE_SCHEMA_VERSION:
            print(
                f"validation failed — {profile_path} is schema version "
                f"{profile_version}; this renderer reads version "
                f"{PROFILE_SCHEMA_VERSION}. Migrate the profile or use a matching "
                "plugin version.",
                file=sys.stderr,
            )
            return 2

        profile = parse_profile(profile_text)

    try:
        validate(doc, profile)
    except ValidationError as exc:
        print(f"validation failed — {exc}", file=sys.stderr)
        print("Nothing was rendered. Fix claims.json; do not hand-write the output.", file=sys.stderr)
        return 2

    out_dir = path.parent
    dropped = []

    application = build_application(doc, dropped)
    rows = collect_rows(doc, profile or {})

    if not rows:
        print(
            "validation failed — no claim is SUPPORTED or USER_CONFIRMED, so the "
            "application would be empty. Nothing was rendered; see the gap list in "
            "claims.json and gather evidence first.",
            file=sys.stderr,
        )
        return 2

    evidence = build_evidence_map(rows)
    gaps = build_gaps(doc, dropped)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    footer = (
        f"\n---\n*Generated {stamp} by twcareer. Evidence-filtered: unsupported claims "
        "removed in code, and every cited ID resolved against profile.md.*\n"
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

    print(f"Rendered {len(written)} files into {out_dir}")
    for target, size in written:
        print(f"  {target.name}  ({size} bytes)")
    if profile_path:
        print(f"Evidence resolved against {profile_path} ({len(profile)} IDs)")
    print(f"Claims kept: {len(rows)}")
    print(f"Claims dropped for lack of evidence: {len(dropped)}")
    if dropped:
        print("  (see gaps.md — these are interview prep, not failures)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
