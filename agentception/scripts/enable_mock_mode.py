"""
Helper script to enable/disable MOCK_SEARCH mode in .env file.
Run: python enable_mock_mode.py [enable|disable]
"""
import sys
import os
import re
from pathlib import Path

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

def update_env_file(enable: bool):
    """Add or update MOCK_SEARCH in .env file"""
    # .env lives at the project root; this script lives in scripts/
    env_path = Path(__file__).resolve().parents[1] / ".env"
    
    if not env_path.exists():
        print(f"[WARN] .env file not found at {env_path}")
        print(f"Creating new .env file with MOCK_SEARCH={'true' if enable else 'false'}")
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(f"MOCK_SEARCH={'true' if enable else 'false'}\n")
        print(f"[SUCCESS] Created .env file")
        return
    
    # Read existing .env
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Check if MOCK_SEARCH already exists
    mock_found = False
    new_lines = []
    
    for line in lines:
        if re.match(r'^\s*MOCK_SEARCH\s*=', line, re.IGNORECASE):
            # Update existing line
            new_lines.append(f"MOCK_SEARCH={'true' if enable else 'false'}\n")
            mock_found = True
        else:
            new_lines.append(line)
    
    # Add if not found
    if not mock_found:
        new_lines.append(f"\n# Mock search mode (set to true to use mock data instead of Tavily)\n")
        new_lines.append(f"MOCK_SEARCH={'true' if enable else 'false'}\n")
    
    # Write back
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    status = "ENABLED" if enable else "DISABLED"
    print(f"[SUCCESS] MOCK_SEARCH mode {status} in .env file")
    print(f"\n[IMPORTANT] Restart your server for changes to take effect!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command in ["enable", "on", "true", "1"]:
            update_env_file(True)
        elif command in ["disable", "off", "false", "0"]:
            update_env_file(False)
        else:
            print(f"Unknown command: {command}")
            print("Usage: python enable_mock_mode.py [enable|disable]")
    else:
        # Default: enable
        print("No command specified, enabling mock mode by default...")
        update_env_file(True)

