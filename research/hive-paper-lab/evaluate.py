"""Bounded local LLM inference on paired, oracle-checked Hive tasks."""
import argparse
import collections
import copy
import datetime
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

from screen import ROOT, RESERVES, digest, encode_compact, queen_counts, rotate, stable, terminal_from_state

VARIANTS = ["verbose", "rotate60", "piece_order", "compact"]
LABELS = list("ABCDEFG")


def api(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def choose_cases(records, count):
    # Deterministic development selection, balanced by local geometry where possible.
    buckets = collections.defaultdict(list)
    for record in records:
        n = record["queen_neighbors"]["white"]
        if n is not None and record["state"]["ply"] >= 8:
            buckets[n].append(record)
    selected, used = [], set()
    while len(selected) < count:
        progress = False
        for n in sorted(buckets):
            while buckets[n]:
                record = buckets[n].pop(0)
                group = (record["seed"], record["episode"])
                if record["state_sha256"] in used or any((r["seed"], r["episode"]) == group for r in selected):
                    continue
                selected.append(record)
                used.add(record["state_sha256"])
                progress = True
                break
            if len(selected) == count:
                break
        if not progress:
            break
    return selected


def rotate_move(move):
    move = copy.deepcopy(move)
    for field in ["from", "to"]:
        if move[field] is not None:
            x, y = move[field]
            move[field] = [y, y - x]
    return move


def prompt(record, variant, task_type):
    state = copy.deepcopy(record["state"])
    if variant == "rotate60":
        state = rotate(state)
    if variant == "piece_order":
        state["pieces"].reverse()
    if queen_counts(state) != record["queen_neighbors"] or terminal_from_state(state) != record["native_terminal"]:
        raise RuntimeError("Prompt transformation changed the oracle")
    if variant == "compact":
        representation = encode_compact(state)
        legend = ("Compact state: each column is [x,y,[piece IDs ordered bottom-to-top]]. "
                  "An ID starts with w=white or b=black, then Q=queen,A=ant,G=grasshopper,B=beetle,S=spider; "
                  "the final integer only distinguishes pieces. Reserve arrays are [ant,grasshopper,beetle,spider,queen], white then black.")
    else:
        representation = state
        legend = "Each piece has an ID, color, kind, x,y coordinates and z height (0 is bottom)."
    common = ("Solve this exact Hive board task. Coordinates use a skew hex grid. "
              "The six neighbors of (x,y) are (x-1,y),(x+1,y),(x,y-1),(x,y+1),(x-1,y-1),(x+1,y+1). "
              "A stack occupies one cell. " + legend + "\nState:\n" + json.dumps(representation, separators=(",", ":")) + "\n")
    if task_type == "neighbors":
        common += "How many of the six cells neighboring the WHITE queen are occupied? Count cells, not pieces in stacks.\n"
        choices = {LABELS[i]: i for i in range(7)}
        expected = LABELS[record["queen_neighbors"]["white"]]
    else:
        task = record["winning_task"]
        choices = {LABELS[i]: rotate_move(option["move"]) if variant == "rotate60" else option["move"]
                   for i, option in enumerate(task["options"])}
        expected = LABELS[task["answer_index"]]
        common += ("The four candidates below are all LEGAL for the player to move. Which one wins immediately? "
                   "A queen loses when at least FOUR neighboring cells are occupied, regardless of piece color. "
                   "After a move the piece leaves its origin (revealing any lower piece) and occupies its destination. "
                   "A placed piece comes from reserve. Choose the unique immediately winning candidate.\n")
    common += "Options:\n" + json.dumps(choices, separators=(",", ":")) + '\nReturn only JSON {"answer":"OPTION_LETTER"}. /no_think'
    return common, expected, list(choices)


def summary(rows):
    report = {}
    for task in sorted({r["task"] for r in rows}):
        task_rows = [r for r in rows if r["task"] == task]
        variants = {}
        for variant in VARIANTS:
            group = [r for r in task_rows if r["variant"] == variant]
            if not group:
                continue
            variants[variant] = {"n": len(group), "correct": sum(r["correct"] for r in group),
                                 "accuracy": sum(r["correct"] for r in group) / len(group),
                                 "mean_input_tokens": sum(r["input_tokens"] for r in group) / len(group),
                                 "mean_seconds": sum(r["seconds"] for r in group) / len(group)}
        paired = {}
        by_case = collections.defaultdict(dict)
        for row in task_rows:
            by_case[row["case_id"]][row["variant"]] = row
        for variant in VARIANTS[1:]:
            pairs = [(group["verbose"], group[variant]) for group in by_case.values() if "verbose" in group and variant in group]
            if pairs:
                paired[variant] = {"pairs": len(pairs), "answer_flips": sum(a["answer"] != b["answer"] for a, b in pairs),
                                   "fixed_errors": sum(not a["correct"] and b["correct"] for a, b in pairs),
                                   "introduced_errors": sum(a["correct"] and not b["correct"] for a, b in pairs)}
        report[task] = {"variants": variants, "paired_vs_verbose": paired}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/screen-2026-10-22/states.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "results/llm-pilot-2026-10-22")
    parser.add_argument("--base-url", default="http://127.0.0.1:11435")
    parser.add_argument("--model", default="qwen3:0.6b")
    parser.add_argument("--cases", type=int, default=8)
    parser.add_argument("--tasks", nargs="+", choices=["neighbors", "tactics"], default=["neighbors", "tactics"])
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = [json.loads(line) for line in args.input.read_text().splitlines()]
    tags = api(args.base_url, "/api/tags")
    model = next((m for m in tags["models"] if m["name"] == args.model), None)
    if not model:
        raise RuntimeError("Requested local model has not been downloaded")
    manifest = {"started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "model": model,
                "dataset_sha256": __import__("hashlib").sha256(args.input.read_bytes()).hexdigest(),
                "cases_per_task": args.cases, "variants": VARIANTS, "tasks": args.tasks,
                "decoding": {"temperature": 0, "seed": 20261022, "num_predict": 32, "num_ctx": 4096, "think": False},
                "limits": "Development pilot on one small model; no held-out confirmation, no global LLM claim"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    response_path = output / "responses.jsonl"
    if response_path.exists():
        rows = [json.loads(line) for line in response_path.read_text().splitlines()]
    completed = {(r["task"], r["case_id"], r["variant"]) for r in rows}
    jobs = []
    for task in args.tasks:
        pool = records if task == "neighbors" else [r for r in records if "winning_task" in r]
        cases = choose_cases(pool, args.cases)
        for index, record in enumerate(cases):
            variants = list(VARIANTS)
            random.Random(20261022 + index).shuffle(variants)
            for variant in variants:
                jobs.append((task, record, variant))
    for task, record, variant in jobs:
        case_id = record["state_sha256"]
        if (task, case_id, variant) in completed:
            continue
        content, expected, choices = prompt(record, variant, task)
        payload = {"model": args.model, "messages": [{"role": "user", "content": content}], "stream": False,
                   "think": False, "format": {"type": "object", "properties": {"answer": {"type": "string", "enum": choices}},
                                               "required": ["answer"], "additionalProperties": False},
                   "options": {"temperature": 0, "seed": 20261022, "num_predict": 32, "num_ctx": 4096}}
        start = time.perf_counter()
        response = api(args.base_url, "/api/chat", payload)
        text = response["message"]["content"]
        try:
            answer = json.loads(text).get("answer")
        except (ValueError, AttributeError):
            answer = None
        row = {"task": task, "case_id": case_id, "seed": record["seed"], "episode": record["episode"], "variant": variant,
               "prompt": content, "expected": expected, "answer": answer, "correct": answer == expected,
               "seconds": time.perf_counter() - start, "input_tokens": response.get("prompt_eval_count", 0), "response": response}
        with response_path.open("a") as stream:
            stream.write(stable(row) + "\n")
        rows.append(row)
        (output / "summary.json").write_text(json.dumps(summary(rows), indent=2) + "\n")
        print(stable({"completed": len(rows), "planned": len(jobs), "task": task, "variant": variant,
                      "correct": row["correct"], "seconds": row["seconds"]}), flush=True)
    manifest["status"] = "completed"
    manifest["completed_requests"] = len(rows)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
