



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

import vl_coord_utils

sensor_options = ["AUTO", "HORIZONTAL", "VERTICAL"]
output_options = [(1920, 1080), (1080, 1920)]
region_options = [(2020, 1500), (1500, 2020)]

@pytest.mark.parametrize("sensor_fit, region_size, output_size", 
  list(product(sensor_options, output_options, region_options)))
def test_output_frame(
    sensor_fit:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
    region_size, 
    output_size):
    
    result = vl_coord_utils.map_from_output_frame_to_region_space(
        sensor_fit=sensor_fit,
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=1.0,
        view_camera_offset=(0.0, 0.0),
        coord=(output_size[0]/2, output_size[1]/2))
    
    print(f"sensor: {sensor_fit}, region: {region_size}, output: {output_size} => result: {result}")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])