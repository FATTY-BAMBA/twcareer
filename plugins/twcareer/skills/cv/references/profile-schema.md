# career/profile.md — schema

The profile is a plain Markdown file the user owns, opens, edits and deletes. Never hide career data in plugin storage. Follow this structure exactly so later sessions and later versions can read it.

## ID rules

Every evidence-bearing entry carries a stable ID:

| Prefix | Applies to |
|---|---|
| `EXP-nn` | one role at one company |
| `SKILL-nn` | one skill |
| `PROJ-nn` | one project |
| `CERT-nn` | one certification or licence |
| `EDU-nn` | one degree |

Rules that must not be broken:

- IDs are assigned once and **never reused, renumbered, or reordered**. Deleting `EXP-02` leaves a gap; the next new entry is `EXP-06`, not `EXP-02`.
- Every ID records where it came from in its `Source:` line — the résumé file and roughly where in it, or `使用者於 YYYY-MM-DD 補充` for things the user stated in conversation. This is enforced: the renderer refuses to build an application citing an entry that has no `Source:`, because it would have no provenance to display. An entry no claim cites may stay unfinished.
- The `Schema version:` line near the top is required. The renderer reads it and stops if the profile is a shape it does not understand, so a profile cannot quietly drift out of step with the claims schema.
- Claims in generated applications point at these IDs. If an ID moves, every past application's evidence map becomes wrong.

## Template

```markdown
# Career Profile

> 這是你的職涯檔案。你可以直接編輯或刪除這個檔案。
> This is your career profile. You can edit or delete this file directly.

Schema version: 1
Last updated: YYYY-MM-DD

## Identity
Preferred name:
Contact email:
Phone:
Languages:            e.g. 中文（母語）、English (professional)

## Target
Target roles:
Target industries:
Location:
Remote preference:

## Compensation
Current compensation:
Expected compensation:
Minimum acceptable:
Notes:                e.g. 目前為責任制，希望轉為正常工時

## Experience

### EXP-01 — <Company> / <Role>
Dates:
Employment type:      正職 / 約聘 / 派遣 / 兼職 / 實習
Responsibilities:
  -
Achievements:
  -
Source:

### EXP-02 — ...

## Skills
- SKILL-01 <skill> — evidence: EXP-01 | Source:
- SKILL-02 ...

## Projects

### PROJ-01 — <name>
Role:
Description:
Outcome:
Source:

## Education
- EDU-01 <degree>, <institution>, <year> | Source:

## Certifications
- CERT-01 <name>, <issuer>, <year> | Source:

## Constraints
Notice period:
Work authorization:
Relocation:
Other:

## Preferences
Company size:
Culture notes:
Deal breakers:

## Application History
<!-- reserved for a future version — do not populate yet -->
```

## Filling it in

- Leave a field blank rather than guessing. A blank field is honest; an invented one poisons every application built from it.
- Do not paraphrase achievements into stronger language at intake. Intake records what the source says. Rewriting happens later, per application, where it can be checked against the record.
- When the user supplies something in conversation, add it with a new ID and a `Source:` of `使用者於 YYYY-MM-DD 補充`. That provenance is what later lets a claim qualify as `USER_CONFIRMED`.
- Keep the file readable. The user will open it.

## Source lines are read by the renderer

The renderer decides whether a claim is document-backed or self-reported by reading each cited entry's `Source:` line. Write them in one of exactly two shapes:

```
Source: <resume file> — <roughly where in it>
Source: USER_CONFIRMED YYYY-MM-DD — 使用者本人陳述：「<their own words>」<scope limits>
```

A self-reported entry whose Source is phrased some other way will be read as document-backed, and the application will claim a stronger provenance than it has. This has happened once already; it is not hypothetical.

Always record the scope limit the user gave, in their words — 「沒有 CI/CD 經驗」, 「只在個人專案」. A later application can then resolve the skill without resolving the limit.

## When the user contradicts the source résumé

The résumé is a document from a point in time; the user knows more than it does. A later statement is not invalid — but it must not silently overwrite history.

When the user supplies something the source résumé lists as absent, record both, with dates:

```
- SKILL-14 SQL 查詢（SELECT / GROUP BY / 簡單 JOIN） | Source: USER_CONFIRMED 2026-08-29 — 使用者本人陳述：「…」
  Conflict: 原始履歷（twcareer-test-resume.md）將 SQL 列為未具備；使用者於 2026-08-29 補充個人練習經驗。以使用者陳述為準，保留原始紀錄以供追溯。
```

Tell the user you noticed, in one line, and let them confirm which is right before writing. Never delete the earlier record — a profile that quietly disagrees with the document it was built from is worse than one that shows its working.

## What must never go in

- Government ID numbers (身分證字號), bank or card numbers
- Health conditions, disability status, pregnancy
- Marital or family status, religion, political affiliation
- Photographs

Some Taiwan résumé templates still ask for several of these. This tool does not store them. If the user volunteers one, do not write it to the profile — say briefly that the tool doesn't keep that kind of information, and carry on.
