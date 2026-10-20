#!/usr/bin/env python3
"""Prepare public PM artifacts in scratch before native package tests.

Run with a normal bootstrap Python (stdlib only). All source copies, PM state,
public downloads and logs live under a new/empty --scratch-dir. This does not
read operator configuration or credentials, and does not invoke any provider.
The subsequent pytest run uses the emitted source and seed paths.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-repo", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--expected-hermes-revision", default="e06df9c2eae6901f4c88f464e0ae6e753c0428b8",
                        help="Full reviewed Hermes HEAD SHA (default: v0.22.0)")
    parser.add_argument("--output-env", type=Path,
                        help="Append HERMES_AGENT_REPO and HERMES_NATIVE_PACKAGE_SEED for CI")
    args = parser.parse_args()
    source = args.hermes_repo.resolve()
    scratch = args.scratch_dir.resolve()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", args.expected_hermes_revision):
        parser.error("--expected-hermes-revision must be a full reviewed commit SHA")
    git_env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    git_env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")

    def git(repo, *argv, **kwargs):
        return subprocess.run(["git", "-C", str(repo), *argv], env=git_env,
                              check=True, stderr=subprocess.PIPE, **kwargs)
    revision = git(source, "rev-parse", "HEAD", stdout=subprocess.PIPE, text=True).stdout.strip()
    if revision != args.expected_hermes_revision.lower():
        parser.error("Hermes HEAD does not match --expected-hermes-revision")
    try:
        git(source, "diff", "--quiet", "HEAD", "--")
    except subprocess.CalledProcessError:
        parser.error("Hermes tracked source differs from HEAD; use a clean reviewed checkout")
    if not (source / "pm/client.py").is_file():
        parser.error("--hermes-repo must contain the native Hermes PM implementation")
    if scratch.exists() and (not scratch.is_dir() or any(scratch.iterdir())):
        parser.error("--scratch-dir must be new or empty; existing state is never reused")
    if scratch == source or source in scratch.parents:
        parser.error("--scratch-dir must be outside the Hermes source checkout")
    scratch.mkdir(parents=True, exist_ok=True)
    hermes = scratch / "hermes-agent"
    home = scratch / "home"
    home.mkdir()

    def archive(repo, destination, *paths):
        # Git archive reads committed blobs only: untracked .env, caches and
        # private operator files are never copied or opened.
        archive_path = scratch / (destination.name + ".tar")
        with archive_path.open("wb") as output:
            git(repo, "archive", "--format=tar", "HEAD", *paths, stdout=output)
        destination.mkdir()
        with tarfile.open(archive_path) as bundle:
            bundle.extractall(destination, filter="data")
        archive_path.unlink()
    archive(source, hermes)
    root = Path(__file__).resolve().parents[1]
    try:
        git(root, "diff", "--quiet", "HEAD", "--", "alibaba-token-plan-media")
    except subprocess.CalledProcessError:
        parser.error("Media tracked source differs from HEAD; commit/review it before cache preparation")
    fixture = scratch / "components"
    archive(root, fixture, "alibaba-token-plan-media")
    candidate = fixture / "alibaba-token-plan-media"
    if not (candidate / "plugin.yaml").is_file():
        parser.error("Media component must be committed before cache preparation")
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(HOME=str(home), HERMES_HOME=str(home / ".hermes"),
               XDG_CACHE_HOME=str(home / ".cache"), PYTHONPATH=str(hermes),
               PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", PIP_CONFIG_FILE=os.devnull)
    code = """
from pathlib import Path
import sys
from pm.paths import repo_root, store_root
from pm.environments import install_state_dir
from pm.client import sync_venv
from pm.plugin_inputs import Candidates
scratch = Path(sys.argv[1]).resolve()
for path in (repo_root(), store_root(), install_state_dir(repo_root())):
    assert path.resolve().is_relative_to(scratch), path
    print('Scratch PM path:', path, flush=True)
# The real dependency transaction must succeed. No validate CLI fallback may
# swallow preparation errors and make a static report look like resolution.
sync_venv(explicit=True, plugins=Candidates([Path(sys.argv[2])]))
"""
    log = scratch / "prepare.log"
    with log.open("w") as output:
        completed = subprocess.run([sys.executable, "-c", code, str(scratch), str(candidate)],
                                   env=env, cwd=scratch, stdout=output,
                                   stderr=subprocess.STDOUT, timeout=600)
    if completed.returncode:
        print(log.read_text(), file=sys.stderr)
        return completed.returncode
    paths = {"HERMES_AGENT_REPO": str(hermes),
             "HERMES_NATIVE_PACKAGE_SEED": str(home / ".hermes")}
    if args.output_env:
        with args.output_env.open("a") as output:
            for key, value in paths.items():
                if "\n" in value or "\r" in value:
                    raise ValueError("CI environment paths must not contain newlines")
                output.write(f"{key}={value}\n")
    print(json.dumps(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
