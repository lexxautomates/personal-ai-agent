"""Parser tests for web_search (DuckDuckGo) and weather (Open-Meteo)
using fixture JSON — no live network."""

from agent import tool_impls


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


DDG_FIXTURE = {
    "AbstractText": "Ada Lovelace was an English mathematician.",
    "RelatedTopics": [
        {"Text": "She worked on Charles Babbage's Analytical Engine.",
         "FirstURL": "https://example.com/1"},
        {"Topics": [{"Text": "Nested topic about the Difference Engine.",
                     "FirstURL": "https://example.com/2"}]},
    ],
}

GEO_FIXTURE = {"results": [{"name": "Atlanta", "country": "United States",
                            "latitude": 33.749, "longitude": -84.388}]}
FORECAST_FIXTURE = {"current": {"temperature_2m": 72.4,
                                "relative_humidity_2m": 55,
                                "apparent_temperature": 74.1,
                                "weather_code": 2,
                                "wind_speed_10m": 8.6}}


def test_ddg_parser_prefers_abstract():
    out = tool_impls._parse_ddg(DDG_FIXTURE)
    assert "Ada Lovelace" in out
    assert "Analytical Engine" in out
    assert "Difference Engine" in out  # nested Topics handled


def test_ddg_parser_empty():
    out = tool_impls._parse_ddg({"AbstractText": "", "RelatedTopics": []})
    assert "came up empty" in out


def test_web_search_wires_params(monkeypatch):
    calls = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.update(url=url, params=params)
        return _Resp(DDG_FIXTURE)

    monkeypatch.setattr(tool_impls.requests, "get", fake_get)
    out = tool_impls.web_search("ada lovelace")
    assert calls["url"] == "https://api.duckduckgo.com/"
    assert calls["params"]["format"] == "json"
    assert "Ada Lovelace" in out


def test_weather_end_to_end(monkeypatch):
    seen = []

    def fake_get(url, params=None, timeout=None):
        seen.append(url)
        if "geocoding" in url:
            return _Resp(GEO_FIXTURE)
        return _Resp(FORECAST_FIXTURE)

    monkeypatch.setattr(tool_impls.requests, "get", fake_get)
    out = tool_impls.weather("Atlanta")
    assert "geocoding-api.open-meteo.com" in seen[0]
    assert "api.open-meteo.com" in seen[1]
    assert "Atlanta" in out
    assert "partly cloudy" in out          # WMO code 2
    assert "72 degrees" in out            # rounded
    assert "ma'am" in out


def test_weather_unknown_place(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _Resp({"results": []})

    monkeypatch.setattr(tool_impls.requests, "get", fake_get)
    assert "couldn't find" in tool_impls.weather("Nowhereville")
