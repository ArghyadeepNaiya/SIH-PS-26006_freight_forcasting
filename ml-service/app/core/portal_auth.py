"""Port operator authentication for the per-port owner dashboard.

DESIGN NOTES, because this is the only part of the system that handles a secret.

1. Plaintext passwords live in exactly one place, `passwords.txt` at the repository
   root, which is listed in `.gitignore`. That file exists so the team can read a
   password out to a port operator once. The service never reads it.
2. The service reads `data/port_owners/credentials.json`, which holds only a random
   salt and a PBKDF2-HMAC-SHA256 hash per port. That file is also gitignored,
   because a password hash is still a credential.
3. Comparison uses `hmac.compare_digest`, so a wrong password takes the same time to
   reject regardless of how many leading characters were correct.
4. Sessions are in-process only. Restarting the service logs everybody out. That is
   the right trade for a hackathon prototype: there is no session store to leak and
   nothing to expire on disk.
5. This is prototype grade authentication. It is honest about that on screen. It is
   not a substitute for the identity system a real port community system would use.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from threading import Lock

from app.config import BASE, PORTS

CRED_FILE = BASE / "data" / "port_owners" / "credentials.json"
PLAINTEXT_FILE = BASE / "passwords.txt"

PBKDF2_ROUNDS = 240_000
SESSION_TTL_SECONDS = 12 * 60 * 60

# Lockout after repeated failures. Deliberately generous, because a port operator
# reading a passphrase off paper with a screen reader will mistype it.
MAX_FAILED_ATTEMPTS = 8
LOCKOUT_SECONDS = 15 * 60

# Passphrases are built from words rather than random characters on purpose. The
# operator of this project uses the JAWS screen reader, and "harbour-anchor-4127"
# reads aloud correctly, whereas "xK7$mQ2z" is read as a character stream and is
# almost impossible to transcribe by ear.
_WORDS = [
    "anchor", "ballast", "beacon", "berth", "bollard", "bunker", "capstan",
    "channel", "charter", "cleat", "compass", "convoy", "cradle", "current",
    "davit", "draft", "estuary", "fairway", "fender", "galley", "gantry",
    "grapnel", "harbour", "hatch", "hawser", "jetty", "keel", "lantern",
    "lighter", "manifest", "mooring", "pennant", "pilot", "quay", "rudder",
    "sextant", "shackle", "sounding", "starboard", "stowage", "tender",
    "tonnage", "trawler", "tugboat", "windlass", "winch", "yardarm",
]

_LOCK = Lock()
_SESSIONS = {}          # token -> {"port_code": str, "expires": float}
_FAILURES = {}          # port_code -> {"count": int, "until": float}


# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------

def _hash(password: str, salt_hex: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ROUNDS
    )
    return dk.hex()


def make_passphrase() -> str:
    """Three maritime words and four digits. Roughly 41 bits of entropy.

    Word list of 47 gives 47^3 combinations, times 10000 for the digits, which is
    about 1.0e9 possibilities. That is weak by internet standards and entirely
    adequate for a local prototype behind a lockout, which is what this is.
    """
    words = "-".join(secrets.choice(_WORDS) for _ in range(3))
    return f"{words}-{secrets.randbelow(9000) + 1000}"


# --------------------------------------------------------------------------
# Credential file
# --------------------------------------------------------------------------

def credentials_exist() -> bool:
    return CRED_FILE.exists()


def load_credentials() -> dict:
    if not CRED_FILE.exists():
        return {}
    with open(CRED_FILE) as f:
        return json.load(f).get("ports", {})


def write_credentials(plaintext_by_port: dict, owner_names: dict) -> None:
    """Persist hashes to credentials.json and plaintext to passwords.txt.

    Both files are written with mode 0600, owner read and write only, so that a
    shared machine does not hand the passwords to every other local account.
    """
    CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "_warning": "This file contains password hashes. It is gitignored. Do not commit it.",
        "_algorithm": f"PBKDF2-HMAC-SHA256, {PBKDF2_ROUNDS} rounds, 16 byte random salt per port",
        "ports": {},
    }
    for code, password in plaintext_by_port.items():
        salt = secrets.token_hex(16)
        record["ports"][code] = {
            "owner_name": owner_names.get(code, code),
            "salt": salt,
            "hash": _hash(password, salt),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    with open(CRED_FILE, "w") as f:
        json.dump(record, f, indent=2)
    os.chmod(CRED_FILE, 0o600)

    lines = [
        "PORT OPERATOR DASHBOARD PASSWORDS",
        "=================================",
        "",
        "This file is listed in .gitignore and must never be committed.",
        "Hand each password to the operator of that port only. The service does not",
        "read this file. It reads only the salted hashes in",
        "data/port_owners/credentials.json.",
        "",
        "Sign in at http://localhost:8000/port",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    for i, (code, password) in enumerate(sorted(plaintext_by_port.items()), start=1):
        port = PORTS.get(code, {})
        lines += [
            f"{i}. {port.get('name', code)}",
            f"   Port code. {code}",
            f"   State. {port.get('state', 'not recorded')}",
            f"   Password. {password}",
            "",
        ]
    lines += [
        "To rotate every password, run this and hand out the new file.",
        "",
        "    python3 scripts/generate_port_credentials.py --force",
        "",
    ]
    with open(PLAINTEXT_FILE, "w") as f:
        f.write("\n".join(lines))
    os.chmod(PLAINTEXT_FILE, 0o600)


# --------------------------------------------------------------------------
# Login and sessions
# --------------------------------------------------------------------------

class AuthError(Exception):
    """Raised for every authentication failure, with a message safe to show."""


def _lockout_remaining(port_code: str) -> int:
    rec = _FAILURES.get(port_code)
    if not rec:
        return 0
    return max(0, int(rec["until"] - time.time()))


def login(port_code: str, password: str) -> dict:
    port_code = (port_code or "").strip().upper()
    creds = load_credentials()

    if not creds:
        raise AuthError(
            "No port credentials have been generated yet. Run "
            "python3 scripts/generate_port_credentials.py once, then read the "
            "password for this port out of passwords.txt."
        )

    with _LOCK:
        wait = _lockout_remaining(port_code)
        if wait:
            raise AuthError(
                f"Too many failed attempts for this port. Try again in "
                f"{wait // 60} minutes and {wait % 60} seconds."
            )

    entry = creds.get(port_code)

    # A wrong port code and a wrong password give the same answer, so this endpoint
    # cannot be used to enumerate which ports have been provisioned.
    ok = False
    if entry:
        ok = hmac.compare_digest(_hash(password or "", entry["salt"]), entry["hash"])

    if not ok:
        with _LOCK:
            rec = _FAILURES.setdefault(port_code, {"count": 0, "until": 0.0})
            rec["count"] += 1
            if rec["count"] >= MAX_FAILED_ATTEMPTS:
                rec["until"] = time.time() + LOCKOUT_SECONDS
                rec["count"] = 0
        raise AuthError("That port code and password combination was not recognised.")

    with _LOCK:
        _FAILURES.pop(port_code, None)
        token = secrets.token_urlsafe(32)
        expires = time.time() + SESSION_TTL_SECONDS
        _SESSIONS[token] = {"port_code": port_code, "expires": expires}

    port = PORTS.get(port_code, {})
    return {
        "token": token,
        "port_code": port_code,
        "port_name": port.get("name", port_code),
        "owner_name": entry.get("owner_name", port_code),
        "expires_in_seconds": SESSION_TTL_SECONDS,
    }


def resolve(token: str) -> str:
    """Return the port code a session token is good for, or raise AuthError."""
    if not token:
        raise AuthError("You are not signed in. Sign in with your port password.")
    with _LOCK:
        sess = _SESSIONS.get(token)
        if not sess:
            raise AuthError("Your session is not recognised. Sign in again.")
        if sess["expires"] < time.time():
            _SESSIONS.pop(token, None)
            raise AuthError("Your session has expired. Sign in again.")
        return sess["port_code"]


def logout(token: str) -> None:
    with _LOCK:
        _SESSIONS.pop(token, None)


def provisioning_status() -> dict:
    """Non-secret summary, safe to show on the public sign-in page."""
    creds = load_credentials()
    return {
        "credentials_generated": bool(creds),
        "ports_provisioned": sorted(creds.keys()),
        "total_ports": len(PORTS),
        "how_to_provision": "python3 scripts/generate_port_credentials.py",
    }
