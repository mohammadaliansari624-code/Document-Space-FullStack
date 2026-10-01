"""Create backend/.env with a hashed admin password and random session secret."""
import getpass
import hashlib
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env_path = root / "backend" / ".env"
email = input("Admin email [documentspace.in@gmail.com]: ").strip() or "documentspace.in@gmail.com"
password = getpass.getpass("Choose an admin password (12+ characters): ")
confirm = getpass.getpass("Confirm password: ")
if len(password) < 12:
    raise SystemExit("Use at least 12 characters.")
if password != confirm:
    raise SystemExit("Passwords do not match.")
rounds = 600_000
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
password_hash = f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"
content = "\n".join([
    f"ADMIN_EMAIL={email}",
    f"ADMIN_PASSWORD_HASH={password_hash}",
    f"SESSION_SECRET={secrets.token_urlsafe(48)}",
    "ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173",
    f"DATABASE_PATH={root.as_posix()}/document_space.sqlite3",
    "",
])
if env_path.exists() and input("backend/.env exists. Replace it? Type YES: ").strip() != "YES":
    raise SystemExit("Existing file left unchanged.")
env_path.write_text(content, encoding="utf-8")
print("Admin configuration saved to backend/.env. Keep that file private.")
