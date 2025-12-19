



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
wide_sensor = (36, 24)
tall_sensor = (24, 36)
sensor_options = ["AUTO", "HORIZONTAL", "VERTICAL"]
output_options = [wide_output, tall_output]
region_options = [wide_region, tall_region]

output_combinations = list(product(sensor_options, output_options, region_options))
output_combinations = [
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
  output_combinations)
def test_project_output_to_region(
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

sensor_combinations = [
  ['AUTO',       wide_region, wide_output, wide_sensor, (1268.5267824794296, 740.7258292983416)],
  ['AUTO',       tall_region, wide_output, wide_sensor, (978.1445992607966, 1013.74676496347)],
  ['AUTO',       wide_region, tall_output, wide_sensor, (1268.5267824794296, 740.7258292983416)],
  ['AUTO',       tall_region, tall_output, wide_sensor, (978.1445992607966, 1013.74676496347)],
  ['HORIZONTAL', wide_region, wide_output, wide_sensor, (1268.5267824794296, 881.2295154284661)],
  ['HORIZONTAL', tall_region, wide_output, wide_sensor, (941.9753335243288, 1130.1376072692829)],
  ['HORIZONTAL', wide_region, tall_output, wide_sensor, (1268.5267824794296, 881.2295154284664)],
  ['HORIZONTAL', tall_region, tall_output, wide_sensor, (941.9753335243288, 1130.1376072692829)],
  ['VERTICAL',   wide_region, wide_output, wide_sensor, (1284.52472693979, 891.8948117353734)],
  ['VERTICAL',   tall_region, wide_output, wide_sensor, (1048.3964423258587, 1201.0850131369696)],
  ['VERTICAL',   wide_region, tall_output, wide_sensor, (1284.52472693979, 891.8948117353734)],
  ['VERTICAL',   tall_region, tall_output, wide_sensor, (1048.3964423258587, 1201.0850131369696)],
  ['AUTO',       wide_region, wide_output, wide_sensor, (1268.5267824794296, 740.7258292983416)],
  ['AUTO',       tall_region, wide_output, tall_sensor, (978.1445992607966, 1482.092385397219)],
  ['AUTO',       wide_region, tall_output, tall_sensor, (1268.5267824794296, 1209.0714497320905)],
  ['AUTO',       tall_region, tall_output, tall_sensor, (978.1445992607966, 1482.092385397219)],
  ['HORIZONTAL', wide_region, wide_output, tall_sensor, (1268.5267824794296, 998.3159205369034)],
  ['HORIZONTAL', tall_region, wide_output, tall_sensor, (941.9753335243288, 1217.0829575973303)],
  ['HORIZONTAL', wide_region, tall_output, tall_sensor, (1268.5267824794296, 998.3159205369034)],
  ['HORIZONTAL', tall_region, tall_output, tall_sensor, (941.9753335243288, 1217.0829575973303)],
  ['VERTICAL',   wide_region, wide_output, tall_sensor, (1197.5793766117426, 891.8948117353734)],
  ['VERTICAL',   tall_region, wide_output, tall_sensor, (931.3100372174216, 1201.0850131369696)],
  ['VERTICAL',   wide_region, tall_output, tall_sensor, (1197.5793766117426, 891.8948117353734)],
  ['VERTICAL',   tall_region, tall_output, tall_sensor, (931.3100372174216, 1201.0850131369696)]
]
@pytest.mark.parametrize("fit_mode, region_size, output_size, sensor_size, expected",
  sensor_combinations)
def test_project_sensor_to_region(
    fit_mode:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
    region_size, 
    output_size,
    sensor_size,
    expected):
    
    result = vl_coord_utils.project_sensor_to_region(
        fit_mode=fit_mode,
        output_size=output_size,
        region_size=region_size,
        sensor_size=sensor_size,
        view_camera_zoom=-6.109,
        view_camera_offset=(-0.07, -0.03),
        sensor_coord=(sensor_size[0]*2/3, sensor_size[1]*2/3))
    
    # print(f"{sensor_fit:10s}, {region_size}, {output_size}, {sensor_size} {result}")

    assert pytest.approx(result[0], rel=1e-3) == expected[0]
    assert pytest.approx(result[1], rel=1e-3) == expected[1]



compute_combinations = [
  ['AUTO',       wide_region, wide_output, wide_sensor, (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, wide_output, wide_sensor, (711.1875956135596, 1692.8479145924057)],
  ['AUTO',       wide_region, tall_output, wide_sensor, (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, tall_output, wide_sensor, (711.1875956135596, 1692.8479145924057)],
  ['HORIZONTAL', wide_region, wide_output, wide_sensor, (1001.5697788321926, 1419.8269789272774)],
  ['HORIZONTAL', tall_region, wide_output, wide_sensor, (743.7399347763807, 1530.0862187783011)],
  ['HORIZONTAL', wide_region, tall_output, wide_sensor, (1001.5697788321926, 1419.8269789272777)],
  ['HORIZONTAL', tall_region, tall_output, wide_sensor, (743.7399347763807, 1530.0862187783011)],
  ['VERTICAL',   wide_region, wide_output, wide_sensor, (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, wide_output, wide_sensor, (711.1875956135597, 1692.8479145924057)],
  ['VERTICAL',   wide_region, tall_output, wide_sensor, (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, tall_output, wide_sensor, (711.1875956135596, 1692.8479145924057)],
  ['AUTO',       wide_region, wide_output, wide_sensor, (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, wide_output, tall_sensor, (711.1875956135596, 1692.8479145924057)],
  ['AUTO',       wide_region, tall_output, tall_sensor, (1001.5697788321926, 1419.8269789272774)],
  ['AUTO',       tall_region, tall_output, tall_sensor, (711.1875956135596, 1692.8479145924057)],
  ['HORIZONTAL', wide_region, wide_output, tall_sensor, (1001.5697788321926, 1419.8269789272774)],
  ['HORIZONTAL', tall_region, wide_output, tall_sensor, (743.7399347763807, 1530.0862187783011)],
  ['HORIZONTAL', wide_region, tall_output, tall_sensor, (1001.5697788321926, 1419.8269789272777)],
  ['HORIZONTAL', tall_region, tall_output, tall_sensor, (743.7399347763807, 1530.0862187783011)],
  ['VERTICAL',   wide_region, wide_output, tall_sensor, (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, wide_output, tall_sensor, (711.1875956135597, 1692.8479145924057)],
  ['VERTICAL',   wide_region, tall_output, tall_sensor, (1034.1221179950135, 1257.0652831131727)],
  ['VERTICAL',   tall_region, tall_output, tall_sensor, (711.1875956135596, 1692.8479145924057)]
]
@pytest.mark.parametrize("fit_mode, region_size, output_size, sensor_size, expected",
  compute_combinations)
def test_project_compute_to_region(
    fit_mode:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
    region_size, 
    output_size,
    sensor_size,
    expected):
    
    result = vl_coord_utils.project_compute_to_region(
        fit_mode=fit_mode,
        compute_rect=(-1,-1, 2, 2),
        output_size=output_size,
        region_size=region_size,
        view_camera_zoom=-6.109,
        view_camera_offset=(-0.07, -0.03),
        compute_coord=(-0.3, 1.5))
    
    # print(f"{fit_mode:10s}, {region_size}, {output_size}, {sensor_size} {result}")
    

    assert pytest.approx(result[0], rel=1e-3) == expected[0]
    assert pytest.approx(result[1], rel=1e-3) == expected[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])