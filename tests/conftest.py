import sys
from pathlib import Path

# Add the vanishing_lines_for_blender directory to Python path
# This allows importing core as a standalone module
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "vanishing_lines_for_blender"))
