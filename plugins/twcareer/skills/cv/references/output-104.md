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
  "evidence_id": "EXP-02",
  "source": "source-resume.pdf — 工作經歷 #2",
  "note": ""
}
```

| Field | Required | Notes |
|---|---|---|
| `text` | yes | the claim in the JD's language |
| `text_en` | no | English version; must state the same thing as `text` |
| `state` | yes | `SUPPORTED`, `USER_CONFIRMED`, or `UNSUPPORTED` |
| `evidence_id` | when `SUPPORTED` | a real ID from profile.md |
| `note` | when `USER_CONFIRMED` | what the user actually said, and when |
| `source` | recommended | where the evidence sits |

The renderer **rejects the file** if a `SUPPORTED` claim has no `evidence_id` or a `USER_CONFIRMED` claim has no `note`. That is deliberate — an unverifiable claim should stop the build, not slip through.

## File structure

```json
{
  "schema_version": 1,
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

Outputs into the same folder:

| File | Contents |
|---|---|
| `104-application.md` | paste-ready sections, evidenced claims only |
| `evidence-map.md` | every accepted claim and what backs it |
| `gaps.md` | dropped claims plus declared gaps, framed as interview prep |

Exit codes: `0` success, `2` validation failure (the message names the offending claim), `1` file or IO error.

If it exits `2`, fix `claims.json`. Do not edit the rendered output to compensate — that defeats the mechanism the product is built on.

## After rendering

Read each output file back and confirm non-zero size before reporting success. Then show the user the sections, the supported/confirmed counts, and the gaps.
