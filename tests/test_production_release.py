"""Release artifacts must come from the commit whose complete CI run passed."""
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


def test_publishing_is_only_callable_after_all_release_checks():
    ci = _workflow("ci.yml")
    publish = ci["jobs"]["publish"]
    assert set(publish["needs"]) == set(ci["jobs"]) - {"publish"}
    assert publish["if"] == "github.event_name == 'push'"
    assert publish["uses"] == "./.github/workflows/publish-image.yml"
    image = _workflow("publish-image.yml")
    assert set(image.get("on", image.get(True))) == {"workflow_call"}
    assert "format=long" in (ROOT / ".github/workflows/publish-image.yml").read_text()
    walk = _workflow("walk.yml")
    assert not any(step.get("continue-on-error") for step in walk["jobs"]["walk"]["steps"])


def test_production_compose_refuses_mutable_images_without_calling_docker(tmp_path):
    docker = tmp_path / "docker"
    called = tmp_path / "called"
    docker.write_text(f"#!/bin/sh\ntouch '{called}'\n")
    docker.chmod(0o700)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "APP_IMAGE": "ghcr.io/pechst1/conversational-language-learning:latest"}
    result = subprocess.run(["/bin/bash", str(ROOT / "scripts/production_compose.sh"), "config"], env=env, capture_output=True, text=True, check=False)  # noqa: S603 - trusted repository script
    assert result.returncode == 2 and not called.exists()
    env["APP_IMAGE"] = f"ghcr.io/pechst1/conversational-language-learning:sha-{'a' * 40}"
    result = subprocess.run(["/bin/bash", str(ROOT / "scripts/production_compose.sh"), "config"], env=env, capture_output=True, text=True, check=False)  # noqa: S603 - trusted repository script
    assert result.returncode == 0 and called.exists()


def test_both_render_processes_wait_for_ci_checks():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    for service in blueprint["services"]:
        if service.get("type") in {"web", "worker"}:
            assert service["autoDeployTrigger"] == "checksPass"


def _env_template():
    values = {}
    for line in (ROOT / ".env.prod.example").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def _render_env(service_type):
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    service = next(item for item in blueprint["services"] if item.get("type") == service_type)
    return {item["key"]: item for item in service["envVars"]}


def test_render_and_the_compose_template_agree_on_the_production_recipe():
    """WP-138: one canonical recipe. Every setting startup requires in production
    is in the template, and the values both files fix are the same."""

    template = _env_template()
    api = _render_env("web")
    for key in ("ATELIER_DAILY_JOURNEY_COHORT", "REGISTRATION_ALLOWED_EMAILS", "LEGAL_CONTACT_EMAIL", "SMTP_HOST", "SMTP_FROM_EMAIL"):
        assert template.get(key), key
        assert api[key].get("sync") is False, key
    for key, item in api.items():
        if "value" in item and key in template:
            assert template[key].strip('"') == str(item["value"]), key
    assert template["APP_ENV"] == "production"
    assert template["REGISTRATION_OPEN"] == "false"


def test_pilot_runs_production_apns_with_sign_up_closed():
    api, worker = _render_env("web"), _render_env("worker")
    assert api["APNS_USE_SANDBOX"]["value"] == "false"
    assert worker["APNS_USE_SANDBOX"]["value"] == "false"
    assert _env_template()["APNS_USE_SANDBOX"] == "false"
    assert api["REGISTRATION_OPEN"]["value"] == "false"
