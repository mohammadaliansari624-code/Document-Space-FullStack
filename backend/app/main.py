from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import re
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "document_space.sqlite3")))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "documentspace.in@gmail.com").strip().lower()
PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SESSION_TTL = 8 * 60 * 60
PACKAGED_MEDIA_DIR = ROOT / "backend" / "media"
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(PACKAGED_MEDIA_DIR)))
SEED_FILE = ROOT / "backend" / "seed_data.json"
DEFAULT_SITE: dict[str, Any] = {
    "name": "DOCUMENT SPACE",
    "tagline": "Digital & Documentation Service Centre",
    "phone": "7498683086",
    "email": "documentspace.in@gmail.com",
    "address": "Shop No. 02, Jivdani Pada, Jivdani Road, Near Madrasa, Virar East, 401305, Palghar, Maharashtra",
    "hours": "9:30 AM – 7:00 PM · Closed Sunday",
    "services": [], "posters": [], "logo": "", "whatsapp": "7498683086",
    "openingTime": "9:30 AM", "closingTime": "7:00 PM", "closedDay": "Sunday",
    "mapsUrl": "", "reviewsUrl": "", "cscId": "", "facebook": "", "instagram": "", "youtube": "", "linkedin": "",
    "notice": "Government and banking services are subject to applicable rules and authority decisions.",
}
if SEED_FILE.is_file():
    DEFAULT_SITE.update(json.loads(SEED_FILE.read_text(encoding="utf-8")))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    if MEDIA_DIR.resolve() != PACKAGED_MEDIA_DIR.resolve():
        for asset in PACKAGED_MEDIA_DIR.iterdir():
            target = MEDIA_DIR / asset.name
            if asset.is_file() and not target.exists():
                target.write_bytes(asset.read_bytes())
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        );
        """)
        if not db.execute("SELECT 1 FROM settings WHERE id=1").fetchone():
            db.execute("INSERT INTO settings(id,data) VALUES(1,?)", (json.dumps(DEFAULT_SITE),))
        else:
            row = db.execute("SELECT data FROM settings WHERE id=1").fetchone()
            existing = json.loads(row["data"])
            merged = {**DEFAULT_SITE, **existing}
            # Upgrade the earlier starter's seven generic strings to the recovered original catalogue.
            if merged.get("services") and all(isinstance(item, str) for item in merged["services"]):
                merged["services"] = DEFAULT_SITE["services"]
            if not merged.get("posters"): merged["posters"] = DEFAULT_SITE["posters"]
            if not merged.get("logo"): merged["logo"] = DEFAULT_SITE["logo"]
            if isinstance(merged.get("logo"), str): merged["logo"] = merged["logo"].replace("/seed-media/", "/media/")
            for poster in merged.get("posters", []):
                for key in ("image", "src"):
                    if isinstance(poster.get(key), str): poster[key] = poster[key].replace("/seed-media/", "/media/")
                if re.fullmatch(r"(?:image|img|photo|poster)[ _-]*\d+", str(poster.get("title", "")).strip(), re.IGNORECASE):
                    poster["title"] = ""
                poster.setdefault("description", "")
            db.execute("UPDATE settings SET data=? WHERE id=1", (json.dumps(merged),))


def site_data() -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT data FROM settings WHERE id=1").fetchone()
    return json.loads(row["data"]) if row else DEFAULT_SITE.copy()


def verify_password(password: str) -> bool:
    try:
        scheme, rounds_s, salt_hex, expected_hex = PASSWORD_HASH.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds_s))
        return hmac.compare_digest(actual.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=40)
    message: str = Field(min_length=1, max_length=4000)


async def admin_email(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Admin sign-in required")
    token = header[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Admin sign-in required")
    digest = hashlib.sha256((SESSION_SECRET + token).encode()).hexdigest()
    with connect() as db:
        row = db.execute("SELECT email,expires_at FROM sessions WHERE token_hash=?", (digest,)).fetchone()
    if not row or row["expires_at"] < int(time.time()):
        raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
    return row["email"]


app = FastAPI(title="Document Space API", version="1.0.0")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
seed_media = ROOT / "frontend" / "public" / "seed-media"
if seed_media.is_dir(): app.mount("/seed-media", StaticFiles(directory=seed_media), name="seed-media")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/site")
def get_site() -> dict[str, Any]:
    return site_data()


@app.put("/api/admin/site")
def update_site(payload: dict[str, Any], _: str = Depends(admin_email)) -> dict[str, Any]:
    allowed = set(DEFAULT_SITE)
    updated = {**site_data(), **{k: v for k, v in payload.items() if k in allowed}}
    with connect() as db:
        db.execute("INSERT INTO settings(id,data) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (json.dumps(updated),))
    return updated


def write_site(site: dict[str, Any]) -> None:
    with connect() as db:
        db.execute("INSERT INTO settings(id,data) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (json.dumps(site),))


@app.post("/api/admin/services", status_code=201)
def add_service(payload: dict[str, Any], _: str = Depends(admin_email)) -> dict[str, Any]:
    item = {"id": secrets.token_urlsafe(9), "category": str(payload.get("category", "General")).strip()[:100],
            "name": str(payload.get("name", "")).strip()[:160],
            "shortDescription": str(payload.get("shortDescription", "")).strip()[:500]}
    if not item["name"]: raise HTTPException(status_code=422, detail="Service name is required")
    site = site_data(); site.setdefault("services", []).append(item); write_site(site); return item


@app.put("/api/admin/services/{service_id}")
def edit_service(service_id: str, payload: dict[str, Any], _: str = Depends(admin_email)) -> dict[str, Any]:
    site = site_data(); item = next((x for x in site.get("services", []) if x.get("id") == service_id), None)
    if item is None: raise HTTPException(status_code=404, detail="Service not found")
    for key in ("name", "category", "shortDescription"):
        if key in payload: item[key] = str(payload[key]).strip()[:500]
    if not item.get("name"): raise HTTPException(status_code=422, detail="Service name is required")
    write_site(site); return item


@app.delete("/api/admin/services/{service_id}")
def remove_service(service_id: str, _: str = Depends(admin_email)) -> dict[str, bool]:
    site = site_data(); before = len(site.get("services", []))
    site["services"] = [x for x in site.get("services", []) if x.get("id") != service_id]
    if before == len(site["services"]): raise HTTPException(status_code=404, detail="Service not found")
    write_site(site); return {"ok": True}


@app.post("/api/admin/media", status_code=201)
async def upload_media(kind: str = Form(...), file: UploadFile = File(...), _: str = Depends(admin_email)) -> dict[str, Any]:
    if kind not in {"logo", "poster"}: raise HTTPException(status_code=400, detail="Choose logo or poster upload")
    allowed = {"image/jpeg": ("jpg", b"\xff\xd8\xff"), "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
               "image/webp": ("webp", b"RIFF"), "image/gif": ("gif", b"GIF8")}
    if file.content_type not in allowed: raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WEBP or GIF image")
    data = await file.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024: raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller")
    ext, signature = allowed[file.content_type]
    if not data.startswith(signature): raise HTTPException(status_code=415, detail="Image file does not match its type")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True); name = f"{uuid4().hex}.{ext}"; (MEDIA_DIR / name).write_bytes(data)
    image = f"/media/{name}"; site = site_data()
    if kind == "logo":
        old = site.get("logo", ""); site["logo"] = image; write_site(site); remove_uploaded_file(old)
        return {"kind": "logo", "image": image}
    poster = {"id": uuid4().hex, "title": "", "description": "", "image": image}
    site.setdefault("posters", []).append(poster); write_site(site); return {"kind": "poster", **poster}


@app.put("/api/admin/posters/{poster_id}")
def update_poster(poster_id: str, payload: dict[str, Any], _: str = Depends(admin_email)) -> dict[str, Any]:
    site = site_data()
    poster = next((p for p in site.get("posters", []) if p.get("id") == poster_id), None)
    if poster is None: raise HTTPException(status_code=404, detail="Poster not found")
    if "title" in payload: poster["title"] = str(payload["title"]).strip()[:120]
    if "description" in payload: poster["description"] = str(payload["description"]).strip()[:1000]
    write_site(site); return poster


@app.delete("/api/admin/posters/{poster_id}")
def delete_poster(poster_id: str, _: str = Depends(admin_email)) -> dict[str, bool]:
    site = site_data(); posters = site.get("posters", [])
    poster = next((p for p in posters if p.get("id") == poster_id), None)
    if poster is None: raise HTTPException(status_code=404, detail="Poster not found")
    site["posters"] = [p for p in posters if p.get("id") != poster_id]; write_site(site)
    remove_uploaded_file(poster.get("image", "")); return {"ok": True}


def remove_uploaded_file(url: str) -> None:
    if url.startswith("/media/"):
        name = Path(url[len("/media/"):]).name; candidate = MEDIA_DIR / name
        if candidate.parent == MEDIA_DIR and candidate.is_file(): candidate.unlink()


@app.post("/api/auth/login")
def login(payload: LoginIn) -> dict[str, str]:
    if not ADMIN_EMAIL or not PASSWORD_HASH or not SESSION_SECRET:
        raise HTTPException(status_code=503, detail="Backend admin setup is incomplete")
    email = str(payload.email).strip().lower()
    valid_email = hmac.compare_digest(email, ADMIN_EMAIL)
    valid_password = verify_password(payload.password)
    if not (valid_email and valid_password):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    token = secrets.token_urlsafe(40)
    digest = hashlib.sha256((SESSION_SECRET + token).encode()).hexdigest()
    with connect() as db:
        db.execute("INSERT INTO sessions(token_hash,email,expires_at) VALUES(?,?,?)", (digest, email, int(time.time()) + SESSION_TTL))
    return {"access_token": token, "token_type": "bearer"}


@app.post("/api/auth/logout")
def logout(request: Request, _: str = Depends(admin_email)) -> dict[str, bool]:
    token = request.headers.get("authorization", "")[7:].strip()
    digest = hashlib.sha256((SESSION_SECRET + token).encode()).hexdigest()
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
    return {"ok": True}


@app.post("/api/contact", status_code=201)
def create_contact(payload: ContactIn) -> dict[str, bool]:
    with connect() as db:
        db.execute("INSERT INTO inquiries(name,email,phone,message,created_at) VALUES(?,?,?,?,?)", (payload.name.strip(), str(payload.email), payload.phone.strip(), payload.message.strip(), int(time.time())))
    return {"ok": True}


@app.get("/api/admin/inquiries")
def list_inquiries(_: str = Depends(admin_email)) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT id,name,email,phone,message,created_at FROM inquiries ORDER BY id DESC LIMIT 300").fetchall()
    return [dict(r) for r in rows]


dist = ROOT / "frontend" / "dist"
assets = dist / "assets"
if assets.is_dir():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"message": "React frontend is not built yet. Run npm run build in frontend."}
