# Choose an LLM provider

Mino asks a language model to read an incident's logs and return a cause, a fix, and a confidence
level. You choose the provider and model, and you supply the key. Mino stores the key encrypted;
it is never an environment variable.

Mino supports two providers today.

## DeepSeek

1. Get a key from DeepSeek.
2. In Mino, open **Settings**, then **LLM diagnosis**.
3. Set the provider to **DeepSeek** and pick a model, such as `deepseek-v4-flash`.
4. Paste the key and save.

## OpenRouter

OpenRouter puts many hosted models behind one API, so you can point Mino at OpenAI, Anthropic,
Google, and others without a separate integration for each.

1. Get a key from OpenRouter (it looks like `sk-or-...`).
2. In Mino, open **Settings**, then **LLM diagnosis**.
3. Set the provider to **OpenRouter**.
4. Type the model id you want in the model field, for example `anthropic/claude-3.5-sonnet` or
   `openai/gpt-4o`.
5. Paste the key and save.

## How a diagnosis is graded

The model is asked to answer in three lines:

```
CAUSE: one sentence on the likely root cause
FIX: one concrete command or action to try
CONFIDENCE: low | medium | high
```

Mino shows that on the incident. If the model returns nothing useful, Mino records that the
diagnosis was skipped and carries on; the fix path does not depend on it.

## Defaults for new deployments

`LLM_PROVIDER` and `LLM_MODEL` in `.env` set the default for the fleet. Each account can override
them in Settings. The key still lives in the database, encrypted, not in `.env`.
