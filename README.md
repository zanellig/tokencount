# tokencount

Count the tokens in a file with Anthropic's or OpenAI's official token-counting
API. One file, standard library only, no SDKs to install.

Local tokenizers guess. These endpoints return the count the model actually
bills, including the tokenizer changes that ship with new model generations.

## Install

```sh
curl -O https://raw.githubusercontent.com/zanellig/tokencount/main/tokencount.py
chmod +x tokencount.py
```

Requires Python 3.8+. Put it on your `PATH` as `tokencount` if you want.

## Usage

```sh
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

tokencount.py file.py                      # Anthropic tokenizer (default)
tokencount.py --oai file.py                # OpenAI tokenizer
tokencount.py --ant --oai file.py          # both, to compare
tokencount.py -m claude-sonnet-5 file.py   # pick the model
git diff | tokencount.py -                 # read stdin
```

```
$ tokencount.py --ant --oai README.md
ant (claude-opus-5): 512
oai (gpt-5.6): 498
```

| Flag | Meaning |
| --- | --- |
| `--ant` | Count with Anthropic's tokenizer. Default when no provider is given. |
| `--oai` | Count with OpenAI's tokenizer. |
| `-m`, `--model` | Override the model whose tokenizer is used. |
| `--self-test` | Verify request building offline. Makes no network calls. |

Default models are `claude-opus-5` and `gpt-5.6`.

## Why the model matters

Token counts are not portable between models. Claude 4.7 and later use a newer
tokenizer that produces roughly 30% more tokens than earlier Claude models for
the same text, and OpenAI's counts differ again. Always count against the model
you plan to send to rather than reusing an old number.

## Cost

Anthropic's token counting is free, with its own requests-per-minute limit
(2,000–8,000 depending on usage tier) that is independent of the Messages API
limit. OpenAI does not document a separate charge for its endpoint; check your
account dashboard.

## Notes

- Input must be UTF-8 text. Binary files are rejected rather than silently
  miscounted.
- An empty file reports 0 without making a request.
- The whole file is sent in one request, so very large files will be rejected by
  the provider rather than chunked.

## Endpoints

- [`POST /v1/messages/count_tokens`](https://platform.claude.com/docs/en/build-with-claude/token-counting)
- [`POST /v1/responses/input_tokens`](https://developers.openai.com/api/docs/guides/token-counting)

## License

MIT. See [LICENSE](LICENSE).
