"""Check both locked dependency graphs against OSV without installing packages."""
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / "frontend/package-lock.json").read_text())
queries = [
    {"package": {"name": path.removeprefix("node_modules/"), "ecosystem": "npm"},
     "version": package["version"]}
    for path, package in lock["packages"].items() if path
]
for name, version in re.findall(r"^([\w-]+)==([^\s;\\]+)",
                              (root / "backend/requirements.txt").read_text(), re.M):
    queries.append({"package": {"name": name, "ecosystem": "PyPI"}, "version": version})
request = Request("https://api.osv.dev/v1/querybatch", method="POST",
                  data=json.dumps({"queries": queries}).encode(),
                  headers={"Content-Type": "application/json"})
with urlopen(request, timeout=60) as response:
    results = json.load(response)["results"]
assert len(results) == len(queries), "Incomplete OSV response"
findings = [
    {"package": query["package"], "version": query["version"], "vulns": result["vulns"]}
    for query, result in zip(queries, results) if result.get("vulns")
]
print(json.dumps({"packages_checked": len(queries), "findings": findings}, indent=2))
raise SystemExit(bool(findings))
