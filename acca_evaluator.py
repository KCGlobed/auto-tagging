"""ACCA scenario-based answer evaluation.

See docs/acca-scenario-evaluation.md for the full logic.
"""
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "acca_scenario_system_prompt.md"

# Keep each text within a safe size for the model context.
MAX_CHARS = 30000

CRITERIA_WEIGHTS = {
    "requirement_and_scenario_application": 0.40,
    "technical_accuracy": 0.30,
    "numerical_accuracy": 0.20,
    "clarity_and_completeness": 0.10,
}


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Input normalization: HTML (Lexical editor), Excel sheet JSON, or plain text
# ---------------------------------------------------------------------------

_BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "tbody", "thead"}


class _HTMLToText(HTMLParser):
    """Converts HTML to plain text, keeping paragraphs and table rows readable."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self.current = []
        self.row = None
        self.cell = None
        self.skip = 0

    def _flush_line(self):
        text = re.sub(r"[ \t ]+", " ", "".join(self.current)).strip()
        if text:
            self.lines.append(text)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "colgroup"):
            self.skip += 1
        elif tag == "tr":
            self._flush_line()
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag == "br":
            self._write(" " if self.cell is not None else "\n")
        elif tag in _BLOCK_TAGS:
            if self.cell is not None:
                self.cell.append(" ")
            else:
                self._flush_line()

    def handle_endtag(self, tag):
        if tag in ("style", "script", "colgroup"):
            self.skip = max(0, self.skip - 1)
        elif tag in ("td", "th") and self.cell is not None:
            text = re.sub(r"[ \t ]+", " ", "".join(self.cell)).strip()
            if self.row is not None:
                self.row.append(text)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            cells = [c for c in self.row if c]
            if cells:
                self.lines.append(" | ".join(cells))
            self.row = None
        elif tag in _BLOCK_TAGS and self.cell is None:
            self._flush_line()

    def _write(self, data):
        if self.cell is not None:
            self.cell.append(data)
        elif data == "\n":
            self._flush_line()
        else:
            self.current.append(data)

    def handle_data(self, data):
        if not self.skip:
            self._write(data.replace("\n", " "))

    def text(self):
        self._flush_line()
        return "\n".join(self.lines)


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _cell_value(value) -> str:
    """Extracts display text from a Fortune-sheet / Luckysheet cell value."""
    if value is None:
        return ""
    if not isinstance(value, dict):
        return str(value)
    ct = value.get("ct") or {}
    if isinstance(ct, dict) and isinstance(ct.get("s"), list):
        return "".join(str(part.get("v", "")) for part in ct["s"] if isinstance(part, dict))
    for key in ("m", "v"):
        if value.get(key) is not None:
            return str(value[key])
    return ""


def _is_sheet_json(data) -> bool:
    sheets = data if isinstance(data, list) else [data]
    return bool(sheets) and all(
        isinstance(s, dict) and ("celldata" in s or "data" in s) for s in sheets
    )


def _sheets_to_text(data) -> str:
    sheets = data if isinstance(data, list) else [data]
    blocks = []
    for sheet in sheets:
        cells = {}
        if isinstance(sheet.get("celldata"), list):
            for item in sheet["celldata"]:
                if isinstance(item, dict) and "r" in item and "c" in item:
                    cells[(item["r"], item["c"])] = _cell_value(item.get("v"))
        elif isinstance(sheet.get("data"), list):
            for r, row in enumerate(sheet["data"]):
                for c, value in enumerate(row or []):
                    cells[(r, c)] = _cell_value(value)

        rows = {}
        for (r, c), text in cells.items():
            text = re.sub(r"\s+", " ", text.replace("\r", "\n")).strip()
            if text:
                rows.setdefault(r, []).append((c, text))

        lines = []
        for r in sorted(rows):
            parts = [f"[{_column_letter(c)}] {t}" for c, t in sorted(rows[r])]
            lines.append(f"Row {r + 1}: " + " | ".join(parts))
        if lines:
            name = sheet.get("name") or "Sheet"
            blocks.append(f"Sheet: {name}\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def _unescape_literal(text: str) -> str:
    """Undoes double-escaping that sometimes arrives from the frontend (\\" and \\u00a3)."""
    if '\\"' in text:
        text = text.replace('\\"', '"')
    if "\\u" in text:
        text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    if "\\n" in text or "\\r" in text:
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    return text


def normalize_answer(content) -> str:
    """Converts HTML, Excel sheet JSON (string or parsed) or plain text into clean plain text."""
    if not content:
        return ""
    if isinstance(content, (list, dict)):
        return _sheets_to_text(content)[:MAX_CHARS] if _is_sheet_json(content) else json.dumps(content)[:MAX_CHARS]
    text = content.strip()

    if text[:1] in ("[", "{"):
        try:
            data = json.loads(text)
            if _is_sheet_json(data):
                return _sheets_to_text(data)[:MAX_CHARS]
        except (ValueError, TypeError):
            pass

    text = _unescape_literal(text)

    if re.search(r"<\s*(p|span|table|tr|td|div|br|strong|b|li)\b", text, re.IGNORECASE):
        parser = _HTMLToText()
        parser.feed(text)
        parser.close()
        text = parser.text()
    else:
        text = html.unescape(text)

    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_CHARS]


# A line starting with "Tutorial Note" (any case, optional plural/colon/dash) begins
# study guidance for students, which is not part of the marking scheme.
_TUTORIAL_NOTE_RE = re.compile(r"^[ \t*#>\-]*tutorial\s+notes?\b", re.IGNORECASE | re.MULTILINE)


def strip_tutorial_notes(reference: str) -> str:
    """Drops everything from the first "Tutorial Note" heading onwards.

    Falls back to the full text if nothing would be left to mark against.
    """
    match = _TUTORIAL_NOTE_RE.search(reference)
    if not match:
        return reference
    trimmed = reference[:match.start()].strip()
    return trimmed or reference


# ---------------------------------------------------------------------------
# Prompt building and result handling
# ---------------------------------------------------------------------------

def build_messages(student_answer: str, reference_answer: str, question: Optional[str] = None):
    question_text = question or "(not provided - infer the requirement from the reference answer)"
    user_content = f"""Mark the student answer against the reference answer. Return ONLY the JSON object defined in the system instructions.

=== QUESTION / REQUIREMENT ===
{question_text}

=== REFERENCE ANSWER (marking scheme) ===
{reference_answer}

=== STUDENT ANSWER ===
{student_answer}
"""
    return [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": user_content},
    ]


def _to_score(value) -> Optional[float]:
    try:
        return min(10.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return None


def weighted_criteria_score(parsed: dict) -> Optional[float]:
    criteria = parsed.get("criteria")
    if not isinstance(criteria, dict):
        return None
    weights = dict(CRITERIA_WEIGHTS)
    if parsed.get("numeric_applicable") is False:
        weights.pop("numerical_accuracy")
    total, weight_sum = 0.0, 0.0
    for key, weight in weights.items():
        score = _to_score(criteria.get(key))
        if score is None:
            return None
        total += score * weight
        weight_sum += weight
    return total / weight_sum if weight_sum else None


def finalize_score(parsed: dict) -> Optional[float]:
    """Blends the model's holistic score with the weighted rubric score for stability."""
    holistic = _to_score(parsed.get("score"))
    weighted = weighted_criteria_score(parsed)
    if holistic is None and weighted is None:
        return None
    if holistic is None:
        final = weighted
    elif weighted is None:
        final = holistic
    else:
        final = (holistic + weighted) / 2
    return round(final, 1)


# ---------------------------------------------------------------------------
# Student-facing reason: where marks were earned and why they were deducted
# ---------------------------------------------------------------------------

def _clean_list(value):
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _num(value, default=0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _split_marking_points(parsed: dict, score: float):
    """Splits marking points into (correct, deductions); deductions add up to exactly 10 - score.

    The model allocates 10 marks across the reference's marking points. The final score is
    blended with the rubric (see finalize_score), so the model's per-point losses are scaled
    to the actual marks lost, keeping the feedback consistent with the score shown.
    """
    points = [p for p in parsed.get("marking_points") or [] if isinstance(p, dict)]
    total_lost = round(10 - score, 1)

    correct, deductions, raw_losses = [], [], []
    for p in points:
        available = _num(p.get("marks_available"))
        awarded = min(_num(p.get("marks_awarded")), available) if available else 0.0
        status = str(p.get("status") or "").lower()
        # Old-style or incomplete output without marks: infer the loss from the status
        if not available:
            raw_loss = {"full": 0.0, "partial": 0.5}.get(status, 1.0)
        else:
            raw_loss = available - awarded
        entry = {
            "point": p.get("point"),
            "status": status,
            "expected": p.get("expected"),
            "student_answer": p.get("student_answer"),
        }
        if raw_loss > 0 and status != "full":
            entry["why_marks_lost"] = p.get("why_marks_lost") or p.get("note")
            deductions.append(entry)
            raw_losses.append(raw_loss)
        else:
            correct.append(entry)

    # Scale the per-point losses so they add up to exactly the marks lost overall
    raw_sum = sum(raw_losses)
    if deductions and raw_sum > 0 and total_lost > 0:
        scaled = [round(loss / raw_sum * total_lost, 1) for loss in raw_losses]
        biggest = max(range(len(scaled)), key=scaled.__getitem__)
        scaled[biggest] = round(scaled[biggest] + total_lost - sum(scaled), 1)
        for entry, marks in zip(deductions, scaled):
            entry["marks_lost"] = marks
    elif total_lost > 0:
        # Every point matched, but the overall mark still fell short (e.g. thin explanation)
        for entry in deductions:
            entry["marks_lost"] = 0.0
        deductions.append({
            "point": "Overall quality of the answer",
            "status": "partial",
            "expected": "Clear, complete answer that fully meets the requirement",
            "student_answer": None,
            "why_marks_lost": "The key points are present, but the explanation, analysis or presentation falls short of a full-mark answer",
            "marks_lost": total_lost,
        })
    else:
        # Full marks: move any stray deductions to the correct list
        correct.extend(deductions)
        deductions = []

    deductions = [d for d in deductions if d.get("marks_lost", 0) > 0]
    deductions.sort(key=lambda d: d["marks_lost"], reverse=True)

    return correct, deductions


def _fmt(marks: float) -> str:
    return f"{marks:g}"


def build_reason(parsed: dict, score: float) -> str:
    """Builds the student-facing reason: summary, then each deduction with why marks were lost.

    Marks lost per point are scaled so they add up to exactly 10 - score.
    """
    correct, deductions = _split_marking_points(parsed, score)
    summary = str(parsed.get("reason") or "").strip()
    lines = [summary] if summary else []

    if deductions:
        lines += ["", f"Marks deducted ({_fmt(round(10 - score, 1))} of 10):"]
        for d in deductions:
            detail = str(d.get("why_marks_lost") or "").strip()
            expected = str(d.get("expected") or "").strip()
            wrote = str(d.get("student_answer") or "").strip()
            line = f"- {d.get('point')} (-{_fmt(d['marks_lost'])}, {d.get('status') or 'partial'})"
            if detail:
                line += f": {detail.rstrip('.')}."
            if expected:
                line += f" Expected: {expected.rstrip('.')}."
            if wrote and d.get("status") != "missing" and wrote.lower() != "not attempted":
                line += f" You wrote: {wrote.rstrip('.')}."
            lines.append(line)

        missing = [str(d.get("point")) for d in deductions if d.get("status") == "missing"]
        if missing:
            lines += ["", "Missing parts: " + "; ".join(missing) + "."]

    earned = [str(c.get("point")) for c in correct if c.get("point")]
    strengths = _clean_list(parsed.get("strengths"))
    if earned or strengths:
        lines += ["", "What you did well:"]
        lines += [f"- {item}" for item in (strengths or earned)]

    improvements = _clean_list(parsed.get("improvements"))
    if improvements:
        lines += ["", "How to improve:"]
        lines += [f"- {item}" for item in improvements]

    return "\n".join(lines).strip()


BLANK_ANSWER_REASON = (
    "No answer was provided.\n\n"
    "Marks deducted (10 of 10):\n"
    "- Whole answer (-10, missing): nothing was attempted.\n\n"
    "How to improve:\n"
    "- Attempt every part of the requirement; even partial workings can earn marks."
)
