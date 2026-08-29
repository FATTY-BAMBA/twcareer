# Evidence rules

The product promise is that output is defensible in an interview. A résumé that wins a screen and collapses in the room is worse than no résumé. These rules are what make the promise real.

## The three states

### SUPPORTED
Directly backed by an entry in `career/profile.md`. Carries that entry's ID.

The claim may be **rewritten** — sharper, more specific, better matched to the JD's vocabulary — but it may not travel beyond what the source says.

```
Profile   EXP-02: 負責 Facebook、Instagram 經營與內容企劃
Claim     規劃並執行品牌社群內容，涵蓋貼文企劃、製作與成效追蹤
State     SUPPORTED (EXP-02)
```

Legitimate: reordering, sharpening verbs, using the JD's terminology for the same work, merging two responsibilities into one line.

Not legitimate: adding scale (「管理 50 萬粉絲」), adding results (「成長 45%」), adding scope (「跨部門」), adding seniority (「帶領團隊」) — unless each is in the source.

### USER_CONFIRMED
Absent from the profile, but the user explicitly stated it in this session when asked. Carries a note recording what they said and when.

Reached only through a **specific** question, never a leading one:

> 好的問法：「JD 要求 SQL，你的履歷沒有提到。你實際上用過嗎？在哪個工作或專案？做了什麼？」
> 壞的問法：「你應該也會 SQL 吧？要不要加上去？」

A vague yes is not confirmation. 「有啊」 is not evidence; 「在前公司做月報，用 SQL 從內部資料庫撈訂單資料」 is. If the answer stays vague after one follow-up, leave it `UNSUPPORTED`.

Every `USER_CONFIRMED` claim is appended to the profile with a new ID, so the second application never has to ask again.

### UNSUPPORTED
No evidence exists. **Never appears in résumé output.** Routed to the gap report.

## State is derived, not chosen

A claim's provenance follows from the profile entries it cites. You do not get to pick it:

```
every cited entry is document-backed   → SUPPORTED
any cited entry is user-supplied       → USER_CONFIRMED
```

The weaker tier always wins. A paragraph resting on one résumé line and one thing the user said this morning is user-supplied, because the moment that self-reported entry is corrected, a claim marked 原始文件 goes on asserting it.

The renderer computes the same thing from `profile.md` and **rejects the build** when the declared state overstates it. It does not quietly relabel — a wrong `state` left sitting in `claims.json` looks valid to everything that reads it later.

## The hard rule

> Only `SUPPORTED` and `USER_CONFIRMED` claims may enter the application.

This is enforced in `scripts/render_application.py`, which drops anything else before rendering.

A second rule is enforced there too: **every cited ID must exist in `profile.md`**. A claim that points at `EXP-99` when no `EXP-99` was ever written fails the build. Without that check the first rule only proves a claim carries something ID-shaped, which is not the same as carrying evidence. The source shown in the evidence map is likewise read from the profile entry, not written alongside the claim, so the two cannot drift apart.

The rule is code, not good intentions. Do not bypass the renderer, and do not hand-write output to include a claim the renderer rejected.

## When the user asks you to add something they can't evidence

This will happen, and it is the moment the product either means something or doesn't.

> 我不會把沒有證據的內容寫進履歷 —— 因為面試時被問到，你會沒有東西可以講。
> I won't put unevidenced claims in your résumé — in the interview you'd have nothing to say.
>
> 但這個缺口很有用。我可以幫你：
> ① 找出你已經有的、最接近的經驗
> ② 準備面試時被問到這一點的回答
> ③ 列出補這個缺口最快的方式

Offer the alternative every time. Refusing without helping is not the product.

## Rewriting standard

Ask of every rewritten line: **if the interviewer says "tell me more about this," can the user talk for two minutes without inventing anything?** If not, the line has drifted past its evidence. Pull it back.

## Numbers

Numbers are the most common failure. A number may appear only if it is in the source résumé, or the user stated it this session. Never estimate, never round up from a guess, never convert a vague scale into a figure. When a JD clearly wants quantification and none exists, put it in the gap report and tell the user what to go measure.

## Bilingual claims

Where a claim appears in both languages, the two must state the same thing. Do not let the English version become stronger than the 中文, or the reverse. A claim whose translations disagree is two different claims and only one of them has evidence.
