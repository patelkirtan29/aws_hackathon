from __future__ import annotations

import os
import subprocess
import sys
import re
import io
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


# IMPORTANT: adjust if your project root is different
PROJECT_ROOT = Path(__file__).resolve().parent


class JobResearchRequest(BaseModel):
    company: str
    role: str


class ScanInboxRequest(BaseModel):
    dry_run: bool = True


app = FastAPI(title="Job Intelligence Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _capture_run(func) -> str:
    """Capture printed stdout/stderr from your existing CLI-style functions."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        func()
    return buf.getvalue()


def _extract_saved_file(output_text: str) -> Optional[str]:
    """
    Looks for: "Saved brief to: prep_amazon_software_engineer.txt"
    Returns the filename if found.
    """
    m = re.search(r"Saved brief to:\s*(.+)$", output_text, flags=re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


@app.post("/api/job-research")
def job_research(payload: JobResearchRequest):
    # Run the CLI script and feed inputs:
    # mode=1, company, role, then exit
    cli_input = f"1\n{payload.company.strip()}\n{payload.role.strip()}\nexit\n"

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    p = subprocess.run(
        [sys.executable, "job_agent.py"],
        input=cli_input,
        text=True,
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )

    output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")

    if p.returncode != 0:
        raise HTTPException(status_code=500, detail=output)

    saved_file = _extract_saved_file(output)

    return {
        "ok": True,
        "company": payload.company,
        "role": payload.role,
        "output": output,
        "saved_file": saved_file,
    }


@app.post("/api/scan-inbox")
def scan_inbox(payload: ScanInboxRequest):
    # mode=2, dry_run y/n, then exit
    dry = "y" if payload.dry_run else "n"
    cli_input = f"2\n{dry}\nexit\n"

    
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    p = subprocess.run(
        [sys.executable, "job_agent.py"],
        input=cli_input,
        text=True,
        capture_output=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        encoding="utf-8",
        errors="replace",
    )

    output = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")

    if p.returncode != 0:
        raise HTTPException(status_code=500, detail=output)

    return {"ok": True, "dry_run": payload.dry_run, "output": output}


@app.get("/api/download")
def download(file: str):
    # Security: only allow downloading files inside PROJECT_ROOT
    file_path = (PROJECT_ROOT / file).resolve()

    if PROJECT_ROOT not in file_path.parents and file_path != PROJECT_ROOT:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(str(file_path), filename=file_path.name)
