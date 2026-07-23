#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///

import json
import os
import shutil
import re
from pathlib import Path

# Paths
DOTFILES_DIR = Path("/Users/vmasrani/dotfiles")
CLAUDE_DIR = DOTFILES_DIR / "maintained_global_claude"
AGY_DIR = DOTFILES_DIR / "maintained_global_agy"
LOCAL_CLAUDE_SETTINGS = Path("/Users/vmasrani/.gemini/antigravity-cli/settings.json")

def clean_and_create_dir(path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

def migrate_settings():
    print("Migrating settings...")
    claude_settings_path = CLAUDE_DIR / "settings.json"
    with open(claude_settings_path) as f:
        claude_settings = json.load(f)

    # 1. Parse and map permissions
    claude_allow = claude_settings.get("permissions", {}).get("allow", [])
    agy_allow = [
        "read_file(*)",
        "write_file(*)",
        "command(*)",
        "read_url(*)",
        "execute_url(*)",
        "mcp(*)",
        "custom(*)"
    ]

    for p in claude_allow:
        if p in ("Read", "Write", "Edit"):
            continue
        elif p == "Bash":
            continue
        elif p == "WebFetch":
            agy_allow.extend(["read_url(*)", "execute_url(*)"])
        elif p == "WebSearch":
            agy_allow.extend(["custom(search_web)", "custom(WebSearch)", "command(search_web)"])
        elif p.startswith("Skill("):
            skill_name = p.split("(")[1].split(")")[0]
            agy_allow.extend([f"custom(Skill({skill_name}))", f"custom({skill_name})"])
        elif p.startswith("mcp__"):
            # Map mcp__context7__get-library-docs to mcp(context7/get-library-docs)
            parts = p.split("__")
            if len(parts) >= 3:
                server = parts[1]
                tool = parts[2]
                agy_allow.append(f"mcp({server}/{tool})")
            else:
                agy_allow.append(f"mcp({p})")
        elif p == "Read(//Volumes/external/**)":
            agy_allow.append("read_file(/Volumes/external)")
        elif p == "Edit(//Volumes/external/**)":
            agy_allow.append("write_file(/Volumes/external)")
        elif p == "ExitPlanMode":
            agy_allow.append("custom(ExitPlanMode)")
        else:
            # General fallback
            agy_allow.append(f"custom({p})")

    # Deduplicate and sort
    agy_allow = sorted(list(set(agy_allow)))

    # Load current local settings to preserve trustedWorkspaces and allowNonWorkspaceAccess
    local_trusted = ["/Users/vmasrani/dev/fsa", "/Users/vmasrani/dotfiles/maintained_global_claude", "/Users/vmasrani/dotfiles/maintained_global_agy"]
    allow_non_ws = True
    if LOCAL_CLAUDE_SETTINGS.exists():
        try:
            with open(LOCAL_CLAUDE_SETTINGS) as f:
                local_settings = json.load(f)
                allow_non_ws = local_settings.get("allowNonWorkspaceAccess", True)
                local_trusted = list(set(local_trusted + local_settings.get("trustedWorkspaces", [])))
        except Exception as e:
            print(f"Warning: could not parse local settings: {e}")

    # Build AGY settings
    agy_settings = {
        "allowNonWorkspaceAccess": allow_non_ws,
        "trustedWorkspaces": sorted(local_trusted),
        "permissions": {
            "allow": agy_allow,
            "deny": [],
            "defaultMode": claude_settings.get("permissions", {}).get("defaultMode", "auto")
        },
        "theme": claude_settings.get("theme", "dark"),
        "preferredNotifChannel": claude_settings.get("preferredNotifChannel", "iterm2"),
        "teammateMode": claude_settings.get("teammateMode", "tmux"),
        "effortLevel": claude_settings.get("effortLevel", "high"),
        "fastMode": claude_settings.get("fastMode", True),
        "skipDangerousModePermissionPrompt": claude_settings.get("skipDangerousModePermissionPrompt", True),
        "skipWorkflowUsageWarning": claude_settings.get("skipWorkflowUsageWarning", True),
        "skipAutoPermissionPrompt": claude_settings.get("skipAutoPermissionPrompt", True),
        "agentPushNotifEnabled": claude_settings.get("agentPushNotifEnabled", True),
        "remoteControlAtStartup": claude_settings.get("remoteControlAtStartup", True),
        "statusLine": {
            "type": "command",
            "command": "~/.gemini/antigravity-cli/statusline.sh"
        },
        "autoMode": claude_settings.get("autoMode", {})
    }

    # Write settings.json
    with open(AGY_DIR / "settings.json", "w") as f:
        json.dump(agy_settings, f, indent=2)

def migrate_hooks():
    print("Migrating hooks.json...")
    hooks_json = {
        "test-queue-guard": {
            "PreToolUse": [
                {
                    "matcher": "run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/usr/bin/python3 /Users/vmasrani/.gemini/antigravity-cli/hooks/test_queue_guard.py"
                        }
                    ]
                }
            ]
        },
        "bash-footgun-guard": {
            "PreToolUse": [
                {
                    "matcher": "run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/usr/bin/python3 /Users/vmasrani/.gemini/antigravity-cli/hooks/bash_footgun_guard.py"
                        }
                    ]
                }
            ]
        },
        "post-tool-use": {
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "uv run /Users/vmasrani/.gemini/antigravity-cli/hooks/post_tool_use.py"
                        }
                    ]
                }
            ]
        },
        "test-count-guard": {
            "PostToolUse": [
                {
                    "matcher": "run_command",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/usr/bin/python3 /Users/vmasrani/.gemini/antigravity-cli/hooks/test_count_guard.py"
                        }
                    ]
                }
            ]
        },
        "pre-compact": {
            "PreCompact": [
                {
                    "type": "command",
                    "command": "uv run /Users/vmasrani/.gemini/antigravity-cli/hooks/pre_compact.py"
                }
            ]
        }
    }

    with open(AGY_DIR / "hooks.json", "w") as f:
        json.dump(hooks_json, f, indent=2)

    # 2. Copy and adapt hook python scripts
    print("Adapting hook python scripts...")
    src_hooks_dir = CLAUDE_DIR / "hooks"
    dest_hooks_dir = AGY_DIR / "hooks"
    clean_and_create_dir(dest_hooks_dir)

    for item in src_hooks_dir.iterdir():
        if item.is_file():
            if item.suffix == ".py":
                content = item.read_text()
                
                # Replace Bash checks
                content = content.replace('data.get("tool_name") != "Bash"', 'data.get("tool_name") not in ("Bash", "run_command")')
                content = content.replace('data.get("tool_name") == "Bash"', 'data.get("tool_name") in ("Bash", "run_command")')
                content = content.replace("tool_name == 'Bash'", "tool_name in ('Bash', 'run_command')")
                content = content.replace("tool_name != 'Bash'", "tool_name not in ('Bash', 'run_command')")
                
                # Replace commands accesses
                content = content.replace('(data.get("tool_input") or {}).get("command")', '((data.get("tool_input") or {}).get("command") or (data.get("tool_input") or {}).get("CommandLine"))')
                content = content.replace('tool_input.get("command")', '(tool_input.get("command") or tool_input.get("CommandLine"))')
                content = content.replace("tool_input.get('command', '')", "(tool_input.get('command') or tool_input.get('CommandLine') or '')")
                
                # Replace log paths to be compatible/dual
                content = content.replace(
                    "Path.cwd() / '.claude/logs'", 
                    "Path.cwd() / '.gemini/antigravity-cli/logs' if (Path.cwd() / '.gemini').exists() or not (Path.cwd() / '.claude').exists() else Path.cwd() / '.claude/logs'"
                )
                content = content.replace(
                    'Path(cwd) / ".claude" / "logs"',
                    'Path(cwd) / ".gemini" / "antigravity-cli" / "logs" if (Path(cwd) / ".gemini").exists() or not (Path(cwd) / ".claude").exists() else Path(cwd) / ".claude" / "logs"'
                )
                content = content.replace(
                    "os.path.join(os.getcwd(), '.claude/logs')",
                    "os.path.join(os.getcwd(), '.gemini/antigravity-cli/logs') if os.path.exists(os.path.join(os.getcwd(), '.gemini')) or not os.path.exists(os.path.join(os.getcwd(), '.claude')) else os.path.join(os.getcwd(), '.claude/logs')"
                )
                content = content.replace(
                    'os.path.join(os.getcwd(), ".claude/logs")',
                    'os.path.join(os.getcwd(), ".gemini/antigravity-cli/logs") if os.path.exists(os.path.join(os.getcwd(), ".gemini")) or not os.path.exists(os.path.join(os.getcwd(), ".claude")) else os.path.join(os.getcwd(), ".claude/logs")'
                )

                # In notification.py, handle specific message check
                content = content.replace(
                    "input_data.get('message') != 'Claude is waiting for your input'",
                    "('waiting for your input' not in (input_data.get('message') or ''))"
                )

                # In test_queue_guard.py, handle updatedInput rewrite
                if item.name == "test_queue_guard.py":
                    old_rewrite = """    new_input = dict(tool_input)
    new_input["command"] = queued(command)"""
                    new_rewrite = """    new_input = dict(tool_input)
    if "command" in new_input:
        new_input["command"] = queued(command)
    else:
        new_input["CommandLine"] = queued(command)"""
                    content = content.replace(old_rewrite, new_rewrite)

                # In pre_tool_use.py, handle is_env_file_access
                if item.name == "pre_tool_use.py":
                    old_env_access = """def is_env_file_access(tool_name, tool_input):
    \"\"\"
    Check if any tool is trying to access .env files containing sensitive data.
    \"\"\"
    if tool_name in ['Read', 'Edit', 'MultiEdit', 'Write', 'Bash']:
        # Check file paths for file-based tools
        if tool_name in ['Read', 'Edit', 'MultiEdit', 'Write']:
            file_path = tool_input.get('file_path', '')
            if '.env' in file_path and not file_path.endswith('.env.sample'):
                return True

        # Check bash commands for .env file access
        elif tool_name == 'Bash':
            command = tool_input.get('command', '')
            # Pattern to detect .env file access (but allow .env.sample)
            env_patterns = [
                r'\\b\\.env\\b(?!\\.sample)',  # .env but not .env.sample
                r'cat\\s+.*\\.env\\b(?!\\.sample)',  # cat .env
                r'echo\\s+.*>\\s*\\.env\\b(?!\\.sample)',  # echo > .env
                r'touch\\s+.*\\.env\\b(?!\\.sample)',  # touch .env
                r'cp\\s+.*\\.env\\b(?!\\.sample)',  # cp .env
                r'mv\\s+.*\\.env\\b(?!\\.sample)',  # mv .env
            ]

            for pattern in env_patterns:
                if re.search(pattern, command):
                    return True

    return False"""
                    new_env_access = """def is_env_file_access(tool_name, tool_input):
    \"\"\"
    Check if any tool is trying to access .env files containing sensitive data.
    \"\"\"
    file_tools = ['Read', 'Edit', 'MultiEdit', 'Write', 'view_file', 'replace_file_content', 'multi_replace_file_content', 'write_to_file']
    bash_tools = ['Bash', 'run_command']
    if tool_name in file_tools + bash_tools:
        if tool_name in file_tools:
            file_path = tool_input.get('file_path') or tool_input.get('AbsolutePath') or tool_input.get('TargetFile') or ''
            if '.env' in file_path and not file_path.endswith('.env.sample'):
                return True
        elif tool_name in bash_tools:
            command = tool_input.get('command') or tool_input.get('CommandLine') or ''
            env_patterns = [
                r'\\b\\.env\\b(?!\\.sample)',
                r'cat\\s+.*\\.env\\b(?!\\.sample)',
                r'echo\\s+.*>\\s*\\.env\\b(?!\\.sample)',
                r'touch\\s+.*\\.env\\b(?!\\.sample)',
                r'cp\\s+.*\\.env\\b(?!\\.sample)',
                r'mv\\s+.*\\.env\\b(?!\\.sample)',
            ]
            for pattern in env_patterns:
                if re.search(pattern, command):
                    return True
    return False"""
                    content = content.replace(old_env_access, new_env_access)

                (dest_hooks_dir / item.name).write_text(content)
                os.chmod(dest_hooks_dir / item.name, item.stat().st_mode)

            else:
                shutil.copy2(item, dest_hooks_dir / item.name)
        elif item.is_dir():
            shutil.copytree(item, dest_hooks_dir / item.name, symlinks=True)

def migrate_skills_and_commands():
    print("Migrating skills...")
    dest_skills_dir = AGY_DIR / "skills"
    clean_and_create_dir(dest_skills_dir)

    # 1. Copy Claude skills
    src_skills_dir = CLAUDE_DIR / "skills"
    for item in src_skills_dir.iterdir():
        if item.is_symlink():
            link_target = os.readlink(item)
            os.symlink(link_target, dest_skills_dir / item.name)
        elif item.is_dir():
            shutil.copytree(item, dest_skills_dir / item.name, symlinks=True)

    # 2. Convert Claude commands to skills
    print("Converting Claude commands to AGY skills...")
    src_commands_dir = CLAUDE_DIR / "commands"
    for item in src_commands_dir.iterdir():
        if item.is_file() and item.suffix == ".md" and item.name != "commands-context.md":
            command_name = item.stem
            skill_folder = dest_skills_dir / command_name
            skill_folder.mkdir(parents=True, exist_ok=True)
            
            content = item.read_text()
            # Ensure name is in frontmatter
            if "name:" not in content:
                # Add name to frontmatter
                # Match frontmatter block at start
                fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
                if fm_match:
                    fm_content = fm_match.group(1)
                    rest = content[fm_match.end():]
                    new_fm = f"---\nname: {command_name}\n{fm_content}\n---\n"
                    content = new_fm + rest
                else:
                    content = f"---\nname: {command_name}\ndescription: Custom slash command {command_name}\n---\n" + content

            (skill_folder / "SKILL.md").write_text(content)

def migrate_agents():
    print("Migrating agents...")
    dest_agents_dir = AGY_DIR / "agents"
    clean_and_create_dir(dest_agents_dir)

    src_agents_dir = CLAUDE_DIR / "agents"
    for item in src_agents_dir.iterdir():
        if item.is_file() and item.suffix == ".md" and item.name != "agents-context.md":
            agent_name = item.stem
            agent_folder = dest_agents_dir / agent_name
            agent_folder.mkdir(parents=True, exist_ok=True)

            content = item.read_text()
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            description = f"Custom agent {agent_name}"
            system_prompt = content
            if fm_match:
                fm_content = fm_match.group(1)
                system_prompt = content[fm_match.end():].strip()
                # Parse description
                desc_match = re.search(r"description:\s*(.*)", fm_content)
                if desc_match:
                    description = desc_match.group(1).strip().strip('"').strip("'")

            agent_json = {
                "name": agent_name,
                "displayName": agent_name,
                "description": description,
                "hidden": False,
                "customAgentSpec": {
                    "customAgent": {
                        "systemPromptSections": [
                            {
                                "title": "Agent System Instructions",
                                "content": system_prompt
                            }
                        ],
                        "toolNames": [
                            "send_message",
                            "view_file",
                            "list_dir",
                            "replace_file_content",
                            "multi_replace_file_content",
                            "write_to_file",
                            "run_command",
                            "search_web",
                            "read_url_content"
                        ]
                    }
                }
            }

            with open(agent_folder / "agent.json", "w") as f:
                json.dump(agent_json, f, indent=2)

def migrate_misc():
    print("Migrating statusline and AGENTS.md...")
    # Copy statusline.sh
    shutil.copy2(CLAUDE_DIR / "statusline.sh", AGY_DIR / "statusline.sh")
    os.chmod(AGY_DIR / "statusline.sh", (CLAUDE_DIR / "statusline.sh").stat().st_mode)

    # Migrate CLAUDE.md to AGENTS.md
    claude_md = CLAUDE_DIR / "CLAUDE.md"
    agents_md = AGY_DIR / "AGENTS.md"
    
    content = claude_md.read_text()
    # Replacements
    content = content.replace("CLAUDE.md", "AGENTS.md")
    content = content.replace("Claude Code", "Antigravity CLI")
    content = content.replace("Claude", "Antigravity")
    content = content.replace("~/.claude/", "~/.gemini/antigravity-cli/")
    content = content.replace(".claude/", ".gemini/antigravity-cli/")
    content = content.replace("Bash hook", "run_command hook")
    content = content.replace("PreToolUse hook (~/.gemini/antigravity-cli/hooks/test_queue_guard.py)", "PreToolUse hook (~/.gemini/antigravity-cli/hooks/test_queue_guard.py)")
    
    agents_md.write_text(content)

def main():
    AGY_DIR.mkdir(parents=True, exist_ok=True)
    migrate_settings()
    migrate_hooks()
    migrate_skills_and_commands()
    migrate_agents()
    migrate_misc()
    print("Migration script generated and executed successfully!")

if __name__ == "__main__":
    main()
