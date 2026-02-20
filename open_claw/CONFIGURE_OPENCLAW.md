# Configure OpenClaw: 5-Agent Team on a Dedicated Mac Mini

Step-by-step guide for setting up a multi-agent OpenClaw team. Based on
[Brian Castle's video](https://www.youtube.com/watch?v=example) with
modifications: 5 agents instead of 4, tailored for an AI consulting business.

> **Always run the latest version.** Earlier versions have critical RCE
> vulnerabilities (CVE-2026-25253, CVSS 8.8). Absolute minimum: v2026.1.29.
> Run `openclaw --version` and update with `npm install -g openclaw@latest`.

**Agents:**

| Agent | Model | Role |
|-------|-------|------|
| HR Agent | Opus | Manages other agents, onboarding, agent configs |
| Dev Agent | Opus | Development, backlog issues, PRs, production errors |
| Business Agent | Sonnet | Marketing, website design, business strategy |
| Researcher Agent | Sonnet | Research people/companies, write reports |
| Media Agent | Sonnet | Social media content, podcast support |

---

## Phase 0: Mac Mini Prep

The Mac Mini runs 24/7 as a headless server. You SSH into it from your
MacBook Pro like any remote machine. You never need to plug in a monitor.

### 0.1 How This Actually Works

```
┌─────────────────┐         SSH / Mosh          ┌─────────────────┐
│  MacBook Pro     │ ◄──────────────────────────► │  Mac Mini       │
│  (daily driver)  │                              │  (agent server) │
│                  │       Syncthing (LAN)        │                 │
│  ~/dev/  ────────│──── Send Only ──────────────►│  ~/dev/         │
│  (YOUR copy)     │                              │  (THEIR copy)   │
│                  │       Tailscale (VPN)        │                 │
│                  │ ◄──────────────────────────► │                 │
└─────────────────┘    (works outside home too)   └─────────────────┘
```

**Key principle:** Your MacBook is the source of truth. The Mac Mini gets a
read-only mirror. If agents nuke everything on the Mini, you hit "Revert" and
it re-syncs from your Mac. Your files are never at risk.

### 0.2 HDMI Dummy Plug (Mandatory, ~$8)

Buy an HDMI dummy plug (HDMI emulator/headless adapter) and plug it into
the Mac Mini. Without it, macOS enters a degraded headless mode where
Screen Recording permissions break, GUI apps fail to render, and browser
tools silently fail. This is the #1 hardware gotcha for headless Macs.

### 0.3 Always-On Configuration (Mac Mini)

On the Mac Mini, configure it to stay awake and recover from power loss.

**System Settings UI:**
- **Energy:** Prevent automatic sleeping, Start up after power failure, Wake for network access
- **Users & Groups:** Automatic Login for your admin user
- **Lock Screen:** Turn display off = Never

**Terminal commands (mandatory — the UI alone is unreliable on M4 Minis):**

```bash
sudo pmset -a sleep 0 displaysleep 0 disksleep 0
sudo pmset -a disablesleep 1
sudo pmset -a autorestart 1
sudo pmset -a tcpkeepalive 1
sudo pmset -a womp 1

# Verify
pmset -g
```

**Install Amphetamine** (free, Mac App Store) for more reliable sleep
prevention than system settings alone. Configure it to keep the Mac awake
indefinitely.

### 0.4 Use Ethernet, Not WiFi

Plug the Mac Mini into your router with an Ethernet cable. WiFi is
unreliable for an always-on server — reconnection delays, interference,
and power-saving disconnects will cause agent downtime.

### 0.5 Enable Remote Access

**System Settings > General > Sharing:**

- [x] **Remote Login (SSH)** — primary access method
- [x] **Screen Sharing** — backup for visual troubleshooting

### 0.6 SSH Setup (MacBook Pro Side)

Generate a key if you don't have one, then copy it to the Mini:

```bash
# On your MacBook Pro
ssh-keygen -t ed25519 -C "macbook-pro"
ssh-copy-id mini-user@<mac-mini-ip>
```

Add an SSH config entry for convenience. Edit `~/.ssh/config`:

```
Host mini
    HostName <mac-mini-local-ip>        # e.g., 192.168.1.50
    User mini-user
    IdentityFile ~/.ssh/id_ed25519
```

Now you can just:

```bash
ssh mini
```

### 0.7 Harden SSH (Mac Mini Side)

Edit `/etc/ssh/sshd_config` on the Mac Mini:

```
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowUsers mini-user
PermitRootLogin no
MaxAuthTries 3
LoginGraceTime 20
```

Validate and reload:

```bash
sudo sshd -t
sudo launchctl kickstart -k system/com.openssh.sshd
```

### 0.8 Install Tailscale (Both Machines)

Tailscale gives you a WireGuard VPN so you can SSH into the Mini from
anywhere — coffee shop, hotel, client site — not just your home network.

```bash
# On BOTH machines
brew install tailscale
```

**Important:** You must use the **Standalone version** of Tailscale, NOT
the Mac App Store version. The App Store version does not support Tailscale
SSH. Download from [tailscale.com/download](https://tailscale.com/download)
or install via `brew install --cask tailscale`.

On the Mac Mini, run Tailscale as a system daemon so it survives reboots
and doesn't need a logged-in GUI session:

```bash
# Mac Mini — run as system service (not menu bar app)
sudo tailscale up --ssh --auth-key tskey-XXXXXXXXXXXXXXXX
```

Get an auth key from [login.tailscale.com/admin/settings/keys](https://login.tailscale.com/admin/settings/keys).

On your MacBook Pro, just use the menu bar app:

```bash
# MacBook Pro — menu bar app is fine
open /Applications/Tailscale.app
```

Verify connectivity:

```bash
tailscale ping mini    # or use the Tailscale hostname
```

Update your SSH config to use the Tailscale hostname (works everywhere):

```
Host mini
    HostName mini.tail12345.ts.net    # your Tailscale hostname
    User mini-user
    IdentityFile ~/.ssh/id_ed25519
```

### 0.9 Install Eternal Terminal (Recommended over Mosh)

[Eternal Terminal](https://eternalterminal.dev/) (ET) is a drop-in SSH
replacement that handles network changes, laptop sleep/wake, and WiFi
drops — like Mosh, but with native scrollback support, full tmux
compatibility, and TCP (works better over Tailscale than Mosh's UDP).

```bash
# On BOTH machines
brew install et
```

Connect via:

```bash
et mini    # uses your SSH config, same auth
```

ET + Tailscale + tmux is the recommended stack: Tailscale handles VPN,
ET handles reconnection, tmux handles session persistence.

### 0.10 Mosh (Alternative to ET)

If you prefer Mosh over Eternal Terminal:

```bash
# On BOTH machines
brew install mosh
```

**Critical macOS fix** — Mosh needs Homebrew in the PATH for non-login shells.
On the Mac Mini, add to `/etc/zshenv`:

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
```

**Known Mosh limitations:** No native scrollback (must rely on tmux),
status bar rendering bugs with tmux, no tmux `-CC` mode support.

### 0.11 tmux on the Mac Mini

Always run a persistent tmux session on the Mini so work survives
disconnects:

```bash
ssh mini
tmux new -s main     # first time
tmux attach -t main  # reconnecting
```

### 0.12 FileVault Warning

FileVault (full-disk encryption) creates a pre-boot login screen that is
**unreachable over SSH**. If your Mac Mini reboots after a kernel update,
it will sit at the FileVault unlock screen indefinitely.

**Options:**
- **Skip FileVault** if the Mini is in a physically secure location
- **Password Utility by Twocanoes** ($10/year) — auto-unlocks on reboot
- **macOS Tahoe** (macOS 26) adds SSH-based pre-boot FileVault unlock
  (wired Ethernet only, password auth only)

### 0.13 LaunchAgent for Auto-Starting OpenClaw

Create `~/Library/LaunchAgents/ai.openclaw.gateway.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.openclaw.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/openclaw</string>
        <string>gateway</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/openclaw-gateway.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/openclaw-gateway-error.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist
```

> **Note:** There is a known bug ([#14161](https://github.com/openclaw/openclaw/issues/14161))
> where Gateway SIGUSR1 restart can destabilize launchd. Monitor logs after
> config changes.

### 0.14 UPS / Power Protection (Recommended)

An always-on server needs a UPS. The Mac Mini draws <20W idle, so even a
small UPS provides long runtime:

- **APC Back-UPS BE600M1** (~$70): 600VA, USB-connected, 30+ min runtime
- **CyberPower CP1500PFCLCD** (~$200): 1500VA, pure sine wave

macOS natively detects USB-connected UPS devices. Configure shutdown
triggers in **System Settings > Energy Saver > UPS**. For more reliable
graceful shutdown, install [NUTty](https://nutty.pingie.com/) ($5).

### 0.15 macOS Sequoia SSH Bug

> **Warning:** After upgrading to macOS Sequoia, SSH and Screen Sharing can
> stop working on headless Mac Minis until someone physically logs in with
> a keyboard. This is caused by new privacy prompts requiring local
> interaction. Test thoroughly after any macOS upgrade.

### 0.16 Create Dedicated Accounts

Treat OpenClaw like a new hire. Give it isolated credentials:

| Account | Purpose |
|---------|---------|
| Dedicated email (e.g., `agents@yourdomain.com`) | GitHub, Slack, Dropbox, service signups |
| GitHub username (e.g., `yourcompany-agents`) | Invite to specific repos only |
| Dropbox account | Shared folders only — never your personal Dropbox |

### 0.17 Install Dev Tools

```bash
# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Basics
brew install git node

# Docker runtime (required for agent sandboxing in Phase 6)
# OrbStack is recommended over Docker Desktop for lower power/CPU on always-on servers
brew install --cask orbstack
```

Verify Node 22+:

```bash
node --version   # must be >= 22
docker --version # verify Docker/OrbStack is available
```

---

## Phase 1: Install OpenClaw

### 1.1 Run the Installer

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

This installs the CLI and launches the onboarding wizard. If you hit a
`sharp`/libvips build error on macOS:

```bash
SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install -g openclaw@latest
openclaw onboard --install-daemon
```

### 1.2 Verify Installation

```bash
openclaw --version   # must be >= 2026.1.29
openclaw doctor --fix
openclaw status
```

### 1.3 Configure Gateway Basics

Edit `~/.openclaw/openclaw.json`:

```json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "loopback",
    "auth": {
      "mode": "token"
    }
  }
}
```

**Important:** Always bind to `loopback` (localhost only), never `0.0.0.0`.

---

## Phase 2: OpenRouter + API Keys

We use OpenRouter to centralize all API usage and select models per agent.

### 2.1 Get an OpenRouter API Key

1. Create an account at [openrouter.ai](https://openrouter.ai)
2. Go to Keys > Create Key
3. Copy the key (`sk-or-...`)

### 2.2 Set Up Environment Variables

Create `~/.openclaw/.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
```

Lock it down:

```bash
chmod 600 ~/.openclaw/.env
```

### 2.3 Configure OpenRouter in openclaw.json

OpenClaw has built-in OpenRouter support — no custom provider config needed.

Add to `~/.openclaw/openclaw.json`:

```json
{
  "env": {
    "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/anthropic/claude-sonnet-4-20250514",
        "fallbacks": [
          "openrouter/anthropic/claude-haiku-4-5"
        ]
      }
    }
  }
}
```

### 2.4 Model Assignment Strategy

OpenRouter model name format: `openrouter/<author>/<slug>`

| Agent | Model | Rationale |
|-------|-------|-----------|
| HR Agent | `openrouter/anthropic/claude-opus-4-5` | Needs strong reasoning for agent management |
| Dev Agent | `openrouter/anthropic/claude-opus-4-5` | Code quality requires top-tier model |
| Business Agent | `openrouter/anthropic/claude-sonnet-4-20250514` | Fast, capable, cost-effective |
| Researcher Agent | `openrouter/anthropic/claude-sonnet-4-20250514` | Good balance for research tasks |
| Media Agent | `openrouter/anthropic/claude-sonnet-4-20250514` | Creative writing doesn't need Opus |

---

## Phase 3: Slack Workspace + 5 Bot Apps

### 3.1 Create a Slack Workspace

Create a new workspace at [slack.com](https://slack.com) using the dedicated
email from Phase 0. This workspace is exclusively for agent communication.

### 3.2 Create 5 Slack Apps (One Per Agent)

Repeat these steps for each agent: `hr-agent`, `dev-agent`, `biz-agent`,
`researcher-agent`, `media-agent`.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) > **Create New App**
2. Choose **From scratch**
3. Name it (e.g., `HR Agent`) and select your workspace

### 3.3 Enable Socket Mode

For each app:

1. Go to **Settings > Socket Mode** > Enable
2. Create an **App-Level Token** with scope `connections:write`
3. Copy the token (`xapp-...`)

### 3.4 Configure OAuth Scopes

For each app, go to **OAuth & Permissions > Bot Token Scopes** and add:

```
chat:write
channels:history
channels:read
groups:history
im:history
mpim:history
users:read
app_mentions:read
assistant:write
reactions:read
reactions:write
pins:read
pins:write
emoji:read
commands
files:read
files:write
```

### 3.5 Subscribe to Bot Events

For each app, go to **Event Subscriptions > Subscribe to bot events** and add:

```
app_mention
message.channels
message.groups
message.im
message.mpim
reaction_added
reaction_removed
member_joined_channel
member_left_channel
channel_rename
pin_added
pin_removed
```

Also enable **App Home > Messages Tab** for DM support.

### 3.6 Install Each App to Workspace

For each app:

1. Go to **Install App** > Install to Workspace
2. Copy the **Bot Token** (`xoxb-...`)

### 3.7 Store Tokens in .env

Add all tokens to `~/.openclaw/.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx

# Slack App Tokens (xapp-)
SLACK_APP_TOKEN_HR=xapp-1-xxxxxxxxxxxx
SLACK_APP_TOKEN_DEV=xapp-1-xxxxxxxxxxxx
SLACK_APP_TOKEN_BIZ=xapp-1-xxxxxxxxxxxx
SLACK_APP_TOKEN_RESEARCHER=xapp-1-xxxxxxxxxxxx
SLACK_APP_TOKEN_MEDIA=xapp-1-xxxxxxxxxxxx

# Slack Bot Tokens (xoxb-)
SLACK_BOT_TOKEN_HR=xoxb-xxxxxxxxxxxx
SLACK_BOT_TOKEN_DEV=xoxb-xxxxxxxxxxxx
SLACK_BOT_TOKEN_BIZ=xoxb-xxxxxxxxxxxx
SLACK_BOT_TOKEN_RESEARCHER=xoxb-xxxxxxxxxxxx
SLACK_BOT_TOKEN_MEDIA=xoxb-xxxxxxxxxxxx

# Gateway auth token (generate with: openssl rand -hex 32)
OPENCLAW_GATEWAY_TOKEN=replace-with-64-char-hex-string
```

### 3.8 Configure Slack Accounts in openclaw.json

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "mode": "socket",
      "accounts": {
        "hr": {
          "appToken": "${SLACK_APP_TOKEN_HR}",
          "botToken": "${SLACK_BOT_TOKEN_HR}"
        },
        "dev": {
          "appToken": "${SLACK_APP_TOKEN_DEV}",
          "botToken": "${SLACK_BOT_TOKEN_DEV}"
        },
        "biz": {
          "appToken": "${SLACK_APP_TOKEN_BIZ}",
          "botToken": "${SLACK_BOT_TOKEN_BIZ}"
        },
        "researcher": {
          "appToken": "${SLACK_APP_TOKEN_RESEARCHER}",
          "botToken": "${SLACK_BOT_TOKEN_RESEARCHER}"
        },
        "media": {
          "appToken": "${SLACK_APP_TOKEN_MEDIA}",
          "botToken": "${SLACK_BOT_TOKEN_MEDIA}"
        }
      },
      "dmPolicy": "pairing",
      "groupPolicy": "open",
      "streaming": true,
      "textChunkLimit": 4000,
      "thread": {
        "historyScope": "thread",
        "inheritParent": false,
        "initialHistoryLimit": 20
      }
    }
  }
}
```

---

## Phase 4: Configure 5 Agents

### 4.1 Create Agent Directories

Each agent gets its own workspace and state directory. Never reuse `agentDir`
across agents (causes auth/session collisions).

```bash
# Shared workspace (all agents access same files + brain)
mkdir -p ~/.openclaw/workspace-team

# Per-agent state directories (sessions/ is auto-created by OpenClaw)
for agent in hr dev biz researcher media; do
  mkdir -p ~/.openclaw/agents/$agent/agent
done
```

### 4.2 Define Agents in openclaw.json

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/anthropic/claude-sonnet-4-20250514",
        "fallbacks": ["openrouter/anthropic/claude-haiku-4-5"]
      }
    },
    "list": [
      {
        "id": "hr",
        "name": "HR Agent",
        "default": true,
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/hr/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-opus-4-5"
        }
      },
      {
        "id": "dev",
        "name": "Dev Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/dev/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-opus-4-5"
        }
      },
      {
        "id": "biz",
        "name": "Business Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/biz/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-sonnet-4-20250514"
        }
      },
      {
        "id": "researcher",
        "name": "Researcher Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/researcher/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-sonnet-4-20250514"
        }
      },
      {
        "id": "media",
        "name": "Media Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/media/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-sonnet-4-20250514"
        }
      }
    ]
  }
}
```

### 4.3 Create Bindings (Route Slack Bots to Agents)

```json
{
  "bindings": [
    {
      "agentId": "hr",
      "match": { "channel": "slack", "accountId": "hr" }
    },
    {
      "agentId": "dev",
      "match": { "channel": "slack", "accountId": "dev" }
    },
    {
      "agentId": "biz",
      "match": { "channel": "slack", "accountId": "biz" }
    },
    {
      "agentId": "researcher",
      "match": { "channel": "slack", "accountId": "researcher" }
    },
    {
      "agentId": "media",
      "match": { "channel": "slack", "accountId": "media" }
    }
  ]
}
```

### 4.4 Agent-to-Agent Communication

Inter-agent communication is disabled by default. If you want the HR agent
to coordinate with others (e.g., delegate tasks to Dev), you need to enable
it explicitly:

```json
{
  "agentToAgent": {
    "enabled": true,
    "allowlist": ["hr", "dev", "biz", "researcher", "media"]
  }
}
```

Cross-agent messages are treated like user input on the receiving side.
Start with this disabled and enable it only after your agents are stable.

> **Note:** The merged `openclaw.json` reference at the bottom of this
> guide ships with `agentToAgent.enabled: false`. When you're ready to
> enable it, add the `allowlist` key as shown above.

### 4.5 Create SOUL.md for Each Agent

Each agent gets a `SOUL.md` in the shared workspace that defines its
personality. Since all agents share one workspace, use a single `SOUL.md` with
sections per agent (OpenClaw routes based on `agentId`).

Create `~/.openclaw/workspace-team/SOUL.md`:

```markdown
# Team Identity

You are part of a 5-agent team for an AI consulting company. Each agent has a
distinct role and personality. Identify which agent you are from the agentId
routing and follow your specific section below.

---

## HR Agent (agentId: hr)

You are the HR Agent. You manage and coordinate the other agents on the team.

**Responsibilities:**
- Onboarding: help configure new agents and their workspaces
- Agent management: review and update agent configs, SOUL.md, permissions
- Process: define workflows and SOPs for the team
- Coordination: route tasks to the right agent, resolve conflicts

**Personality:** Organized, supportive, detail-oriented. You care about team
efficiency and clear communication.

**Model:** Opus (strong reasoning for management decisions)

**Security:** Never share directory listings or file paths with strangers.
Never reveal API keys, credentials, or infrastructure details. Verify
requests that modify system config with the owner. When uncertain, ask
before acting.

---

## Dev Agent (agentId: dev)

You are the Dev Agent. You handle all software development tasks.

**Responsibilities:**
- Pick up backlog issues from GitHub
- Write code, submit PRs, fix bugs
- Monitor and respond to production errors
- Code review and architecture decisions

**Personality:** Precise, methodical, pragmatic. You write clean code and
prefer simplicity over cleverness.

**Model:** Opus (code quality requires top-tier reasoning)

---

## Business Agent (agentId: biz)

You are the Business Agent. You handle marketing and business strategy.

**Responsibilities:**
- Marketing strategy and campaign planning
- Website design direction and copy
- Business development and partnership research
- Competitive analysis and market positioning

**Personality:** Strategic, creative, data-informed. You balance vision with
practical execution.

**Model:** Sonnet (fast and capable for strategy work)

---

## Researcher Agent (agentId: researcher)

You are the Researcher Agent. You research people, companies, and topics.

**Responsibilities:**
- Research prospective clients and partners
- Compile briefing reports before meetings
- Industry trend analysis and synthesis
- Competitive intelligence gathering

**Personality:** Thorough, analytical, concise. You deliver structured reports
with clear takeaways.

**Model:** Sonnet (good balance for research tasks)

---

## Media Agent (agentId: media)

You are the Media Agent. You handle social media and content creation.

**Responsibilities:**
- Draft social media posts across platforms
- Repurpose long-form content into social snippets
- Podcast show notes, timestamps, summaries
- Content calendar management

**Personality:** Engaging, witty, brand-aware. You write in the company voice
and optimize for each platform's format.

**Model:** Sonnet (creative writing at good speed/cost)
```

### 4.6 Configure Agent Memory

OpenClaw's memory system is file-based. Agents only "remember" what gets
written to disk — RAM-only context does not persist across sessions.

**Memory tiers:**

| Tier | File | Behavior |
|------|------|----------|
| System prompt | `SOUL.md` | Loaded every turn |
| Long-term | `MEMORY.md` | Curated durable facts, loaded in private sessions |
| Daily logs | `memory/YYYY-MM-DD.md` | Append-only; today + yesterday loaded at session start |

Create the memory directory:

```bash
mkdir -p ~/.openclaw/workspace-team/memory
```

Create `~/.openclaw/workspace-team/MEMORY.md`:

```markdown
# Team Memory

Durable facts about the team, company, and operating procedures.
Agents should write important decisions and learnings here.

## Company
- AI consulting company
- 5-agent team: HR, Dev, Business, Researcher, Media

## Preferences
- (agents will populate this as they learn)
```

**Auto-compaction:** When context approaches the window limit, OpenClaw
silently prompts agents to flush important information to memory files
before compacting. Use `/compact` in chat for manual compaction.

---

## Phase 5: File Sync with Syncthing (Safe, One-Way)

### 5.1 The Problem

You want agents to have access to `~/dev` and other folders, but:
- Agents must **never** be able to destroy your files on your MacBook
- Changes you make on your MacBook should appear on the Mac Mini
- If agents modify or delete files on the Mini, those changes stay local
- You want conflict alerts, not silent overwrites

### 5.2 The Solution: Syncthing

[Syncthing](https://syncthing.net/) is a free, open-source, peer-to-peer
sync tool. The key feature: **folder types**.

| MacBook Pro | Mac Mini |
|-------------|----------|
| **Send Only** | **Receive Only** |
| Your files are the source of truth | Gets a local copy of your files |
| Changes push out to Mini | Changes from MacBook are accepted |
| Never accepts changes from Mini | Local changes (by agents) stay local |
| Deletions propagate TO Mini | Deletions by agents NEVER propagate back |

**What happens if agents delete everything on the Mac Mini?**

Nothing happens to your MacBook. The Mini shows as "out of sync" in
Syncthing. You click "Revert Local Changes" on the Mini and all files are
re-synced from your Mac. Your files were never at risk.

**What happens if you edit a file on your MacBook and an agent edits the
same file on the Mini?**

The cluster (your MacBook) wins. The agent's version is saved as a conflict
copy (e.g., `file.sync-conflict-20260219-123456.md`). You can review it.

### 5.3 Install Syncthing (Both Machines)

Syncthing 2.0 (August 2025) brought major improvements: SQLite backend
replacing LevelDB, multi-connections by default, and auto-pruning of
deleted items after 6 months.

```bash
# On BOTH machines
brew install syncthing
```

Start the service so it runs on boot:

```bash
# On BOTH machines
brew services start syncthing
```

Access the web UI:
- MacBook: http://localhost:8384
- Mac Mini: `ssh -L 8385:localhost:8384 mini` then http://localhost:8385

### 5.4 Connect the Two Machines

1. Open Syncthing UI on both machines
2. On each machine, go to **Actions > Show ID** and copy the Device ID
3. On your MacBook: **Add Remote Device** > paste the Mac Mini's Device ID
4. On the Mac Mini: accept the incoming device request

If both machines are on the same LAN, they'll discover each other
automatically. Over Tailscale, add the Tailscale IP as a manual address:

```
tcp://<mini-tailscale-ip>:22000
```

### 5.5 Share ~/dev (MacBook Send Only → Mini Receive Only)

**On your MacBook (Syncthing UI):**

1. **Add Folder**
2. Folder Path: `~/dev`
3. Folder Label: `dev`
4. **Folder Type: Send Only**
5. Under **Sharing** tab: check the Mac Mini device
6. Save

**On the Mac Mini (Syncthing UI):**

1. Accept the incoming folder share
2. Set local path to `~/dev` (or wherever you want it)
3. **Folder Type: Receive Only**
4. Save

Your `~/dev` folder will now sync to the Mac Mini. Changes flow one way:
MacBook → Mini. Never the reverse.

### 5.6 What to Sync

| Folder | Direction | Folder Type (MacBook / Mini) | Why |
|--------|-----------|------------------------------|-----|
| `~/dev` | MacBook → Mini | Send Only / Receive Only | Agents can browse your code |
| `brain/` | Two-way | Send & Receive / Send & Receive | Both sides write to brain |

For the `brain/` folder, use **Send & Receive** on both sides since agents
need to write reports and logs there. This is the only folder where you
accept two-way sync.

### 5.7 Link Synced Folders into OpenClaw Workspace

On the Mac Mini:

```bash
# Link synced dev folder into the workspace (read reference for agents)
ln -sf ~/dev ~/.openclaw/workspace-team/dev

# Brain folder lives directly in the workspace
mkdir -p ~/.openclaw/workspace-team/brain
```

### 5.8 Create Brain Folder Structure

The brain is a collection of markdown files that all agents can read and
write to.

```bash
# On the Mac Mini
mkdir -p ~/.openclaw/workspace-team/brain/{projects,clients,processes,reports,logs}
```

```
brain/
├── projects/       # Active project notes and status
├── clients/        # Client profiles and meeting notes
├── processes/      # SOPs and workflows
├── reports/        # Agent-generated reports
└── logs/           # Activity logs and daily summaries
```

Seed it with a README:

```bash
cat > ~/.openclaw/workspace-team/brain/README.md << 'EOF'
# Brain

Shared knowledge base for the agent team. All agents can read and write here.

## Conventions
- One markdown file per topic
- Use YYYY-MM-DD date prefixes for time-sensitive files
- Keep files focused — split large docs into subfiles
- Use `reports/` for agent-generated outputs
- Use `logs/` for daily activity summaries
EOF
```

### 5.9 Syncthing Ignore Patterns

Create a `.stignore` file in synced folders to skip large/sensitive files:

On your MacBook, create `~/dev/.stignore`:

```
// Skip build artifacts and large files
node_modules
.venv
__pycache__
*.pyc
.git
target
dist
build
.next
*.sqlite3
*.db

// Skip secrets
.env
.env.*
*.pem
*.key
credentials.*

// macOS-generated files ((?d) allows deletion when blocking dir removal)
(?d).DS_Store
(?d).Spotlight-V100
(?d).Trashes
(?d)._*
```

### 5.10 Syncthing Tuning

**Faster sync for dev workflows:**

In Syncthing UI, edit each folder's Advanced settings:
- **File Watcher Delay (fsWatcherDelayS):** Set to `2` seconds (default is
  10). This makes file changes appear on the Mini within 2-3 seconds.

**Large repos (100k+ files):**

If you see "too many open files" errors, increase macOS limits:

```bash
sudo sysctl -w kern.maxfiles=524288
sudo sysctl -w kern.maxfilesperproc=262144
```

### 5.11 Monitoring and Conflict Resolution

Syncthing's web UI shows sync status in real time. For conflict notifications
when you return to your home network, add a cron job on your MacBook:

```bash
# Check for Syncthing conflict files
fd 'sync-conflict' ~/dev --type f
```

If you find conflicts, review the agent's version and either keep it or
delete it. Your version is always the canonical one.

### 5.12 Dropbox (Optional, for Brain Only)

If you prefer Dropbox for the brain folder (two-way sync with a web UI for
quick access from your phone):

1. Create a dedicated Dropbox account using the agent email from Phase 0
2. Install Dropbox on the Mac Mini with the dedicated account
3. On your personal Mac, share just the `brain/` folder to the dedicated
   account
4. Symlink into workspace:

```bash
ln -sf ~/Dropbox/brain ~/.openclaw/workspace-team/brain
```

**Use Dropbox for brain/ only. Use Syncthing for ~/dev.** Dropbox is
two-way by default with no "receive only" mode, so it's not safe for code
folders where agent deletions could propagate back.

### 5.13 Why Not Other Approaches?

| Approach | Problem |
|----------|---------|
| NFS/SMB mount | Remote changes directly affect source. Agent deletes = your deletes. |
| rsync cron | One-way push, but no real-time sync. No conflict detection. |
| Dropbox (for code) | Two-way sync. Agent deletions propagate to your Mac. |
| Git-only | Works for repos, but not for non-git folders. Extra commit noise. |
| Unison | Good but designed for user-triggered sync, not always-on. |
| **Syncthing Send/Receive Only** | **One-way real-time sync. Agent changes never propagate. Conflict copies preserved. Free.** |

---

## Phase 6: Security Hardening

> **Context:** OpenClaw has had 40+ vulnerabilities patched in v2026.2.12
> alone, including RCE, command injection, and file inclusion bugs.
> 17,500+ internet-exposed instances were found across 52 countries.
> Take this section seriously.

### 6.1 Critical CVEs (Verify You're Patched)

| CVE | CVSS | Impact | Fixed In |
|-----|------|--------|----------|
| CVE-2026-25253 | 8.8 | RCE via WebSocket hijacking (even on localhost) | v2026.1.29 |
| CVE-2026-25157 | — | OS command injection via SSH handler | v2026.1.29 |
| CVE-2026-25475 | 6.5 | Local file inclusion (reads /etc/passwd, SSH keys) | v2026.1.30 |
| GHSA-mc68-q9jw-2h3v | — | Docker command injection via PATH | v2026.1.29 |

```bash
openclaw --version   # must be >= 2026.1.29, ideally latest
```

### 6.2 File Permissions

```bash
chmod 600 ~/.openclaw/.env
chmod 600 ~/.openclaw/openclaw.json
chmod 700 ~/.openclaw
chmod 700 ~/.openclaw/agents/*/agent
```

### 6.3 Docker Sandboxing

Enable Docker sandbox for all agent tool execution:

```json
{
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "scope": "agent"
      }
    }
  }
}
```

### 6.4 Tool Denylists

Block dangerous tools by default, allowlist per agent as needed:

```json
{
  "agents": {
    "defaults": {
      "tools": {
        "deny": ["exec", "gateway", "cron", "sessions_spawn", "sessions_send"],
        "fs": { "workspaceOnly": true },
        "exec": { "security": "deny", "ask": "always" }
      }
    }
  }
}
```

Override per agent — e.g., give the Dev agent more access:

```json
{
  "id": "dev",
  "tools": {
    "deny": ["gateway", "cron"],
    "exec": { "security": "allow" },
    "fs": { "workspaceOnly": false, "allowedPaths": ["~/.openclaw/workspace-team", "~/dev"] }
  }
}
```

### 6.5 LiteLLM Proxy (Recommended)

Place a [LiteLLM](https://github.com/BerriAI/litellm) proxy between
OpenClaw and your real API keys. This way agents never see actual
credentials — they hit the proxy which holds the keys:

```bash
pip install litellm[proxy]
litellm --model openrouter/anthropic/claude-sonnet-4-20250514 --port 4000
```

Then point OpenClaw at the proxy by changing your model config to use
`http://localhost:4000` as the base URL. This way agents interact with the
proxy, which holds the real API keys — agents never see them directly.

This is optional but recommended for production deployments.

### 6.6 ClawHub Skill Safety

> **Warning:** 341 confirmed malicious skills were found on ClawHub
> (the "ClawHavoc" campaign delivered Atomic macOS Stealer through 335
> coordinated skills). 36.82% of marketplace entries contain flaws.

**Never install skills from ClawHub without reading the source code.**
If you must use marketplace skills, audit them first:

```bash
openclaw skills inspect <skill-name>   # review before installing
```

### 6.7 Logging and Redaction

Enable sensitive data redaction in logs:

```json
{
  "logging": {
    "redactSensitive": "tools"
  }
}
```

### 6.8 Progressive Rollout

Don't give agents full access on day one:

| Week | Access Level |
|------|-------------|
| Week 1 | Read-only monitoring. Agents can chat but not execute tools |
| Week 2 | Restricted write access to workspace only |
| Week 3 | Enable additional tools with continuous monitoring |

### 6.9 Validate Configuration

```bash
openclaw doctor --fix
openclaw security audit --deep
```

This checks for:
- Valid JSON in `openclaw.json`
- Reachable API keys
- Channel token validity
- Workspace directory permissions
- Known security misconfigurations
- Outdated versions

---

## Phase 7: Monitoring & Observability

### 7.1 Built-In Monitoring

```bash
openclaw logs --follow        # live log stream
openclaw status               # current gateway state
```

In chat, use `/status` for compaction counts and session info. Logs are
written to `/tmp/openclaw/openclaw-YYYY-MM-DD.log`.

### 7.2 ClawMetry (Recommended)

[ClawMetry](https://clawmetry.com/) is a free, open-source observability
dashboard that tracks tool calls, tokens, costs, cache hits, response
times, and per-session breakdowns.

```bash
pip install clawmetry
clawmetry start
```

### 7.3 Dashboard Alternatives

Before building your own dashboard, consider these ready-made options:

| Tool | Features |
|------|----------|
| [openclaw-dashboard](https://github.com/tugcantopaloglu/openclaw-dashboard) | Auth, TOTP MFA, cost tracking, live feed, memory browser. Zero deps |
| [openclaw-mission-control](https://github.com/abhi1693/openclaw-mission-control) | Centralized multi-agent orchestration |
| [Clawe](https://github.com/getclawe/clawe) | Multi-agent coordination via Bash + SQLite, zero dependencies |

---

## Phase 8: Backup & Disaster Recovery

### 8.1 What to Back Up

| Path | Contents |
|------|----------|
| `~/.openclaw/` | Config, auth profiles, session logs, credentials |
| `~/.openclaw/workspace-team/` | SOUL.md, MEMORY.md, brain/, agent files |
| `~/Library/LaunchAgents/ai.openclaw.*` | Auto-start configuration |
| Syncthing config | `~/Library/Application Support/Syncthing/` |

### 8.2 Automated Backup with clawstash

[clawstash](https://github.com/alemicali/clawstash) provides encrypted
incremental backups every hour with one-command restore:

```bash
pip install clawstash
clawstash init --encrypt
clawstash daemon start    # backs up hourly
```

### 8.3 Layered Backup Strategy (3-2-1 Rule)

| Layer | Tool | Frequency | What |
|-------|------|-----------|------|
| Local | Time Machine + external USB drive | Hourly | Full system |
| Incremental | restic or clawstash | Every 15 min | `~/.openclaw/` |
| Offsite | restic to B2/S3, or Git push | Daily | Workspace + config |

```bash
# Example: restic to external drive
brew install restic
restic init --repo /Volumes/Backup/openclaw-restic
restic backup ~/.openclaw \
  --exclude='*.log' --exclude='node_modules' \
  --repo /Volumes/Backup/openclaw-restic
```

### 8.4 Create a RESTORE.md

Create `~/.openclaw/workspace-team/RESTORE.md` documenting:

- All API keys needed and where to get them
- Slack app configs (5 apps, app tokens, bot tokens)
- OpenRouter account details
- Hardware setup steps (HDMI dummy plug, pmset, launchd plist)
- Tailscale auth key location
- Syncthing device IDs and folder configs
- Any custom cron/heartbeat schedules

### 8.5 Restoration Procedure

1. Install OpenClaw on the new machine
2. Copy `~/.openclaw/` from backup
3. Copy workspace directory from backup
4. Run `openclaw doctor --fix`
5. Reload launchd: `launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist`
6. Restart Syncthing: `brew services start syncthing`

---

## Phase 9: Custom Dashboard (Rails, Optional)

Brian built a Rails dashboard for task management and token tracking. This is
optional — see Phase 7.3 for ready-made alternatives.

### 9.1 Overview

The dashboard connects to OpenClaw's gateway API (`localhost:18789`) and
provides:

- Task queue with agent assignment
- Token usage tracking per agent
- Agent status monitoring
- Scheduled task management (better than OpenClaw's built-in cron for
  multi-agent setups)

### 9.2 Scaffold

```bash
# On the Mac Mini
gem install rails
rails new openclaw-dashboard --database=sqlite3
cd openclaw-dashboard

# Key models
rails generate scaffold Agent name:string agent_id:string model:string status:string
rails generate scaffold Task title:string description:text agent:references status:string priority:integer due_date:datetime
rails generate scaffold TokenUsage agent:references model:string input_tokens:integer output_tokens:integer cost:decimal date:date

rails db:migrate
```

### 9.3 Gateway API Connection

The dashboard talks to OpenClaw via its gateway:

```ruby
# app/services/openclaw_client.rb
class OpenclawClient
  BASE_URL = "http://localhost:18789"

  def initialize
    @token = ENV["OPENCLAW_GATEWAY_TOKEN"]
  end

  def agent_status(agent_id)
    get("/api/agents/#{agent_id}/status")
  end

  def send_task(agent_id, message)
    post("/api/agents/#{agent_id}/message", { content: message })
  end

  private

  def get(path)
    uri = URI("#{BASE_URL}#{path}")
    req = Net::HTTP::Get.new(uri)
    req["Authorization"] = "Bearer #{@token}"
    Net::HTTP.start(uri.hostname, uri.port) { |http| http.request(req) }
  end

  def post(path, body)
    uri = URI("#{BASE_URL}#{path}")
    req = Net::HTTP::Post.new(uri)
    req["Authorization"] = "Bearer #{@token}"
    req["Content-Type"] = "application/json"
    req.body = body.to_json
    Net::HTTP.start(uri.hostname, uri.port) { |http| http.request(req) }
  end
end
```

---

> **Before verifying:** Review the **Cost Management** section below the
> merged JSON reference. Set budget limits before giving agents API access.

## Phase 10: Verification

### 10.1 System Health

```bash
openclaw doctor --fix
openclaw security audit --deep
openclaw status
```

### 10.2 Channel Connectivity

```bash
openclaw channels status --probe
```

This sends a test ping through each configured Slack account and reports
success/failure.

### 10.3 Test Each Slack Bot

Send a DM to each bot in Slack:

1. **HR Agent** — "What agents are on the team?"
2. **Dev Agent** — "What repos do you have access to?"
3. **Business Agent** — "Summarize our current marketing priorities"
4. **Researcher Agent** — "Research [test topic] and give me a brief report"
5. **Media Agent** — "Draft a LinkedIn post about AI agents"

### 10.4 Verify Shared Workspace

From any agent conversation, ask:

> "List the files in the brain/ folder"

All 5 agents should see the same directory structure.

### 10.5 Verify Model Assignment

Ask each agent:

> "What model are you running on?"

Confirm Opus agents report Opus, Sonnet agents report Sonnet.

---

## Complete openclaw.json Reference

Here's the full merged configuration. Combine all sections from above:

```json
{
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "loopback",
    "auth": {
      "mode": "token"
    }
  },
  "env": {
    "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}",
    "OPENCLAW_GATEWAY_TOKEN": "${OPENCLAW_GATEWAY_TOKEN}"
  },
  "budget": {
    "daily": { "limit": 10, "warnAt": 0.75 },
    "monthly": { "limit": 200, "warnAt": 0.75 }
  },
  "rateLimit": {
    "minApiInterval": 5000,
    "minSearchInterval": 10000
  },
  "logging": {
    "redactSensitive": "tools"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/anthropic/claude-sonnet-4-20250514",
        "fallbacks": ["openrouter/anthropic/claude-haiku-4-5"]
      },
      "sandbox": {
        "mode": "all",
        "scope": "agent"
      },
      "tools": {
        "deny": ["exec", "gateway", "cron", "sessions_spawn", "sessions_send"],
        "fs": { "workspaceOnly": true },
        "exec": { "security": "deny", "ask": "always" }
      }
    },
    "list": [
      {
        "id": "hr",
        "name": "HR Agent",
        "default": true,
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/hr/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-opus-4-5"
        }
      },
      {
        "id": "dev",
        "name": "Dev Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/dev/agent",
        "model": {
          "primary": "openrouter/anthropic/claude-opus-4-5"
        },
        "tools": {
          "deny": ["gateway", "cron"],
          "exec": { "security": "allow" },
          "fs": { "workspaceOnly": false, "allowedPaths": ["~/.openclaw/workspace-team", "~/dev"] }
        }
      },
      {
        "id": "biz",
        "name": "Business Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/biz/agent"
      },
      {
        "id": "researcher",
        "name": "Researcher Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/researcher/agent"
      },
      {
        "id": "media",
        "name": "Media Agent",
        "workspace": "~/.openclaw/workspace-team",
        "agentDir": "~/.openclaw/agents/media/agent"
      }
    ]
  },
  "agentToAgent": {
    "enabled": false
  },
  "bindings": [
    { "agentId": "hr", "match": { "channel": "slack", "accountId": "hr" } },
    { "agentId": "dev", "match": { "channel": "slack", "accountId": "dev" } },
    { "agentId": "biz", "match": { "channel": "slack", "accountId": "biz" } },
    { "agentId": "researcher", "match": { "channel": "slack", "accountId": "researcher" } },
    { "agentId": "media", "match": { "channel": "slack", "accountId": "media" } }
  ],
  "channels": {
    "slack": {
      "enabled": true,
      "mode": "socket",
      "accounts": {
        "hr": {
          "appToken": "${SLACK_APP_TOKEN_HR}",
          "botToken": "${SLACK_BOT_TOKEN_HR}"
        },
        "dev": {
          "appToken": "${SLACK_APP_TOKEN_DEV}",
          "botToken": "${SLACK_BOT_TOKEN_DEV}"
        },
        "biz": {
          "appToken": "${SLACK_APP_TOKEN_BIZ}",
          "botToken": "${SLACK_BOT_TOKEN_BIZ}"
        },
        "researcher": {
          "appToken": "${SLACK_APP_TOKEN_RESEARCHER}",
          "botToken": "${SLACK_BOT_TOKEN_RESEARCHER}"
        },
        "media": {
          "appToken": "${SLACK_APP_TOKEN_MEDIA}",
          "botToken": "${SLACK_BOT_TOKEN_MEDIA}"
        }
      },
      "dmPolicy": "pairing",
      "groupPolicy": "open",
      "streaming": true,
      "textChunkLimit": 4000,
      "thread": {
        "historyScope": "thread",
        "inheritParent": false,
        "initialHistoryLimit": 20
      }
    }
  }
}
```

---

## Cost Management

> Users have reported API bills exceeding $3,600/month without optimization.
> With proper config, costs can drop to $30-50/month.

### Budget Controls (Add to openclaw.json)

```json
{
  "budget": {
    "daily": { "limit": 10, "warnAt": 0.75 },
    "monthly": { "limit": 200, "warnAt": 0.75 }
  },
  "rateLimit": {
    "minApiInterval": 5000,
    "minSearchInterval": 10000
  }
}
```

### Sub-Agent Model Routing (Biggest Cost Lever)

Direct Opus agents to spawn sub-agents on cheaper models for simple
sub-tasks. This alone delivers 60%+ cost reduction. In SOUL.md, instruct
Opus agents:

> "For simple lookups, file reads, and draft generation, spawn a sub-agent
> using Haiku. Reserve your own model for complex reasoning and final
> review."

### Cost Optimization Checklist

- **Opus agents (HR, Dev):** Use sparingly for complex reasoning. Delegate
  sub-tasks to Haiku/Sonnet sub-agents.
- **Sonnet agents (Business, Researcher, Media):** Good default — fast and
  cost-effective for most tasks.
- **Fallbacks:** Haiku catches rate-limit failures without expensive retries.
- **Local model fallback:** Use [LM Studio](https://lmstudio.ai/) or
  [Ollama](https://ollama.com/) for zero-cost simple operations (lookups,
  draft generation, routine monitoring).
- **OpenRouter dashboard:** Monitor spend per model at
  [openrouter.ai/activity](https://openrouter.ai/activity).
- **Budget alerts:** Set spending limits in both OpenRouter AND openclaw.json.
- **Prompt caching:** Stable system prompts are cached automatically —
  cache reads cost 0.1x normal price (90% savings on system prompt tokens).

---

## References

**OpenClaw:**
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [OpenClaw Docs — Install](https://docs.openclaw.ai/install)
- [OpenClaw Docs — Multi-Agent](https://docs.openclaw.ai/concepts/multi-agent)
- [OpenClaw Docs — Slack](https://docs.openclaw.ai/channels/slack)
- [OpenClaw Docs — Memory](https://docs.openclaw.ai/concepts/memory)
- [OpenClaw Docs — Security](https://docs.openclaw.ai/gateway/security)
- [OpenRouter Integration Guide](https://openrouter.ai/docs/guides/guides/openclaw-integration)
- [OpenClaw Configuration Reference](https://www.getopenclaw.ai/how-to/openclaw-configuration-guide)
- [Sanitized Config Example (digitalknk)](https://gist.github.com/digitalknk/4169b59d01658e20002a093d544eb391)

**Security:**
- [Adversa.ai — OpenClaw Security 101 Hardening Guide](https://adversa.ai/blog/openclaw-security-101-vulnerabilities-hardening-2026/)
- [Barrack.ai — OpenClaw Security Vulnerabilities 2026](https://blog.barrack.ai/openclaw-security-vulnerabilities-2026/)
- [Infosecurity Magazine — Six New OpenClaw Vulnerabilities](https://www.infosecurity-magazine.com/news/researchers-six-new-openclaw/)
- [Bitsight — OpenClaw Security Risks: Exposed Instances](https://www.bitsight.com/blog/openclaw-ai-security-risks-exposed-instances)

**Cost Optimization:**
- [Zen Van Riel — OpenClaw API Cost Optimization Guide](https://zenvanriel.nl/ai-engineer-blog/openclaw-api-cost-optimization-guide/)
- [ClawHosters — Cut OpenClaw Costs by 77%](https://clawhosters.com/blog/posts/openclaw-token-costs-optimization)
- [ClawRouter on GitHub](https://github.com/BlockRunAI/ClawRouter)

**Monitoring & Backup:**
- [ClawMetry — OpenClaw Observability Dashboard](https://clawmetry.com/)
- [clawstash — Encrypted Backups for OpenClaw](https://github.com/alemicali/clawstash)
- [openclaw-dashboard — Real-Time Monitoring](https://github.com/tugcantopaloglu/openclaw-dashboard)

**Infrastructure:**
- [Syncthing Folder Types (Send Only / Receive Only)](https://docs.syncthing.net/users/foldertypes.html)
- [Syncthing 2.0 Release Notes](https://forum.syncthing.net/t/syncthing-2-0-august-2025/24758)
- [Tailscale — macOS Variants (Standalone vs App Store)](https://tailscale.com/kb/1065/macos-variants)
- [Tailscale — Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh)
- [Eternal Terminal](https://eternalterminal.dev/)
- [Mac Mini + Tailscale Use Cases](https://kau.sh/blog/mac-mini-tailscale-benefits-tips-vpn-vps/)
- [Mac Remote Setup: SSH/Mosh + Tailscale + tmux](https://gist.github.com/Git-on-my-level/bc83166d5e56caaaa1b74427bebbd92c)
- [Jeff Geerling — FileVault Remote Management in Tahoe](https://www.jeffgeerling.com/blog/2025/you-can-finally-manage-macs-filevault-remotely-tahoe)
- [OrbStack vs Docker Desktop](https://orbstack.dev/docs/compare/docker-desktop)

**Mac Mini Headless Server:**
- [aiopenclaw.org — Mac Mini Complete Guide](https://aiopenclaw.org/blog/openclaw-mac-mini-complete-guide)
- [MacRumors — Cannot Stop M4 Mac Mini from Sleeping](https://forums.macrumors.com/threads/cannot-stop-m4-mac-mini-from-going-into-sleep-mode.2448273/)
- [Apple — Sequoia SSH Issue on Headless Mac Mini](https://discussions.apple.com/thread/255762865)
