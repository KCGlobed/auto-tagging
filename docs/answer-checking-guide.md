# How Automatic Answer Checking Works

A plain-language guide to the two answer-checking services used by the KC Global Ed learning platform.

---

## 1. What these two services do

When a student types an answer on the platform, the platform can mark it automatically. It sends the answer to one of two checking services. The service returns a **mark out of 10** and a **short reason** for that mark.

| Service | Short name | In one sentence |
|---|---|---|
| `/api/essay-verify` | **Essay Checker** | Compares the student's answer with the model answer and judges how closely they match. |
| `/api/scenario-verify` | **ACCA Scenario Checker** | Marks the answer the way an ACCA examiner would, point by point against the model answer. |

Both services use an AI model (OpenAI's GPT) to read and compare the answers. The difference is in the **instructions** each one gives the AI:

- The **Essay Checker** asks: *"How similar is this answer to the model answer?"*
- The **Scenario Checker** asks: *"If you were an ACCA examiner holding this model answer as the marking scheme, how many marks would this answer earn?"*

---

## 2. Which one should I use?

| Situation | Use |
|---|---|
| Short written answers, definitions, simple journal entries | Essay Checker |
| ACCA-style questions built around a case study (a company, its figures and notes) | **Scenario Checker** |
| Calculation questions such as ratios, EPS, adjusted profit or schedules | **Scenario Checker** |
| The student answered in the **spreadsheet (Excel) editor** | **Scenario Checker** |
| The answer contains tables | **Scenario Checker** |

**In short:** for ACCA exam-style questions, use the Scenario Checker. It is stricter about what matters (the requirement, the scenario, the figures) and more forgiving about what doesn't (spelling, layout, wording).

---

## 3. What you send to the checker

Both services receive the same basic information.

| Item | Required? | What it is |
|---|---|---|
| **Student's answer** | Yes | What the student wrote. It can come from the text editor (with formatting and tables) or the spreadsheet editor. |
| **Model answer** | Yes | The correct solution prepared by the tutor. The checker treats it as the **marking scheme**. |
| **AI model** | No | Which version of the AI to use. If left empty, the standard one (GPT-4o) is used. |
| **Question text** | No (Scenario Checker only) | The question and its requirement, e.g. *"Calculate the diluted EPS…"*. It is optional, but sending it gives more accurate marks. |

> **Tutorial notes are ignored.** In the Scenario Checker, anything in the model answer from the heading **"Tutorial Note"** onwards is removed before marking. Tutorial notes are study guidance for students, so they never add to or take away from a student's mark. Put everything you want marked **above** the Tutorial Note heading.

> **Important:** the quality of the mark depends on the quality of the model answer. A complete model answer with all figures, workings and explanations produces much better marking than a short or partial one.

---

## 4. What you get back

**From both checkers:**

- **Score**: a number from 0 to 10. Decimals are allowed, e.g. 7.5.
- **Reason**: 1–4 sentences explaining the mark, such as what matched, what was missing and what was wrong.

**In the Scenario Checker, the reason explains every deduction**

The Scenario Checker marks like an examiner. It shares out the 10 marks across the key points of the model answer. Its **reason** then tells the student where each mark was won or lost:

- **Summary**: 2–4 sentences on the overall answer.
- **Marks deducted**: one line per point that lost marks, showing:
  - how many marks were lost, and whether the point was partly right, missing or wrong
  - **why** the marks were deducted
  - **what was expected** from the model answer
  - **what the student wrote**, so they can compare
- **Missing parts**: the points the student did not attempt at all.
- **What you did well**: the points and strengths that earned marks.
- **How to improve**: practical steps to gain the lost marks next time.

The marks deducted always **add up to exactly 10 minus the score**. A student with 4.6/10 sees exactly 5.4 marks of deductions, each with a reason.

Example of what a student sees:

> **Score: 4.6 / 10**
>
> Your ratio formulas are correct, but you did not apply Note 3, so the 1,050 write-down is missing and all five ratios differ from the reference (e.g. ROCE 27.8% vs 27.0%).
>
> **Marks deducted (5.4 of 10):**
> - Note 3 inventory write-down (−1.9, missing): You did not apply Note 3, so the 1,050 write-down to NRV was never recognised. Expected: write down inventory by 1,050.
> - ROCE (−1, partial): Correct formula, but you used the profit before the write-down. Expected: 27.0%. You wrote: 27.8%.
> - Inventory holding period (−1, partial): Inventory and cost of sales were not adjusted. Expected: 17.8 days. You wrote: 20.6 days.
> - …and 3 more ratios (−0.5 each)
>
> **Missing parts:** Note 3 inventory write-down.
>
> **What you did well:** all five ratio formulas are correct.
>
> **How to improve:** apply the Note 3 adjustment before calculating ratios.

The Scenario Checker also records four sub-scores behind the scenes (application, technical accuracy, numbers and clarity, explained in section 6).

---

## 5. How the flow works, step by step

### Essay Checker

```
Student submits answer
        ↓
Platform sends: student answer + model answer
        ↓
AI compares the two texts
        ↓
Score (0–10) + reason are returned to the platform
```

1. The student submits the answer.
2. The platform sends the student's answer and the model answer to the Essay Checker exactly as they are.
3. The AI reads both and judges how closely the ideas and numbers match.
4. The score and reason are shown.

### ACCA Scenario Checker

```
Student submits answer (text editor or spreadsheet)
        ↓
Platform sends: student answer + model answer (+ question, if available)
        ↓
STEP 1: Clean up      → formatting, tables and spreadsheet cells become plain readable text; tutorial notes are removed from the model answer
        ↓
STEP 2: Blank check   → if the answer is empty, return 0 straight away
        ↓
STEP 3: Build the marking scheme → the AI lists the key points in the model answer
        ↓
STEP 4: Tick off each point      → full / partial / missing / incorrect
        ↓
STEP 5: Score four areas         → application, accuracy, numbers, clarity
        ↓
STEP 6: Final mark               → overall judgement and weighted score are averaged
        ↓
Score + reason + breakdown are returned to the platform
```

**Step 1: Clean up.** Students answer in a rich text editor (bold text, tables) or a spreadsheet grid. The checker first turns this into clean, readable text, like copying a page into Notepad but keeping tables and rows in order. This way the AI reads the *content* and is not confused by formatting. Any **Tutorial Note** at the end of the model answer is also removed here, because it is guidance for students and not part of the marking scheme.

**Step 2: Blank check.** If nothing was written, the student gets 0 immediately and the AI is not called.

**Step 3: Build the marking scheme.** The AI reads the model answer and lists the points an examiner would award marks for. These are usually 3–10 points, such as *"inventory write-down of £1.05m"*, *"ROCE 27.0%"* or *"diluted EPS 28.9p"*.

**Step 4: Tick off each point.** The AI looks for each point in the student's answer and marks it full, partial, missing or incorrect.

**Step 5: Score four areas.** See section 6.

**Step 6: Final mark.** The AI gives an overall mark. The system also works out a mark from the four area scores using fixed weights. The final score is the **average of the two**, which makes marking more consistent.

---

## 6. What the answers are compared on

### Essay Checker

| Area | Weight | What it means |
|---|---|---|
| Ideas / concepts | 50% | Are the main ideas present and correct? |
| Numbers and key terms | 40% | Do amounts, totals, debit/credit entries and names match? |
| Clarity and completeness | 10% | Is it readable, and is anything important missing? |

### ACCA Scenario Checker

This follows the published marking approach of **ACCA Global**.

| Area | Weight | What it means, in plain words |
|---|---|---|
| **Answering the question, using the case study** | 40% | Did the student do what was asked, for *this* company? Textbook knowledge alone earns little; applying it to the company's situation earns the marks. |
| **Technical correctness** | 30% | Are the accounting rules, standards and formulas right? |
| **Numbers** | 20% | Do the figures, ratios, percentages and totals match the model answer? |
| **Clarity and completeness** | 10% | Are all parts of the question covered, and can the answer be followed? |

If a question has **no numbers at all**, such as a pure discussion question, the "Numbers" area is left out. The other three areas then share its weight, so students are never penalised for not writing numbers when none were needed.

### The question's instruction word matters

ACCA questions start with a word that tells the student how much to write. The Scenario Checker adjusts its expectations to that word:

| The question says… | What earns marks |
|---|---|
| **Calculate / Prepare** | Correct figures and workings. A long explanation is not needed. |
| **Identify / List / State** | Short, correct points |
| **Explain / Describe / Discuss** | Each point with a supporting explanation |
| **Analyse / Evaluate** | Linking each fact to its effect or consequence |
| **Recommend / Advise** | A sensible action that fixes the problem in the case study |

---

## 7. What the checker is forgiving about, and what it is strict about

### ✅ Forgiving: these do NOT lose marks

- **Spelling and grammar mistakes**, e.g. *"invetory writen down"*
- **Different wording.** "Operating profit", "profit from operations" and "PBIT" are treated as the same thing.
- **Different layout.** A table, a list or a paragraph all work, and rows can be in a different order.
- **Different number formats.** 5,000 = 5000 = 5k. "25,270" in a £000 table = £25.27m.
- **Small rounding differences.** 27% = 27.0%. 2.2 times ≈ 2.16 times. 18 days ≈ 17.8 days.
- **Short answers**, as long as the key figures and points are there and the question didn't ask for an explanation.
- **Correct extra points** that aren't in the model answer but are valid for the case study.
- **Carried-forward errors.** If a student makes one mistake early and then uses that wrong figure correctly in later steps, they lose marks only once. Examiners call this the "own figure rule".

### ⛔ Strict: these DO lose marks

- **Copying the question back.** Text pasted from the question earns **zero**.
- **Wrong figures** that change the final answer.
- **Skipping an adjustment the question asked for.** For example, calculating ratios without applying Note 3 when the question says "Using Note 3…".
- **Theory with no link to the company**, when the question asks for application.
- **Missing explanation** when the question says *explain*, *discuss* or *recommend*.
- **Wrong or contradictory extra content.**

---

## 8. What the scores mean

| Score | Meaning |
|---|---|
| **9 – 10** | Excellent. Full answer, all key points and figures correct. |
| **7 – 8.5** | Strong. Core points and most figures right, with small slips or gaps. |
| **5 – 6.5** | Moderate. About half the key points correct, with noticeable gaps. |
| **3 – 4.5** | Weak. A few correct points or figures, but major gaps or errors. |
| **0.5 – 2.5** | Very weak. Mostly irrelevant or wrong. |
| **0** | Blank, only the question copied back, or completely off-topic. |

---

## 9. Worked examples

### Example A: Brownie Co (ratios question)

**Question:** Using Note 3 (slow-moving stock sold at a loss after the year end), adjust the figures and calculate five ratios.

**Model answer (key points):** a stock write-down of £1.05m, then ROCE 27.0%, operating margin 12.5%, asset turnover 2.16 times, inventory days 17.8, debt/equity 44.5%.

| What the student wrote | Expected mark | Why |
|---|---|---|
| All adjustments and all five ratios correct, with lots of spelling mistakes | **about 9** | Every figure matches. Spelling doesn't matter. |
| Correct formulas, but forgot Note 3, so ratios of 27.8%, 13.1%, 2.13, 20.6 days, 43.8% | **about 4.5** | Good method, but the question specifically asked to apply Note 3, so every final figure is off. |
| Only explained the £1.05m write-down, with no ratios | **about 3** | The key adjustment is right, but the main task (the ratios) is missing. |

### Example B: Tulip Co (diluted EPS question)

**Model answer (key points):** interest saved £1,512k, less 20% tax = £1,209.6k. Earnings £8,372.6k. Shares 25m + 4m = 29m. **Diluted EPS 28.9p.**

| What the student wrote | Expected mark | Why |
|---|---|---|
| All figures correct, in their own layout, with an answer of 28.87p | **about 9.5** | 28.87p rounds to 28.9p. Everything matches. |
| Used the 6% coupon interest instead of the 8% effective interest, giving 28.0p | **about 6.5** | The share count and method are right, but the interest figure is wrong, so the final answer is wrong. |
| Pasted the question into the spreadsheet plus a few random words | **0** | Copied question text earns nothing. |

---

## 10. Tips for tutors and content teams

1. **Write complete model answers.** Include every working, figure and explanation you would give marks for. The checker can only find what is in the model answer.
2. **Send the question text** to the Scenario Checker whenever possible. It helps the checker understand what was actually asked.
3. **Use the Scenario Checker for ACCA case-study and calculation questions**, and the Essay Checker for simple short answers.
4. **Review borderline marks.** If a mark looks wrong, note the question, the student's answer, and the mark you would give. The development team can use these cases to "teach" the checker (see section 12).

---

## 11. Good to know (limitations)

- **The mark is an AI judgement, not a human examiner's.** It is designed to be close to an examiner's mark, but tutors should review important or borderline results.
- **Consistency.** The Scenario Checker is set up to give the same mark for the same answer every time. The Essay Checker may vary slightly, by a few tenths of a mark, between runs.
- **Formatting.** The Essay Checker reads answers exactly as submitted, including formatting code. The Scenario Checker cleans formatting first, so it handles tables and spreadsheets better.
- **Very long answers** are cut off at roughly 30,000 characters (about 10–12 pages).
- **Internet connection to OpenAI is required.** If the AI service is unavailable, the checker returns an error instead of a mark.

---

## 12. How the Scenario Checker is "trained"

The checker is not retrained like a traditional machine-learning model. Instead, its instructions include **worked examples**: sample answers with the mark an examiner would give, such as the Brownie Co and Tulip Co cases above. The AI uses these as a benchmark, much as a new marker is shown sample scripts before starting.

To improve it over time:

1. Tutors collect cases where the automatic mark differs from their own by more than 1 mark.
2. The development team adds the most useful cases as new worked examples.
3. A test run checks that all examples still get the expected marks.

---

## 13. Frequently asked questions

**Does a spelling mistake reduce the mark?**
No. Both checkers ignore spelling, grammar and punctuation.

**The student's answer is correct but worded completely differently. Will it lose marks?**
No. The checker compares meaning and figures, not exact words.

**The student answered in a spreadsheet. Does that work?**
Yes, with the Scenario Checker. It reads each cell and row, whatever the layout.

**Does a short answer always get a low mark?**
No. If the key figures and points are there, a short answer can score highly. It loses marks only when the question asked for an explanation that isn't there.

**What happens if the student copies the question into their answer?**
The copied part is ignored and earns no marks.

**Can the student get marks for a correct point that isn't in the model answer?**
Yes, in the Scenario Checker, if the point is valid for the case study and relevant to the question.

**The model answer has a Tutorial Note at the end. Is it used for marking?**
No. The Scenario Checker only uses the part of the model answer that comes before the "Tutorial Note" heading.

**Why is the Scenario Checker's reason more detailed than the Essay Checker's?**
The Scenario Checker marks point by point like an examiner, so its reason can list which points earned marks, which lost marks and why. The Essay Checker gives an overall similarity judgement only.

**Do the marks deducted always match the score?**
Yes. The marks deducted in the reason always add up to exactly 10 minus the score.

---

*For technical details (request format, fields, error codes), see [acca-scenario-evaluation.md](acca-scenario-evaluation.md).*
