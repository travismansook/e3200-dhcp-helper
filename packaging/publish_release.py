"""Publish verified CI assets as an immutable preview release using its job token."""
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
SHA = os.environ["GITHUB_SHA"]
VERSION = (ROOT / "VERSION").read_text().strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", VERSION):
    raise ValueError("VERSION must be a semantic version")
TAG = "v" + VERSION
API = "https://api.github.com/repos/" + REPO
FILES = (
    "E3200-Helper-Windows-x64.zip",
    "E3200-Helper-macOS-AppleSilicon.zip",
    "E3200-Helper-macOS-Intel.zip",
    "E3200-Helper-Ubuntu-amd64.deb",
)


def request(url, method="GET", data=None, content_type="application/json"):
    headers = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "Content-Type": content_type,
               "User-Agent": "E3200-Helper-release"}
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=method, data=body), timeout=180) as response:
        contents = response.read()
        return json.loads(contents) if contents else None


def main():
    assets = ROOT / "release"
    for name in FILES:
        path = assets / name
        if not path.is_file() or path.stat().st_size < 1024:
            raise RuntimeError("Missing build asset: " + name)
    sums = "".join(hashlib.sha256((assets / n).read_bytes()).hexdigest() + "  " + n + "\n" for n in FILES)
    (assets / "SHA256SUMS.txt").write_text(sums)
    notes = (ROOT / "packaging/RELEASE_NOTES.md").read_text()
    release = None
    # Include drafts owned by this token, and never replace a published release.
    for item in request(API + "/releases?per_page=100"):
        if item["tag_name"] == TAG:
            if not item["draft"]:
                raise RuntimeError("This version is already published. Bump VERSION; published downloads are immutable.")
            release = item
            break
    if release is None:
        release = request(API + "/releases", "POST", {
            "tag_name": TAG, "target_commitish": SHA, "name": "E3200 DHCP Helper " + TAG + " — preview",
            "body": notes, "draft": True, "prerelease": True,
        })
    request(API + "/releases/" + str(release["id"]), "PATCH",
            {"body": notes, "target_commitish": SHA})
    existing = {a["name"]: a for a in request(API + "/releases/" + str(release["id"]) + "/assets")}
    for name in (*FILES, "SHA256SUMS.txt"):
        contents = (assets / name).read_bytes()
        if name in existing:
            request(API + "/releases/assets/" + str(existing[name]["id"]), "DELETE")
        url = release["upload_url"].split("{", 1)[0] + "?name=" + urllib.parse.quote(name)
        uploaded = request(url, "POST", contents, "application/octet-stream")
        if uploaded["size"] != len(contents):
            raise RuntimeError("Uploaded asset size differs: " + name)
        digest = uploaded.get("digest")
        if digest and digest != "sha256:" + hashlib.sha256(contents).hexdigest():
            raise RuntimeError("Uploaded asset digest differs: " + name)
    request(API + "/releases/" + str(release["id"]), "PATCH", {"draft": False, "prerelease": True})
    print("Published preview release: https://github.com/" + REPO + "/releases/tag/" + TAG)


if __name__ == "__main__":
    main()
