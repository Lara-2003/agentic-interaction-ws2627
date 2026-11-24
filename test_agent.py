import json
import os
import subprocess
import sys
import time
from pathlib import Path


LIVE_SCENARIOS = [
    {"name": "exercise 1: one day",
     "task": "Was habe ich am 29. Oktober 2026 vor?",
     "exit": 0, "end": "final"},
    {"name": "exercise 3: two days",
     "task": "What is on 29 Oct 2026 and on 30 Oct 2026?",
     "exit": 0, "end": "final"},
    {"name": "several days in one task",
     "task": "An welchem Tag zwischen dem 2. und 4. November 2026 habe ich die wenigsten Termine?",
     "exit": 0, "end": "final"},
    {"name": "exercise 4: train + weather",
     "task": "How do I get to Munich on 29 Oct 2026, and do I need an umbrella?",
     "exit": 0, "end": "final", "tools": {"get_connections", "get_weather"}},
    {"name": "train suggestion checked against calendar",
     "task": "Welchen Zug nehme ich am 29. Oktober 2026 nach München zum Werkstattbesuch?",
     "exit": 0, "end": "final", "tools": {"get_connections"}},
    {"name": "weather only",
     "task": "Brauche ich am 29. Oktober 2026 in Ulm einen Regenschirm?",
     "exit": 0, "end": "final", "tools": {"get_weather"}},
    {"name": "city without data -> no invented values",
     "task": "What is the weather in Berlin on 29 Oct 2026?",
     "exit": 0, "end": "final", "tool_fail": True},
    {"name": "day without data -> no invented trains",
     "task": "Welche Züge fahren am 24. Dezember 2026 von Ulm nach München?",
     "exit": 0, "end": "final", "tool_fail": True},
    {"name": "no tool needed",
     "task": "Hallo, wer bist du?",
     "exit": 0, "end": "final"},
    {"name": "one day without data -> run continues",
     "task": "Was ist am 24. Dezember 2026 und am 30. Oktober 2026?",
     "exit": 0, "end": "final", "tool_fail": True},
    {"name": "date that does not exist -> run continues",
     "task": "Was habe ich am 31. Februar 2026 vor?",
     "exit": 0, "end": "final"},
    {"name": "data server unreachable -> run continues",
     "task": "Was habe ich am 29. Oktober 2026 vor?",
     "env": {"DATA_BASE_URL": "https://does-not-exist.invalid"},
     "exit": 0, "end": "final", "tool_fail": True},
    {"name": "step limit reached -> error",
     "task": "What is on 29 Oct 2026 and on 30 Oct 2026?",
     "env": {"MAX_STEPS": "1"},
     "exit": 1, "end": "error"},
    {"name": "step limit reached after several tool steps -> error",
     "task": "Check my calendar day by day starting on 26 Oct 2026: look up one day, read the result, "
             "and only then decide whether to look up the next day. Stop at the first day that has "
             "an appointment after 18:00. Which day is it?",
     "env": {"MAX_STEPS": "2"},
     "exit": 1, "end": "error"},
    {"name": "wrong API key -> error",
     "task": "Was habe ich am 29. Oktober 2026 vor?",
     "env": {"OPENAI_API_KEY": "invalid-key"},
     "exit": 1, "end": "error"},
    {"name": "model does not exist -> error",
     "task": "Was habe ich am 29. Oktober 2026 vor?",
     "env": {"MODEL": "does-not-exist"},
     "exit": 1, "end": "error"},
]
RATE_LIMIT_WAIT = 60   
MAX_RETRIES = 3      


def run_once(s, log_dir):
    """Runs the agent once for scenario s. Returns (process, log events)."""
    logs_before = set(log_dir.glob("*.jsonl"))
    proc = subprocess.run([sys.executable, "-m", "agent", s["task"]],
                          capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, **s.get("env", {})})
    new_logs = set(log_dir.glob("*.jsonl")) - logs_before
    events = []
    if new_logs:
        log_file = new_logs.pop()
        events = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
        events[0]["_file"] = log_file.name
    return proc, events


def hit_rate_limit(proc, events):
    """True if the run ended because of the rate limit (HTTP 429)."""
    text = proc.stderr + " ".join(str(e.get("content", "")) for e in events if e["event"] == "error")
    return proc.returncode != 0 and ("429" in text or "rate limit" in text.lower())


def run_live():
    sys.stdout.reconfigure(encoding="utf-8")  
    log_dir = Path(__file__).parent / "logs"
    results = []
    for s in LIVE_SCENARIOS:
        print("=" * 70 + f"\n[{s['name']}]\n> {s['task']}")
        if s.get("env"):
            print(f"  env: {s['env']}")

        for attempt in range(MAX_RETRIES + 1):
            proc, events = run_once(s, log_dir)
            if not hit_rate_limit(proc, events) or attempt == MAX_RETRIES:
                break
            print(f"(rate limit hit, waiting {RATE_LIMIT_WAIT}s and repeating this scenario)")
            time.sleep(RATE_LIMIT_WAIT)

        print(proc.stdout.strip() or proc.stderr.strip())
        if events:
            print(f"\nlog: {events[0]['_file']}")
            for e in events:
                detail = e.get("args") or e.get("content") or ""
                print(f"  step {e.get('step', '-')}: {e['event']:<12} ok={e.get('ok')}  {str(detail)[:60]}")

        problems = []
        if proc.returncode != s["exit"]:
            problems.append(f"exit code {proc.returncode}, expected {s['exit']}")
        last = events[-1]["event"] if events else None
        if last != s["end"]:
            problems.append(f"last log event {last}, expected {s['end']}")
        if s.get("tool_fail") and not any(e["event"] == "tool_result" and not e["ok"] for e in events):
            problems.append("expected a failed tool_result, found none")
        used = {e.get("tool") for e in events if e["event"] == "tool_call"}
        if s.get("tools") and not s["tools"] <= used:
            problems.append(f"expected tools {sorted(s['tools'])}, used {sorted(t for t in used if t)}")
        verdict = "PASS" if not problems else "FAIL  " + "; ".join(problems)
        print(f"\nexit code: {proc.returncode}  ->  {verdict}")
        results.append((s["name"], verdict))

    print("\n" + "=" * 70)
    for name, verdict in results:
        print(f"{verdict[:4]}  {name}  {verdict[4:].strip()}")
    passed = sum(v == "PASS" for _, v in results)
    print(f"\n{passed}/{len(results)} passed")
    return passed == len(results)


if __name__ == "__main__":
    sys.exit(0 if run_live() else 1)
