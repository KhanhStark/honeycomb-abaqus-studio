import json
import os
import subprocess
import sys

import pytest

from honeycomb_studio.cloud_github import configured_repository


def test_local_default_and_explicit_repository():
    assert configured_repository({}) == "xuankhanh24/honeycomb-abaqus-studio"
    assert configured_repository({"HONEYCOMB_GITHUB_REPOSITORY": "KhanhStark/honeycomb-abaqus-studio"}) == (
        "KhanhStark/honeycomb-abaqus-studio"
    )


@pytest.mark.parametrize("value", ["owner/../other", "owner/..", "owner/name?x=1", "https://github.com/a/b"])
def test_invalid_repository_fails_instead_of_falling_back(value):
    with pytest.raises(ValueError):
        configured_repository({"GITHUB_REPOSITORY": value})


@pytest.mark.parametrize("owner", ["KhanhStark", "luukhanh24"])
def test_fork_worker_import_routes_catalog_requests_to_its_own_repository(owner):
    code = '''
import json
import httpx
from honeycomb_studio.cloud_github import Github, REPOSITORY
seen=[]
def handle(request):
    seen.append(str(request.url))
    return httpx.Response(200,json={"ok":True})
github=Github(token="test",client=httpx.Client(transport=httpx.MockTransport(handle)))
github.repo("GET","/contents/jobs/example.json?ref=cloud-data")
print(json.dumps({"repository":REPOSITORY,"requests":seen}))
'''
    env = dict(os.environ, GITHUB_REPOSITORY=f"{owner}/honeycomb-abaqus-studio")
    env.pop("HONEYCOMB_GITHUB_REPOSITORY", None)
    result = subprocess.run([sys.executable, "-c", code], env=env, check=True,
                            capture_output=True, text=True, encoding="utf-8")
    receipt = json.loads(result.stdout)
    assert receipt["repository"] == f"{owner}/honeycomb-abaqus-studio"
    assert receipt["requests"] == [
        f"https://api.github.com/repos/{owner}/honeycomb-abaqus-studio/contents/jobs/example.json?ref=cloud-data"
    ]
