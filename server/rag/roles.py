from __future__ import annotations
import yaml, os
from typing import Dict, List

# Global roles cache
ROLES: Dict[str, Dict[str, List[str]]] = {}

# Load roles from YAML file
_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "seeds", "roles.yaml"))

def _load_roles():
    """Load role profiles from YAML file"""
    global ROLES
    if os.path.exists(_path):
        try:
            with open(_path, "r", encoding="utf-8") as f:
                ROLES = yaml.safe_load(f) or {}
            print(f"📋 Loaded {len(ROLES)} role profiles from {_path}")
        except Exception as e:
            print(f"❌ Failed to load roles from {_path}: {e}")
            ROLES = {}
    else:
        print(f"⚠️ Roles file not found at {_path}")
        ROLES = {}

# Load roles on import
_load_roles()

def role_profile(name: str) -> Dict[str, List[str]]:
    """Get role profile by name, returns keywords and value_props"""
    profile = ROLES.get(name, {"keywords": [], "value_props": []})
    print(f"🎯 Role profile for '{name}': {len(profile.get('keywords', []))} keywords, {len(profile.get('value_props', []))} value props")
    return profile

def get_role_keywords(name: str) -> List[str]:
    """Get just the keywords for a role"""
    return role_profile(name).get("keywords", [])

def get_role_value_props(name: str) -> List[str]:
    """Get just the value propositions for a role"""
    return role_profile(name).get("value_props", [])

def all_roles() -> List[str]:
    """Get list of all available role names"""
    return list(ROLES.keys())

def reload_roles():
    """Reload roles from file (useful for development)"""
    _load_roles()
