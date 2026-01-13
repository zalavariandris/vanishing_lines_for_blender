# Dev and Stable Extension Setup

## Overview
This addon now supports both dev and stable versions that can be installed simultaneously in Blender without conflicts.

## How It Works

The system automatically detects whether it's a dev or stable build by reading `blender_manifest.toml`:
- **Stable**: `id = "vanishinglines"`
- **Dev**: `id = "vanishinglines_dev"`

All Python class identifiers (`bl_idname`) are automatically suffixed with `_dev` for dev builds.

## Setup Instructions

### On the `main` branch (Stable):

1. Edit `vanishing_lines_for_blender/blender_manifest.toml`:
```toml
id = "vanishinglines"
name = "VanishingLines"
```

2. Commit this to main:
```bash
git checkout main
git commit -am "Configure stable version"
```

### On the `dev` branch (Dev):

1. Edit `vanishing_lines_for_blender/blender_manifest.toml`:
```toml
id = "vanishinglines_dev"
name = "VanishingLines (dev)"
```

2. Commit this to dev:
```bash
git checkout dev
git commit -am "Configure dev version"
```

## Result

- **Stable (main)**: 
  - Extension ID: `vanishinglines`
  - Operator ID: `view.vanishing_lines_view_tool`
  - Menu ID: `MODAL_MT_vl_context_menu`
  
- **Dev (dev)**:
  - Extension ID: `vanishinglines_dev`
  - Operator ID: `view.vanishing_lines_view_tool_dev`
  - Menu ID: `MODAL_MT_vl_context_menu_dev`

Both can be installed and run simultaneously in Blender without any RNA conflicts!

## Files Modified

- **NEW**: `vanishing_lines_for_blender/vl_config.py` - Configuration system
- **MODIFIED**: `vanishing_lines_for_blender/vanishing_lines_tool.py` - Uses dynamic identifiers

## Building

Just run your existing build script:
```bash
python build_addon.py
```

The build will automatically create the correct version based on the current branch's manifest.
