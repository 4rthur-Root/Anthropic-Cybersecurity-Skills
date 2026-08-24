#!/usr/bin/env python3
"""Regenerate the contributor avatar wall in README.md from the GitHub API.

Writes between the markers:

    <!-- contributors:start -->
    ...generated...
    <!-- contributors:end -->

Avatars are served from github.com/<login>.png rather than a third-party
contributor-image service. That is deliberate: a README image is fetched on
every page view, so an external host would be an uncontrolled dependency in the
most-viewed file in the repository. GitHub's own avatar endpoint has neither
problem, and GitHub proxies it through camo like any other image.

Usage:
    python tools/update-contributors.py            # rewrite README.md
    python tools/update-contributors.py --check    # exit 1 if out of date
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "mukul975/Anthropic-Cybersecurity-Skills")
MAINTAINER = REPO.split("/")[0]
README = "README.md"

START = "<!-- contributors:start -->"
END = "<!-- contributors:end -->"

# Accounts that are bots or automation, excluded from the wall.
EXCLUDE_SUFFIXES = ("[bot]",)
EXCLUDE_LOGINS = {"github-actions", "dependabot", "pull"}

AVATAR_PX = 72


def fetch_contributors() -> list[dict]:
    """Every non-bot contributor, most contributions first."""
    people: list[dict] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{REPO}/contributors?per_page=100&page={page}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "update-contributors",
        })
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        if not batch:
            break
        people.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return [
        p for p in people
        if p.get("type") != "Bot"
        and not p.get("login", "").endswith(EXCLUDE_SUFFIXES)
        and p.get("login") not in EXCLUDE_LOGINS
    ]


def render(people: list[dict]) -> str:
    lines = ['<p align="center">']
    for person in people:
        login = person["login"]
        count = person.get("contributions", 0)
        plural = "" if count == 1 else "s"
        title = f"{login} — maintainer" if login == MAINTAINER else f"{login} — {count} contribution{plural}"
        lines.append(
            f'<a href="https://github.com/{login}" title="{title}">'
            f'<img src="https://github.com/{login}.png?size=100" '
            f'width="{AVATAR_PX}" height="{AVATAR_PX}" alt="@{login}"></a>'
        )
    lines.append("</p>")
    lines.append("")
    lines.append(
        f'<p align="center"><sub>{len(people)} contributors, ordered by contribution count · '
        f'see the full <a href="https://github.com/{REPO}/graphs/contributors">contributor graph</a>'
        "</sub></p>"
    )
    return "\n".join(lines)


def splice(readme: str, block: str) -> str:
    if START not in readme or END not in readme:
        raise SystemExit(
            f"ERROR: {README} is missing the {START} / {END} markers. "
            "Add them around the contributor wall."
        )
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if README.md is out of date; do not write")
    args = parser.parse_args()

    if not os.path.isfile(README):
        print(f"ERROR: {README} not found. Run from the repository root.")
        return 1

    people = fetch_contributors()
    if not people:
        print("ERROR: the API returned no contributors; refusing to blank the section.")
        return 1

    current = open(README, encoding="utf-8").read()
    updated = splice(current, render(people))

    if updated == current:
        print(f"OK: contributor wall is current ({len(people)} contributors)")
        return 0

    if args.check:
        print(f"ERROR: contributor wall is out of date ({len(people)} contributors). "
              "Run: python tools/update-contributors.py")
        return 1

    with open(README, "w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    print(f"Updated contributor wall: {len(people)} contributors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
