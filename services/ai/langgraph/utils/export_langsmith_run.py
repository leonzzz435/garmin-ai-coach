from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

def get_client() -> Client:
    if not os.getenv("LANGSMITH_API_KEY"):
        print("ERROR: LANGSMITH_API_KEY environment variable is not set!")
        print("\nSet it via:")
        print("  export LANGSMITH_API_KEY='lsv2_...'")
        print("or add to your .env:")
        print("  LANGSMITH_API_KEY=lsv2_...")
        sys.exit(1)
    return Client()

client = get_client()

def iso(dt): return dt.isoformat() if dt else None

def safe_jsonable(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

def fetch_trace_index(root_run_id: str):
    root = client.read_run(root_run_id)
    runs = list(client.list_runs(trace_id=root.trace_id))
    children_by_parent: dict[str, list[Any]] = defaultdict(list)
    by_id: dict[str, Any] = {str(r.id): r for r in runs}
    for r in runs:
        pid = getattr(r, "parent_run_id", None)
        if pid:
            children_by_parent[str(pid)].append(r)
    for lst in children_by_parent.values():
        lst.sort(key=lambda c: (getattr(c, "execution_order", 0) or 0, iso(getattr(c, "start_time", None)) or ""))
    return root, runs, by_id, children_by_parent

def find_focus_runs(
    runs: Iterable[Any],
    focus_name: str | None,
    focus_tag: str | None,
) -> list[Any]:
    out = []
    for r in runs:
        name_ok = (not focus_name) or (focus_name.lower() in (getattr(r, "name", "") or "").lower())
        tag_ok  = (not focus_tag) or (focus_tag in (getattr(r, "tags", []) or []))
        if name_ok and tag_ok:
            out.append(r)
    out.sort(key=lambda r: getattr(r, "start_time", datetime.min))
    return out

def truncate(obj, max_chars: int):
    if max_chars is None:
        return obj
    if isinstance(obj, str):
        if len(obj) <= max_chars:
            return obj
        extra = len(obj) - max_chars
        return obj[:max_chars] + f"... [truncated {extra} chars]"
    if isinstance(obj, list):
        return [truncate(x, max_chars) for x in obj]
    if isinstance(obj, tuple):
        return tuple(truncate(x, max_chars) for x in obj)
    if isinstance(obj, dict):
        return {k: truncate(v, max_chars) for k, v in obj.items()}
    return obj

def strip_keys(obj, keys_to_strip: set[str]):
    if not keys_to_strip:
        return obj
    if isinstance(obj, dict):
        return {k: strip_keys(v, keys_to_strip) for k, v in obj.items() if k not in keys_to_strip}
    if isinstance(obj, list):
        return [strip_keys(x, keys_to_strip) for x in obj]
    if isinstance(obj, tuple):
        return tuple(strip_keys(x, keys_to_strip) for x in obj)
    return obj

def run_to_dict(
    r,
    children_by_parent: dict[str, list[Any]],
    max_depth: int | None,
    depth: int,
    strip_input_keys: set[str],
    strip_output_keys: set[str],
    max_chars_json: int | None,
) -> dict[str, Any]:
    try:
        fdbk = list(client.list_feedback(run_ids=[r.id]))
        feedback = [f.model_dump() if hasattr(f, "model_dump") else getattr(f, "dict", lambda: {} )() for f in fdbk]
    except Exception:
        feedback = []

    inputs = safe_jsonable(getattr(r, "inputs", {}))
    outputs = safe_jsonable(getattr(r, "outputs", {}))

    if strip_input_keys:
        inputs = strip_keys(inputs, strip_input_keys)
    if strip_output_keys:
        outputs = strip_keys(outputs, strip_output_keys)

    if max_chars_json is not None:
        inputs  = truncate(inputs,  max_chars_json)
        outputs = truncate(outputs, max_chars_json)

    d = {
        "id": str(r.id),
        "trace_id": str(getattr(r, "trace_id", "")),
        "project_id": str(getattr(r, "project_id", "")),
        "name": getattr(r, "name", None),
        "run_type": getattr(r, "run_type", None),
        "status": getattr(r, "status", None),
        "tags": getattr(r, "tags", []),
        "start_time": iso(getattr(r, "start_time", None)),
        "end_time": iso(getattr(r, "end_time", None)),
        "latency_ms": (
            (r.end_time - r.start_time).total_seconds() * 1000
            if getattr(r, "end_time", None) and getattr(r, "start_time", None)
            else None
        ),
        "inputs": inputs,
        "outputs": outputs,
        "error": getattr(r, "error", None),
        "metadata": safe_jsonable(getattr(r, "metadata", {})),
        "extra": safe_jsonable(getattr(r, "extra", {})),
        "app_path": getattr(r, "app_path", None),
        "feedback": feedback,
        "children": [],
    }

    if (max_depth is None) or (depth < max_depth):
        kids = children_by_parent.get(str(r.id), [])
        d["children"] = [
            run_to_dict(
                c,
                children_by_parent,
                max_depth=max_depth,
                depth=depth + 1,
                strip_input_keys=strip_input_keys,
                strip_output_keys=strip_output_keys,
                max_chars_json=max_chars_json,
            )
            for c in kids
        ]
    return d

def dict_to_markdown(d: dict[str, Any], level=1, max_chars_md: int | None = None) -> str:
    h = "#" * min(level, 6)
    parts = []
    title = f"{d.get('name') or 'run'} — {d.get('run_type') or ''}".strip()
    parts.append(f"{h} {title}  \n`{d['id']}`")
    meta = [
        f"status: **{d.get('status')}**",
        f"latency: {d.get('latency_ms')} ms" if d.get("latency_ms") else None,
        f"start: {d.get('start_time')}",
        f"end: {d.get('end_time')}",
        f"tags: {', '.join(d.get('tags', []))}" if d.get("tags") else None,
    ]
    parts.append("> " + " | ".join([m for m in meta if m]))

    def dumps(obj):
        obj = truncate(obj, max_chars_md) if max_chars_md is not None else obj
        return json.dumps(obj, indent=2, ensure_ascii=False)

    if d.get("error"):
        parts.append(f"**Error**:\n\n```\n{d['error']}\n```")

    if d.get("inputs"):
        parts.append("**Inputs**:\n\n```json\n" + dumps(d["inputs"]) + "\n```")
    if d.get("outputs"):
        parts.append("**Outputs**:\n\n```json\n" + dumps(d["outputs"]) + "\n```")

    if d.get("feedback"):
        parts.append("**Feedback**:")
        for fb in d["feedback"]:
            key = fb.get("key") or fb.get("feedback_key") or "feedback"
            score = fb.get("score")
            comment = fb.get("comment") or fb.get("correction") or ""
            parts.append(f"- {key}: {score} — {comment}")

    for c in d.get("children", []):
        parts.append(dict_to_markdown(c, level=level + 1, max_chars_md=max_chars_md))

    return "\n\n".join(parts)

def export_focus_subtrees(
    root_id: str,
    out_dir: str,
    focus_name: str | None,
    focus_tag: str | None,
    latest_only: bool,
    max_depth: int | None,
    strip_input_keys: set[str],
    strip_output_keys: set[str],
    max_chars_json: int | None,
    max_chars_md: int | None,
):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    root, runs, by_id, children = fetch_trace_index(root_id)
    matches = find_focus_runs(runs, focus_name=focus_name, focus_tag=focus_tag)
    if not matches:
        print("No focus runs found. (Try adjusting --focus-name/--focus-tag)")
        matches = [root]

    if latest_only and len(matches) > 1:
        matches = [matches[-1]]

    written = []
    for _idx, fr in enumerate(matches, 1):
        tree_dict = run_to_dict(
            fr,
            children_by_parent=children,
            max_depth=max_depth,
            depth=0,
            strip_input_keys=strip_input_keys,
            strip_output_keys=strip_output_keys,
            max_chars_json=max_chars_json,
        )

        base = f"{fr.name or 'run'}_{fr.id}"
        base = base.replace(" ", "_")
        json_path = Path(out_dir) / f"{base}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(tree_dict, f, indent=2, ensure_ascii=False)

        md = dict_to_markdown(tree_dict, max_chars_md=max_chars_md)
        md_path = Path(out_dir) / f"{base}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- project: {getattr(fr, 'project_id', '')} trace: {getattr(fr,'trace_id','')} -->\n")
            f.write(md)

        try:
            url = client.get_run_url(fr.id)
            print(f"Run URL: {url}")
        except Exception:
            pass

        written.append((md_path, json_path))

    print("Wrote:")
    for md_path, json_path in written:
        print(f"- {md_path}\n- {json_path}")

def parse_args():
    p = argparse.ArgumentParser(description="Export a specific LangSmith run (or focused subtree) to Markdown/JSON.")
    p.add_argument("run_id", help="Any run UUID within the desired trace")
    p.add_argument("out_dir", nargs="?", default="langsmith_export", help="Output directory (default: langsmith_export)")
    p.add_argument("--focus-name", default=None, help="Substring match on run.name (e.g., season_planner)")
    p.add_argument("--focus-tag",  default=None, help="Exact tag to match (e.g., agent:season_planner)")
    p.add_argument("--all-matches", action="store_true", help="Export all matching runs (default: only the latest)")
    p.add_argument("--max-depth", type=int, default=None, help="Limit subtree depth (0 = only the focus run)")
    p.add_argument("--max-chars-json", type=int, default=None, help="Truncate strings in JSON to this many chars")
    p.add_argument("--max-chars-md",   type=int, default=4000, help="Truncate strings in Markdown (default: 4000)")
    p.add_argument("--strip-keys-inputs", default="chat_history,messages,docs,state,garmin_data", help="Comma list of keys to remove from inputs")
    p.add_argument("--strip-keys-outputs", default="state,garmin_data", help="Comma list of keys to remove from outputs")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    strip_inputs = set([k for k in (args.strip_keys_inputs or "").split(",") if k])
    strip_outputs = set([k for k in (args.strip_keys_outputs or "").split(",") if k])

    export_focus_subtrees(
        root_id=args.run_id,
        out_dir=args.out_dir,
        focus_name=args.focus_name,
        focus_tag=args.focus_tag,
        latest_only=not args.all_matches,
        max_depth=args.max_depth,
        strip_input_keys=strip_inputs,
        strip_output_keys=strip_outputs,
        max_chars_json=args.max_chars_json,
        max_chars_md=args.max_chars_md,
    )