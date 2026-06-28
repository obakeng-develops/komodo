# Manage your team

Komodo has two roles. Owners run everything. Operators, your backup on-call, see the whole fleet
and can act on incidents but cannot change settings, the LLM key, hosts, services, guardrails, or
the team. The full split is in [Architecture](../reference/architecture.md#roles).

## Add an operator

1. Sign in as the owner.
2. Open **Settings**, then **Team**.
3. Enter the person's name, email, and a password, then click **Add**.
4. Send them the email and password. They sign in at `/login`.

## Remove an operator

In the same **Team** panel, click **Remove** next to the person. You cannot remove the owner.

## Where the owner comes from

The first owner is created once, in one of two ways:

- **The first-run setup page.** On a fresh deployment, the first visitor creates the owner. Set a
  `SETUP_TOKEN` on a public URL so a stranger cannot claim it first.
- **The environment.** Set `OWNER_EMAIL` and `OWNER_PASSWORD` and Komodo creates the owner on first
  boot. This bootstrap runs once; a later restart never overwrites a password you have changed.
