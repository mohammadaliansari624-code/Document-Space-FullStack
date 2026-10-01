# Document Space — React + FastAPI

React frontend with a FastAPI backend and server-side admin authentication. Password hashes and session secrets stay in the backend `.env`; SQLite stores website settings, services, gallery entries and contact inquiries.

The original website content is restored: its logo, three office/gallery photos and 20 services. Existing starter contact details are preserved when the database is upgraded.

## First-time setup

Open PowerShell in this project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\setup_admin.py
```

The setup asks for the admin email and password, then creates `backend\.env`. Keep that file private and do not put secrets in frontend files or share them in chat.

## Run the backend

```powershell
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL Vite prints (normally `http://localhost:5173`). Admin login is the small copyright link at the very bottom of the public page.

The admin panel lets you replace the logo, edit business/contact/social details, add/edit/remove services, upload/delete gallery photos and posters, and read inquiries. Image uploads accept JPG, PNG, WEBP and GIF up to 8 MB. Uploads are saved in `backend/media`; use persistent storage for this folder when hosting.

## API

- `GET /api/site` — public site content
- `POST /api/contact` — public contact request
- `POST /api/auth/login`, `POST /api/auth/logout` — admin session
- `GET /api/admin/inquiries` — authenticated inquiries
- `PUT /api/admin/site` — authenticated business details
- `POST /api/admin/services`, `PUT/DELETE /api/admin/services/{id}` — service management
- `POST /api/admin/media` — authenticated logo/poster upload
- `PUT /api/admin/posters/{id}` — authenticated poster name and description update
- `DELETE /api/admin/posters/{id}` — authenticated poster removal

The previous Supabase keys are not used by this project. Revoke the previously shared Supabase secret key in Supabase.

## Public demo deployment

The root `Dockerfile` builds the React site and runs it with FastAPI as one web service. Push this project folder to a private GitHub repository, create a Render **Web Service** from that repository, choose the Docker runtime, and deploy. Add these environment variables in the Render service settings before sharing the generated `onrender.com` URL:

- `ADMIN_EMAIL` — the admin login email
- `ADMIN_PASSWORD_HASH` — generate locally with `py backend\make_password_hash.py`; paste only the resulting hash
- `SESSION_SECRET` — generate locally with `py -c "import secrets; print(secrets.token_urlsafe(48))"`
- `DATABASE_PATH` — `/var/data/document_space.sqlite3`
- `MEDIA_DIR` — `/var/data/media`

Never commit `backend/.env` or send the password/hash in chat. A free demo can sleep when unused, and without a persistent disk its database and uploaded media can be lost when the host replaces the running instance. Add persistent storage before treating this as the client's permanent site.

### If PowerShell is already inside `backend`

Use these paths instead:

```powershell
pip install -r requirements.txt
python setup_admin.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another window, run `cd ..\frontend`, then `npm install` and `npm run dev`.
