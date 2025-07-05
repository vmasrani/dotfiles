# AICore Service Management

A systemd service management system for ADK API Server instances. This tool allows you to easily start, stop, and manage multiple AI Core projects as system services.

## Overview

This system provides a unified interface to manage ADK API Server instances as systemd services. It automatically generates service files, handles virtual environment paths, and provides convenient commands for service lifecycle management.

## Files

- `aicore` - Main service management script
- `aicore-service.template` - Systemd service template
- `setup.sh` - Installation script that creates symlinks and sets up the system
- `README.md` - This documentation

## Installation

```bash
cd /home/vaden/dotfiles/local/services
./setup.sh
```

The setup script will:
- Create `~/bin` directory if it doesn't exist
- Make the aicore script executable
- Create a symlink from `~/bin/aicore` to the script
- Check if `~/bin` is in your PATH
- Verify sudo privileges for systemctl operations

## Usage

### Basic Commands

```bash
# Start a service
aicore start --project <path> --port <port>

# Stop a service
aicore stop --project <path>

# Check service status
aicore status --project <path>

# Restart a service
aicore restart --project <path>

# View service logs (follow mode)
aicore logs --project <path>

# Show help
aicore --help
```

### Examples

```bash
# Start ai_core_brandon on port 8004
aicore start --project /home/vaden/dev/projects/live/ai_core_brandon --port 8004

# Stop ai_core_leif
aicore stop --project /home/vaden/dev/projects/live/ai_core_leif

# Check status of ai_core_brandon
aicore status --project /home/vaden/dev/projects/live/ai_core_brandon

# View logs for ai_core_leif
aicore logs --project /home/vaden/dev/projects/live/ai_core_leif
```

## Requirements

- **Systemd**: Required for service management
- **Virtual Environment**: Each project must have a `.venv` directory
- **ADK Command**: The `adk` command must be installed in the project's virtual environment
- **Sudo Access**: Required for systemctl operations

## Testing

### Setup Testing
```bash
# Test setup script
cd /home/vaden/dotfiles/local/services
./setup.sh

# Verify symlink creation
ls -la ~/bin/aicore
which aicore
```

### Basic Validation Testing
```bash
# Test help and syntax
aicore --help
aicore -h
aicore

# Test invalid commands
aicore invalid-command
aicore start
aicore start --project /nonexistent
aicore start --project /home/vaden/dev/projects/live/ai_core_brandon
aicore start --project /home/vaden/dev/projects/live/ai_core_brandon --port abc
aicore start --project /home/vaden/dev/projects/live/ai_core_brandon --port 70000
```

### Core Functionality Testing
```bash
# Test with ai_core_brandon (replace with actual paths)
aicore start --project /home/vaden/dev/projects/live/ai_core_brandon --port 8004
aicore status --project /home/vaden/dev/projects/live/ai_core_brandon
aicore logs --project /home/vaden/dev/projects/live/ai_core_brandon
# Press Ctrl+C to exit logs
aicore restart --project /home/vaden/dev/projects/live/ai_core_brandon
aicore stop --project /home/vaden/dev/projects/live/ai_core_brandon

# Test with ai_core_leif
aicore start --project /home/vaden/dev/projects/live/ai_core_leif --port 8005
aicore status --project /home/vaden/dev/projects/live/ai_core_leif
aicore stop --project /home/vaden/dev/projects/live/ai_core_leif
```

### System Integration Testing
```bash
# Check generated service files
ls -la /home/vaden/dotfiles/local/services/*.service
cat /home/vaden/dotfiles/local/services/aicore-ai_core_brandon.service

# Check systemd integration
sudo systemctl status aicore-ai_core_brandon
sudo systemctl list-unit-files | grep aicore
journalctl -u aicore-ai_core_brandon --no-pager
```

### Port Conflict Testing
```bash
# Start both services on different ports
aicore start --project /home/vaden/dev/projects/live/ai_core_brandon --port 8004
aicore start --project /home/vaden/dev/projects/live/ai_core_leif --port 8005

# Check both are running
aicore status --project /home/vaden/dev/projects/live/ai_core_brandon
aicore status --project /home/vaden/dev/projects/live/ai_core_leif

# Test port conflicts (should fail gracefully)
curl http://localhost:8004 || echo "Connection failed (expected if service not responding)"
curl http://localhost:8005 || echo "Connection failed (expected if service not responding)"
```

### Cleanup Testing
```bash
# Stop all services
aicore stop --project /home/vaden/dev/projects/live/ai_core_brandon
aicore stop --project /home/vaden/dev/projects/live/ai_core_leif

# Verify cleanup
sudo systemctl list-unit-files | grep aicore
ls -la /etc/systemd/system/aicore-*.service
```

### Edge Case Testing
```bash
# Test with missing .venv
mkdir -p /tmp/test-project
aicore start --project /tmp/test-project --port 9999

# Test permission issues (run as different user if possible)
# Test with very long paths
# Test with special characters in project names (if any)
```

### Shellcheck and Syntax Testing
```bash
# Validate script syntax
bash -n /home/vaden/dotfiles/local/services/aicore
bash -n /home/vaden/dotfiles/local/services/setup.sh
shellcheck /home/vaden/dotfiles/local/services/aicore
shellcheck /home/vaden/dotfiles/local/services/setup.sh
```

## How It Works

1. **Service Naming**: Services are named `aicore-{project_name}` where `project_name` is the basename of the project directory
2. **Service Files**: Generated from the template and stored in both the local services directory and `/etc/systemd/system/`
3. **Virtual Environment**: Uses the `.venv` directory in each project for the Python environment
4. **Process Management**: Services run as the current user in the project's working directory
5. **Logging**: Output goes to systemd journal, viewable with `journalctl` or `aicore logs`

## Troubleshooting

### Common Issues

**"systemctl not found"**
- This system requires systemd. Ensure you're running on a systemd-based Linux distribution.

**"Virtual environment not found"**
- Create a virtual environment: `cd /path/to/project && python -m venv .venv`
- Install adk: `source .venv/bin/activate && pip install adk`

**"adk command not found"**
- Install adk in the virtual environment: `source .venv/bin/activate && pip install adk`

**Permission denied errors**
- Ensure you have sudo privileges for systemctl operations
- Check that the project directory is accessible

**Port already in use**
- Use a different port number
- Check what's using the port: `sudo netstat -tlnp | grep :8004`

### Debugging

View detailed service logs:
```bash
journalctl -u aicore-{project_name} -f --no-pager
```

Check service file contents:
```bash
cat /etc/systemd/system/aicore-{project_name}.service
```

Verify service status:
```bash
systemctl status aicore-{project_name}
```

## Prerequisites for Testing

Before running tests, ensure:
1. The project directories exist: `/home/vaden/dev/projects/live/ai_core_brandon` and `/home/vaden/dev/projects/live/ai_core_leif`
2. Each has a `.venv` directory with the `adk` command installed
3. You have sudo privileges for systemctl operations

**Start with the setup and basic validation tests first**, then proceed to core functionality once those pass.
