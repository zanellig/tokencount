#!/usr/bin/env python3
"""Count the tokens in a file using Anthropic's or OpenAI's token-counting API.

Both providers expose plain JSON endpoints for counting tokens and listing
models, so this needs no SDKs.

    tokencount.py file.py                # Anthropic, or OpenAI if it is unavailable
    tokencount.py --oai -m gpt-5.6 file.py
    tokencount.py --ant --oai -          # read stdin, compare both
    tokencount.py --ant --list-models

Keys come from ANTHROPIC_API_KEY / OPENAI_API_KEY. Counting and listing models
are both free on both providers.

SPDX-License-Identifier: MIT
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


class ApiError(Exception):
    """A request to a provider failed."""


def _ant_models(payload):
    # Newest first, as returned. A limit of 0 means the API did not report one.
    return [
        {"id": m["id"], "limit": m.get("max_input_tokens") or None, "note": m.get("display_name", "")}
        for m in payload.get("data", [])
    ]


def _oai_models(payload):
    # Unordered and includes non-chat models; sort so the output is stable.
    return sorted(
        ({"id": m["id"], "limit": None, "note": m.get("owned_by", "")} for m in payload.get("data", [])),
        key=lambda m: m["id"],
    )


PROVIDERS = {
    "ant": {
        "count_url": "https://api.anthropic.com/v1/messages/count_tokens",
        # ponytail: single page; Anthropic has far fewer than 1000 models.
        "models_url": "https://api.anthropic.com/v1/models?limit=1000",
        "env": "ANTHROPIC_API_KEY",
        "model": "claude-opus-5",
        "auth": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"},
        "body": lambda model, text: {
            "model": model,
            "messages": [{"role": "user", "content": text}],
        },
        "models": _ant_models,
        "note_col": "NAME",
    },
    "oai": {
        "count_url": "https://api.openai.com/v1/responses/input_tokens",
        "models_url": "https://api.openai.com/v1/models",
        "env": "OPENAI_API_KEY",
        "model": "gpt-5.6",
        "auth": lambda key: {"authorization": f"Bearer {key}"},
        "body": lambda model, text: {"model": model, "input": text},
        "models": _oai_models,
        "note_col": "OWNER",
    },
}


def build_request(url, headers, body=None):
    """Build a GET (no body) or POST (body) request. Pure: no network, no env."""
    return urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
        method="GET" if body is None else "POST",
    )


def count_request(name, text, model, key):
    p = PROVIDERS[name]
    return build_request(p["count_url"], _headers(name, key), p["body"](model, text))


def models_request(name, key):
    return build_request(PROVIDERS[name]["models_url"], _headers(name, key))


def _headers(name, key):
    return {"content-type": "application/json", **PROVIDERS[name]["auth"](key)}


def api_key(name):
    key = os.environ.get(PROVIDERS[name]["env"])
    if not key:
        raise ApiError(f"{name}: {PROVIDERS[name]['env']} is not set")
    return key


def send(name, req):
    """Send a request and return the decoded JSON body."""
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ApiError(f"{name}: HTTP {e.code} {e.read().decode(errors='replace').strip()}")
    except urllib.error.URLError as e:
        raise ApiError(f"{name}: {e.reason}")
    except json.JSONDecodeError:
        raise ApiError(f"{name}: unreadable response")


def count(name, text, model):
    """Return the token count for `text` under `model`'s tokenizer."""
    if not text:
        return 0  # both APIs reject empty input; an empty file is 0 tokens
    payload = send(name, count_request(name, text, model, api_key(name)))
    tokens = payload.get("input_tokens")
    if not isinstance(tokens, int):
        raise ApiError(f"{name}: response had no input_tokens")
    return tokens


def list_models(name):
    """Return the provider's models as {id, limit, note} dicts."""
    return PROVIDERS[name]["models"](send(name, models_request(name, api_key(name))))


def model_limit(name, model):
    """Best-effort input-token limit for `model`, or None if unavailable."""
    try:
        for m in list_models(name):
            if m["id"] == model:
                return m["limit"]
    except ApiError:
        return None  # the count is the job; the limit is a nicety
    return None


def read_source(path):
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"{path}: {e.strerror}")
    except UnicodeDecodeError:
        sys.exit(f"{path}: not UTF-8 text")


def render_table(headers, rows, align=""):
    """Box-draw a table, each column sized to its widest cell.

    `align` is one character per column, "<" or ">"; missing entries are "<".
    """
    widths = [max(len(c) for c in col) for col in zip(headers, *rows)]
    align = [a for a in align.ljust(len(widths), "<")]
    rule = lambda l, m, r: l + m.join("─" * (w + 2) for w in widths) + r
    row = lambda cells, al: "│ " + " │ ".join(
        c.rjust(w) if a == ">" else c.ljust(w) for c, w, a in zip(cells, widths, al)
    ) + " │"
    yield rule("┌", "┬", "┐")
    yield row(headers, "<" * len(widths))  # headers read better left-aligned
    yield rule("├", "┼", "┤")
    for cells in rows:
        yield row(cells, align)
    yield rule("└", "┴", "┘")


def format_models(name, models):
    """Render one provider's model list as a titled table."""
    rows = [(m["id"], f"{m['limit']:,}" if m["limit"] else "-", m["note"]) for m in models]
    yield f"{name}: {len(models)} model{'s' * (len(models) != 1)}"
    yield from render_table(("MODEL", "CONTEXT", PROVIDERS[name]["note_col"]), rows, "<>")


def fit_note(tokens, limit):
    if not limit:
        return ""
    if tokens > limit:
        return f"  (EXCEEDS {limit} limit)"
    return f"  ({100 * tokens / limit:.1f}% of {limit} limit)"


def self_test():
    req = count_request("ant", "hi", "claude-opus-5", "sk-a")
    assert req.full_url == "https://api.anthropic.com/v1/messages/count_tokens"
    assert req.get_method() == "POST"
    assert req.get_header("X-api-key") == "sk-a"
    assert req.get_header("Anthropic-version") == "2023-06-01"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {
        "model": "claude-opus-5",
        "messages": [{"role": "user", "content": "hi"}],
    }

    req = count_request("oai", "hi", "gpt-5.6", "sk-o")
    assert req.full_url == "https://api.openai.com/v1/responses/input_tokens"
    assert req.get_header("Authorization") == "Bearer sk-o"
    assert json.loads(req.data) == {"model": "gpt-5.6", "input": "hi"}

    # model override reaches the payload; unicode survives the round trip
    assert json.loads(count_request("oai", "áé", "gpt-4o", "k").data)["model"] == "gpt-4o"
    assert json.loads(count_request("oai", "áé", "gpt-4o", "k").data)["input"] == "áé"

    # listing models is a GET with no body, same auth
    req = models_request("ant", "sk-a")
    assert req.full_url == "https://api.anthropic.com/v1/models?limit=1000"
    assert req.get_method() == "GET"
    assert req.data is None
    assert req.get_header("X-api-key") == "sk-a"
    assert models_request("oai", "sk-o").get_header("Authorization") == "Bearer sk-o"

    # Anthropic parsing keeps API order and treats a 0 limit as unknown
    parsed = _ant_models(
        {
            "data": [
                {"id": "b", "max_input_tokens": 200000, "display_name": "B"},
                {"id": "a", "max_input_tokens": 0, "display_name": "A"},
            ]
        }
    )
    assert [m["id"] for m in parsed] == ["b", "a"]
    assert parsed[0]["limit"] == 200000
    assert parsed[1]["limit"] is None

    # OpenAI parsing sorts by id and reports no limit
    parsed = _oai_models({"data": [{"id": "z", "owned_by": "openai"}, {"id": "a", "owned_by": "sys"}]})
    assert [m["id"] for m in parsed] == ["a", "z"]
    assert parsed[0]["limit"] is None and parsed[0]["note"] == "sys"

    # missing keys are reported per provider, not crashed on
    assert _ant_models({}) == [] and _oai_models({}) == []

    # columns are sized to the widest cell, header included, and can right-align
    assert list(render_table(("A", "BB"), [("xxx", "y")], "<>")) == [
        "┌─────┬────┐",
        "│ A   │ BB │",
        "├─────┼────┤",
        "│ xxx │  y │",
        "└─────┴────┘",
    ]
    # an empty table still sizes to its headers rather than crashing
    assert list(render_table(("A", "BB"), []))[1] == "│ A │ BB │"

    # listing is titled per provider, with the note column named per provider
    lines = list(
        format_models(
            "ant",
            [{"id": "claude-opus-5", "limit": 1000000, "note": "Claude Opus 5"}, {"id": "x", "limit": None, "note": ""}],
        )
    )
    assert lines[0] == "ant: 2 models"
    assert lines[2] == "│ MODEL         │ CONTEXT   │ NAME          │"
    assert lines[4] == "│ claude-opus-5 │ 1,000,000 │ Claude Opus 5 │"
    assert lines[5] == "│ x             │         - │               │"
    assert "OWNER" in list(format_models("oai", []))[2]

    assert fit_note(1000, 200000) == "  (0.5% of 200000 limit)"
    assert fit_note(300000, 200000) == "  (EXCEEDS 200000 limit)"
    assert fit_note(1000, None) == ""

    # empty input short-circuits before any request
    assert count("ant", "", None) == 0
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", nargs="?", help="file to count, or - for stdin")
    ap.add_argument("--ant", action="store_true", help="use Anthropic's tokenizer")
    ap.add_argument("--oai", action="store_true", help="use OpenAI's tokenizer")
    ap.add_argument("-m", "--model", help="override the model whose tokenizer is used")
    ap.add_argument("--list-models", action="store_true", help="list available models and exit")
    ap.add_argument("--self-test", action="store_true", help="check request building, no network")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    # No flags: Anthropic, falling back to OpenAI if it is unavailable.
    fallback = not (args.ant or args.oai)
    selected = ["ant", "oai"] if fallback else [n for n in ("ant", "oai") if getattr(args, n)]

    if not (args.list_models or args.file):
        ap.error("a file (or -) is required")
    text = None if args.list_models else read_source(args.file)

    # Explicitly selected providers are independent: one failing must not hide
    # the other's result, which is the point of passing --ant and --oai together.
    errors = []
    for name in selected:
        try:
            if args.list_models:
                print("\n".join(format_models(name, list_models(name))))
            else:
                model = args.model or PROVIDERS[name]["model"]
                tokens = count(name, text, model)
                print(f"{name} ({model}): {tokens}{fit_note(tokens, model_limit(name, model))}")
        except ApiError as e:
            errors.append(e)
            continue
        if fallback:
            return  # first provider that works wins
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
