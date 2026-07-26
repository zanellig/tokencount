# tokencount

Count the tokens in a file with Anthropic's or OpenAI's official token-counting
API. One file, standard library only, no SDKs to install.

A local tokenizer only sees plain text. These endpoints use the provider's own
tokenizer for the model you name, so they follow the tokenizer changes that ship
with new model generations and account for message structure.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/zanellig/tokencount/main/install.sh | sh
```

Requires Python 3.8+. This drops a single executable at `~/.local/bin/tokencount`.
Re-run the same command to update. Set `BINDIR` to install elsewhere, `REF` to
pin a tag or branch:

```sh
curl -fsSL https://raw.githubusercontent.com/zanellig/tokencount/main/install.sh \
  | BINDIR=/usr/local/bin REF=v1.0.0 sh
```

To uninstall, delete the file. Or skip the installer entirely and grab the
script:

```sh
curl -O https://raw.githubusercontent.com/zanellig/tokencount/main/tokencount.py
chmod +x tokencount.py
```

## Usage

```sh
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

tokencount file.py                      # Anthropic, or OpenAI if it is unavailable
tokencount --oai file.py                # OpenAI tokenizer
tokencount --ant --oai file.py          # both, to compare
tokencount -m claude-sonnet-5 file.py   # pick the model
git diff | tokencount -                 # read stdin
tokencount --ant --list-models          # what can I pass to -m?
```

```
$ tokencount --ant --oai README.md
ant (claude-opus-5): 512  (0.1% of 1000000 limit)
oai (gpt-5.6): 498
```

Anthropic publishes each model's input limit, so counts against `--ant` also
report how much of the context window the file uses, or that it exceeds it.
OpenAI's models endpoint does not expose a limit, so `--oai` prints the count
alone.

| Flag | Meaning |
| --- | --- |
| `--ant` | Count with Anthropic's tokenizer. |
| `--oai` | Count with OpenAI's tokenizer. |
| `-m`, `--model` | Override the model whose tokenizer is used. |
| `--list-models` | List available models and exit. |
| `--self-test` | Verify request building offline. Makes no network calls. |

Default models are `claude-opus-5` and `gpt-5.6`.

```
$ tokencount --ant --list-models
ant: 11 models
┌────────────────────────────┬───────────┬───────────────────┐
│ MODEL                      │ CONTEXT   │ NAME              │
├────────────────────────────┼───────────┼───────────────────┤
│ claude-opus-5              │ 1,000,000 │ Claude Opus 5     │
│ claude-sonnet-5            │ 1,000,000 │ Claude Sonnet 5   │
│ claude-fable-5             │ 1,000,000 │ Claude Fable 5    │
└────────────────────────────┴───────────┴───────────────────┘
```

Each provider gets its own table, titled with its name and model count and sized
to its own contents. Anthropic lists newest first with display names and input
limits. OpenAI's list is sorted by id, names the owning org instead, and
includes non-chat models (embeddings, audio, images) since that is what the
endpoint returns — its `CONTEXT` column is all `-`, as that endpoint publishes no
limits.

## Why the model matters

Token counts are not portable between models. Claude 4.7 and later use a newer
tokenizer that produces roughly 30% more tokens than earlier Claude models for
the same text, and OpenAI's counts differ again. Always count against the model
you plan to send to rather than reusing an old number.

## Cost

Anthropic's token counting is free, with its own requests-per-minute limit
(2,000–8,000 depending on usage tier) that is independent of the Messages API
limit. OpenAI does not document a separate charge for its endpoint; check your
account dashboard. Listing models is free on both.

Free of token charges is not the same as free to reach: Anthropic's
`count_tokens` returns HTTP 400 `invalid_request_error` ("credit balance is too
low") on an account with no credits, even though the count itself costs nothing.
`GET /v1/models` still works on such an account, so `--list-models` is a good
way to confirm a key is valid.

An `--ant` count makes a second, free request to look up the model's input
limit. If that lookup fails the count is still printed, just without the
context-window note.

With no provider flag, Anthropic is used and OpenAI is only tried if Anthropic
is unavailable (no key, no credit, network error). The fallback is silent: the
Anthropic error is only reported if OpenAI fails too.

With explicit flags the providers are independent: if one fails, the other's
result is still printed, errors go to stderr, and the exit code is 1.

## Notes

- The result is an estimate. Anthropic notes the real request may differ by a
  small amount, and that tokens it adds for its own optimizations are counted
  here but not billed.
- Input must be UTF-8 text. Binary files are rejected rather than silently
  miscounted.
- An empty file reports 0 without making a request.
- The whole file is sent in one request, so very large files will be rejected by
  the provider rather than chunked.

## Endpoints

- [`POST /v1/messages/count_tokens`](https://platform.claude.com/docs/en/build-with-claude/token-counting)
- [`POST /v1/responses/input_tokens`](https://developers.openai.com/api/docs/guides/token-counting)
- [`GET /v1/models`](https://platform.claude.com/docs/en/api/models-list) (Anthropic)
- [`GET /v1/models`](https://developers.openai.com/api/docs/api-reference/models/list) (OpenAI)

## License

MIT. See [LICENSE](LICENSE).
