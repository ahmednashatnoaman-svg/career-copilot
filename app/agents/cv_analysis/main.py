"""
FastAPI app for the CV Analysis Agent.

Two endpoints:
  POST /analyze            - standalone resume analysis
  POST /analyze/tailored   - resume analysis tailored against a job description

Each accepts EITHER a file upload (PDF/DOCX) OR raw pasted resume text via
the `resume_text` form field. Exactly one must be provided.
"""

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.extraction.parser import UnsupportedFileTypeError
from app.core.pipeline import run_standalone_analysis, run_tailored_analysis
from app.schemas import CVAnalysisResponse

app = FastAPI(title="CV Analysis Agent", version="1.0")


async def _read_upload(resume_file: UploadFile | None) -> tuple[bytes | None, str | None]:
    if resume_file is None:
        return None, None
    contents = await resume_file.read()
    return contents, resume_file.filename


def _validate_exactly_one_input(resume_file: UploadFile | None, resume_text: str | None) -> None:
    has_file = resume_file is not None and resume_file.filename
    has_text = resume_text is not None and resume_text.strip() != ""
    if has_file and has_text:
        raise HTTPException(
            status_code=400,
            detail="Provide either resume_file or resume_text, not both.",
        )
    if not has_file and not has_text:
        raise HTTPException(
            status_code=400,
            detail="Provide either resume_file or resume_text.",
        )


@app.post("/analyze", response_model=CVAnalysisResponse)
async def analyze(
    resume_file: UploadFile | None = None,
    resume_text: str | None = Form(default=None),
) -> CVAnalysisResponse:
    _validate_exactly_one_input(resume_file, resume_text)
    file_bytes, filename = await _read_upload(resume_file)

    try:
        return run_standalone_analysis(
            file_bytes=file_bytes,
            filename=filename,
            raw_text=resume_text,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/tailored", response_model=CVAnalysisResponse)
async def analyze_tailored(
    job_description: str = Form(...),
    resume_file: UploadFile | None = None,
    resume_text: str | None = Form(default=None),
) -> CVAnalysisResponse:
    _validate_exactly_one_input(resume_file, resume_text)

    if not job_description or not job_description.strip():
        raise HTTPException(status_code=400, detail="job_description is required and cannot be empty.")

    file_bytes, filename = await _read_upload(resume_file)

    try:
        return run_tailored_analysis(
            job_description=job_description,
            file_bytes=file_bytes,
            filename=filename,
            raw_text=resume_text,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse({"message": "Welcome to the CV Analysis Agent API. Visit /docs for interactive API documentation."})
