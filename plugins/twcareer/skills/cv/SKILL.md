---
name: cv
description: Tailors the user's résumé to a specific Taiwan job posting and produces paste-ready 104 application sections, using only claims traceable to real evidence. Use when the user runs /twcareer:cv, pastes a JD or job posting and wants their résumé adapted to it, asks to 客製履歷, 改履歷, 調整履歷, tailor a resume, or prepare a 104 application. Also handles first-run setup of the career profile.
---

# 客製履歷 / Tailor résumé for a Taiwan job posting

Produce application material for one specific job posting, in which **every substantive claim is traceable to evidence the user actually has**. Missing qualifications are reported as gaps, never written into the résumé.

Speak to the user bilingually: 繁體中文 first, English second, on separate lines. Résumé content itself follows the language of the job description.

## Step 0 — Announce the build, then locate the workspace

First, print which build is running:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_application.py" --version
```

Show that line to the user before anything else. During preview this is not decoration: an installed copy can silently differ from the repo, and without the version on screen you cannot tell whether a bug you are chasing exists in the committed code or only in a stale install.

Then run `pwd`. Look for `career/profile.md` relative to it.

### 0a. Durability check — do this before writing anything

A career profile is only worth building somewhere it will still exist next week. Before any intake, confirm the working directory is a folder on the user's own computer that they can reconnect later.

Treat the location as **not durable** when any of these hold:

- the working directory is a container or session home such as `/home/claude`, `/workspace`, `/tmp`, or a path the user has never named
- the folder contains no files belonging to the user — only tooling, caches or plugin directories
- the session is running in a browser or a cloud environment with no folder connected from the user's machine

If the location is not durable, **stop and say so**. Do not run intake.

> 這個工作階段沒有連到你電腦上的資料夾，我現在能寫入的地方在工作階段結束後就會消失。
> This session isn't connected to a folder on your computer — anything I write here disappears when the session ends.
>
> 請在桌面版開啟一個任務，連到你要放職涯檔案的資料夾，再執行一次。
> Open a task in the desktop app, connect the folder where your career profile should live, and run this again.

If the location looks durable but you are not certain, say where you are about to write, in full, and ask the user to confirm it is the right folder before proceeding. One confirmation on first run is cheap; a profile that silently evaporates is not.

Once confirmed, continue:

**If `career/profile.md` exists** → read it, confirm in one line whose profile it is, and go to Step 2.

**If it does not exist**, check whether a `career/` folder exists at all with any files in it. Then:

- **No `career/` folder** → this is likely genuine first use. Go to Step 1.
- **`career/` exists but `profile.md` is missing or empty** → say so plainly and offer to rebuild the profile. Do not silently overwrite anything already there.

**Folder-miss path (important).** If the user has used this before but the profile is not here, the likely cause is a different folder being connected, not lost data. Say:

> 我在這個資料夾找不到你的職涯檔案。你之前可能連到別的資料夾。
> I can't find your career profile in this folder — you may have connected a different one.
>
> 要（A）重新指定正確的資料夾，還是（B）在這裡建立新的檔案？
> Would you like to (A) point me at the right folder, or (B) start a new profile here?

Never re-run intake without asking. Repeating setup on someone who already did it is the worst failure mode of this skill.

## Step 1 — First-run intake

Read `references/profile-schema.md` before writing anything.

1. Ask the user for their existing résumé — a file in this folder, an upload, or pasted text. If they have none, say intake will take longer and ask whether to continue.
2. Read it. Extract everything into the schema. **Assign a stable ID to every experience, skill, project and certification** (`EXP-01`, `SKILL-04`, `PROJ-02`, `CERT-01`). These IDs are what evidence references point at, so they must never be reused or renumbered later.
3. Ask **only** for what is genuinely missing and genuinely needed: target roles, expected compensation range, notice period, location and remote preference, work authorization. Ask in small batches, not one giant form. Do not ask for anything already in the résumé.
4. Write `career/profile.md` using the schema exactly.
5. Copy or note the source résumé path as `career/source-resume.*` if it is not already in this folder.
6. **Read the file back and confirm its byte size is non-zero.** Creating a file and writing content to it are separate operations and the second can fail silently. Never report success without reading back.
7. Tell the user where the profile lives, in plain language, and that they can open, edit or delete it themselves.

## Step 2 — Get the job description

Accept a JD as: text pasted in the message, a file path in this folder, an uploaded file, or a screenshot. If a URL is given, ask the user to paste the text instead — do not fetch job boards.

Extract into a requirements list, each tagged as **必要 (required)** or **加分 (preferred)**. Read `references/taiwan-resume-conventions.md` for what a Taiwan JD's sections usually mean and which requirements are real versus boilerplate.

## Step 3 — Match claims to evidence

Read `references/evidence-rules.md` before this step. It is the core of the product; do not improvise it.

For every requirement, search the profile for supporting evidence and assign exactly one state:

- `SUPPORTED` — directly backed by a profile entry. Must carry that entry's ID.
- `USER_CONFIRMED` — absent from the profile, but the user explicitly supplied it during this session. Must carry a note on what they said.
- `UNSUPPORTED` — no evidence exists.

When a requirement looks important and evidence is thin, **ask the user before concluding**. Ask concretely: 「JD 要求 SQL，但你的履歷裡沒有相關證據。你實際上用過 SQL 嗎？在哪個專案？」 If they give a real answer, it becomes `USER_CONFIRMED` and gets appended to the profile with a new ID. If they say no, it stays `UNSUPPORTED` and is not negotiable.

Never upgrade a state to make the application look better. An `UNSUPPORTED` requirement is useful information, not a problem to be solved by wording.

## Step 4 — Build the claims file

Write `career/outputs/<company>-<role>/claims.json` following the schema documented in `references/output-104.md`.

Every claim object needs `text`, `state`, and — for `SUPPORTED` — an `evidence_id` pointing at a real profile ID. Rewriting is allowed and encouraged: turn 「負責社群媒體」 into a specific, concrete description of what they actually did. Adding facts is not. If a number was not in the source and the user did not state it, it does not appear.

## Step 5 — Render deterministically

Do not hand-write the final output. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_application.py" career/outputs/<company>-<role>/claims.json
```

The renderer drops any claim not in `SUPPORTED` or `USER_CONFIRMED` and routes it to the gap report. This is enforced in code, not by instruction — if the script rejects the file, fix the claims, never work around the script or write the output manually.

It produces, in the same folder:

- `104-application.md` — paste-ready sections
- `evidence-map.md` — every claim and what backs it
- `gaps.md` — unmet requirements and how they are likely to come up in interview

Read each back and confirm non-zero size.

## Step 6 — Report

Show the user:

1. The 104 sections, ready to paste, section by section
2. A short evidence summary: how many claims are `SUPPORTED`, how many `USER_CONFIRMED`
3. The gaps, framed as interview preparation rather than failure
4. Where the files are saved

Then state plainly what was **not** done: 「我沒有幫你加上任何你沒有證據的經歷。」 / "I did not add anything you don't have evidence for."

## Hard rules

- Never write an `UNSUPPORTED` claim into résumé output, even if the user asks. If pressed, explain that the value of the tool is that its output is defensible in an interview, and offer to help them build real evidence instead.
- Never invent numbers, percentages, team sizes, budgets, or dates.
- Never fetch or scrape job boards. The user supplies the JD.
- Never write outside the `career/` folder in the current working directory.
- Always read back what you write and confirm it is non-empty before reporting success.
- If any step fails, say so directly. A silent partial success is worse than a clear failure.
