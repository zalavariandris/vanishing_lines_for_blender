"""
Build script for packaging Blender addon.
"""
import sys
import subprocess
import shutil
import zipfile
from pathlib import Path

from pprint import pprint

# Configuration
ADDON_NAME = "VanishingLines"  # Your addon folder name
SRC_DIR = "vanishing_lines_for_blender"
BUILD_DIR = "build"
DIST_DIR = "dist"

SOURCE = [
    "blender_manifest.toml",
    "__init__.py",
    "view3d_painter.py",
    "view3d_gui.py",
    "vl_props.py",
    "vl_utils.py",
    "vl_operators.py",
    "vl_sidepanel.py",
    "solver/**/*"
]


PACKAGES = [
    "pyglm"
]

if __name__ == "__main__":
    # copy source files to dist directory
    print("Copying source files...")
    Path(BUILD_DIR).mkdir(exist_ok=True)
    for pattern in SOURCE:
        for src_file in Path(SRC_DIR).glob(pattern):
            if src_file.is_file():
                dest_file = Path(BUILD_DIR) / src_file.relative_to(SRC_DIR)
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                print(f"- {dest_file}")
    print("Source files copied to dist directory.")

    # Create wheels for third party modules
    print("Creating wheels for third-party modules...")
    wheels_dir = Path(BUILD_DIR) / 'wheels'
    wheels_dir.mkdir(exist_ok=True)
    
    # Download wheels for all platforms
    platforms = [
        ('win_amd64', '3.11'),            # Windows 64-bit
        ('manylinux2014_x86_64', '3.11'), # Linux 64-bit
        ('macosx_10_9_x86_64', '3.11'),   # macOS Intel
        ('macosx_11_0_arm64', '3.11'),    # macOS Apple Silicon
    ]
    
    print(f"Downloading wheels for all platforms... to {wheels_dir}")
    for module in PACKAGES:
        for platform, python_version in platforms:
            print(f"- {module} for {platform}...")
            try:
                subprocess.run([
                    sys.executable, "-m", "pip", "download",
                    "--dest", str(wheels_dir),
                    "--platform", platform,
                    "--python-version", python_version,
                    "--implementation", "cp",
                    "--only-binary=:all:",
                    "--no-deps",
                    module
                ], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                print(f"    Warning: Could not download for {platform}: {e.stderr}")
    
    wheels = list(wheels_dir.glob('*.whl'))
    print(f"Wheels created. Total files: {len(wheels)}")

    # Read blender_manifest.toml to get the current version
    import tomllib
    manifest_path = Path(SRC_DIR) / "blender_manifest.toml"
    with open(manifest_path, "rb") as f:
        manifest_data = tomllib.load(f)
    addon_id = manifest_data.get("id", "VanishingLines").replace(" ", "_")
    version = manifest_data.get("version", "0.0.1")

    # Create zip file directly from source
    Path(DIST_DIR).mkdir(exist_ok=True)
    zip_filename = Path(DIST_DIR) / f"{ADDON_NAME}-v{version}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in Path(BUILD_DIR).rglob('*'):
            if file_path.is_file():
                arcname = f"{ADDON_NAME}/{file_path.relative_to(BUILD_DIR)}"
                zipf.write(file_path, arcname)

    # print("Cleaning up build directory...")
    # shutil.rmtree(BUILD_DIR)

    print(f"Addon packaged successfully: {zip_filename}")