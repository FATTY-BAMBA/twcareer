# twcareer — 台灣職涯 Copilot

把你想投的職缺丟進來，它用你**真的做過**的經歷改寫履歷，產出可以直接貼進 104 的內容，並告訴你哪裡有缺口。

Give it the job you want to apply for. It rewrites your résumé from experience you can actually evidence, produces paste-ready 104 sections, and tells you where the gaps are.

---

## 為什麼不是一個 prompt？ / Why not just a prompt?

因為它**記得你**。

- 你的職涯檔案存在你自己的資料夾裡，不是聊天記錄裡
- 設定一次，之後每個職缺都用同一份真實經歷
- 每一句寫進履歷的話，都可以追溯到你原本的哪一段經驗
- 產出的是檔案，不是聊天視窗裡的文字

Because it remembers you. Your profile lives in a folder you own, setup happens once, and every claim in the output traces back to real evidence.

## 它不會做的事 / What it will not do

**它不會幫你加上你沒做過的東西。** 沒有證據的內容不會進履歷 —— 這條規則寫在程式碼裡，不是寫在提示詞裡。渲染器會直接把沒有證據標記的敘述丟掉。

It will not invent qualifications. Unevidenced claims are stripped by the renderer before output — enforced in code, not by instruction.

---

## 使用方式 / Usage

```
/twcareer:cv
```

第一次執行時，它會請你提供現有履歷，建立 `career/profile.md`。之後每次只要給它職缺內容就好。

First run builds your profile. After that, just give it a JD.

## 產出 / Output

```
career/
├── profile.md                  ← 你的職涯檔案，可自行編輯或刪除
├── source-resume.pdf
└── outputs/
    └── <公司>-<職務>/
        ├── claims.json         ← 每一項主張與其證據
        ├── 104-application.md  ← 可直接貼上的 104 各欄位
        ├── evidence-map.md     ← 證據對照表
        └── gaps.md             ← 缺口與面試風險
```

## 證據狀態 / Evidence states

| 狀態 | 意義 | 會進履歷嗎 |
|---|---|---|
| `SUPPORTED` | 原履歷裡有 | ✅ |
| `USER_CONFIRMED` | 你在對話中具體補充 | ✅ |
| `UNSUPPORTED` | 找不到證據 | ❌ → 進 `gaps.md` |

## 隱私 / Privacy

你的履歷和職涯檔案放在**你自己選的工作資料夾**。這個外掛沒有伺服器，不建立會員系統，也不保存任何履歷資料庫。當 Claude 執行分析時，完成任務所需的內容會依你使用的 Claude 服務傳送進行模型處理。

Your résumé and profile live in a folder you choose. This plugin has no server, no accounts, and keeps no résumé database. When Claude performs the analysis, the content needed for the task is processed by whichever Claude service you use.

它也不會把身分證字號、健康狀況、婚姻或家庭狀況寫進你的檔案 —— 即使某些履歷範本要求這些欄位。

## 範圍 / Scope

V1 只做一件事，並且做好：**JD → 有證據的應徵內容**。

不做：職缺搜尋、爬蟲、薪資資料庫、104 帳號整合。職缺由你提供。

V1 does one thing: JD in, evidenced application out. No job search, no scraping, no salary database, no 104 integration.

---

*Built by PrimeStride AI (首越人工智能)*
