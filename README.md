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

The agent prints the answer and exits with code 0. The mock calendar covers 26 Oct to 8 Nov 2026.

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

## Structure

```
agent/
  __init__.py   marks the folder as a Python package
  __main__.py   entry point and agent flow
  config.py     reads the settings and creates the API client
  logger.py     writes the run log
  tools.py      calendar tool and its schema for the model
```
