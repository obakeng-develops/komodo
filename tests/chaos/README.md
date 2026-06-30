# Chaos tests

These tests break Mino on purpose and check that it fails the way it should.
They run against a real stack, not mocks: a real executor container, a real
agent process, a real Docker daemon.

They test what Mino does today, not what it might do later. Scenarios that
would assert features Mino lacks (per-target allowlists, confidence gating)
are noted in the files and left out, so a pass means something.

## executor_chaos.py

The executor's job is to run only safe, signed actions. This stands up a
throwaway executor with an ephemeral RSA key and a target container, then tries
to get past its guard:

- A whitelisted, validly-signed restart runs, and the container restarts.
- A non-whitelisted action (`exec_shell rm -rf /`) is rejected.
- A garbage token, a token signed with the wrong key, and a token naming an
  unsafe container are each rejected.
- An unreachable executor surfaces as a clean error, not a crash.

This caught a real bug: the executor image shipped without `cryptography`, so
PyJWT could not verify RS256 tokens and every signed action failed. The fix is
in this branch (`executor/requirements.txt`).

```
.venv/bin/python tests/chaos/executor_chaos.py
```

## detection_chaos.py

The monitoring loop's job is to notice a container die, open an incident,
diagnose it, and recover. This runs a real agent against local Docker and
drives it through the loop:

- Stop a container. An incident opens with severity `down`.
- With an LLM key set, the incident gets a diagnosis.
- Start the container again. The recovery is detected.
- Kill the agent. The watched container is left untouched.

```
.venv/bin/python tests/chaos/detection_chaos.py
```

## Running

Both need Docker. `detection_chaos.py` needs a local Mino already up
(`docker compose up`) with an owner you can log in as; set `KOMODO_EMAIL` and
`KOMODO_PASSWORD` if they differ from the defaults at the top of the file.
