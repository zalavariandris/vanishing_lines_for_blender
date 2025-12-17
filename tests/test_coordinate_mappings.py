



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

wide_output = (1920, 1080)
tall_output = (1080, 1920)
wide_region = (2020, 1500)
tall_region = (1500, 2020)
sensor_options = ["AUTO", "HORIZONTAL", "VERTICAL"]
output_options = [wide_output, tall_output]
region_options = [wide_region, tall_region]

combinations = list(product(sensor_options, output_options, region_options))
combinations = [
  ['AUTO',       wide_region, wide_output, (1268.5267824794296, 866.5937147899116)],
  ['AUTO',       tall_region, wide_output, (978.1445992607966, 1139.61465045504)],
  ['AUTO',       wide_region, tall_output, (1207.0564197974998, 928.0640774718411)],
  ['AUTO',       tall_region, tall_output, (916.674236578867, 1201.0850131369696)],
  ['HORIZONTAL', wide_region, wide_output, (1268.5267824794296, 866.5937147899116)],
  ['HORIZONTAL', tall_region, wide_output, (941.9753335243288, 1119.269438478277)],
  ['HORIZONTAL', wide_region, tall_output, (1268.5267824794296, 1037.3447222397158)],
  ['HORIZONTAL', tall_region, tall_output, (941.9753335243288, 1246.0647410400127)],
  ['VERTICAL',   wide_region, wide_output, (1313.5065103824725, 891.8948117353734)],
  ['VERTICAL',   tall_region, wide_output, (1087.4252440286712, 1201.0850131369696)],
  ['VERTICAL',   wide_region, tall_output, (1186.7112078207367, 891.8948117353734)],
  ['VERTICAL',   tall_region, tall_output, (916.674236578867, 1201.0850131369696)]
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
    
    # print(f"{sensor_fit:10s}, {region_size}, {output_size}, {result}")

    assert pytest.approx(result[0], rel=1e-3) == expected[0]
    assert pytest.approx(result[1], rel=1e-3) == expected[1]


combinations = [
  ['AUTO',       wide_region, wide_output, (1205.728426911141, 666.2128318431751)],
  ['AUTO',       tall_region, wide_output, (1171.349718884399, 700.5915398699168)],
  ['AUTO',       wide_region, tall_output, (736.6495155579646, 1107.2466509945364)],
  ['AUTO',       tall_region, tall_output, (702.2708075312229, 1141.625359021278)],
  ['HORIZONTAL', wide_region, wide_output, (1205.728426911141, 666.2128318431751)],
  ['HORIZONTAL', tall_region, wide_output, (1205.728426911141, 746.8882000125956)],
  ['HORIZONTAL', wide_region, tall_output, (678.2222401375168, 1063.860060335788)],
  ['HORIZONTAL', tall_region, tall_output, (678.2222401375168, 1109.239954931087)],
  ['VERTICAL',   wide_region, wide_output, (1173.3430228209497, 642.1642644494689)],
  ['VERTICAL',   tall_region, wide_output, (1127.9631282256507, 642.1642644494689)],
  ['VERTICAL',   wide_region, tall_output, (782.9461757006433, 1141.625359021278)],
  ['VERTICAL',   tall_region, tall_output, (702.2708075312229, 1141.625359021278)]
]
@pytest.mark.parametrize("sensor_fit, region_size, output_size, expected",
  combinations)
def test_compute_frame(
    sensor_fit:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
    region_size, 
    output_size,
    expected):
    
    result = vl_coord_utils.project_compute_to_region(
        sensor_fit=sensor_fit,
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=-6.109,
        view_camera_offset=(-0.07, -0.03),
        output_coords=(output_size[0]*2/3, output_size[1]*2/3))
    
    print(f"{sensor_fit}, {region_size}, {output_size}, {result}")

    assert pytest.approx(result[0], rel=1e-3) == expected[0]
    assert pytest.approx(result[1], rel=1e-3) == expected[1]

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])