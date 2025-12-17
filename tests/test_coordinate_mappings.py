



import pytest
from typing import Literal
"""
Output Frame

test cases
- _auto_ sensor_mode: 
  - _wide_ region
    - [x] _wide_ output frame
    - [x] _tall_ output frame
  - _tall_ region
    - [x] _wide_ output frame
    - [x] _tall_ output frame

- horizonal sensor_mode:
  - _wide_ region
    - [X] _wide_ output frame
    - [x] _tall_ output frame
  - _tall_ region
    - [x] _wide_ output frame
    - [x] _tall_ output frame

- vertical sensor_mode:
  - _wide_ region
    - [x] _wide_ output frame
    - [x] _tall_ output frame
  - _tall_ region
    - [x] _wide_ output frame
    - [x] _tall_ output frame
"""

# TODO: use combinations
from itertools import product


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add the vanishing_lines_for_blender directory to Python path
    # This allows importing core as a standalone module
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root / "vanishing_lines_for_blender"))

import vl_coord_utils

sensor_options = ["AUTO", "HORIZONTAL", "VERTICAL"]
output_options = [(1920, 1080), (1080, 1920)]
region_options = [(2020, 1500), (1500, 2020)]

combinations = list(product(sensor_options, output_options, region_options))
combinations = [
  ['AUTO',       (1920, 1080), (2020, 1500), (1205.728426911141, 666.2128318431751)],
  ['AUTO',       (1920, 1080), (1500, 2020), (1171.349718884399, 700.5915398699168)],
  ['AUTO',       (1080, 1920), (2020, 1500), (736.6495155579646, 1107.2466509945364)],
  ['AUTO',       (1080, 1920), (1500, 2020), (702.2708075312229, 1141.625359021278)],
  ['HORIZONTAL', (1920, 1080), (2020, 1500), (1205.728426911141, 666.2128318431751)],
  ['HORIZONTAL', (1920, 1080), (1500, 2020), (1205.728426911141, 746.8882000125956)],
  ['HORIZONTAL', (1080, 1920), (2020, 1500), (678.2222401375168, 1063.860060335788)],
  ['HORIZONTAL', (1080, 1920), (1500, 2020), (678.2222401375168, 1109.239954931087)],
  ['VERTICAL',   (1920, 1080), (2020, 1500), (1173.3430228209497, 642.1642644494689)],
  ['VERTICAL',   (1920, 1080), (1500, 2020), (1127.9631282256507, 642.1642644494689)],
  ['VERTICAL',   (1080, 1920), (2020, 1500), (782.9461757006433, 1141.625359021278)],
  ['VERTICAL',   (1080, 1920), (1500, 2020), (702.2708075312229, 1141.625359021278)]
]
@pytest.mark.parametrize("sensor_fit, region_size, output_size, expected",
  combinations)
def test_output_frame(
    sensor_fit:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
    region_size, 
    output_size,
    expected):
    
    result = vl_coord_utils.project_output_to_region(
        sensor_fit=sensor_fit,
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=-6.109,
        view_camera_offset=(-0.07, -0.03),
        output_coords=(output_size[0]*2/3, output_size[1]*2/3))
    
    # print(f"{sensor_fit}, {region_size}, {output_size}, {result}")

    assert pytest.approx(result[0], rel=1e-3) == expected[0]
    assert pytest.approx(result[1], rel=1e-3) == expected[1]

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])