"""Minimal Marionette client. Drives the real Firefox that is installed here.

Marionette is Firefox's own remote protocol and is built into the browser, so this
needs no geckodriver and no selenium. Packets are length-prefixed JSON:

    <byte length>:[type, messageId, command, params]

This exists so that the dashboard can be tested through the path a person actually
travels, which is a real click on a real button in a real browser, rather than by
calling the page's own functions from a test harness that skips the event handler.
"""
import json
import socket
import time


class Marionette:
    def __init__(self, host="127.0.0.1", port=2828, timeout=45):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""
        self.msg_id = 0
        self._read_packet()  # server handshake

    # --- wire format ------------------------------------------------------
    def _read_packet(self):
        while b":" not in self.buf:
            self.buf += self.sock.recv(65536)
        head, rest = self.buf.split(b":", 1)
        n = int(head)
        while len(rest) < n:
            rest += self.sock.recv(65536)
        self.buf = rest[n:]
        return json.loads(rest[:n].decode("utf-8"))

    def send(self, command, params=None):
        self.msg_id += 1
        payload = json.dumps([0, self.msg_id, command, params or {}])
        raw = payload.encode("utf-8")
        self.sock.sendall(str(len(raw)).encode() + b":" + raw)
        while True:
            msg = self._read_packet()
            if isinstance(msg, list) and len(msg) >= 4 and msg[0] == 1 and msg[1] == self.msg_id:
                if msg[2]:
                    raise RuntimeError(f"{command} failed: {msg[2]}")
                return msg[3]

    # --- webdriver commands ----------------------------------------------
    def new_session(self):
        return self.send("WebDriver:NewSession", {"capabilities": {}})

    def get(self, url):
        self.send("WebDriver:Navigate", {"url": url})

    def script(self, js, args=None):
        r = self.send("WebDriver:ExecuteScript",
                      {"script": js, "args": args or [], "sandbox": "default"})
        return r.get("value") if isinstance(r, dict) else r

    def find(self, css):
        r = self.send("WebDriver:FindElement", {"using": "css selector", "value": css})
        v = r.get("value", r)
        return list(v.values())[0] if isinstance(v, dict) else v

    def click(self, css):
        self.send("WebDriver:ElementClick", {"id": self.find(css)})

    def type(self, css, text):
        self.send("WebDriver:ElementSendKeys", {"id": self.find(css), "text": text})

    def wait_for(self, js, seconds=25, label=""):
        """Poll a JavaScript expression until it is truthy, in the page itself."""
        end = time.time() + seconds
        last = None
        while time.time() < end:
            last = self.script("return (" + js + ");")
            if last:
                return last
            time.sleep(0.4)
        raise AssertionError(f"timed out waiting for {label or js}. Last value {last!r}")

    def quit(self):
        try:
            self.send("Marionette:Quit")
        except Exception:
            pass
        self.sock.close()
