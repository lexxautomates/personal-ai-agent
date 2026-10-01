# Jarvis personal agent - deployment runbook (Contabo Cloud VPS 6)

Target: Ubuntu 24.04, 6 vCPU / 12 GB RAM, IP 86.48.18.41.
Already on the box: docker, ollama (`qwen2.5:7b-instruct` on :11434), Caddy on
80/443 with on-demand TLS for `*.86-48-18-41.sslip.io`, n8n, the openmuse stack.
ufw allows 22/80/443. Everything runs as root; secrets live in 600 files under
`/opt/jarvis/`.

Nothing here is run against the VPS by the authoring agent - this is a
files-only package for review. A human (or a deploy session) runs the steps below.

## Pieces

| Piece | What | Where on the VPS |
|---|---|---|
| LiveKit server | `livekit/livekit-server:v1.13.7` (pinned) docker container | `jarvis-livekit`, ports 7880/7881/7882 |
| Flask web | `web/app.py` via systemd | `jarvis-web.service`, localhost:5000 |
| Agent worker | `agent/agent.py start` via systemd | `jarvis-agent.service` |
| Public web | Caddy reverse proxy | https://jarvis.86-48-18-41.sslip.io |
| Public signaling | Caddy reverse proxy (ws) | https://livekit.86-48-18-41.sslip.io |
| Secrets | `/opt/jarvis/.env`, `/opt/jarvis/livekit/keys.yaml` (both 600) | `/opt/jarvis/` |

## Order of operations

### 1. Clone on the VPS
```bash
ssh -i ~/.ssh/contabo_beacon root@86.48.18.41   # via ~/workspace/vps-ssh.sh helper
git clone https://github.com/lexxautomates/personal-ai-agent /root/personal-ai-agent
cd /root/personal-ai-agent
git checkout main && git pull
```

### 2. Run the deploy script (idempotent - safe to re-run after every code change)
```bash
bash deploy/deploy.sh
```
First run: creates `/opt/jarvis/{app,venv,data,livekit,caddy}`, generates LiveKit
keys + `JARVIS_WEBHOOK_SECRET`, installs systemd units, starts LiveKit, restarts
the web + agent services. Re-runs: re-syncs code, reinstalls deps, restarts
services - keys, config, and `.env` are left untouched.

### 3. Firewall (YOU run these - deploy.sh only prints them)
```bash
ufw allow 7881/tcp comment 'jarvis livekit rtc-tcp'
ufw allow 7882/udp comment 'jarvis livekit rtc-udp'
ufw allow 3478/udp comment 'jarvis livekit turn'   # optional, only if TURN fallback is needed
```
Port 7880 stays localhost-only (Caddy proxies it). Port 5000 stays localhost-only.

### 4. Caddy (one-time manual step)
Add to the existing Caddyfile, global scope:
```
import /opt/jarvis/caddy/caddy-snippets.conf
```
Then:
```bash
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload caddy
```
deploy.sh detects the import on later runs and reloads Caddy itself.

## Verify each piece

### Flask web
```bash
curl -s http://localhost:5000/health
# {"status":"ok","utc":"..."}
curl -s https://jarvis.86-48-18-41.sslip.io/health   # via Caddy, valid on-demand cert
systemctl status jarvis-web --no-pager
journalctl -u jarvis-web -n 30 --no-pager
```

### LiveKit server
```bash
docker ps --filter name=jarvis-livekit
docker logs jarvis-livekit --tail 30
# look for: "starting LiveKit server", no "could not parse config" errors
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:7880/   # 404 means "up"
curl -s -o /dev/null -w '%{http_code}\n' https://livekit.86-48-18-41.sslip.io/  # 404 via Caddy
```

### Token generation test
Mint a join token with the venv's livekit SDK and validate it against the server:
```bash
export $(grep -E '^(LIVEKIT_API_KEY|LIVEKIT_API_SECRET)=' /opt/jarvis/.env | xargs)
TOKEN=$(/opt/jarvis/venv/bin/python - <<'EOF'
import os, asyncio
from livekit import api
async def main():
    token = api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"]) \
        .with_identity("deploy-check").with_name("deploy-check") \
        .with_grants(api.VideoGrants(room_join=True, room="deploy-check-room")).to_jwt()
    print(token)
asyncio.run(main())
EOF
)
curl -s "http://localhost:7880/rtc/validate?access_token=$TOKEN" | head -c 300; echo
# expect: {"valid":true,...}  (or HTTP 200 with token details)
```
(`rtc/validate` confirms the key/secret pair the agent will use actually signs.)

### Agent worker
```bash
systemctl status jarvis-agent --no-pager
journalctl -u jarvis-agent -n 50 --no-pager
# expect: worker/agent-server started, no import errors, no "connection refused" to :7880
```
End-to-end: from the Flutter client (or any LiveKit client pointed at
`wss://livekit.86-48-18-41.sslip.io` with a token for the agent room), join the
room and watch `journalctl -u jarvis-agent -f` - a session should start and the
agent should greet. If the agent never joins the room, see "Agent never
dispatched" below.

### Full-stack smoke (after code changes)
```bash
cd /root/personal-ai-agent && git pull && bash deploy/deploy.sh
curl -s https://jarvis.86-48-18-41.sslip.io/health
docker ps --filter name=jarvis-livekit --format '{{.Status}}'
systemctl is-active jarvis-web jarvis-agent
```

## Troubleshooting

**`docker logs jarvis-livekit` shows `could not parse config: ... field X not found`**
LiveKit parses `livekit.yaml` in strict mode. The field was renamed/removed in the
pinned version. Edit `/opt/jarvis/livekit/livekit.yaml` to match, then
`docker compose -f deploy/docker-compose.livekit.yml up -d`.

**Agent never dispatched / never joins rooms**
Two worker shapes exist; the deploy assumes the AgentServer one:
- AgentServer shape (`AgentServer` + `cli.run_app(server)`, current `agent.py`):
  `python agent/agent.py start` listens on :8081 and LiveKit forwards jobs via the
  `agent_dispatch` block in `livekit.yaml`. Confirm the block is present and the
  agent logs show it listening.
- Classic worker shape (`cli.run_app(WorkerOptions(entrypoint_fnc=...))`):
  the worker opens its own websocket to `LIVEKIT_URL` - then DELETE the
  `agent_dispatch` block from `/opt/jarvis/livekit/livekit.yaml` and restart LiveKit.
If the sibling rewrite changed the entrypoint, check which shape landed first.

**`jarvis-agent` restarts in a loop with import errors**
The venv was built before `agent/requirements.txt` existed, or deps changed.
Re-run `deploy.sh` (it reinstalls requirements every run). Inspect with
`journalctl -u jarvis-agent -n 50`.

**Clients connect to signaling but no audio/video**
Media ports blocked: confirm `ufw status` shows 7881/tcp + 7882/udp, and that no
cloud-side firewall (Contabo panel) filters them. Check `rtc.use_external_ip`
in `livekit.yaml` (the VPS has a public IP on its interface, so this is correct).

**Caddy serves the old site / cert errors on the new hostnames**
On-demand TLS issues the cert on first request; a failed first request can cache
nothing - just retry. Confirm the `import` line is in the active Caddyfile and
`caddy validate` passes.

## Rollback

```bash
# stop the new stack (secrets and data are kept)
systemctl disable --now jarvis-web jarvis-agent
docker compose -f /root/personal-ai-agent/deploy/docker-compose.livekit.yml down

# if a LiveKit version bump misbehaves: revert the tag in
# deploy/docker-compose.livekit.yml and re-run deploy.sh (or up -d directly).
# the previous image stays in the local docker cache as the one-command rollback.

# full removal (destructive - keeps nothing):
#   rm -rf /opt/jarvis
#   rm /etc/systemd/system/jarvis-*.service && systemctl daemon-reload
#   remove the `import` line from the Caddyfile && systemctl reload caddy
#   ufw delete allow 7881/tcp; ufw delete allow 7882/udp
```

## Open items (not this package's job)

- **`/token` endpoint**: the Flutter client needs an HTTP endpoint that mints
  join tokens. Current `web/app.py` doesn't have one (sibling owns `web/`);
  the key/secret are already in `/opt/jarvis/.env` so it's ready when they add it.
- **STT/LLM/TTS credentials**: current `agent.py` uses `inference.*` providers
  (e.g. `google/gemini-2.5-flash`); those need provider keys or a LiveKit
  inference setup. `OLLAMA_URL` is in `.env` for a future local-model path.
- **AgentServer port**: assumed default :8081. If the rewrite sets
  `AGENT_SERVER_PORT` (or similar) to something else, update the
  `agent_dispatch` URL in `/opt/jarvis/livekit/livekit.yaml` to match.
- **Requirements**: if `agent/requirements.txt` is still absent when this is
  first deployed, `deploy.sh` installs `flask` + `livekit-agents` as a
  placeholder and warns loudly.
