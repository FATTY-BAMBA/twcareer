# claims.json — schema and rendering

Build this file, then let the renderer produce the output. Never write the final application by hand: the renderer is what enforces the evidence rule, and output that bypassed it carries no guarantee.

## Location

```
career/outputs/<company>-<role>/claims.json
```

Use a short, filesystem-safe folder name — lowercase, hyphens, no spaces.

## Claim object

```json
{
  "text": "規劃並執行品牌社群內容，涵蓋貼文企劃、製作與成效追蹤",
  "text_en": "Planned and produced brand social content, including scheduling and performance tracking",
  "state": "SUPPORTED",
  "evidence_ids": ["EXP-02", "SKILL-04"],
  "note": ""
}
```

| Field | Required | Notes |
|---|---|---|
| `text` | yes | the claim in the JD's language |
| `text_en` | no | English version; must state the same thing as `text` |
| `state` | yes | `SUPPORTED`, `USER_CONFIRMED`, or `UNSUPPORTED` |
| `evidence_ids` | when `SUPPORTED` | a **list** of real IDs from `profile.md` |
| `note` | when `USER_CONFIRMED` | what the user actually said, and when |

`evidence_ids` is a list because a rewritten line legitimately draws on more than one entry — `EXP-02` establishes the work, `SKILL-04` establishes the tooling. Use one ID when one is honest; do not pad the list to look better sourced.

There is no `source` field. The source string is read out of the cited profile entry's `Source:` line at render time, so what the evidence map prints cannot disagree with what the profile says.

## Validation the renderer enforces

The renderer **rejects the whole file** — exit `2`, nothing written — when:

- a `SUPPORTED` claim has no `evidence_ids`
- a `USER_CONFIRMED` claim has no `note`
- **an `evidence_ids` entry does not exist in `profile.md`** — a well-formed pointer to nothing is the failure this check exists for
- any object carries a field not in the schema, including a near-miss like `experiencee`
- an `evidence_ids` list repeats the same ID
- a cited profile entry has no `Source:` line, so its provenance could not be shown
- a section has the wrong type — `skills` as a string rather than a list
- `profile.md` has no `Schema version:` line, or one this renderer does not read
- no claim at all is `SUPPORTED` or `USER_CONFIRMED`, which would produce an empty application

That last group matters as much as the first. A silently ignored typo drops a whole section from a résumé without telling anyone.

**What the renderer cannot check.** It proves a cited ID exists and shows what that entry says. It cannot tell whether the entry actually supports the sentence written next to it — `EXP-01` is a real ID whether the claim reads 「規劃社群內容」 or 「帶領 10 人團隊」. Keeping a rewritten line inside its evidence is still a judgment call, governed by `evidence-rules.md`. The code closes the pointer, not the reasoning.

## File structure

```json
{
  "schema_version": 2,
  "meta": {
    "company": "某某科技",
    "role": "行銷企劃",
    "jd_language": "zh-TW",
    "register": "本土"
  },
  "summary": [ claim, ... ],
  "experience": [
    {
      "company": "ABC 公司",
      "role": "行銷專員",
      "dates": "2022/03 – 2025/06",
      "employment_type": "正職",
      "bullets": [ claim, ... ]
    }
  ],
  "skills": [ claim, ... ],
  "projects": [
    { "name": "官網改版", "bullets": [ claim, ... ] }
  ],
  "autobiography": [ claim, ... ],
  "motivation": [ claim, ... ],
  "conditions": {
    "expected_salary": "月薪 55,000–62,000，可依職務內容討論",
    "notice_period": "一個月",
    "location": "新北 / 台北",
    "notes": ""
  },
  "gaps": [
    {
      "requirement": "SQL",
      "importance": "必要",
      "note": "履歷與對話中皆無使用 SQL 的證據",
      "interview_risk": "面試很可能直接問資料處理經驗，建議準備替代方案說明"
    }
  ]
}
```

`autobiography` claims are paragraphs — one claim per paragraph, each still carrying a state and evidence.

## Running the renderer

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_application.py" career/outputs/<folder>/claims.json
```

The profile is discovered automatically by walking up from the claims file to `career/profile.md`. Pass `--profile <path>` when it lives somewhere else.

Outputs into the same folder:

| File | Contents |
|---|---|
| `104-application.md` | paste-ready sections, evidenced claims only |
| `evidence-map.md` | every accepted claim, its IDs, and the profile's own source line |
| `gaps.md` | dropped claims plus declared gaps, framed as interview prep |

Exit codes: `0` success, `2` validation failure (the message names the offending claim), `1` file or IO error.

If it exits `2`, fix `claims.json`. Do not edit the rendered output to compensate — that defeats the mechanism the product is built on.

## Migrating from schema_version 1

Version 1 files are rejected with an explanatory message. To migrate: rename `evidence_id` to `evidence_ids` and wrap the value in a list, delete any `source` field, and set `"schema_version": 2`.

## After rendering

Read each output file back and confirm non-zero size before reporting success. Then show the user the sections, the counts, and the gaps.
