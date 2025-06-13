from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
import os
import subprocess

app = FastAPI()

@app.post("/generate-pdf/")
def generate_pdf(
    url: str = Form(...),
    db: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    try:
        env = os.environ.copy()
        env["ODOO_URL"] = url
        env["ODOO_DB"] = db
        env["ODOO_USER"] = username
        env["ODOO_PASS"] = password

        result = subprocess.run(
            ["python3", "generate_pdf.py"],
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)

        filename = f"acco_OntbrekendeDocumenten_{db}.pdf"
        if not os.path.isfile(filename):
            raise HTTPException(status_code=404, detail="PDF not found")

        return FileResponse(filename, media_type='application/pdf', filename=filename)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))