"""The few Notion and Stripe calls the poller makes, over plain HTTPS, with the transport injectable for tests.

Notion is read and written as data sources (API version 2025-09-03). Selects are checked against the live
options before a write: a value the database doesn't have is left out and reported, never created, because
adding an option to a shared database is Justin's call.
"""

import json
import urllib.error
import urllib.request

NOTION = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
STRIPE = "https://api.stripe.com/v1"
CHUNK = 1900


def urllib_http(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


class Api:
    def __init__(self, notion_token, stripe_key, http=urllib_http):
        self.notion_token, self.stripe_key, self.http = notion_token, stripe_key, http

    def _notion(self, method, path, body=None):
        status, out = self.http(method, NOTION + path, {
            "Authorization": f"Bearer {self.notion_token}", "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json"}, body)
        if status >= 300:
            raise RuntimeError(f"Notion {method} {path}: {status} {out.get('message', '')}")
        return out

    def query(self, data_source, flt=None):
        rows, cursor = [], None
        while True:
            body = {"page_size": 100, **({"filter": flt} if flt else {}), **({"start_cursor": cursor} if cursor else {})}
            out = self._notion("POST", f"/data_sources/{data_source}/query", body)
            rows += out.get("results", [])
            if not out.get("has_more"):
                return rows
            cursor = out.get("next_cursor")

    def schema(self, data_source):
        return self._notion("GET", f"/data_sources/{data_source}").get("properties", {})

    def create(self, data_source, properties):
        return self._notion("POST", "/pages", {"parent": {"data_source_id": data_source}, "properties": properties})

    def update(self, page_id, properties):
        return self._notion("PATCH", f"/pages/{page_id}", {"properties": properties})

    def checkout_session(self, session_id):
        status, out = self.http("GET", f"{STRIPE}/checkout/sessions/{session_id}",
                                {"Authorization": f"Bearer {self.stripe_key}"}, None)
        if status >= 300:
            raise RuntimeError(f"Stripe session {session_id}: {status} {(out.get('error') or {}).get('message', '')}")
        return out


def text_of(prop):
    """Plain text from a Notion title or rich_text property."""
    items = (prop or {}).get("title") or (prop or {}).get("rich_text") or []
    return "".join(i.get("plain_text") or (i.get("text") or {}).get("content", "") for i in items)


def plain(page):
    """A page's properties as plain values: text, select names, numbers, emails, checkboxes."""
    out = {}
    for name, p in (page.get("properties") or {}).items():
        t = p.get("type")
        if t in ("title", "rich_text"):
            out[name] = text_of(p)
        elif t == "select":
            out[name] = (p.get("select") or {}).get("name")
        elif t in ("number", "email", "checkbox", "url"):
            out[name] = p.get(t)
    return out


def rich(text):
    text = str(text)
    return {"rich_text": [{"type": "text", "text": {"content": text[i:i + CHUNK]}} for i in range(0, len(text), CHUNK)] or []}


def props(values, schema):
    """Plain values to Notion property objects, typed by the live schema. Returns (properties, left_out)."""
    out, left = {}, []
    for name, value in values.items():
        p = schema.get(name)
        if p is None or value is None:
            left.append(f"{name}: not in the database" if p is None else f"{name}: empty")
            continue
        t = p.get("type")
        if t == "title":
            out[name] = {"title": [{"type": "text", "text": {"content": str(value)[:CHUNK]}}]}
        elif t == "rich_text":
            out[name] = rich(value)
        elif t == "select":
            options = [o["name"] for o in (p.get("select") or {}).get("options", [])]
            if value in options:
                out[name] = {"select": {"name": value}}
            else:
                left.append(f"{name}: {value!r} isn't one of its options")
        elif t in ("number", "email", "url", "checkbox"):
            out[name] = {t: value}
        else:
            left.append(f"{name}: type {t} isn't written by rcm")
    return out, left
