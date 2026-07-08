from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
from dotenv import load_dotenv
import markdown
import os
import io

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def text_to_html(text):
    if text is None:
        return None

    return markdown.markdown(
        str(text),
        extensions=[
            "tables",
            "fenced_code",
            "nl2br",
        ],
    )


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

        # Convert every text cell
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.value = text_to_html(cell.value)

        # Output filename
        output_filename = f"converted_{file.filename}"

        # Save in current working directory
        output_path = os.path.join(os.getcwd(), output_filename)

        # wb.save(output_path)

        # print("=" * 60)
        # print("✅ Excel Converted Successfully")
        # print(f"📁 Saved At : {output_path}")
        # print("=" * 60)

        # Return downloadable file
        return FileResponse(
            path=output_path,
            filename=output_filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )