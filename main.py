from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import json

app = FastAPI()

# CORS toestaan
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later kun je dit beperken tot je Lovable URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PDF-generator endpoint
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

# GET alle klanten
@app.get("/clients")
def get_clients():
    try:
        with open("clients.json", encoding="utf-8") as f:
            clients = json.load(f)
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# POST nieuwe klant toevoegen
@app.post("/clients")
async def add_client(request: Request):
    try:
        new_client = await request.json()
        with open("clients.json", encoding="utf-8") as f:
            clients = json.load(f)
        clients.append(new_client)
        with open("clients.json", "w", encoding="utf-8") as f:
            json.dump(clients, f, indent=2, ensure_ascii=False)
        return {"status": "added", "client": new_client}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
