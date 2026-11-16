import json
import os
import sys
import time
from datetime import date

from .config import MODEL, client
from .logger import elapsed_ms, log
from .tools import TOOL_FUNCTIONS, TOOLS

MAX_STEPS = int(os.environ.get("MAX_STEPS", 10))

SYSTEM_PROMPT = """You are a calendar assistant. Today is {today} ({weekday}).
Answer questions about the user's appointments.
- Use get_calendar_day for every day you need, one call per day. Never invent appointments.
- If the tool returns an error for a day (e.g. no data), say so in your answer and still answer for the other days.
- Answer in the language of the question. Be brief and always include the times of appointments.
- If a question has nothing to do with the calendar, briefly say that you are a calendar assistant."""


def run_tool(name, raw_args):
    """Executes one tool call. Never raises: errors are returned as {"error": ...}
    so that a single failed step does not abort the whole run."""
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return {}, {"error": "arguments are not valid JSON"}

    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return args, {"error": f"unknown tool: {name}"}

    try:
        return args, func(**args)
    except Exception as e:
        return args, {"error": str(e)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit('Bitte eine Frage angeben: python -m agent "Deine Frage"')
    task = " ".join(sys.argv[1:])
    log("user_task", content=task, ok=True, duration_ms=0)

    today = date.today()
    system = SYSTEM_PROMPT.format(today=today.isoformat(), weekday=today.strftime("%A"))
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task},
    ]

    for step in range(1, MAX_STEPS + 1):
        try:
            t0 = time.perf_counter()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS
            )
        except Exception as e:
            log("error", content=f"model call failed: {e}", step=step, ok=False, duration_ms=elapsed_ms(t0))
            print(f"Fehler: {e}", file=sys.stderr)
            sys.exit(1)
        model_ms = elapsed_ms(t0)
        msg = response.choices[0].message

        if not msg.tool_calls:
            log("final", content=msg.content, step=step, ok=True, duration_ms=model_ms)
            print(msg.content)
            sys.exit(0)


        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [{
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            } for call in msg.tool_calls],
        })

        for call in msg.tool_calls:
            name = call.function.name
            t1 = time.perf_counter()
            args, result = run_tool(name, call.function.arguments)
            log("tool_call", tool=name, args=args, step=step, ok=True, duration_ms=model_ms)
            log("tool_result", tool=name, args=args, step=step,
                ok="error" not in result, duration_ms=elapsed_ms(t1))
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    log("error", content=f"step limit reached ({MAX_STEPS} steps)", step=MAX_STEPS, ok=False, duration_ms=0)
    print(f"Fehler: Schrittlimit von {MAX_STEPS} erreicht, keine Antwort.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
