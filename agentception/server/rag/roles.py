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

def normalize_role_name(role: str) -> str:
    """Normalize role name for consistent lookup."""
    if not role:
        return role
    
    # Common abbreviation fixes
    normalized = role.strip()
    normalized = normalized.replace('Ai ', 'AI ')
    normalized = normalized.replace('Ml ', 'ML ')
    normalized = normalized.replace('ai ', 'AI ')
    normalized = normalized.replace('ml ', 'ML ')
    normalized = normalized.replace(' ai', ' AI')
    normalized = normalized.replace(' ml', ' ML')
    
    # Handle edge cases with exact matches
    lower = normalized.lower()
    if lower == 'ai engineer':
        normalized = 'AI Engineer'
    elif lower == 'ml engineer':
        normalized = 'ML Engineer'
    elif lower == 'ai/ml engineer':
        normalized = 'AI/ML Engineer'
    
    return normalized

def role_profile(name: str) -> Dict[str, List[str]]:
    """Get role profile by name with normalized lookup."""
    # Try exact match first
    if name in ROLES:
        profile = ROLES[name]
        print(f"🎯 Role profile for '{name}': {len(profile.get('keywords', []))} keywords, {len(profile.get('value_props', []))} value props")
        return profile
    
    # Try normalized version
    normalized = normalize_role_name(name)
    if normalized in ROLES:
        print(f"🔄 Role normalized: '{name}' → '{normalized}'")
        profile = ROLES[normalized]
        print(f"🎯 Role profile for '{normalized}': {len(profile.get('keywords', []))} keywords, {len(profile.get('value_props', []))} value props")
        return profile
    
    # Try case-insensitive match
    name_lower = name.lower()
    for key, profile in ROLES.items():
        if key.lower() == name_lower:
            print(f"🔄 Role matched (case-insensitive): '{name}' → '{key}'")
            print(f"🎯 Role profile for '{key}': {len(profile.get('keywords', []))} keywords, {len(profile.get('value_props', []))} value props")
            return profile
    
    # No match found
    print(f"⚠️ No role profile found for '{name}'")
    return {"keywords": [], "value_props": []}

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
