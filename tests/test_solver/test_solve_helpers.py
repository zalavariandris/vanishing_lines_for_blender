import pytest
from pyglm import glm
import numpy as np
import sys
from pathlib import Path
from typing import Literal

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent.parent
    print("Project root:", project_root)
    sys.path.insert(0, str(project_root / "vanishing_lines_for_blender"))

from vanishing_lines_for_blender import solver


##############################
# test orientation functions #
##############################

def test_focal_length_from_two_vp():
    vp1 = (-368, 731)
    vp2 = (1229, 613)

    f = solver.helpers.compute_focal_length_from_vanishing_points(
        Fu=vp1,
        Fv=vp2,
        P=(640,360)
    )

    expected_f = 707

    assert np.isclose(f, expected_f), f"Focal length does not match expected."
    
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])