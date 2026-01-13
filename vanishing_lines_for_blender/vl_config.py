"""
Configuration for VanishingLines addon.
Determines whether this is dev or stable version based on blender_manifest.toml
"""
from pathlib import Path
import tomllib

def _load_config():
    """Load configuration from blender_manifest.toml"""
    manifest_path = Path(__file__).parent / "blender_manifest.toml"
    with open(manifest_path, "rb") as f:
        manifest = tomllib.load(f)
    
    addon_id = manifest.get("id", "vanishinglines")
    is_dev = "_dev" in addon_id or "dev" in manifest.get("name", "").lower()
    
    return {
        "addon_id": addon_id,
        "is_dev": is_dev,
        "suffix": "_dev" if is_dev else ""
    }

# Load config once on import
_config = _load_config()

# Export configuration
ADDON_ID = _config["addon_id"]
IS_DEV = _config["is_dev"]
ID_SUFFIX = _config["suffix"]

def make_idname(base_name: str) -> str:
    """
    Create a bl_idname with appropriate suffix for dev/stable.
    
    Args:
        base_name: Base identifier (e.g., "view.vanishing_lines_view_tool")
    
    Returns:
        Suffixed identifier for dev builds or original for stable
    """
    if IS_DEV:
        # For operators: view.vanishing_lines_view_tool -> view.vanishing_lines_view_tool_dev
        # For menus/panels: MODAL_MT_vl_context_menu -> MODAL_MT_vl_context_menu_dev
        return f"{base_name}{ID_SUFFIX}"
    return base_name
