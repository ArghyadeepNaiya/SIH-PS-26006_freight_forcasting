#!/usr/bin/env python3
"""Generate one dashboard password per port.

Run this once, from the repository root.

    python3 scripts/generate_port_credentials.py

It writes two files, both of which are listed in .gitignore.

1. passwords.txt at the repository root. Plaintext, mode 0600. This is the file you
   read a password out of when you hand it to a port operator. The service never
   reads it. Delete it once every operator has their password.
2. data/port_owners/credentials.json. Salted PBKDF2 hashes only, mode 0600. This is
   what the service actually checks a login against.

Re-running without --force refuses, so that you cannot lock out every port operator
by accident. Re-running with --force rotates every password at once.

    python3 scripts/generate_port_credentials.py --force
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml-service"))

from app.config import PORTS                      # noqa: E402
from app.core import portal_auth as auth          # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Generate port operator dashboard passwords.")
    ap.add_argument("--force", action="store_true",
                    help="Rotate every password even though credentials already exist.")
    ap.add_argument("--port", action="append", default=None,
                    help="Limit to one port code. Repeatable. Requires --force to rotate.")
    args = ap.parse_args()

    if auth.credentials_exist() and not args.force:
        print("Credentials already exist at data/port_owners/credentials.json.")
        print("Nothing was changed. Pass --force to rotate every password.")
        print("The current passwords are in passwords.txt, if you have not deleted it.")
        return 1

    codes = args.port or list(PORTS.keys())
    unknown = [c for c in codes if c not in PORTS]
    if unknown:
        print(f"Unknown port codes: {', '.join(unknown)}")
        print(f"Known codes: {', '.join(PORTS)}")
        return 2

    plaintext = {c: auth.make_passphrase() for c in codes}
    owners = {c: f"{PORTS[c]['name']} port operator" for c in codes}
    auth.write_credentials(plaintext, owners)

    print(f"Generated {len(plaintext)} port operator passwords.")
    print("")
    print("1. Plaintext passwords are in passwords.txt, readable only by you.")
    print("2. Salted hashes are in data/port_owners/credentials.json.")
    print("3. Both files are in .gitignore. Do not commit either one.")
    print("4. Operators sign in at http://localhost:8000/port")
    print("")
    for code in sorted(plaintext):
        print(f"   {PORTS[code]['name']} ({code}). {plaintext[code]}")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
