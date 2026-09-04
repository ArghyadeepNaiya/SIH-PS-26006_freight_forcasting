#!/usr/bin/env python3
"""Drive both dashboards in a real Firefox, through real clicks.

WHY THIS EXISTS. Every other test in this project answers a question that can be
answered without a browser. This one answers the question that cannot: does pressing
the button actually do the thing. That question has been answered wrongly on this
project twice. Once because a request tested with curl carried a field the page was
silently dropping. Once because a page function called directly from a test harness
worked while every real click did nothing, since the failure lived in the handler the
direct call skipped. It caught a third case on the day it was written, where the
quantity field's own default value failed the browser's number validation, so the
form never submitted and the recommendation button did nothing at all.

WHAT IT NEEDS. Firefox, which is already installed on this machine, and nothing else.
No geckodriver, no selenium, no node. Marionette is Firefox's own remote protocol and
is built into the browser. See scripts/browser/marionette.py.

HOW TO RUN IT.

    ./run.sh                                   # in one terminal
    python3 scripts/browser_e2e.py             # in another

It reads the Paradip password out of passwords.txt itself. Pass --password to give
one explicitly, and --url to point at a service somewhere other than localhost.

    python3 scripts/browser_e2e.py --accessibility    # structural audit instead
"""
import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "browser"))

MARIONETTE_PORT = 2828


def read_password(port_code="INPRT"):
    """Pull one port's password out of passwords.txt, which is gitignored."""
    f = ROOT / "passwords.txt"
    if not f.exists():
        sys.exit("passwords.txt is not present. Run "
                 "python3 scripts/generate_port_credentials.py first, or pass "
                 "--password.")
    block = re.search(rf"Port code\. {port_code}\b.*?Password\. (\S+)",
                      f.read_text(), re.S)
    if not block:
        sys.exit(f"No password for {port_code} was found in passwords.txt.")
    return block.group(1)


def marionette_listening():
    try:
        with socket.create_connection(("127.0.0.1", MARIONETTE_PORT), timeout=1):
            return True
    except OSError:
        return False


def start_firefox():
    """Start a headless Firefox with Marionette on a throwaway profile."""
    if marionette_listening():
        print("Using the Firefox already listening on port 2828.")
        return None, None
    if not shutil.which("firefox"):
        sys.exit("Firefox is not installed, so the browser tests cannot run. "
                 "Every other test in this project runs without it.")
    profile = tempfile.mkdtemp(prefix="freight-e2e-profile-")
    proc = subprocess.Popen(
        ["firefox", "--headless", "--marionette", "--no-remote",
         "--profile", profile, "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    for _ in range(120):
        if marionette_listening():
            print("Started a headless Firefox on port 2828.")
            return proc, profile
        time.sleep(0.5)
    proc.kill()
    sys.exit("Firefox started but never opened the Marionette port.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default="http://127.0.0.1:8000",
                    help="Where the service is running.")
    ap.add_argument("--password", default=None,
                    help="Paradip's dashboard password. Read from passwords.txt if omitted.")
    ap.add_argument("--accessibility", action="store_true",
                    help="Run the structural accessibility audit instead of the "
                         "functional checks.")
    args = ap.parse_args()

    password = args.password or read_password()
    proc, profile = start_firefox()
    module = "accessibility" if args.accessibility else "checks"
    try:
        rc = subprocess.call(
            [sys.executable, str(ROOT / "scripts" / "browser" / f"{module}.py"), password],
            cwd=str(ROOT / "scripts" / "browser"),
            env={**os.environ, "FREIGHT_BASE_URL": args.url})
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        if profile:
            shutil.rmtree(profile, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
