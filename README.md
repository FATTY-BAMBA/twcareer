# twcareer — 台灣職涯 Copilot

> **v0.x — Preview / 開發中.** Interfaces and output format will change. Not yet recommended for a real job application you care about.

把你想投的職缺丟進來，它用你**真的做過**的經歷改寫履歷，產出可以直接貼進 104 的內容，並告訴你哪裡有缺口。

Give it the job you want to apply for. It rewrites your résumé from experience you can actually evidence, produces paste-ready 104 sections, and tells you where the gaps are.

---

## 安裝 / Install

**Cowork（桌面版）**

Customize → Plugins → Add marketplace → 貼上這個 repo 的網址 → Install `twcareer`

**Claude Code**

```bash
/plugin marketplace add <owner>/twcareer
/plugin install twcareer@twcareer
```

## 使用 / Usage

```
/twcareer:cv
```

第一次執行會建立 `career/profile.md`。之後每次只要給它職缺內容。

**必須在桌面版、並連到你電腦上的資料夾執行。** 沒有連到資料夾時，外掛會拒絕建立檔案 —— 因為那些檔案在工作階段結束後就消失了。

Run it in the desktop app with a folder connected. Without one, the plugin refuses to write, rather than building a profile that silently disappears.

---

## 它不會做的事 / What it will not do

**不會幫你加上你沒做過的東西。** 沒有證據的敘述不會進履歷。這條規則寫在 `scripts/render_application.py` 裡，不是寫在提示詞裡 —— 渲染器會在產出前把沒有證據標記的主張直接移除，並記錄到 `gaps.md`。

Unevidenced claims are stripped by the renderer before output. Enforced in code, not by instruction.

| 狀態 | 意義 | 會進履歷嗎 |
|---|---|---|
| `SUPPORTED` | 原履歷裡有 | ✅ |
| `USER_CONFIRMED` | 你在對話中具體補充 | ✅ |
| `UNSUPPORTED` | 找不到證據 | ❌ → `gaps.md` |

---

## 兩個資料來源，永遠不混在一起 / Two sources of truth

```
GitHub repo              ← 公開 PUBLIC
├── skills/
├── references/          Taiwan conventions, evidence rules
└── scripts/             the renderer

你的 career/ 資料夾        ← 私人 PRIVATE，只在你電腦上
├── profile.md
├── source-resume.*
└── outputs/
```

`career/` 在 `.gitignore` 裡，而且永遠不該被移出去。履歷一旦推上公開 repo，即使刪掉也留在 git 歷史裡。

`career/` is gitignored and must stay that way. A résumé pushed to a public repo remains in git history after deletion.

---

## 隱私 / Privacy

你的履歷和職涯檔案放在**你自己選的工作資料夾**。這個外掛沒有伺服器，不建立會員系統，也不保存任何履歷資料庫。當 Claude 執行分析時，完成任務所需的內容會依你使用的 Claude 服務傳送進行模型處理。

No server, no accounts, no résumé database. Content needed for the analysis is processed by whichever Claude service you use.

它也不會把身分證字號、健康狀況、婚姻或家庭狀況寫進你的檔案 —— 即使某些履歷範本要求這些欄位。

---

## 範圍 / Scope

V1 只做一件事：**JD → 有證據的應徵內容**。

不做：職缺搜尋、爬蟲、薪資資料庫、104 帳號整合。職缺由你提供。

No job search, no scraping, no salary database, no 104 account integration. You supply the JD.

---

## 開發 / Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the release loop.

*Built by PrimeStride AI (首越人工智能)*
