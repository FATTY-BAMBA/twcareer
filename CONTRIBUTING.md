# Development loop

## Repo layout

```
.claude-plugin/marketplace.json     ← the catalogue (marketplace level)
plugins/twcareer/
  .claude-plugin/plugin.json        ← the plugin manifest (plugin level)
  skills/cv/SKILL.md
  skills/cv/references/*.md         ← Taiwan judgment, one module per topic
  scripts/render_application.py     ← the evidence filter
tests/                              ← renderer tests; run before every release
```

The two `.claude-plugin/` directories are at different levels on purpose. `marketplace.json` sits at the repo root; `plugin.json` sits inside the plugin's own folder. They are not interchangeable and cannot share a directory.

## The loop

```
edit  →  bump version in plugins/twcareer/.claude-plugin/plugin.json  →  push  →  update in Cowork
```

The skill reports its version at the start of every run by reading `plugin.json`, so a stale installed copy announces itself instead of silently applying old rules. Nothing to maintain by hand.

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
2. Run the test suite. It covers the checks the product is built on — an unevidenced claim never reaching the application, and a `SUPPORTED` claim citing an ID that does not exist in `profile.md` failing the build rather than rendering.

   ```bash
   python3 -m unittest discover tests
   ```

   No dependencies; the fixtures live in `tests/fixtures/`. Add a case whenever you add a validation rule — a rule without a test is a rule that will regress quietly.

   After a real adversarial run, check the rendered output too:

   ```bash
   python3 tests/check_adversarial.py career/outputs/<folder> \
       --profile career/profile.md \
       --claims career/outputs/<folder>/claims.json \
       --forbid Python SQL RAG Docker
   ```

   It asserts that no forbidden capability reached the application, that each
   one is surfaced in `gaps.md`, that every evidence row resolves, and that a
   fake ID and a misspelled section still fail the build.
3. Bump the version.

## Testing a change

Install your own copy from this marketplace rather than uploading a `.plugin` file. Uploaded packages are treated as one-off installs and a second upload of the same plugin name collides instead of upgrading. Marketplace installs update in place.

## Knowledge modules

`skills/cv/references/taiwan-resume-conventions.md` carries a `Last reviewed` date per rule. When a convention changes — 104 changes its sections, expectations around 自傳 shift — update that one module and its date, then PATCH bump. Do not scatter local facts into `SKILL.md`; the point of the modules is that the moat is maintainable in one place.

## Roadmap

- `/twcareer:interview` — fixed-arc Taiwan HR interview simulation with a written assessment
- Application tracker — `Application History` is already stubbed in `profile.md`
- `/twcareer:find` — 台灣就業通 open data matching. Verify the dataset's fields and per-query limits directly before building against them; they are not confirmed.
