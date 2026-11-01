import json
import sys
import time

from .config import MODEL, client
from .logger import elapsed_ms, log
from .tools import TOOLS, get_calendar_day


def main():
    if len(sys.argv) < 2:
        sys.exit('Bitte eine Frage angeben: python -m agent "Deine Frage"')
    task = " ".join(sys.argv[1:])
    log("user_task", content=task, ok=True, duration_ms=0)

    messages = [{"role": "user", "content": task}]

    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS
        )
        first_ms = elapsed_ms(t0)
        msg = response.choices[0].message

        if not msg.tool_calls:
            log("final", content=msg.content, ok=True, duration_ms=first_ms)
            print(msg.content)
            return

        call = msg.tool_calls[0]
        args = json.loads(call.function.arguments)
        log("tool_call", tool=call.function.name, args=args, ok=True, duration_ms=first_ms)

        t1 = time.perf_counter()
        result = get_calendar_day(args["date"])
        log("tool_result", tool=call.function.name, args=args,
            ok="error" not in result, duration_ms=elapsed_ms(t1))

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [{
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

        t2 = time.perf_counter()
        final = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS
        )
        answer = final.choices[0].message.content
        log("final", content=answer, ok=True, duration_ms=elapsed_ms(t2))
        print(answer)

    except Exception as e:
        log("error", content=str(e), ok=False, duration_ms=0)
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
