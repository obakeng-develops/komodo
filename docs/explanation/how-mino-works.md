# How Mino works

This page is about why Mino behaves as it does. For steps, see the how-to guides; for facts, see
the reference.

## The incident lifecycle

A container fails. The agent reports it on its next heartbeat. The backend opens an incident and
moves it through a small state machine: detect, diagnose, act, verify, resolve. Along the way it
pulls the container's recent logs and sends them to the llm-service, which returns a cause, a fix,
and a confidence level. The whole arc streams to the browser over Server-Sent Events, so the Now
view shows each step as it happens rather than after the fact.

The point of the visible arc is trust. An agent that silently restarts things is hard to believe in
at three in the morning. An agent that shows its reasoning, then acts, is one you can hand the pager
to.

## Autonomy: act, or ask first

You set how far Mino goes on its own.

- **Auto-fix.** Mino restarts the container as soon as it has diagnosed the problem, then verifies
  the container came back.
- **Ask first.** Mino stops at a diagnosis and waits for a person to approve the fix.

Ask-first is the safer default while you are learning to trust it. Auto-fix is what you want once
you do, for the failures you have seen before.

## Guardrails

Guardrails are the limits Mino will not cross, whatever the autonomy. The agent only ever runs
`docker restart`. It never stops, scales, or deletes. It backs off after repeated restarts in a
short window rather than fighting a crash loop, and it escalates to a person when a restart does not
bring the container back in time. The aim is a system that fails safe: when in doubt, it hands the
problem to you rather than guessing.

## Why a separate llm-service

The model call lives in its own service for two reasons. It keeps the provider key in one place,
decrypted only where it is used. And it isolates a slow, external dependency from the control plane,
so a sluggish model never blocks incident handling. If the model returns nothing useful, Mino
records that and carries on; the fix path does not depend on the diagnosis.

## Owners and operators

The two roles answer a real on-call need. You want a backup who can act in an emergency without
being able to reconfigure the system. Operators can approve and resolve incidents but cannot change
settings, keys, or hosts. See [Architecture](../reference/architecture.md#roles) for the exact
split.
