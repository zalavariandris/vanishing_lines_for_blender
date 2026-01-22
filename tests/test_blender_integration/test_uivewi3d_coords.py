



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

from vanishing_lines_for_blender import vl_coord_utils

wide_output = (1920, 1080)
tall_output = (1080, 1920)
wide_region = (2020, 1500)
tall_region = (1500, 2020)
wide_sensor = (36, 24)
tall_sensor = (24, 36)
sensor_options = ["AUTO", "HORIZONTAL", "VERTICAL"]
output_options = [wide_output, tall_output]
region_options = [wide_region, tall_region]


compute_combinations = [
  ['AUTO',       wide_region, wide_output, wide_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, wide_output, wide_sensor, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
  ['AUTO',       wide_region, tall_output, wide_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, tall_output, wide_sensor, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
  ['HORIZONTAL', wide_region, wide_output, wide_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
  ['HORIZONTAL', tall_region, wide_output, wide_sensor, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
  ['HORIZONTAL', wide_region, tall_output, wide_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272777)],
  ['HORIZONTAL', tall_region, tall_output, wide_sensor, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
  ['VERTICAL',   wide_region, wide_output, wide_sensor, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, wide_output, wide_sensor, (-0.3, 1.5), (711.1875956135597, 1692.8479145924057)],
  ['VERTICAL',   wide_region, tall_output, wide_sensor, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, tall_output, wide_sensor, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
  ['AUTO',       wide_region, wide_output, wide_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, wide_output, tall_sensor, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
  ['AUTO',       wide_region, tall_output, tall_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, tall_output, tall_sensor, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
  ['HORIZONTAL', wide_region, wide_output, tall_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
  ['HORIZONTAL', tall_region, wide_output, tall_sensor, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
  ['HORIZONTAL', wide_region, tall_output, tall_sensor, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272777)],
  ['HORIZONTAL', tall_region, tall_output, tall_sensor, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
  ['VERTICAL',   wide_region, wide_output, tall_sensor, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, wide_output, tall_sensor, (-0.3, 1.5), (711.1875956135597, 1692.8479145924057)],
  ['VERTICAL',   wide_region, tall_output, tall_sensor, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, tall_output, tall_sensor, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)]
]

from vanishing_lines_for_blender import view3d_gui
from conftest import MockContext

@pytest.mark.parametrize("fit_mode, region_size, output_size, sensor_size, compute_coords, region_coords",
  compute_combinations)
def test_project_compute_to_region(
    fit_mode:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
    region_size, 
    output_size,
    sensor_size,
    compute_coords,
    region_coords):
    
    # Create mock context
    context = MockContext(region_size, output_size, fit_mode)
    
    uiview = view3d_gui.View3dGUI()
    uiview.set_coordinate_system_to_camera_frame(context)

    result = uiview.project(compute_coords)
    
    assert pytest.approx(result[0], rel=1e-3) == region_coords[0]
    assert pytest.approx(result[1], rel=1e-3) == region_coords[1]

  

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])