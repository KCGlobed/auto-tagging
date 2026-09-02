from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openpyxl import load_workbook
from dotenv import load_dotenv
import markdown
import os
import io
import re
import httpx
import json

load_dotenv()

app = FastAPI(title="Excel Markdown to HTML Converter")

# Get origins from environment variable, default to ["*"] if not set
origins_str = os.getenv("ALLOWED_ORIGINS", "*")
if origins_str == "*":
    origins = ["*"]
else:
    origins = [origin.strip() for origin in origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://kcglobed-lms-admin.web.app",
        'https://lms-admin.kcglobed.com'
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def text_to_html(text):
    if text is None:
        return None

    print(f"\n--- PROCESSING NEW CELL ---")
    print(f"RAW EXCEL TEXT (repr): {repr(text)}")

    text_str = str(text)
    # Excel sometimes uses \r (carriage return) or \x0b (vertical tab) instead of \n for soft line breaks.
    # We must normalize all these weird characters into standard \n first.
    text_str = text_str.replace('\r\n', '\n')
    text_str = text_str.replace('\r', '\n')
    text_str = text_str.replace('\x0b', '\n')
    text_str = text_str.replace('\u2028', '\n')

    # Now that we only have \n, we replace 1 or more newlines with double newlines
    # so that Markdown wraps each line block in its own <p> tag.
    text_str = re.sub(r'\n+', '\n\n', text_str).strip()

    print(f"NORMALIZED TEXT (repr): {repr(text_str)}")

    html_output = markdown.markdown(
        text_str,
        extensions=[
            "tables",
            "fenced_code",
        ],
    )

    print(f"FINAL HTML OUTPUT: {repr(html_output)}")
    print(f"---------------------------\n")

    return html_output


@app.post("/convert")
async def convert_excel(file: UploadFile = File(...)):
    try:

        if not file.filename.endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail="Please upload only .xlsx file"
            )

        # Read uploaded file
        contents = await file.read()

        # Load workbook
        wb = load_workbook(io.BytesIO(contents))

        # Convert specific columns
        target_columns = {"question", "solution"}

        for sheet in wb.worksheets:
            col_indices = []

            for i, row in enumerate(sheet.iter_rows()):
                if i == 4:
                    # Parse header row (Row 5 is index 4)
                    for idx, cell in enumerate(row):
                        if isinstance(cell.value, str) and cell.value.strip().lower() in target_columns:
                            col_indices.append(idx)
                    continue
                
                # Process data rows for only the target columns
                # (Rows 1-4 will naturally be skipped because col_indices is empty until row 5)
                for idx in col_indices:
                    if idx < len(row):
                        cell = row[idx]
                        if isinstance(cell.value, str):
                            cell.value = text_to_html(cell.value)

        # Save the modified workbook to a new in-memory byte stream
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Output filename
        output_filename = f"converted_{file.filename}"

        headers = {
            'Content-Disposition': f'attachment; filename="{output_filename}"',
            'Access-Control-Expose-Headers': 'Content-Disposition'
        }

        # Return downloadable file from memory
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


from typing import Optional

class EssayVerifyRequest(BaseModel):
    user_input: str
    explanation: str
    model: Optional[str] = "gpt-4o"

@app.post("/api/essay-verify")
async def verify_essay(request: EssayVerifyRequest):
    if not request.user_input or not request.explanation:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: user_input and explanation",
        )

    messages = [
        {
            "role": "system",
            "content": """
You are an automated essay comparator. You will compare two texts (a User Essay and a Reference Essay) and OUTPUT ONLY a single JSON object (no explanatory text, no markdown, nothing else):

{
  "score": number,   // integer or float between 0 and 10 (higher is better)
  "reason": string   // short explanation (1-3 sentences) of how score was derived
}

Important rules:
1. ALWAYS output Valid JSON only. If you cannot produce valid JSON, output nothing.
2. Score range: 0 (completely incorrect) to 10 (excellent match). Fractions are allowed (e.g. 7.5).
3. Use the rubric below to compute the score. Be consistent and concise in the reason.
4. Be robust to short or partial user answers: if the user's text is short but contains the **key entities or numeric amounts** (for example: debit/credit entries, balances, currency amounts, totals, years, percentages), treat those matches as highly significant and give a positive score even when prose is short.
5. Numerical matches (exact amounts, totals, debit/credit values) are high-weight signals and should strongly influence the score — they should compensate for missing wording if present in user text.
6. Consider synonyms, paraphrases, and reorderings as matches (e.g., "budget slack" ~ "deliberate understatement of revenues or overstatement of costs").
7. Do NOT penalize for minor punctuation, casing, formatting, or small grammatical differences.
8. **Handle Tables and Lists:** The user's or reference's text may contain tabular data, T-accounts, or lists (e.g., Markdown tables, CSV, or plain-text columns). Accurately parse and compare the relationships between entities and numbers in these structures, regardless of whether their raw formatting matches exactly.
9. If the reference contains specific numbers (amounts) and the user repeats those numbers or shows logically equivalent numbers (e.g., 1000 vs 1,000), consider them matched.
10. If the user omits some details but captures the core idea and numeric facts, give a moderate-to-high score; if numeric facts match exactly, increase the score further.
11. If the user writes extra incorrect numeric facts that contradict the reference, penalize accordingly.

Scoring rubric (suggested weights — apply reasonably):
- Content / Concept match: 50% — Are the main ideas present and correct?
- Numeric / Entity match: 40% — Do the amounts, debit/credit labels, totals and key entities match?
- Clarity & Completeness: 10% — Readability and whether critical steps are missing.

Produce a concise reason explaining which aspects matched or failed (mention numeric matches or missing key concepts). Examples (for your internal guidance — still output only JSON):

Example 1 -> Good numeric match:
User Essay: "Total debit 5000, credit 5000. Budget slack is understating revenue."
Reference: "Budget slack: deliberate understatement of revenues... Debit 5000, Credit 5000."
Output: {"score": 9.0, "reason":"Core concept correct; numeric debit/credit (5000) match exactly — minor wording differences."}

Example 2 -> Short but numeric present:
User Essay: "Debit: 2000; Credit: 2000."
Reference: "Explain how debits and credits balance (2000) and affect profit."
Output: {"score": 7.0, "reason":"Numeric entries match and indicate understanding of balancing; explanation is brief/missing conceptual details."}

Example 3 -> Contradiction:
User Essay: "Debit 3000, Credit 4000."
Reference: "Debit 3000, Credit 3000."
Output: {"score": 3.0, "reason":"Numeric values contradict reference (credit mismatch); concept partially present but facts differ."}
"""
        },
        {
            "role": "user",
            "content": f"""
Compare the following two essays and RETURN ONLY JSON with keys "score" and "reason":

User Essay:
{request.user_input}

Reference Essay:
{request.explanation}

Scoring instructions:
- Follow the system instructions above exactly.
- If numeric amounts, debit/credit labels, totals, or other explicit data in either text match, treat them as strong positive evidence.
- If the user provides logically equivalent numbers (e.g., formatted differently) treat them as matches.
- If the user provides contradicting numeric facts, lower the score and explain the contradiction in the reason.
- Be brief and precise in the reason (1-3 sentences).
"""
        }
    ]

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY environment variable is not set")

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }

    # Use the model passed in the request (defaults to gpt-4o)
    payload = {
        "model": request.model,
        "messages": messages,
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            raw = data["choices"][0]["message"]["content"]
    except Exception as error:
        print("❌ Essay verification error:", error)
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "message": str(error)}
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback to extract JSON from markdown if the model hallucinates it
        match = re.search(r'```(?:json)?(.*?)```', raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1).strip())
            except:
                raise HTTPException(status_code=500, detail={"error": "AI returned invalid JSON", "raw_response": raw})
        else:
            raise HTTPException(status_code=500, detail={"error": "AI returned invalid JSON", "raw_response": raw})

    return {
        "status": "success",
        "score": parsed.get("score"),
        "reason": parsed.get("reason"),
    }