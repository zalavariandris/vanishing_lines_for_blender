"""
Build script for packaging Blender addon.
"""

import shutil
import zipfile
from pathlib import Path

from pprint import pprint

# Configuration
ADDON_NAME = "VanishingLines"  # Your addon folder name
SRC_DIR = "vanishing_lines_for_blender"
BUILD_DIR = "build"
DIST_DIR = "dist"

if __name__ == "__main__":
    # Create build and dist directories
    src_path = Path(SRC_DIR)
    build_path = Path(BUILD_DIR)
    dist_path = Path(DIST_DIR)
    build_path.mkdir(exist_ok=True)
    dist_path.mkdir(exist_ok=True)

    # Collect addon files and wheels
    files = [
        "__init__.py",
        "blender_manifest.toml",
        "solver.py",
        "vl_op.py",
        "vl_params.py",
        "vl_sidepanel.py"
    ]
    wheels = list((src_path / 'wheels').glob('*.whl'))
    files += [str(wheel.relative_to(src_path)) for wheel in wheels]

    pprint(files)

    # Read blender_manifest.toml to get the current version
    import tomllib
    manifest_path = src_path / "blender_manifest.toml"
    with open(manifest_path, "rb") as f:
        manifest_data = tomllib.load(f)
    addon_id = manifest_data.get("id", "VanishingLines").replace(" ", "_")
    version = manifest_data.get("version", "0.0.1")

    # Create zip file directly from source
    zip_filename = dist_path / f"{ADDON_NAME}-v{version}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            file_path = src_path / file
            zipf.write(file_path, f"{ADDON_NAME}/{file}")

    print(f"Addon packaged successfully: {zip_filename}")