"""Calibration runner for /api/scenario-verify.

Sends each example case to the running API and checks the score falls in the expected range.

Usage:
    uvicorn main:app --port 8000          # in another terminal
    python scripts/eval_scenario_examples.py [--url http://localhost:8000] [--model gpt-4o]
"""
import argparse
import json
from pathlib import Path

import httpx

EXAMPLES = Path(__file__).resolve().parent.parent / "docs" / "examples"


def read(name):
    return (EXAMPLES / name).read_text(encoding="utf-8")


BROWNIE_FULL_TYPOS = """Note 3 - its an adjustng event (sold feb, accounts aprooved 15 march) so invetory writen down to NRV.
cost = 3000 x 70% = 2100, sold for 1050, so loss 1050 (£000)
COS 141,050 , operating profit 26320-1050 = 25,270
inventory 6870, equity 65760-1050 = 64710
capital employed 64710 + 28800 loan = 93510
ROCE 25270/93510 = 27.02%
Op margin 25270/201600 = 12.53%
asset turnover 201600/93510 = 2.16x
inventory days 6870/141050*365 = 17.8
debt:equity 28800/64710 = 44.5%"""

BROWNIE_UNADJUSTED = """ROCE = 26,320 / (65,760 + 28,800) = 27.8%
Operating profit margin = 26,320 / 201,600 = 13.1%
Net asset turnover = 201,600 / 94,560 = 2.13 times
Inventory holding period = 7,920 / 140,000 x 365 = 20.6 days
Debt to equity = 28,800 / 65,760 = 43.8%"""

BROWNIE_WRITEDOWN_ONLY = """The seasonal stock cost £2.1m (70% of £3m) but was sold after the year end for only £1.05m,
so net realisable value is below cost. Because the sale happened before the accounts were authorised
this is an adjusting event under IAS 10 and inventory must be written down by £1.05m."""

TULIP_EPS_PARAPHRASE = """<p>Earnings: profit 7,163 plus interest saved on conversion 1,512 (effective 8% on 18,896) less tax 20% = 1,209.6</p>
<p>so diluted earnings = 8,372.6 (£000)</p>
<table><tr><td>Existing shares</td><td>25m</td></tr><tr><td>Conversion 20m/100 x 20</td><td>4m</td></tr><tr><td>Total</td><td>29m</td></tr></table>
<p>Diluted EPS = 8,372.6 / 29,000 = 28.87p</p>"""

TULIP_EPS_NOMINAL_INTEREST = """Add back interest 20,000 x 6% = 1,200 net of tax 20% = 960. Earnings 7,163 + 960 = 8,123.
Shares 25m + 4m (200,000 units x 20) = 29m. Diluted EPS = 8,123/29,000 = 28.0p"""

CASES = [
    # (name, user_input, explanation, question, min_score, max_score)
    ("brownie: full answer with typos", BROWNIE_FULL_TYPOS, read("brownie_reference.txt"), read("brownie_question.txt"), 8.5, 10),
    ("brownie: Note 3 not applied", BROWNIE_UNADJUSTED, read("brownie_reference.txt"), read("brownie_question.txt"), 3, 6),
    ("brownie: write-down only, no ratios", BROWNIE_WRITEDOWN_ONLY, read("brownie_reference.txt"), None, 1.5, 4.5),
    ("tulip eps: correct, different layout (HTML)", TULIP_EPS_PARAPHRASE, read("tulip_eps_reference.html"), None, 8.5, 10),
    ("tulip eps: nominal instead of effective interest", TULIP_EPS_NOMINAL_INTEREST, read("tulip_eps_reference.html"), None, 5, 7.5),
    ("tulip eps: question copied back (HTML)", read("tulip_eps_student_html.html"), read("tulip_eps_reference.html"), None, 0, 1),
    ("tulip schedule: question + fragments (Excel JSON)", read("tulip_student_excel.json"), read("tulip_schedule_reference.html"), None, 0, 1),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--model", default="gpt-4o")
    args = parser.parse_args()

    passed = 0
    for name, user_input, explanation, question, low, high in CASES:
        body = {"user_input": user_input, "explanation": explanation, "model": args.model}
        if question:
            body["question"] = question
        response = httpx.post(f"{args.url}/api/scenario-verify", json=body, timeout=180)
        result = response.json()
        score = result.get("score")
        ok = score is not None and low <= score <= high
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: score={score} expected={low}-{high}")
        print(f"       reason: {result.get('reason')}")
        if not ok:
            print("       breakdown:", json.dumps(result.get("breakdown"), indent=2)[:2000])
    print(f"\n{passed}/{len(CASES)} cases in expected range")


if __name__ == "__main__":
    main()
