import json
import urllib.error
import urllib.request

from .config import DATA_BASE_URL


def get_calendar_day(date):
    url = f"{DATA_BASE_URL}/calendar/{date}.json"
    try:
        with urllib.request.urlopen(url) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": "no data for this day"}
        return {"error": f"HTTP {e.code}"}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_calendar_day",
            "description": "Returns all appointments of the calendar for one specific day. "
                           "Use it whenever the user asks about appointments or events on a date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The day in ISO format YYYY-MM-DD, e.g. 2026-10-29",
                    }
                },
                "required": ["date"],
            },
        },
    }
]
