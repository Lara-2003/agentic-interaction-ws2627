# agentic-interaction-ws2627

Calendar agent for the course *Agentic Human-AI Interaction* (WS 26/27). It answers questions
about a mock calendar. To do so, the model calls the tool `get_calendar_day`, which reads the
appointments of one day from the calendar endpoint.

## Setup

Requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Create a file named `.env` in the repository root with these variables. Environment variables
override `.env`. Never commit this file, as it contains your API key.

```
OPENAI_BASE_URL=https://api.groq.com/openai/v1
MODEL=openai/gpt-oss-20b
OPENAI_API_KEY=your-groq-key
DATA_BASE_URL=https://jhbelz.github.io/agentic-interaction-data/v1
```

## Run

From the repository root:

```bash
python -m agent "Was habe ich am 29. Oktober 2026 vor?"
```

A system prompt tells the model that it is a calendar assistant, gives it today's date and asks it
to look up every needed day with the tool instead of inventing appointments.

The agent works in a loop: each step is one model call; requested tool calls are executed and
their results sent back, until the model answers without a tool call. A failing tool call does
not abort the run — the error is passed to the model as the tool result.

- Answer found: prints the answer, logs `final`, exit code 0.
- Error (model call failed, or step limit of 10 model calls reached): logs `error`, exit code 1.

The mock calendar covers 26 Oct to 8 Nov 2026.

## Tests

```bash
python test_agent.py
```

Runs `python -m agent` with the real client for every scenario in `LIVE_SCENARIOS` (normal
questions and edge cases such as missing data, unreachable data server, step limit, wrong API
key) and checks exit code and log. Uses API tokens; if a run hits the rate limit, the script waits 60 s and repeats that scenario.

## Run log

Every run writes its own file `logs/<timestamp>_<run_id>.jsonl` with one JSON object per event.

| Field               | Content                                                |
|---------------------|--------------------------------------------------------|
| `ts`                | Time stamp, ISO 8601                                   |
| `run_id`            | One ID per run                                         |
| `event`             | `user_task`, `tool_call`, `tool_result`, `final`, `error` |
| `tool`, `args`      | Tool name and arguments                                |
| `ok`                | Whether the step succeeded                             |
| `model`             | Model name as sent to the endpoint                     |
| `duration_ms`       | Duration of the step                                   |
| `step`              | Number of the loop step (model call) the event belongs to |

## Structure

```
agent/
  __init__.py   marks the folder as a Python package
  __main__.py   entry point and agent flow
  config.py     reads the settings and creates the API client
  logger.py     writes the run log
  tools.py      calendar tool and its schema for the model
```
