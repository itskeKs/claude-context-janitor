#!/usr/bin/env python3
"""The one check of this repository: manifests, skill frontmatter and a smoke run of audit.py.

Standard library only, Python 3.8 compatible. Read-only apart from a temporary directory that is
removed again. Prints one `ok` or `FAIL` line per check and exits 1 if any check failed.
Usage: python3 -I tools/check.py
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
CHECKS = []


class Problem(Exception):
    pass


def check(label):
    def register(fn):
        CHECKS.append((label, fn))
        return fn
    return register


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Problem("%s: %s" % (path.relative_to(ROOT), e))


def plugin_dir():
    plugins = load(MARKETPLACE).get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or "source" not in plugins[0]:
        raise Problem("expected exactly one plugin entry with a source")
    return plugins[0], ROOT / plugins[0]["source"]


def skill_dir():
    entry, pdir = plugin_dir()
    return pdir / "skills" / entry["name"]


def frontmatter(path):
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", path.read_text(encoding="utf-8"), re.S)
    if not m:
        raise Problem("no frontmatter in %s" % path.relative_to(ROOT))
    out = {}
    for line in m.group(1).splitlines():
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            out[top.group(1)] = top.group(2).strip().strip("'\"")
    return out


@check("marketplace.json and plugin.json parse")
def _():
    load(plugin_dir()[1] / ".claude-plugin" / "plugin.json")


@check("marketplace source path exists")
def _():
    if not plugin_dir()[1].is_dir():
        raise Problem("%s is not a directory" % plugin_dir()[0]["source"])


@check("marketplace entry equals plugin.json (name, version, description)")
def _():
    entry, pdir = plugin_dir()
    manifest = load(pdir / ".claude-plugin" / "plugin.json")
    for key in ("name", "version", "description"):
        if not entry.get(key) or entry.get(key) != manifest.get(key):
            raise Problem("%s differs: marketplace %r, plugin.json %r" % (key, entry.get(key), manifest.get(key)))


@check("SKILL.md name equals skill directory and plugin name")
def _():
    sdir = skill_dir()
    name = frontmatter(sdir / "SKILL.md").get("name")
    plugin_name = load(plugin_dir()[1] / ".claude-plugin" / "plugin.json").get("name")
    if not name or not (name == sdir.name == plugin_name):
        raise Problem("frontmatter name %r, directory %r, plugin %r" % (name, sdir.name, plugin_name))


@check("SKILL.md has a non-empty description")
def _():
    if not frontmatter(skill_dir() / "SKILL.md").get("description"):
        raise Problem("description is missing or empty")


@check("audit.py compiles, with Python 3.8 syntax, without writing bytecode")
def _():
    path = skill_dir() / "scripts" / "audit.py"
    source = path.read_text(encoding="utf-8")
    try:
        compile(source, str(path), "exec")
        ast.parse(source, str(path), feature_version=(3, 8))
    except SyntaxError as e:
        raise Problem(str(e))


def run_audit(args, env=None):
    cmd = [sys.executable, "-I", str(skill_dir() / "scripts" / "audit.py")] + args
    return subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)


@check("audit.py --help exits 0")
def _():
    done = run_audit(["--help"])
    if done.returncode != 0:
        raise Problem("exit status %d" % done.returncode)


@check("audit.py smoke run (empty HOME and --cwd) exits 0 and writes nothing")
def _():
    root = tempfile.mkdtemp(prefix="janitor-check-")
    try:
        home, cwd = os.path.join(root, "home"), os.path.join(root, "cwd")
        for d in (home, cwd):
            os.mkdir(d)
        done = run_audit(["--cwd", cwd, "--no-usage"], env={"HOME": home, "PATH": os.environ.get("PATH", "")})
        if done.returncode != 0:
            raise Problem("exit status %d: %s" % (done.returncode, done.stderr.decode(errors="replace")[-300:]))
        left = os.listdir(home) + os.listdir(cwd)
        if left:
            raise Problem("left files behind: %s" % ", ".join(sorted(left)))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    failed = 0
    for label, fn in CHECKS:
        try:
            fn()
            print("ok       %s" % label)
        except Exception as e:  # a failing check must not stop the others
            failed += 1
            print("FAIL     %s: %s" % (label, e))
    print("check: %d of %d checks passed" % (len(CHECKS) - failed, len(CHECKS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
