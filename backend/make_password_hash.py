"""Create a PBKDF2 password hash for backend/.env without echoing the password."""
import getpass
import hashlib
import secrets

ROUNDS = 600_000
password = getpass.getpass("New admin password: ")
confirm = getpass.getpass("Confirm password: ")
if len(password) < 12:
    raise SystemExit("Use at least 12 characters.")
if password != confirm:
    raise SystemExit("Passwords do not match.")
salt = secrets.token_bytes(16)
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ROUNDS)
print(f"pbkdf2_sha256${ROUNDS}${salt.hex()}${digest.hex()}")
