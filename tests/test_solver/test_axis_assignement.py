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

import solver


##############################
# test orientation functions #
##############################

def test_axis_assignement():
    m = glm.mat4(1.0)

    solver.core.apply_axis_assignment(m, 'X', 'Y', 'Z')
    # check the forward, right, up vector directions

    raise NotImplementedError("Test not implemented yet.")
    
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])