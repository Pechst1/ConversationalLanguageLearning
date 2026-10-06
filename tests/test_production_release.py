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
