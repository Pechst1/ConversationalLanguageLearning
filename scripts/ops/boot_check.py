#!/usr/bin/env python3
"""Pre-deploy check: boot the built image the way Render will, inside the plan's memory.

#134: production returned 502 for one to three minutes on several nights because
Render killed the API for running out of memory (512 MB, ``oomKilled`` in the
service events). Nothing before the deploy looked at memory or at whether the
image starts with the manifest's production settings at all.

This runs in CI against the image the docker job just built, before Render's
``checksPass`` deploy trigger can fire:

1. reads the service's literal ``envVars`` from ``render.yaml`` (so a bad value
   in the manifest fails here, not on Render) and fills the dashboard-only
   secrets the production start-up guard requires with harmless placeholders;
2. runs the image with ``--memory`` set to the plan's limit, the same entrypoint
   (migrations, reference data, cache warm-up) and ``APP_ENV=production``;
3. waits for ``/ready``, makes a few real requests, and reads the container's
   resident memory once it has settled.

It fails when the container exits or is OOM-killed, when ``/ready`` never answers,
or when the idle footprint leaves less than ``--fail-headroom-mib`` of the plan
(default 64 MiB; a live walk adds about 100 MiB). Under ``--warn-headroom-mib`` it
prints a GitHub warning annotation instead.

Usage (CI)::

    python scripts/ops/boot_check.py --image conversational-language-learning:ci \\
        --database-url postgresql+psycopg2://postgres:postgres@localhost:5432/atelier_boot \\
        --redis-url redis://localhost:6379/0
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

#: Render instance memory per plan (MiB).
PLAN_MEMORY_MIB = {"starter": 512, "standard": 2048, "pro": 4096, "pro_plus": 8192}

#: Dashboard-only values the production start-up guard insists on. Placeholders
#: only: nothing in the boot check sends mail or prints the legal pages' contact.
PLACEHOLDERS = {
    "SMTP_HOST": "smtp.example.invalid",
    "SMTP_FROM_EMAIL": "boot-check@example.invalid",
    "LEGAL_CONTACT_EMAIL": "boot-check@example.invalid",
    "REGISTRATION_ALLOWED_EMAILS": "boot-check@example.invalid",
}

#: Wired from other Render resources (fromDatabase / fromService); CI passes its own.
WIRED = {"DATABASE_URL", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"}


def manifest_service(name: str) -> dict:
    manifest = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    for service in manifest.get("services", []):
        if service.get("name") == name:
            return service
    raise SystemExit(f"render.yaml has no service named {name!r}")


def service_env(service: dict, database_url: str, redis_url: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for entry in service.get("envVars", []):
        key = entry["key"]
        if "value" in entry:
            env[key] = str(entry["value"])
        elif key in PLACEHOLDERS:
            env[key] = PLACEHOLDERS[key]
        elif "generateValue" in entry:
            env[key] = "boot-check-generated-secret"
    env["DATABASE_URL"] = database_url
    for key in WIRED - {"DATABASE_URL"}:
        env[key] = redis_url
    env["PORT"] = "8000"
    return env


def docker(*args: str, check: bool = True) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True)  # noqa: S603, S607
    if check and result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def http_status(url: str, *, method: str = "GET", body: dict | None = None) -> int:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - fixed http(s) hosts
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return 0


def container_state(container: str) -> dict:
    raw = docker("inspect", "--format", "{{json .State}}", container, check=False)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def memory_mib(container: str) -> float:
    usage = docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container)
    match = re.match(r"\s*([\d.]+)\s*([KMG]i?B)", usage)
    if not match:
        raise RuntimeError(f"could not read memory from docker stats: {usage!r}")
    value, unit = float(match.group(1)), match.group(2)
    factor = {"KiB": 1 / 1024, "KB": 1 / 1024, "MiB": 1, "MB": 1, "GiB": 1024, "GB": 1024}[unit]
    return value * factor


def fail(message: str, container: str) -> int:
    print(f"::error title=Boot check::{message}")
    print("--- container log (last 80 lines) ---")
    print(docker("logs", "--tail", "80", container, check=False))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", required=True)
    parser.add_argument("--service", default="atelier-api")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--redis-url", required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--ready-timeout", type=int, default=300)
    parser.add_argument("--settle-seconds", type=int, default=15)
    parser.add_argument("--fail-headroom-mib", type=int, default=64)
    parser.add_argument("--warn-headroom-mib", type=int, default=128)
    args = parser.parse_args()

    service = manifest_service(args.service)
    plan = str(service.get("plan", "starter"))
    limit = PLAN_MEMORY_MIB.get(plan)
    if limit is None:
        raise SystemExit(f"unknown Render plan {plan!r}; add it to PLAN_MEMORY_MIB")
    env = service_env(service, args.database_url, args.redis_url)
    env["PORT"] = str(args.port)

    name = f"boot-check-{int(time.time())}"
    run = ["run", "-d", "--name", name, "--network", "host",
           f"--memory={limit}m", f"--memory-swap={limit}m"]
    for key, value in sorted(env.items()):
        run += ["-e", f"{key}={value}"]
    docker(*run, args.image)
    print(f"Booting {args.image} as {args.service} ({plan}, {limit} MiB) …")

    base = f"http://127.0.0.1:{args.port}"
    started = time.monotonic()
    try:
        while True:
            state = container_state(name)
            if not state.get("Running", False):
                why = "OOM-killed" if state.get("OOMKilled") else f"exited with {state.get('ExitCode')}"
                return fail(f"the container {why} before /ready answered", name)
            if http_status(f"{base}/ready") == 200:
                break
            if time.monotonic() - started > args.ready_timeout:
                return fail(f"/ready did not answer 200 within {args.ready_timeout} s", name)
            time.sleep(2)
        boot_seconds = time.monotonic() - started
        print(f"/ready is 200 after {boot_seconds:.0f} s")

        checks = {
            "GET /health": http_status(f"{base}/health"),
            "GET /privacy": http_status(f"{base}/privacy"),
            "POST /api/v1/auth/login (wrong password)": http_status(
                f"{base}/api/v1/auth/login",
                method="POST",
                body={"email": "nobody@example.com", "password": "not-a-password"},
            ),
        }
        for label, status in checks.items():
            print(f"  {label}: {status}")
        if checks["GET /health"] != 200 or checks["GET /privacy"] != 200:
            return fail("a public endpoint did not answer 200", name)
        if not 400 <= checks["POST /api/v1/auth/login (wrong password)"] < 500:
            return fail("login with a wrong password did not answer 4xx (database path broken?)", name)

        time.sleep(args.settle_seconds)
        state = container_state(name)
        if not state.get("Running", False):
            return fail("the container stopped after start-up" + (" (OOM-killed)" if state.get("OOMKilled") else ""), name)
        used = memory_mib(name)
        headroom = limit - used
        print(f"Idle memory after warm-up: {used:.0f} MiB of {limit} MiB ({headroom:.0f} MiB headroom)")
        if headroom < args.fail_headroom_mib:
            return fail(
                f"idle memory {used:.0f} MiB leaves {headroom:.0f} MiB of the {plan} plan's {limit} MiB; "
                f"the first busy minute would OOM-kill it on Render (#134)",
                name,
            )
        if headroom < args.warn_headroom_mib:
            print(
                f"::warning title=Memory headroom::{args.service} idles at {used:.0f} MiB of {limit} MiB "
                f"({headroom:.0f} MiB headroom); a live walk adds about 100 MiB (#134)"
            )
        print("Boot check passed.")
        return 0
    finally:
        docker("rm", "-f", name, check=False)


if __name__ == "__main__":
    sys.exit(main())
