"""Owner-authorized campaign inventory/provisioning. Tokens never leave process memory."""
import argparse
import json
import subprocess

import httpx

from honeycomb_studio.campaign import OWNERS
from honeycomb_studio.cloud_github import Github


def owner_client(owner):
    token = subprocess.run(["gh", "auth", "token", "--hostname", "github.com", "--user", owner],
                           check=True, capture_output=True, text=True).stdout.strip()
    return Github(token=token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provision", action="store_true")
    args = parser.parse_args()
    rows = []
    for owner in OWNERS:
        github = owner_client(owner)
        repository = owner + "/honeycomb-abaqus-studio"
        user = github.request("GET", "/user")
        if user["login"].lower() != owner.lower():
            raise ValueError("GitHub identity mismatch")
        repo = github.request("GET", "/repos/" + repository, allow_missing=True)
        if repo is None and args.provision:
            repo = github.request("POST", "/user/repos", {"name": "honeycomb-abaqus-studio", "private": False,
                                  "description": "Authorized core-damage simulation campaign", "auto_init": False})
        try:
            installations = github.request("GET", "/user/installations?per_page=100")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise
            installations = {}
        secrets = github.request("GET", "/repos/" + repository + "/actions/secrets") if repo else {}
        rows.append({"owner": owner, "repository_exists": repo is not None,
                     "push": (repo or {}).get("permissions", {}).get("push", False),
                     "secrets": [s["name"] for s in secrets.get("secrets", [])],
                     "apps": [{"slug": i["app_slug"], "installation": i["id"]}
                              for i in installations.get("installations", [])]})
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
