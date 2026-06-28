# Sign off before pushing

Komodo ships two scripts that run the same quality gates:

- `scripts/checks` runs the gates and stops at the first failure.
- `scripts/signoff` runs the gates on a clean repo, then records a `signoff` status on the commit
  in GitHub.

The gates are: compile the Python, run `svelte-check`, build the frontend, and validate the Compose
file.

## Run the checks

```bash
./scripts/checks
```

## Sign off a commit

```bash
./scripts/signoff
```

It refuses a dirty repo, so commit first. On success it stamps the commit through the GitHub API.
You need the `gh` CLI logged in.

## Block bad pushes automatically

Turn on the pre-push hook once per clone:

```bash
git config core.hooksPath .githooks
```

Now a push runs the gates first and aborts if any fail. Skip the hook for a single push with
`git push --no-verify`.
