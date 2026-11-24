# agentic-interaction-ws2627

Agent for the course *Agentic Human-AI Interaction* (WS 26/27). It answers questions about a mock
calendar, the weather and train connections. All data comes from the mock data endpoints under
`DATA_BASE_URL` (see the README of the data repository).

## Tools

| Tool | Arguments | Endpoint under `DATA_BASE_URL` |
|------|-----------|--------------------------------|
| `get_calendar_day` | `date` | `calendar/{date}.json` |
| `get_weather` | `city`, `date` | `weather/{city}/{date}.json` |
| `get_connections` | `from_city`, `to_city`, `date` | `transit/{from}/{to}/{date}.json` |

Dates as `YYYY-MM-DD`, cities as codes (`ulm`, `muenchen`; "München"/"Munich" are mapped to
`muenchen`). HTTP 404 means *no data*: the tool returns an error to the model, which then says
that there is no data instead of inventing values. Arguments that are not a valid date or a plain
city name are rejected before any request is made.

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
python -m agent "How do I get to Munich on 29 Oct 2026, and do I need an umbrella?"
```

A system prompt tells the model what it can help with, gives it today's date and asks it to look
up everything with the tools (several tools per task if needed) instead of inventing values.
`get_connections` also reads the calendar of that day and adds a `calendar_check` to every
connection (`fits_calendar`, `conflicts`, `notes`): does the train arrive before the appointment at
the destination, which in-person appointments are missed after leaving, which online appointments
fall into the ride. This is computed in code because the model compared times unreliably.
Appointments whose location names no known city (e.g. a room like `O27/3302`) count as being in Ulm.

The agent works in a loop: each step is one model call; requested tool calls are executed and
their results sent back, until the model answers without a tool call. A failing tool call does
not abort the run — the error is passed to the model as the tool result.

- Answer found: prints the answer, logs `final`, exit code 0.
- Error (model call failed, or step limit of 10 model calls reached): logs `error`, exit code 1.
- If the provider rejects a model output as an unparseable tool call (HTTP 400 "Parsing failed"),
  the same model call is repeated up to 2 times before the run ends as an error.

The mock calendar covers 26 Oct to 8 Nov 2026. Weather and connections exist only for single days.

## Tests

```bash
python test_agent.py
```

Runs `python -m agent` with the real client for every scenario in `LIVE_SCENARIOS` (normal
questions, combined train + weather tasks and edge cases such as missing data or unknown cities, unreachable data server, step limit, wrong API
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
  tools.py      calendar, weather and connection tools and their schemas for the model
```
