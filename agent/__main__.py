import json
import os
import sys
import time
from datetime import date

from openai import BadRequestError

from .config import MODEL, client
from .logger import elapsed_ms, log
from .tools import TOOL_FUNCTIONS, TOOLS

MAX_STEPS = int(os.environ.get("MAX_STEPS", 10))
PARSE_RETRIES = 2  # extra tries when the model produced an unparseable tool call (see call_model)

SYSTEM_PROMPT = """You are a personal assistant for appointments, weather and train travel. Today is {today} ({weekday}).
The user lives in Ulm.
- Use get_calendar_day for appointments (one call per day), get_weather for weather and get_connections for trains.
- A task may need several tools; call all of them before you answer.
- For a trip, weather questions refer to the destination on the day of travel unless the user says otherwise.
- For any question about trains or travel, also call get_calendar_day for the day of travel and check the
  connections against the appointments:
  1. A train must arrive before the appointment at the destination starts.
  2. Once the user has left, they are no longer at the departure city: an in-person appointment there that
     starts after the departure time cannot be attended in person. Say so, even if it applies to every train.
  3. Online appointments are not a conflict, but mention them if they fall into the travel time.
  Recommend one suitable train and name the conflicts in one short sentence each.
  Always give a train's name together with its own departure and arrival time, exactly as the tool returned them.
- Never assume that data is missing: always call the tool first, also for unknown cities or days.
- Only state facts that a tool returned. Never invent appointments, weather values, trains or times.
- If a tool returns an error (e.g. no data for that city or day), say clearly that there is no data for it and still answer the rest.
- Always answer in the language the user wrote the question in (English question -> English answer). Be brief; include times of appointments and departure/arrival times of trains.
- If a question has nothing to do with appointments, weather or trains, briefly say what you can help with."""


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


def call_model(messages):
    """One model call. If the provider rejects the model's output because it generated a broken
    tool call (HTTP 400 "Parsing failed" / "tool_use_failed"), the same call is repeated up to
    PARSE_RETRIES times: the output is random, so a second try usually works. All other errors
    are raised immediately."""
    for attempt in range(PARSE_RETRIES + 1):
        try:
            return client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        except BadRequestError as e:
            text = str(e)
            broken_output = "failed_generation" in text or "tool_use_failed" in text
            if not broken_output or attempt == PARSE_RETRIES:
                raise
            print(f"(model output could not be parsed, retrying {attempt + 1}/{PARSE_RETRIES})",
                  file=sys.stderr)


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
            response = call_model(messages)
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
