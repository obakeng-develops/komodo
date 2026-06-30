# Security

Mino can restart your containers, so it is worth understanding what holds that power and how it is
contained.

## The executor is the sharp edge

The executor runs privileged with the Docker socket mounted. That is what lets it control containers
on its host, and it means the executor host deserves the same care as any box that can run arbitrary
containers.

What contains it: the executor accepts only short-lived, signed tokens, and only for a fixed set of
actions: restart, stop, fetch logs, list. The backend holds the RSA private key and signs each
action; the executor holds the matching public key and verifies it. A token is good for one action
for a few seconds. There is no general "run this" path.

## Secrets

Keep `secrets/`, `.env`, and the database files out of git. The `.gitignore` already excludes them.
The LLM API key lives in the database, encrypted with `ENCRYPTION_KEY`, not in any environment
variable. If you lose `ENCRYPTION_KEY`, the stored key cannot be decrypted, which is the point.

## On a public deploy

Set `COOKIE_SECURE=true` so the session cookie is only sent over HTTPS, and set a `SETUP_TOKEN` so
the first-run owner page cannot be claimed by whoever finds the URL first.

## What is not here yet

Mino has no rate limiting on login, no server-side session revocation, and no in-app password
change. These are reasonable next steps before exposing it widely. They are listed as future work
rather than promised.
