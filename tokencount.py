#!/usr/bin/env python3
"""Count the tokens in a file using Anthropic's or OpenAI's token-counting API.

Both providers expose a plain JSON endpoint that returns `input_tokens`, so this
needs no SDKs.

    tokencount.py --ant file.py
    tokencount.py --oai -m gpt-5.6 file.py
    tokencount.py --ant --oai -          # read stdin, compare both

Keys come from ANTHROPIC_API_KEY / OPENAI_API_KEY. Counting is free on both.

SPDX-License-Identifier: MIT
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

PROVIDERS = {
    "ant": {
        "url": "https://api.anthropic.com/v1/messages/count_tokens",
        "env": "ANTHROPIC_API_KEY",
        "model": "claude-opus-5",
        "auth": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01"},
        "body": lambda model, text: {
            "model": model,
            "messages": [{"role": "user", "content": text}],
        },
    },
    "oai": {
        "url": "https://api.openai.com/v1/responses/input_tokens",
        "env": "OPENAI_API_KEY",
        "model": "gpt-5.6",
        "auth": lambda key: {"authorization": f"Bearer {key}"},
        "body": lambda model, text: {"model": model, "input": text},
    },
}


def build_request(name, text, model, key):
    """Build the POST request for a provider. Pure: no network, no env."""
    p = PROVIDERS[name]
    return urllib.request.Request(
        p["url"],
        data=json.dumps(p["body"](model, text)).encode(),
        headers={"content-type": "application/json", **p["auth"](key)},
        method="POST",
    )


def count(name, text, model):
    """Return the token count for `text`, or exit with a readable error."""
    if not text:
        return 0  # both APIs reject empty input; an empty file is 0 tokens
    key = os.environ.get(PROVIDERS[name]["env"])
    if not key:
        sys.exit(f"{name}: {PROVIDERS[name]['env']} is not set")
    try:
        with urllib.request.urlopen(build_request(name, text, model, key), timeout=60) as resp:
            tokens = json.load(resp).get("input_tokens")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace").strip()
        sys.exit(f"{name}: HTTP {e.code} {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"{name}: {e.reason}")
    except json.JSONDecodeError:
        sys.exit(f"{name}: unreadable response")
    if not isinstance(tokens, int):
        sys.exit(f"{name}: response had no input_tokens")
    return tokens


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


def self_test():
    req = build_request("ant", "hi", "claude-opus-5", "sk-a")
    assert req.full_url == "https://api.anthropic.com/v1/messages/count_tokens"
    assert req.get_method() == "POST"
    assert req.get_header("X-api-key") == "sk-a"
    assert req.get_header("Anthropic-version") == "2023-06-01"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {
        "model": "claude-opus-5",
        "messages": [{"role": "user", "content": "hi"}],
    }

    req = build_request("oai", "hi", "gpt-5.6", "sk-o")
    assert req.full_url == "https://api.openai.com/v1/responses/input_tokens"
    assert req.get_header("Authorization") == "Bearer sk-o"
    assert json.loads(req.data) == {"model": "gpt-5.6", "input": "hi"}

    # model override reaches the payload; unicode survives the round trip
    assert json.loads(build_request("oai", "áé", "gpt-4o", "k").data)["model"] == "gpt-4o"
    assert json.loads(build_request("oai", "áé", "gpt-4o", "k").data)["input"] == "áé"

    # empty input short-circuits before any request
    assert count("ant", "", None) == 0
    print("self-test ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", nargs="?", help="file to count, or - for stdin")
    ap.add_argument("--ant", action="store_true", help="use Anthropic's tokenizer (default)")
    ap.add_argument("--oai", action="store_true", help="use OpenAI's tokenizer")
    ap.add_argument("-m", "--model", help="override the model whose tokenizer is used")
    ap.add_argument("--self-test", action="store_true", help="check request building, no network")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.file:
        ap.error("a file (or -) is required")

    if not (args.ant or args.oai):
        args.ant = True

    text = read_source(args.file)
    for name in ("ant", "oai"):
        if getattr(args, name):
            model = args.model or PROVIDERS[name]["model"]
            print(f"{name} ({model}): {count(name, text, model)}")


if __name__ == "__main__":
    main()
