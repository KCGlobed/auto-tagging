# ACCA Scenario-Based Answer Evaluation

`POST /api/scenario-verify` marks a student's answer to an ACCA scenario-based question out of 10. It compares the answer with the reference (model) answer the way an ACCA examiner would.

It sits next to `/api/essay-verify` and accepts the same request body. The difference is that this endpoint:

- converts HTML (Lexical editor) and Excel-sheet JSON answers into clean text before marking
- marks against a marking scheme built from the reference answer, point by point
- follows ACCA marking principles: requirement verbs, scenario application, own-figure rule
- is calibrated with worked examples (Brownie Co, Tulip Co)
- returns a stable score (temperature 0, fixed seed, weighted-rubric blend)

| File | Purpose |
|---|---|
| [main.py](../main.py) | `/api/scenario-verify` endpoint |
| [acca_evaluator.py](../acca_evaluator.py) | Input normalization, prompt building, score finalization |
| [prompts/acca_scenario_system_prompt.md](../prompts/acca_scenario_system_prompt.md) | The system prompt (marking logic and calibration examples) |
| [scripts/eval_scenario_examples.py](../scripts/eval_scenario_examples.py) | Calibration runner: checks scores against expected ranges |
| [docs/examples/](examples/) | Sample questions, reference answers and student answers |

---

## 1. API

### Request

```json
{
  "user_input": "<student answer: HTML, Excel sheet JSON string, or plain text>",
  "explanation": "<reference answer: HTML or plain text>",
  "model": "gpt-4o",
  "question": "<optional: scenario + requirement text>"
}
```

`user_input`, `explanation` and `model` work exactly as in `/api/essay-verify`. `question` is **optional** and backward compatible. When you send the requirement, marking is more accurate. Without it, the model works out the requirement from the reference answer.

### Response

```json
{
  "status": "success",
  "score": 8.7,
  "reason": "All five ratios match the reference (ROCE 27.0%, margin 12.5%, ...). The adjusting-event justification under IAS 10 is not stated.",
  "breakdown": {
    "requirement_verb": "calculate",
    "criteria": {
      "requirement_and_scenario_application": 9,
      "technical_accuracy": 8,
      "numerical_accuracy": 10,
      "clarity_and_completeness": 8
    },
    "marking_points": [
      {"point": "Inventory write-down 1,050", "status": "full", "note": "..."}
    ]
  }
}
```

`score` and `reason` have the same meaning as in `/api/essay-verify`. `breakdown` is extra detail for debugging or for showing feedback to students.

Special cases:

- Blank student answer (for example `<p> </p>` or an empty sheet): returns score `0` without calling OpenAI.
- Missing `user_input` or `explanation`: returns HTTP 400.

---

## 2. Processing pipeline

```
user_input / explanation / question
        │
        ▼
normalize_answer()          HTML → text (tables as "cell | cell | cell")
                            Excel JSON → "Row N: [A] ... | [B] ..."
                            un-escapes \"  £  &nbsp;  &amp;
        │
        ▼
build_messages()            system prompt (marking logic + calibration)
                            + QUESTION / REFERENCE / STUDENT sections
        │
        ▼
OpenAI chat completion      JSON mode, temperature 0, seed 42
        │
        ▼
finalize_score()            (holistic score + weighted criteria score) / 2
        │
        ▼
{status, score, reason, breakdown}
```

### 2.1 Input normalization

| Input shape | Detection | Conversion |
|---|---|---|
| Excel sheet JSON (Fortune-sheet/Luckysheet) | Starts with `[`/`{`, parses as JSON, sheets have `celldata` or `data` | Each non-empty row becomes `Row N: [A] text \| [B] text`. Rich text (`ct.s[].v`), `m` and `v` values are supported. |
| HTML | Contains `<p>`, `<span>`, `<table>`, `<td>`, `<div>`, `<br>`, ... | Paragraphs become lines. Table rows become `cell \| cell \| cell`. Styles and `colgroup` are dropped. Entities are decoded. |
| Double-escaped HTML (`\"`, `£`) | Literal backslash sequences | Un-escaped first, then treated as HTML |
| Plain text | Anything else | Line endings and whitespace are normalized |

Example: the Excel answer in the samples becomes:

```
Sheet: Sheet1
Row 1: [A] he issue of convertible loan notes has the potential to dilute ... Calculate the diluted earnings per share ...
Row 2: [A] to the profit or loss for th=89
Row 12: [A] Prepare a schedule
```

Each text is capped at 30,000 characters.

---

## 3. Marking logic (system prompt)

The full prompt is in [prompts/acca_scenario_system_prompt.md](../prompts/acca_scenario_system_prompt.md). It is loaded from disk on every request, so you can edit it without changing code. It is built from the original evaluation spec, restructured so the model marks the way an examiner does.

### 3.1 Official basis (ACCA Global)

- Constructed-response questions reward applying knowledge to the scenario, not reproducing theory.
- Valid points that address the requirement and scenario earn credit, including valid alternatives not in the reference.
- The requirement verb sets the depth of answer expected.
- Repeating scenario facts without analysis earns limited credit.
- Workings and numerical application earn marks.

References:
- [Passing Strategic Professional exams](https://www.accaglobal.com/gb/en/student/exam-support-resources/professional-exams-study-resources/strategic-business-leader/technical-articles/passing-strategic-professional-exams.html)
- [Maximise marks (SBR)](https://www.accaglobal.com/gb/en/student/exam-support-resources/professional-exams-study-resources/strategic-business-reporting/technical-articles/maximise-marks.html)
- [Approach to questions (F8)](https://www.accaglobal.com/gb/en/student/exam-support-resources/fundamentals-exams-study-resources/f8/technical-articles/approach-sept16.html)

### 3.2 Requirement verbs

| Verb | What earns marks |
|---|---|
| calculate / compute / prepare | Figures, workings and final answers. Brief labels are enough. |
| identify / list / state | Concise valid points |
| explain / describe / discuss | Each point plus supporting explanation |
| analyse / evaluate / assess | Scenario fact, then its implication or consequence |
| recommend / advise | An action that logically fixes the scenario issue |

### 3.3 Marking procedure (steps the model follows)

1. **Build the marking scheme** from the reference answer: 3–10 key points (adjustments, calculation steps, final figures, conclusions). Final answers and scenario-specific adjustments weigh most.
2. **Clean the student answer.** Copied question text earns zero. Spelling, grammar, abbreviations and layout are ignored. Synonyms count as matches (PBIT = EBIT = profit from operations).
3. **Classify each marking point** as `full`, `partial`, `missing` or `incorrect`.
4. **Score four criteria** from 0 to 10:

   | Criterion | Weight |
   |---|---|
   | Requirement and scenario application | 40% |
   | Technical concept and accuracy | 30% |
   | Numeric, entity and calculation match | 20% |
   | Clarity, completeness and structure | 10% |

   If the question is purely discursive (`numeric_applicable: false`), the numeric weight is removed and the other weights are rescaled.
5. **Give a holistic score** that fits the score bands.

### 3.4 Numeric rules

- Different formats of the same value match: `5,000 = 5000 = 5k`, and `25,270` in a £000 table = `£25.27m`.
- Rounding differences match: `27.0% = 27%`, `2.16x ≈ 2.2x`, `17.8 days ≈ 18 days`.
- **Own-figure rule:** if a later step correctly uses an earlier wrong figure, the error is penalised only once.
- A correct method with an arithmetic slip earns partial credit.
- If the student skips a required adjustment, the adjustment is marked `missing` and the figures that depend on it are `partial` at best.
- A materially wrong figure that changes the conclusion is marked `incorrect`.
- Correct numbers with no explanation keep substantial credit when the requirement is a calculation.

### 3.5 Score bands

| Score | Meaning |
|---|---|
| 9–10 | Full answer: all key points and figures, appropriate workings |
| 7–8.5 | Core points and most figures correct, with minor slips or omissions |
| 5–6.5 | About half the key points; noticeable gaps |
| 3–4.5 | Isolated correct knowledge or figures; substantial gaps or errors |
| 0.5–2.5 | Largely irrelevant or wrong |
| 0 | Blank, question copied back, or entirely irrelevant |

Answer length is never penalised on its own. A short answer loses marks only when the requirement asks for explanation, discussion or recommendation and it is missing. Extra content lowers the score only when it is wrong or contradicts the correct answer.

### 3.6 Final score

```
weighted = Σ criterion_score × weight   (numeric weight removed if not applicable)
score    = round((holistic_score + weighted) / 2, 1)
```

Blending the model's holistic score with the weighted rubric score smooths out single-number noise. The model still has to justify each criterion.

---

## 4. "Training": calibration by worked examples

The system is not fine-tuned. It is **calibrated with in-prompt worked examples** (few-shot), which tell the model what score each type of answer deserves. There are six examples in the prompt:

| # | Question | Student answer type | Target score |
|---|---|---|---|
| 1 | Brownie Co ratios (Note 3) | All adjustments and ratios correct, with typos | 9.0 |
| 2 | Brownie Co ratios | Correct formulas, but Note 3 not applied | 4.5 |
| 3 | Brownie Co ratios | Write-down correct, no ratios | 3.0 |
| 4 | Tulip Co diluted EPS | All figures correct, different wording | 9.5 |
| 5 | Tulip Co | Question copied back plus fragments | 0.0 |
| 6 | Tulip Co diluted EPS | Coupon interest used instead of effective interest | 6.5 |

### Reference figures used in the examples

**Brownie Co (£000)**: cost 3,000 × 70% = 2,100. Write-down 1,050 (adjusting event, IAS 10). Adjusted PFO 25,270. Inventory 6,870. Equity 64,710. Capital employed 93,510.
Ratios: ROCE 27.0%, operating margin 12.5%, asset turnover 2.16x, inventory days 17.8, debt/equity 44.5%.
If Note 3 is not applied: 27.8%, 13.1%, 2.13x, 20.6 days, 43.8%.

**Tulip Co diluted EPS (£000)**: interest saved 18,896 × 8% = 1,512. After 20% tax: 1,209.6. Earnings 7,163 + 1,209.6 = 8,372.6. New shares 20,000/100 × 20 = 4m, so 29m shares in total. Diluted EPS = 28.9p.

### How to improve accuracy over time

1. Collect real student answers with the score a tutor gave them.
2. When the API disagrees with the tutor by more than 1 mark, add a compact worked example to section 6 of the prompt. Describe the answer *type* and its target score; don't paste whole answers. Also add the case to `CASES` in [scripts/eval_scenario_examples.py](../scripts/eval_scenario_examples.py).
3. Re-run the calibration runner and check that the other cases still pass.
4. Keep the prompt to about 10–12 examples at most. When you have 100 or more tutor-marked answers, consider fine-tuning (for example OpenAI fine-tuning on `gpt-4o-mini`) with the same JSON output schema.

### Running the calibration

```bash
uvicorn main:app --port 8000                     # terminal 1 (needs OPENAI_API_KEY in .env)
python scripts/eval_scenario_examples.py          # terminal 2
python scripts/eval_scenario_examples.py --model gpt-4o-mini
```

The runner prints PASS/FAIL, the score and the reason for each case, plus the full breakdown for any failures.

---

## 5. Example requests

```bash
curl -X POST http://localhost:8000/api/scenario-verify \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "ROCE = 25270/93510 = 27%, margin 12.5%, turnover 2.16, inv days 17.8, D/E 44.5%",
    "explanation": "... Brownie Co reference answer ...",
    "model": "gpt-4o"
  }'
```

For an Excel answer, `user_input` can be the sheet array as a JSON **string** or as the raw array:

```json
{ "user_input": "[{\"name\":\"Sheet1\",\"celldata\":[...]}]", "explanation": "<p>...</p>" }
{ "user_input": [{"name": "Sheet1", "celldata": [...]}], "explanation": "<p>...</p>" }
```
