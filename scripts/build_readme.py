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


# What the event was, in plain words. The widget shows the repo, the kind of
# activity and how long ago. It never shows a commit message: public commit
# subjects are working notes, not copy.
EVENT_VERBS = {
    "PushEvent": "pushed to",
    "ReleaseEvent": "published a release in",
    "PullRequestEvent": "worked on a pull request in",
    "IssuesEvent": "worked on an issue in",
    "CreateEvent": "created a branch or tag in",
}


def latest_activity():
    """Return (repo, verb, when) for the most recent public event that is real
    work (a push, release, pull request, issue or branch/tag). Stars, forks and
    watches are not work and are skipped. Returns None if there is none."""
    for ev in api("/users/%s/events/public" % USER):
        verb = EVENT_VERBS.get(ev.get("type"))
        if not verb:
            continue
        repo = ev["repo"]["name"].split("/")[-1]
        return repo, verb, ago(ev["created_at"])
    return None


def build_block():
    lines = []
    act = latest_activity()
    if act:
        repo, verb, when = act
        url = "https://github.com/%s/%s" % (USER, repo)
        lines.append("🛠 **Latest:** %s [`%s`](%s) · %s" % (verb, repo, url, when))
    # the flagship's own freshness, as a second honest signal. Skipped when it
    # would only repeat the line above.
    try:
        eo = api("/repos/%s/executive-office" % USER)
        eo_when = ago(eo["pushed_at"])
        if not act or act[0] != "executive-office" or act[2] != eo_when:
            lines.append("📡 **executive-office** last updated %s" % eo_when)
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
