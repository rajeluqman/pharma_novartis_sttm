#!/usr/bin/env python3
"""
publish_to_confluence.py — push signed-off Lead Deliverables (Markdown) to Confluence Cloud.

Owner: Data Platform Engineer. Runs ONLY after Data Architect sign-off (governance gate;
this script executes, it does not approve). Project Manager logs the publish event in
SIGN_OFF_LOG.md.

What it does
------------
- Reads Confluence config from the project .env (python-dotenv / os.environ). NEVER hardcodes
  or prints the API token.
- Converts each Markdown doc -> Confluence "storage" format (XHTML-ish) using the `markdown`
  lib (extensions: tables, fenced_code, toc) with a fallback minimal converter if unavailable.
  Fenced code blocks are rewrapped as Confluence `code` macros so DBML / ASCII diagrams render.
- Publishes via the Confluence Cloud REST API (body.storage.representation = "storage"),
  Basic auth (email + API token):
    * page_id given  -> UPDATE: GET current version, PUT version.number = current+1.
    * page_id is None -> CREATE: POST new page in the space, capture the new id.
- Parametrizable PUBLISH_TARGETS mapping so AH / ERD / (later) STTM publish without code edits.
- Prints a clean per-doc summary (id, title, version, URL). No secrets.

Usage
-----
    python scripts/publish_to_confluence.py            # publish all enabled targets
    python scripts/publish_to_confluence.py ah erd     # publish only named targets

Exit code is non-zero if any target fails.
"""
from __future__ import annotations

import html
import os
import re
import sys
from dataclasses import dataclass, field

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Target:
    """A single doc -> page publish target."""

    key: str  # short cli name, e.g. "ah"
    md_path: str  # path relative to PROJECT_ROOT
    title: str  # Confluence page title (used on both create + update)
    page_id_env: str  # env var holding the existing page id (may be empty => create)
    enabled: bool = True
    # populated at runtime
    page_id: str | None = field(default=None, init=False)


# Order matters only for readability; AH updates an existing page, ERD creates a new one.
PUBLISH_TARGETS: list[Target] = [
    Target(
        key="ah",
        md_path="docs/architecture_handbook/AH.md",
        title="Architecture Handbook (AH) — Novartis Pharma STTM Lab",
        page_id_env="CONFLUENCE_PAGE_ID_AH",
    ),
    Target(
        key="erd",
        md_path="docs/erwin/ERD.md",
        title="Erwin Data Model (ERD) — Novartis Pharma STTM Lab",
        page_id_env="CONFLUENCE_PAGE_ID_ERD",  # not set yet -> will CREATE
    ),
    # STTM (page id 98534) — Data Architect publish gate PASSED 2026-06-18 (SIGN_OFF_LOG.md
    # "STTM Publish Sign-off"), now enabled. UPDATEs the existing page.
    Target(
        key="sttm",
        md_path="docs/sttm/STTM.md",
        title="Source-to-Target Mapping (STTM) — Novartis Pharma STTM Lab",
        page_id_env="CONFLUENCE_PAGE_ID_STTM",
    ),
]


# ---------------------------------------------------------------------------
# Markdown -> Confluence storage conversion
# ---------------------------------------------------------------------------
def _code_macro(code: str, language: str | None) -> str:
    """Wrap a code block in a Confluence `code` storage macro."""
    lang = (language or "").strip().lower()
    # Confluence code macro supports a known set; unknown langs (e.g. dbml) -> plain "text".
    known = {
        "bash", "python", "sql", "yaml", "json", "java", "javascript", "xml",
        "html", "text", "none", "shell", "powershell", "go", "ruby",
    }
    macro_lang = lang if lang in known else "text"
    lang_param = (
        f'<ac:parameter ac:name="language">{macro_lang}</ac:parameter>'
        if macro_lang
        else ""
    )
    return (
        '<ac:structured-macro ac:name="code">'
        f"{lang_param}"
        f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )


def _convert_with_markdown_lib(md_text: str) -> str:
    import markdown  # local import so the fallback path doesn't require it

    # Pre-extract fenced code blocks so we control them as Confluence code macros
    # (the markdown lib would emit <pre><code> which renders but loses language +
    #  can choke the storage XHTML parser on < / & inside the DBML).
    placeholders: dict[str, str] = {}

    def _stash(match: re.Match) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        token = "xxcodeblock{}xx".format(len(placeholders))
        placeholders[token] = _code_macro(code, lang)
        return f"\n\n{token}\n\n"

    fenced = re.compile(r"```([\w+-]*)\n(.*?)```", re.DOTALL)
    stripped = fenced.sub(_stash, md_text)

    body = markdown.markdown(
        stripped,
        extensions=["tables", "fenced_code", "toc"],
        output_format="xhtml",
    )

    # Re-insert code macros. The tokens may have been wrapped in <p>...</p>.
    for token, macro in placeholders.items():
        body = body.replace(f"<p>{token}</p>", macro)
        body = body.replace(token, macro)
    return body


def _convert_minimal(md_text: str) -> str:
    """Very small MD->HTML fallback (used only if `markdown` lib is missing)."""
    placeholders: dict[str, str] = {}

    def _stash(match: re.Match) -> str:
        token = "xxcbxx{}xx".format(len(placeholders))
        placeholders[token] = _code_macro(match.group(2), match.group(1))
        return token

    text = re.sub(r"```([\w+-]*)\n(.*?)```", _stash, md_text, flags=re.DOTALL)

    out_lines: list[str] = []
    for line in text.splitlines():
        if line in placeholders:
            out_lines.append(placeholders[line])
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out_lines.append(f"<h{lvl}>{html.escape(m.group(2))}</h{lvl}>")
        elif line.strip() == "":
            out_lines.append("")
        else:
            out_lines.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(out_lines)


def markdown_to_storage(md_path: str) -> str:
    with open(md_path, "r", encoding="utf-8") as fh:
        md_text = fh.read()
    try:
        import markdown  # noqa: F401

        return _convert_with_markdown_lib(md_text)
    except ImportError:
        print(
            "  WARNING: `markdown` lib not installed — using minimal fallback "
            "(tables will NOT render). Install it: pip install markdown",
            file=sys.stderr,
        )
        return _convert_minimal(md_text)


# ---------------------------------------------------------------------------
# Confluence REST client
# ---------------------------------------------------------------------------
class Confluence:
    def __init__(self, site_url: str, email: str, token: str, space_key: str):
        self.base = site_url.rstrip("/")
        self.api = f"{self.base}/wiki/rest/api/content"
        self.space_key = space_key
        self.session = requests.Session()
        self.session.auth = (email, token)
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    def get_page(self, page_id: str) -> dict:
        resp = self.session.get(
            f"{self.api}/{page_id}", params={"expand": "version,space"}
        )
        resp.raise_for_status()
        return resp.json()

    def _page_url(self, data: dict) -> str:
        webui = data.get("_links", {}).get("webui", "")
        if webui:
            return f"{self.base}/wiki{webui}"
        return f"{self.base}/wiki/spaces/{self.space_key}/pages/{data.get('id')}"

    def update_page(self, page_id: str, title: str, body_storage: str) -> dict:
        current = self.get_page(page_id)
        cur_version = current["version"]["number"]
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "space": {"key": self.space_key},
            "version": {"number": cur_version + 1},
            "body": {
                "storage": {"value": body_storage, "representation": "storage"}
            },
        }
        resp = self.session.put(f"{self.api}/{page_id}", json=payload)
        if not resp.ok:
            raise RuntimeError(f"UPDATE {page_id} failed [{resp.status_code}]: {resp.text}")
        data = resp.json()
        return {
            "id": data["id"],
            "title": data["title"],
            "old_version": cur_version,
            "new_version": data["version"]["number"],
            "url": self._page_url(data),
        }

    def create_page(self, title: str, body_storage: str) -> dict:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": self.space_key},
            "body": {
                "storage": {"value": body_storage, "representation": "storage"}
            },
        }
        resp = self.session.post(self.api, json=payload)
        if not resp.ok:
            raise RuntimeError(f"CREATE '{title}' failed [{resp.status_code}]: {resp.text}")
        data = resp.json()
        return {
            "id": data["id"],
            "title": data["title"],
            "old_version": None,
            "new_version": data["version"]["number"],
            "url": self._page_url(data),
        }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _load_env() -> dict:
    if load_dotenv is not None:
        load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    required = ["CONFLUENCE_SITE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_SPACE_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")
    return {
        "site": os.environ["CONFLUENCE_SITE_URL"],
        "email": os.environ["CONFLUENCE_EMAIL"],
        "token": os.environ["CONFLUENCE_API_TOKEN"],
        "space": os.environ["CONFLUENCE_SPACE_KEY"],
    }


def main(argv: list[str]) -> int:
    cfg = _load_env()
    client = Confluence(cfg["site"], cfg["email"], cfg["token"], cfg["space"])

    requested = {a.lower() for a in argv}
    targets = [t for t in PUBLISH_TARGETS if (t.key in requested) if requested] or [
        t for t in PUBLISH_TARGETS if t.enabled
    ]

    print(f"Confluence site: {cfg['site'].rstrip('/')}  | space: {cfg['space']}")
    print(f"Publishing {len(targets)} target(s): {', '.join(t.key for t in targets)}\n")

    failures = 0
    for t in targets:
        t.page_id = os.environ.get(t.page_id_env) or None
        md_abspath = os.path.join(PROJECT_ROOT, t.md_path)
        action = "UPDATE" if t.page_id else "CREATE"
        print(f"[{t.key.upper()}] {action}  ({t.md_path})")
        try:
            body = markdown_to_storage(md_abspath)
            if t.page_id:
                result = client.update_page(t.page_id, t.title, body)
            else:
                result = client.create_page(t.title, body)
            ver = (
                f"v{result['old_version']} -> v{result['new_version']}"
                if result["old_version"] is not None
                else f"v{result['new_version']} (new)"
            )
            print(f"  OK  id={result['id']}  {ver}")
            print(f"      title : {result['title']}")
            print(f"      url   : {result['url']}\n")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAILED: {exc}\n", file=sys.stderr)

    if failures:
        print(f"Done with {failures} failure(s).")
        return 1
    print("Done — all targets published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
