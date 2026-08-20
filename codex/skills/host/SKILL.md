---
name: host
description: Host a local app on the Mac Mini at https://tools.sophiaconsulting.ai/<path> with basic auth, via Cloudflare Tunnel + Caddy. Use when the user wants to share a running app with clients.
---

# Host a local app on tools.sophiaconsulting.ai

Expose a locally running app on the Mac Mini to the internet at `https://tools.sophiaconsulting.ai/<path>` with basic auth password protection, using the existing Cloudflare Tunnel (`ironclaw`) and Caddy reverse proxy.

**Architecture:** Internet → Cloudflare Tunnel → Caddy (:8888, basic auth) → App (localhost:<port>)

## Prerequisites (already installed)

- `cloudflared` — Cloudflare Tunnel client
- `caddy` — reverse proxy with basic auth
- Tunnel `ironclaw` configured in `~/.cloudflared/config.yml`
- DNS CNAME for `tools.sophiaconsulting.ai` pointing to the tunnel

## Step 1 — Determine app details

Gather from the user or infer from context:

1. **Path** — the URL path segment (e.g., `denoising` → `https://tools.sophiaconsulting.ai/denoising`)
2. **Local port** — the port the app runs on (e.g., `3000`)
3. **Start command** — the command to start the app (e.g., `fuzzy-img-viewer output`)
4. **Credentials** — username and password for basic auth. Ask the user.

## Step 2 — Generate bcrypt hash

```bash
caddy hash-password --plaintext "<password>"
```

## Step 3 — Create or update the project's Caddyfile

Create a `Caddyfile` in the project directory:

```
:8888 {
    basic_auth * {
        <username> <bcrypt-hash>
    }

    handle_path /<path>* {
        reverse_proxy localhost:<port>
    }

    # Assets/API requests from the app (browser caches auth credentials)
    reverse_proxy localhost:<port>

    redir / /<path> permanent
}
```

**If a Caddyfile already exists** in the project, update it rather than overwriting.

## Step 4 — Update the shared cloudflared config

Read `~/.cloudflared/config.yml`. Ensure the `tools.sophiaconsulting.ai` hostname points to `http://localhost:8888` (Caddy's port). If it already does, no change needed.

**Do NOT change** any other ingress entries in the config.

## Step 5 — Create serve.sh

Create a `serve.sh` script in the project directory that manages all three services (app, caddy, tunnel) with start/stop/status/restart commands. Use PID files in `/tmp/<project-name>-serve/` for process management.

```bash
#!/usr/bin/env zsh

PID_DIR="/tmp/<project-name>-serve"

start() {
    mkdir -p "$PID_DIR"

    if [[ -f "$PID_DIR/app.pid" ]] && kill -0 "$(cat "$PID_DIR/app.pid")" 2>/dev/null; then
        gum style --foreground 208 "Already running. Use: $0 stop"
        return 1
    fi

    gum style --bold --foreground 212 "Starting <app-name> stack..."

    <start-command> &
    echo $! > "$PID_DIR/app.pid"

    caddy run --config ./Caddyfile &
    echo $! > "$PID_DIR/caddy.pid"

    cloudflared tunnel run ironclaw &
    echo $! > "$PID_DIR/tunnel.pid"

    sleep 2

    gum style --bold --foreground 82 "
  ✓ App running on :<port>
  ✓ Caddy proxy on :8888
  ✓ Cloudflare Tunnel active

  URL:      https://tools.sophiaconsulting.ai/<path>
  Username: <username>
  Password: <password>
"
}

stop() {
    gum style --bold --foreground 212 "Stopping services..."

    for svc in tunnel caddy app; do
        local pidfile="$PID_DIR/$svc.pid"
        if [[ -f "$pidfile" ]]; then
            local pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                gum style --foreground 82 "  ✓ Stopped $svc (pid $pid)"
            fi
            rm -f "$pidfile"
        fi
    done

    gum style --bold --foreground 82 "All services stopped."
}

status() {
    for svc in app caddy tunnel; do
        local pidfile="$PID_DIR/$svc.pid"
        if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
            gum style --foreground 82 "  ✓ $svc running (pid $(cat "$pidfile"))"
        else
            gum style --foreground 196 "  ✗ $svc not running"
        fi
    done
}

case "${1:-start}" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
    restart) stop; sleep 1; start ;;
    *)      echo "Usage: $0 {start|stop|status|restart}" ;;
esac
```

Make it executable: `chmod +x serve.sh`

## Step 6 — Create or update justfile

Add these recipes to the project's justfile:

```just
# Start all services (app + proxy + tunnel)
serve:
    ./serve.sh start

# Stop all services
stop:
    ./serve.sh stop

# Check service status
status:
    ./serve.sh status

# Restart all services
restart:
    ./serve.sh restart
```

**If a justfile already exists**, add the recipes alongside existing ones.

## Step 7 — Start and verify

Start the services:
```bash
./serve.sh start
```

Verify:
```bash
# Should return 401
curl -s -o /dev/null -w "%{http_code}" https://tools.sophiaconsulting.ai/<path>

# Should return 200
curl -s -o /dev/null -w "%{http_code}" -u <username>:<password> https://tools.sophiaconsulting.ai/<path>
```

Report the URL and credentials to the user.

## Important notes

- The Cloudflare Tunnel name is `ironclaw` — always use this tunnel
- Caddy always runs on port `:8888`
- The cloudflared config is at `~/.cloudflared/config.yml`
- When multiple apps need to be hosted simultaneously, each app gets its own `handle_path` block in the Caddyfile and runs on a different local port. The tunnel and Caddy are shared.
- If the tunnel or Caddy are already running from another project, the script may conflict. Check with `./serve.sh status` first.
