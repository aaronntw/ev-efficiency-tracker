"""Fail the release build when known October security floors are not met."""
from importlib.metadata import version
import json
import platform
import sqlite3
import ssl
import subprocess

import psycopg.pq


def numeric(value):
    return tuple(int(part) for part in value.split("."))


assert numeric(platform.python_version()) >= (3, 12, 15)
for package, minimum in {
    "pip": "26.2.2", "starlette": "1.3.1", "psycopg": "3.3.6",
}.items():
    assert numeric(version(package)) >= numeric(minimum), package

packages = {}
for package, minimum in {
    "nginx": "1.26.3-3+deb13u10",
    "ca-certificates": "20250419+deb13u1",
}.items():
    installed = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Version}", package], text=True
    ).strip()
    subprocess.run(["dpkg", "--compare-versions", installed, "ge", minimum], check=True)
    packages[package] = installed

print(json.dumps({
    "python": platform.python_version(), "pip": version("pip"),
    "fastapi": version("fastapi"), "starlette": version("starlette"),
    "sqlite": sqlite3.sqlite_version, "openssl": ssl.OPENSSL_VERSION,
    "psycopg": version("psycopg"), "libpq": psycopg.pq.version(),
    "debian_packages": packages,
}, indent=2))
