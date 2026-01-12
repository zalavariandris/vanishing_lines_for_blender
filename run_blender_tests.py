"""
Run pytest inside Blender
Usage: blender --background --python run_blender_tests.py -- [pytest args]
"""
import sys
import pytest

# Add the project to the path
sys.path.insert(0, str(__file__.rsplit('\\', 1)[0]))

if __name__ == "__main__":
    # Arguments after -- are for pytest
    if "--" in sys.argv:
        pytest_args = sys.argv[sys.argv.index("--") + 1:]
    else:
        pytest_args = ["tests/", "-v"]
    
    sys.exit(pytest.main(pytest_args))
