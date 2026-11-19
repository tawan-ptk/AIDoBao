"""Minimal .env loader for the launch scripts (no third-party dependency).

Reads KEY=VALUE lines from the project's .env; never overrides variables that
are already set in the real environment, and never prints values.
"""
import os,pathlib

def load_env(path):
    path=pathlib.Path(path)
    if not path.is_file():return
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip().removeprefix('export ').strip()
        value=value.strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in '"\'':value=value[1:-1]
        if key and key not in os.environ:os.environ[key]=value
