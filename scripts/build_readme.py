#!/usr/bin/env python3
"""Self-updating profile README.

Pulls Kyle's most recent public GitHub activity and rewrites the block between
<!-- latest:start --> and <!-- latest:end --> in README.md. Runs in GitHub
Actions on a schedule; the README visibly maintains itself off real data.

Standard library only, so the Action needs no `pip install`.
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

USER = "khlittlejohn-hue"
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
START, END = "<!-- latest:start -->", "<!-- latest:end -->"


def api(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def ago(iso):
    then = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    secs = (datetime.now(timezone.utc) - then).total_seconds()
    if secs < 3600:
        return "%dm ago" % max(1, round(secs / 60))
    if secs < 86400:
        return "%dh ago" % round(secs / 3600)
    if secs < 2592000:
        return "%dd ago" % round(secs / 86400)
    return "%dmo ago" % round(secs / 2592000)


def latest_push():
    """Return (repo, message, when) for the most recent public push, or None."""
    for ev in api("/users/%s/events/public" % USER):
        if ev.get("type") != "PushEvent":
            continue
        repo = ev["repo"]["name"].split("/")[-1]
        commits = ev.get("payload", {}).get("commits", [])
        msg = commits[-1]["message"].splitlines()[0] if commits else "pushed changes"
        if len(msg) > 72:
            msg = msg[:69] + "..."
        return repo, msg, ago(ev["created_at"])
    return None


def build_block():
    lines = []
    push = latest_push()
    if push:
        repo, msg, when = push
        url = "https://github.com/%s/%s" % (USER, repo)
        lines.append("🛠 **Latest:** `%s` in [`%s`](%s) · %s" % (msg, repo, url, when))
    # the flagship's own freshness, as a second honest signal
    try:
        eo = api("/repos/%s/executive-office" % USER)
        lines.append(
            "📡 **executive-office** last updated %s" % ago(eo["pushed_at"])
        )
    except Exception:
        pass
    if not lines:
        lines.append("🛠 Building in public. See the pinned repositories below.")
    stamp = datetime.now(timezone.utc).strftime("%b %d, %Y")
    lines.append("")
    lines.append("<sub>Auto-updated from my public GitHub activity · last run %s</sub>" % stamp)
    return "\n".join(lines)


def main():
    path = os.path.abspath(README)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if START not in text or END not in text:
        raise SystemExit("markers not found in README.md")
    block = build_block()
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        START + "\n" + block + "\n" + END,
        text,
        flags=re.S,
    )
    if new != text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        print("README updated.")
    else:
        print("No change.")


if __name__ == "__main__":
    main()
