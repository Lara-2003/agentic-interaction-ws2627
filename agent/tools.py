import json
import re
import urllib.error
import urllib.request

from .config import DATA_BASE_URL

CITY_ALIASES = {
    "münchen": "muenchen",
    "munchen": "muenchen",
    "munich": "muenchen",
}


def _city_code(city):
    """Normalises a city name to the code used in the URLs (e.g. "München" -> "muenchen").
    Unknown cities are passed through unchanged; the server then answers 404 = no data.
    Anything that is not a plain word (e.g. "../calendar") is rejected, so the model cannot
    reach other endpoints through the city parameter. run_tool() turns the error into a result."""
    code = city.strip().lower()
    code = CITY_ALIASES.get(code, code)
    if not re.fullmatch(r"[a-z]+", code):
        raise ValueError(f"invalid city name: {city!r}")
    return code


def _check_date(date):
    """Only accepts YYYY-MM-DD, so the model cannot reach other endpoints through the date."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date.strip()):
        raise ValueError(f"invalid date {date!r}, expected YYYY-MM-DD")
    return date.strip()


def _fetch(path):
    """GETs DATA_BASE_URL/path and returns the JSON. Errors are returned, not raised,
    so the model can see them and the run continues."""
    url = f"{DATA_BASE_URL}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": "no data available for this request (HTTP 404)"}
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": f"could not load data: {e}"}


def get_calendar_day(date):
    """Fetches the appointments of one day."""
    return _fetch(f"calendar/{_check_date(date)}.json")


def get_weather(city, date):
    """Fetches the weather forecast for one city and one day."""
    return _fetch(f"weather/{_city_code(city)}/{_check_date(date)}.json")


HOME_CITY = "ulm"  # the user lives in Ulm (scenario of exercise 2)


def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _place_of(location):
    """Where an appointment takes place: "online", a city code, or HOME_CITY if the location
    names no known city (e.g. a room like "O27/3302")."""
    loc = (location or "").lower().replace("ü", "ue")
    if "online" in loc:
        return "online"
    for code in ("muenchen", "ulm"):
        if code in loc:
            return code
    return HOME_CITY


def _check_against_calendar(connection, events, src, dst):
    """Compares one train with the appointments of the day. Done in code, not by the model,
    because the model compared times unreliably (e.g. called a 9:00 meeting "before" a 7:12 train)."""
    dep, arr = _minutes(connection["departure"]), _minutes(connection["arrival"])
    problems, notes = [], []
    for ev in events:
        if ev.get("all_day") or not ev.get("start"):
            continue
        start, end = _minutes(ev["start"]), _minutes(ev["end"])
        what = f"{ev['title']} {ev['start']}-{ev['end']} ({ev.get('location') or 'no location'})"
        place = _place_of(ev.get("location"))
        if end <= dep:
            continue  # over before the train leaves
        if place == "online":
            if start < arr:
                notes.append(f"online appointment during the ride: {what}")
        elif place == dst:
            if start < arr:
                problems.append(f"arrives too late for {what}")
            else:
                notes.append(f"arrives in time for {what}")
        else:
            later = " (unless you travel back in time)" if start >= arr else ""
            problems.append(f"cannot attend in person, you will have left {src}: {what}{later}")
    return {"fits_calendar": not problems, "conflicts": problems, "notes": notes}


def get_connections(from_city, to_city, date):
    """Fetches the train connections from one city to another on one day and checks every
    connection against the calendar of that day (field "calendar_check")."""
    src, dst, day = _city_code(from_city), _city_code(to_city), _check_date(date)
    result = _fetch(f"transit/{src}/{dst}/{day}.json")
    if "error" in result:
        return result
    calendar = _fetch(f"calendar/{day}.json")
    if "error" in calendar:
        result["calendar_check"] = f"calendar not available: {calendar['error']}"
        return result
    for connection in result.get("connections", []):
        connection["calendar_check"] = _check_against_calendar(
            connection, calendar.get("events", []), src, dst)
    return result


TOOL_FUNCTIONS = {
    "get_calendar_day": get_calendar_day,
    "get_weather": get_weather,
    "get_connections": get_connections,
}


_DATE_PARAM = {
    "type": "string",
    "description": "The day in ISO format YYYY-MM-DD, e.g. 2026-10-29",
}
_CITY_HINT = ("Lowercase city code, e.g. 'ulm' or 'muenchen' (Munich). For any other city, "
              "call the tool anyway; it returns an error if there is no data.")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_calendar_day",
            "description": "Returns all appointments of the calendar for one specific day. "
                           "Use it whenever the user asks about appointments or events on a date.",
            "parameters": {
                "type": "object",
                "properties": {"date": _DATE_PARAM},
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Returns the weather forecast for one city on one day: temperature (°C), "
                           "condition, rain probability (0-1) and wind (km/h). Use it for questions "
                           "about weather, rain or whether an umbrella is needed. "
                           "Returns an error if there is no forecast for that city or day.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City code. " + _CITY_HINT},
                    "date": _DATE_PARAM,
                },
                "required": ["city", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_connections",
            "description": "Returns the train connections from one city to another on one day: "
                           "departure, arrival, number of changes, train name and price (EUR). "
                           "Each connection also has a 'calendar_check' that was computed against "
                           "the user's appointments of that day: fits_calendar, conflicts, notes. "
                           "Use it for questions about how to travel, trains or departure times. "
                           "Returns an error if there are no connections for that route or day.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_city": {"type": "string", "description": "Departure city code. " + _CITY_HINT},
                    "to_city": {"type": "string", "description": "Destination city code. " + _CITY_HINT},
                    "date": _DATE_PARAM,
                },
                "required": ["from_city", "to_city", "date"],
            },
        },
    },
]
