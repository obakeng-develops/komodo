# Install the agent on a host

Every server you want watched runs the agent. It is a single Python file with no dependencies. It
needs Python 3 and access to the Docker socket.

## Steps

1. In Mino, open **Settings**, then **Connected servers**, then **Add server**. Only owners can do
   this. Name the server.
2. Click **Install**. Mino shows a command with a one-time token in it. Copy it.
3. Run it on the host:

```bash
curl -fsSL https://komodo.example.com/api/v1/agent/script \
  | python3 - --server https://komodo.example.com --token <agent-token>
```

The agent reports `docker ps` every few seconds and runs `docker restart` only when Mino approves
it. Nothing else.

## Keep it running

Wrap the command in a systemd unit so it survives reboots:

```ini
# /etc/systemd/system/mino-agent.service
[Unit]
Description=Mino agent
After=docker.service

[Service]
ExecStart=/usr/bin/python3 /opt/komodo/mino-agent.py \
  --server https://komodo.example.com --token <agent-token>
Restart=always

[Install]
WantedBy=multi-user.target
```

Save the script to `/opt/komodo/mino-agent.py` first (download it from the same `/api/v1/agent/script`
URL), then `systemctl enable --now mino-agent`.

## Agent flags

| Flag | Default | Meaning |
|---|---|---|
| `--server` | required | the Mino URL the agent reports to |
| `--token` | required | the host token from the Add server screen |
| `--interval` | 10 | seconds between heartbeats |
| `--once` | off | send one heartbeat and exit |
