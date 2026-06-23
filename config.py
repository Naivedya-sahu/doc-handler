#!/usr/bin/env python3
"""
config — central settings for Doc-handler (model endpoints, hosts, locations, options).

Designed for Pi5 deployment: the Pi orchestrates while the model runs on another
machine (e.g. the laptop's LM Studio reached over Tailscale). `hosts` maps names to
API URLs; `locations` maps names to local/mounted folders you point the tagger at.

Precedence: CLI flag  >  config.json  >  built-in DEFAULTS.
Config file search: --config PATH, else config.json next to this file.
JSON (stdlib, no deps). Edit config.json; keep config.example.json as the template.
"""
from __future__ import annotations
import os, json, copy

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "model": {
        "host": "localhost",          # which entry in "hosts" to call
        "model": "local-model",       # text model id in LM Studio
        "vision_model": "local-vision",
        "backend": "local",           # local | openai
        "frontier": "none",           # none | claude | openai  (hard-99UNS fallback)
        "openai_model": "gpt-4o-mini",
        "timeout": 180,
    },
    "hosts": {                        # name -> OpenAI-compatible chat/completions URL
        "localhost": "http://localhost:1234/v1/chat/completions",
    },
    "locations": {},                  # name -> {type: local|mount|ssh, path, note}
    "archive_root": "",               # default destination for --move @archive
    "options": {
        "vision": False, "apply": False,
        "min_text": 80, "deep_pages": 5, "deep_cap": 4000, "dpi": 120,
    },
}

def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out

def load_config(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    for p in (path, os.path.join(HERE, "config.json")):
        if p and os.path.isfile(p):
            try: cfg = _merge(cfg, json.load(open(p, encoding="utf-8")))
            except Exception as e: print(f"[config] ignored {p}: {e}")
            break
    return cfg

def resolve_api(cfg, host=None):
    h = host or cfg["model"]["host"]
    if isinstance(h, str) and h.startswith("http"):
        return h                                   # host given as a raw URL
    return cfg["hosts"].get(h, DEFAULTS["hosts"]["localhost"])

def resolve_location(cfg, name):
    """Return a filesystem path for a named location (or treat name as a raw path)."""
    loc = cfg["locations"].get(name)
    if not loc:
        return name                                # not a named location -> raw path
    t = loc.get("type", "local")
    if t in ("local", "mount"):
        return loc["path"]                         # 'mount' must already be OS-mounted
    if t == "ssh":
        raise SystemExit(f"[config] location '{name}' is ssh — mount it first (see GUIDE).")
    return loc.get("path", name)

def arg_defaults(cfg):
    """(argparse defaults dict, globals dict) derived from config."""
    m, o = cfg["model"], cfg["options"]
    args = {
        "api": resolve_api(cfg), "model": m["model"], "vision_model": m["vision_model"],
        "backend": m["backend"], "frontier": m["frontier"], "openai_model": m["openai_model"],
        "vision": bool(o.get("vision", False)), "apply": bool(o.get("apply", False)),
    }
    glob = {"MIN_TEXT": o.get("min_text", 80), "DEEP_PAGES": o.get("deep_pages", 5),
            "DEEP_CAP": o.get("deep_cap", 4000), "DPI": o.get("dpi", 120)}
    return args, glob
