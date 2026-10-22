#!/usr/bin/env python3
"""Register the explicitly selected Mac over SSH; credentials travel on stdin only."""
import argparse
import json
import shlex
import subprocess


def gh(*args):
    return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh", required=True, help="Authorized SSH user@host")
    parser.add_argument("--repo", default="mariia-osipova/hive")
    parser.add_argument("--name", default="hutter-mac")
    parser.add_argument("--tailscale", action="store_true")
    args = parser.parse_args()
    if args.ssh.startswith("-"):
        parser.error("Invalid SSH target")
    transport = ["tailscale", "ssh"] if args.tailscale else ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    release = gh("repos/actions/runner/releases/latest")
    assets = {a["name"]: a for a in release["assets"]}
    probe = subprocess.check_output(transport + [args.ssh, "uname -s; uname -m"], text=True).splitlines()
    if probe != ["Darwin", "arm64"] and probe != ["Darwin", "x86_64"]:
        raise SystemExit(f"Expected a Mac, got {probe}")
    arch = "arm64" if probe[1] == "arm64" else "x64"
    version = release["tag_name"].removeprefix("v")
    asset = assets[f"actions-runner-osx-{arch}-{version}.tar.gz"]
    digest = asset.get("digest", "")
    if not digest.startswith("sha256:"):
        raise SystemExit("Official release has no SHA256 digest")
    # Do not replace another runner, or generate credentials before confirming access.
    directory = f".local/share/github-actions/{args.repo.replace('/', '-')}-{args.name}"
    probe_command = f"test ! -f \"$HOME\"/{shlex.quote(directory)}/.runner"
    subprocess.run(transport + [args.ssh, probe_command], check=True)
    token = gh("--method", "POST", f"repos/{args.repo}/actions/runners/registration-token")["token"]
    # Positional arguments are shell-quoted; never put the registration token in the SSH command.
    script = "\n".join([
        "set -eu", "umask 077", "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH",
        'IFS= read -r runner_token',
        f'mkdir -p "$HOME"/{shlex.quote(directory)}',
        f'cd "$HOME"/{shlex.quote(directory)}',
        f"curl --fail --location --retry 3 {shlex.quote(asset['browser_download_url'])} --output runner.tar.gz",
        f"printf '%s  runner.tar.gz\\n' {shlex.quote(digest.split(':', 1)[1])} | shasum -a 256 -c -",
        "tar xzf runner.tar.gz", "rm runner.tar.gz",
        f'./config.sh --unattended --url {shlex.quote("https://github.com/" + args.repo)} --token "$runner_token" --name {shlex.quote(args.name)} --labels {shlex.quote(args.name + ",az-hive")} --work _work',
        "unset runner_token", "./svc.sh install", "./svc.sh start", "./svc.sh status",
    ])
    # Supply the script as a quoted remote command so stdin contains only the token.
    remote = "bash -c " + shlex.quote(script)
    result = subprocess.run(transport + [args.ssh, remote], input=token + "\n", text=True)
    if result.returncode:
        raise SystemExit("Runner setup failed; inspect the service on the selected Mac before retrying")
    print(json.dumps({"repo": args.repo, "name": args.name, "version": version, "architecture": arch,
                      "sha256": digest.split(":", 1)[1], "directory": "~/" + directory}, indent=2))


if __name__ == "__main__":
    main()
