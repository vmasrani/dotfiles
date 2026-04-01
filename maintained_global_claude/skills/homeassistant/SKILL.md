---
name: homeassistant
description: Configure and manage Home Assistant — create automations, scripts, scenes, dashboards, light routines, integrations, and YAML config. Use this skill whenever the user mentions home assistant, HA, smart home, lights, automations, routines, Lutron, Caseta, Chromecast, or wants to control any home device. Also use when the user says things like "turn on the lights", "set up a routine", "dim the kitchen", or anything related to smart home control and configuration.
---

# Home Assistant Manager

Full management of a Home Assistant Docker installation. Create automations, scripts, scenes, dashboards, and configure integrations — all via YAML files or the HA REST API.

## Setup Overview

- **Install type:** Docker container on Mac Mini (OrbStack)
- **HA version:** 2026.3.1
- **Docker compose:** `/Users/vmasrani/dev/homeassistant/docker-compose.yml`
- **Config directory:** `/Users/vmasrani/dev/homeassistant/config/`
- **Network mode:** `host` (required for mDNS device discovery)
- **Timezone:** `America/Vancouver`
- **Location:** Vancouver, BC, Canada (49.28N, -123.12W)
- **Currency:** CAD
- **Web UI:** `http://localhost:8123` (from Mac Mini) or `http://100.123.228.17:8123` (via Tailscale)
- **Mac Mini Tailscale IP:** `100.123.228.17`

## Config Files

| File | Purpose | Format |
|------|---------|--------|
| `config/configuration.yaml` | Main config — integrations, HTTP settings, includes | YAML |
| `config/automations.yaml` | All automations (UI-created ones also go here) | YAML list |
| `config/scripts.yaml` | Reusable action sequences | YAML dict |
| `config/scenes.yaml` | Saved state snapshots | YAML list |
| `config/secrets.yaml` | Passwords and API keys (use `!secret key_name` to reference) | YAML dict |
| `config/.storage/` | UI-configured data — never hand-edit these | JSON |

When editing `automations.yaml` or `scenes.yaml`, the file contains a YAML list (starts with `- `). When editing `scripts.yaml`, the file contains a YAML dict (top-level keys are script IDs).

## Entities

### Lights (Lutron Caseta dimmers — all PD-6WCL-XX WallDimmer)

| Entity ID | Name | Area |
|-----------|------|------|
| `light.dining_room_chandelier` | Dining Room Chandelier | Dining Room |
| `light.living_room_overhead_lights` | Living Room Overhead Lights | Living Room |
| `light.kitchen_island_pendants` | Kitchen Island Pendants | Kitchen |
| `light.kitchen_main_lights` | Kitchen Main Lights | Kitchen |
| `light.stairs_main_lights` | Stairs Main Lights | Stairs |
| `light.front_foyer_main_lights` | Front Foyer Main Lights | Front Foyer |

### Switches (Lutron Caseta — PD-8ANS-XX WallSwitch, on/off only)

| Entity ID | Name |
|-----------|------|
| `switch.kitchen_under_cabinet` | Kitchen Under Cabinet |
| `switch.front_foyer_laundry_room` | Front Foyer Laundry Room |

### Pico Remotes (Lutron Caseta)

| Entity ID | Name |
|-----------|------|
| `button.front_foyer_pico_on` / `_off` | Front Foyer Pico (2-button) |
| `button.upstairs_hallway_pico_on` / `_stop` / `_off` / `_raise` / `_lower` | Upstairs Hallway Pico (3-button raise/lower) |

### Media Players (Google Cast)

| Entity ID | Name | Device |
|-----------|------|--------|
| `media_player.tv` | TV | Google TV Streamer |
| `media_player.audio` | Audio | Google Cast Group |
| `media_player.kitchen_display` | Kitchen display | Google Nest Hub |

### Other Entities

| Entity ID | Purpose |
|-----------|---------|
| `person.vaden_masrani` | Presence detection |
| `weather.forecast_home` | Weather (Met.no) |
| `sun.sun` | Sunrise/sunset times |
| `todo.shopping_list` | Shopping list |
| `tts.google_translate_en_com` | Text-to-speech |
| `scene.evening_lights` | Lutron "Evening Lights" scene |

### Areas

`living_room`, `kitchen`, `bedroom`, `front_foyer`, `upstairs_hallway`, `dining_room`, `stairs`

## Integrations

| Integration | Protocol | Bridge/Hub |
|-------------|----------|------------|
| Lutron Caseta | LEAP over LAN | Smart Bridge 2 (L-BDG2-WH) at `192.168.86.30` |
| Google Cast | mDNS/Cast protocol | Direct (no hub) |
| Met.no | HTTP API | None |
| Sun | Local calculation | None |

## Hardware Constraints

**Caseta dimmers ignore the `transition` parameter.** The hardware caps fade at ~4 seconds. To do slow transitions (sunrise over 30 min), use a looping script that increments brightness by 1% with delays between steps.

**Caseta switches are on/off only.** No dimming, no brightness control. Use `switch.turn_on` / `switch.turn_off`, not `light.turn_on`.

**Chromecasts use Google DNS (8.8.8.8).** Always use IP addresses in media URLs, not `.local` hostnames.

## How to Make Changes

### Approach 1: Edit YAML Files Directly (preferred for this skill)

Edit the YAML files in `config/`, then reload:

```bash
# Reload automations (no restart needed)
docker exec homeassistant python3 -c "
import requests
requests.post('http://localhost:8123/api/services/automation/reload',
  headers={'Authorization': 'Bearer TOKEN'})
"

# Or just restart the container (always works)
docker compose -f /Users/vmasrani/dev/homeassistant/docker-compose.yml restart
```

For quick reloads without restart, use the HA REST API (read the long-lived access token from the UI: Profile > Security > Long-Lived Access Tokens). But restarting the container is always safe and takes ~30 seconds.

### Approach 2: HA REST API

The REST API can be used for real-time control and querying state:

```bash
# Get entity state
curl -s http://localhost:8123/api/states/light.kitchen_main_lights \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -m json.tool

# Call a service
curl -s -X POST http://localhost:8123/api/services/light/turn_on \
  -H "Authorization: Bearer $HA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.kitchen_main_lights", "brightness_pct": 50}'

# Fire an event
curl -s -X POST http://localhost:8123/api/events/my_custom_event \
  -H "Authorization: Bearer $HA_TOKEN"
```

Note: the token must be created in the HA UI first (Profile > Security > Long-Lived Access Tokens). If no token exists yet, guide the user to create one.

## YAML Patterns

### Automation

```yaml
# automations.yaml is a list — each automation starts with -
- id: "unique_id_here"
  alias: "Human-readable name"
  description: "What this does"
  mode: single  # single, restart, queued, parallel
  trigger:
    - trigger: state  # entity state change
      entity_id: light.kitchen_main_lights
      to: "on"
    - trigger: time   # specific time
      at: "07:00:00"
    - trigger: sun    # sunrise/sunset
      event: sunset
      offset: "-00:30:00"  # 30 min before sunset
    - trigger: numeric_state  # threshold
      entity_id: sensor.sun_solar_elevation
      below: 5
  condition:
    - condition: state
      entity_id: person.vaden_masrani
      state: "home"
    - condition: time
      after: "06:00:00"
      before: "23:00:00"
  action:
    - action: light.turn_on
      target:
        entity_id: light.kitchen_main_lights
      data:
        brightness_pct: 80
    - delay:
        seconds: 5
    - action: light.turn_off
      target:
        entity_id: light.kitchen_main_lights
```

### Script

```yaml
# scripts.yaml is a dict — top-level keys are script IDs
sunrise_routine:
  alias: "Sunrise Routine"
  icon: "mdi:weather-sunset-up"
  mode: restart
  fields:
    target_brightness:
      description: "Final brightness percentage"
      default: 100
      selector:
        number:
          min: 1
          max: 100
  sequence:
    - repeat:
        count: "{{ target_brightness }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id:
                - light.kitchen_main_lights
                - light.living_room_overhead_lights
            data:
              brightness_pct: "{{ repeat.index }}"
          - delay:
              seconds: 18  # 100 steps x 18s = 30 min
```

### Scene

```yaml
# scenes.yaml is a list
- id: "movie_mode"
  name: "Movie Mode"
  entities:
    light.living_room_overhead_lights:
      state: "on"
      brightness: 25  # 0-255 scale
    light.kitchen_main_lights:
      state: "off"
    light.dining_room_chandelier:
      state: "off"
    switch.kitchen_under_cabinet:
      state: "off"
```

### Useful Light Groups

To target multiple lights at once, either list them in `target.entity_id` or define a group in `configuration.yaml`:

```yaml
# In configuration.yaml
light:
  - platform: group
    name: "Kitchen All"
    entities:
      - light.kitchen_main_lights
      - light.kitchen_island_pendants

  - platform: group
    name: "Downstairs All"
    entities:
      - light.kitchen_main_lights
      - light.kitchen_island_pendants
      - light.living_room_overhead_lights
      - light.dining_room_chandelier
      - light.front_foyer_main_lights
```

## Templates (Jinja2)

HA uses Jinja2 for dynamic values in automations and scripts:

```yaml
# Time-based brightness
brightness_pct: >
  {% if now().hour < 7 %}
    30
  {% elif now().hour < 18 %}
    100
  {% else %}
    60
  {% endif %}

# Sun elevation-based brightness (dimmer as sun sets)
brightness_pct: >
  {{ [[(state_attr('sun.sun', 'elevation') * 3) | int, 10] | max, 100] | min }}

# Current state of an entity
{{ states('light.kitchen_main_lights') }}

# Attribute of an entity
{{ state_attr('light.kitchen_main_lights', 'brightness') }}

# Time math
{{ as_timestamp(now()) - as_timestamp(states.light.kitchen_main_lights.last_changed) > 3600 }}
```

## Slow Light Transition Pattern

Since Caseta ignores `transition`, use this pattern for gradual changes:

```yaml
# Script: gradual brightness change over N minutes
gradual_brightness:
  alias: "Gradual Brightness"
  mode: restart  # restart cancels previous run if called again
  fields:
    target_lights:
      description: "Light entity IDs"
      selector:
        entity:
          domain: light
          multiple: true
    target_brightness:
      description: "Target brightness (0-100)"
      selector:
        number:
          min: 0
          max: 100
    duration_minutes:
      description: "Duration in minutes"
      selector:
        number:
          min: 1
          max: 120
  sequence:
    - variables:
        current: "{{ state_attr(target_lights[0], 'brightness') | default(0) | int }}"
        current_pct: "{{ (current / 255 * 100) | int }}"
        steps: "{{ (target_brightness - current_pct) | abs }}"
        delay_seconds: "{{ ((duration_minutes * 60) / [steps, 1] | max) | int }}"
        direction: "{{ 1 if target_brightness > current_pct else -1 }}"
    - repeat:
        count: "{{ steps }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: "{{ target_lights }}"
            data:
              brightness_pct: "{{ current_pct + (repeat.index * direction) }}"
          - delay:
              seconds: "{{ delay_seconds }}"
```

## Docker Management

```bash
# Restart HA (safe, ~30s downtime)
docker compose -f /Users/vmasrani/dev/homeassistant/docker-compose.yml restart

# View logs
docker logs homeassistant --tail 50 -f

# Check config validity before restart
docker exec homeassistant python3 -m homeassistant --script check_config -c /config

# Shell into the container
docker exec -it homeassistant bash
```

## HACS (Community Store)

Not yet installed. To install:

```bash
docker exec -it homeassistant bash -c "wget -O - https://get.hacs.xyz | bash -"
docker compose -f /Users/vmasrani/dev/homeassistant/docker-compose.yml restart
```

Then add via UI: Settings > Devices & Services > Add Integration > HACS (requires GitHub OAuth).

Popular HACS integrations for this setup:
- **Adaptive Lighting** — circadian color temperature shifts
- **Mushroom Cards** — clean, modern dashboard cards

## Workflow

When the user asks to modify their HA setup:

1. Read the relevant YAML file(s) first to see current state
2. Make the edit using the Edit tool (or Write if the file is empty)
3. Validate: `docker exec homeassistant python3 -m homeassistant --script check_config -c /config`
4. Restart: `docker compose -f /Users/vmasrani/dev/homeassistant/docker-compose.yml restart`
5. Verify: check logs for errors with `docker logs homeassistant --tail 20`

Always read before editing. Always validate before restarting. The user's other Docker containers (plex stack with 15 containers) must never be touched.
