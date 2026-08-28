# Development loop

## Repo layout

```
.claude-plugin/marketplace.json     ← the catalogue (marketplace level)
plugins/twcareer/
  .claude-plugin/plugin.json        ← the plugin manifest (plugin level)
  skills/cv/SKILL.md
  skills/cv/references/*.md         ← Taiwan judgment, one module per topic
  scripts/render_application.py     ← the evidence filter
```

The two `.claude-plugin/` directories are at different levels on purpose. `marketplace.json` sits at the repo root; `plugin.json` sits inside the plugin's own folder. They are not interchangeable and cannot share a directory.

## The loop

```
edit  →  bump version in plugins/twcareer/.claude-plugin/plugin.json  →  push  →  update in Cowork
```

**Always bump the version.** Update detection keys off the `version` field in `plugin.json`. Push a change without bumping and installed copies will not see it — and you will spend an hour debugging a fix that shipped correctly.

## Versioning

| Bump | When |
|---|---|
| PATCH `0.1.1` | bug fix, wording, a knowledge module correction |
| MINOR `0.2.0` | a new skill, a new output, a schema addition |
| MAJOR `1.0.0` | breaking change to `profile.md` or `claims.json`, or the public launch |

Anything that changes the shape of `career/profile.md` or `claims.json` is breaking, because existing users have files in the old shape. Either bump MAJOR or write a migration.

## Before pushing

1. `git status` — confirm no `career/`, no `*.pdf`, no `profile.md`. The `.gitignore` covers these, but check anyway. A résumé in a public repo stays in git history after deletion.
2. Run the renderer against a test claims file and confirm it still drops unevidenced claims:

   ```bash
   python3 plugins/twcareer/scripts/render_application.py path/to/claims.json
   ```

   Deliberately break a claim — remove an `evidence_id` from a `SUPPORTED` one — and confirm it exits `2` rather than rendering. That check is the product; it should be exercised before every release.
3. Bump the version.

## Testing a change

Install your own copy from this marketplace rather than uploading a `.plugin` file. Uploaded packages are treated as one-off installs and a second upload of the same plugin name collides instead of upgrading. Marketplace installs update in place.

## Knowledge modules

`skills/cv/references/taiwan-resume-conventions.md` carries a `Last reviewed` date per rule. When a convention changes — 104 changes its sections, expectations around 自傳 shift — update that one module and its date, then PATCH bump. Do not scatter local facts into `SKILL.md`; the point of the modules is that the moat is maintainable in one place.

## Roadmap

- `/twcareer:interview` — fixed-arc Taiwan HR interview simulation with a written assessment
- Application tracker — `Application History` is already stubbed in `profile.md`
- `/twcareer:find` — 台灣就業通 open data matching. Verify the dataset's fields and per-query limits directly before building against them; they are not confirmed.
