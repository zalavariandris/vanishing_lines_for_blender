# import pytest
# from typing import Literal


# from vanishing_lines_for_blender import vl_coord_utils

# WIDE_OUTPUT = (1920, 1080)
# TALL_OUTPUT = (1080, 1920)
# WIDE_REGION = (2020, 1500)
# TAL_REGION = (1500, 2020)
# WIDE_SENSOR = (36, 24)
# TALL_SENSOR = (24, 36)

# compute_combinations = [
#   ['AUTO',       WIDE_REGION, WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
#   ['AUTO',       TAL_REGION,  WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
#   ['AUTO',       WIDE_REGION, TALL_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
#   ['AUTO',       TAL_REGION,  TALL_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
#   ['HORIZONTAL', WIDE_REGION, WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
#   ['HORIZONTAL', TAL_REGION,  WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
#   ['HORIZONTAL', WIDE_REGION, TALL_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272777)],
#   ['HORIZONTAL', TAL_REGION,  TALL_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
#   ['VERTICAL',   WIDE_REGION, WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
#   ['VERTICAL',   TAL_REGION,  WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (711.1875956135597, 1692.8479145924057)],
#   ['VERTICAL',   WIDE_REGION, TALL_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
#   ['VERTICAL',   TAL_REGION,  TALL_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
#   ['AUTO',       WIDE_REGION, WIDE_OUTPUT, WIDE_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
#   ['AUTO',       TAL_REGION,  WIDE_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
#   ['AUTO',       WIDE_REGION, TALL_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
#   ['AUTO',       TAL_REGION,  TALL_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)],
#   ['HORIZONTAL', WIDE_REGION, WIDE_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272774)],
#   ['HORIZONTAL', TAL_REGION,  WIDE_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
#   ['HORIZONTAL', WIDE_REGION, TALL_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (1001.5697788321926, 1419.8269789272777)],
#   ['HORIZONTAL', TAL_REGION,  TALL_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (743.7399347763807, 1530.0862187783011)],
#   ['VERTICAL',   WIDE_REGION, WIDE_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
#   ['VERTICAL',   TAL_REGION,  WIDE_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (711.1875956135597, 1692.8479145924057)],
#   ['VERTICAL',   WIDE_REGION, TALL_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (1034.1221179950135, 1257.0652831131727)],
#   ['VERTICAL',   TAL_REGION,  TALL_OUTPUT, TALL_SENSOR, (-0.3, 1.5), (711.1875956135596, 1692.8479145924057)]
# ]

# @pytest.mark.parametrize("fit_mode, region_size, output_size, sensor_size, compute_coords, region_coords",
#   compute_combinations)
# def test_cameraframe_to_region(
#     fit_mode:Literal['AUTO', 'HORIZONTAL', 'VERTICAL'], 
#     region_size, 
#     output_size,
#     sensor_size,
#     compute_coords,
#     region_coords):
    
#     # Mock context
#     class MockContext:
#         class Region:
#             def __init__(self, width, height):
#                 self.width = width
#                 self.height = height
        
#         class Scene:
#             class Render:
#                 def __init__(self, res_x, res_y):
#                     self.resolution_x = res_x
#                     self.resolution_y = res_y
            
#             def __init__(self, res_x, res_y):
#                 self.render = self.Render(res_x, res_y)
        
#         class SpaceData:
#             class Camera:
#                 class Data:
#                     def __init__(self, sensor_fit, sensor_width, sensor_height):
#                         self.sensor_fit = sensor_fit
#                         self.sensor_width = sensor_width
#                         self.sensor_height = sensor_height
                
#                 def __init__(self, sensor_fit, sensor_width, sensor_height):
#                     self.data = self.Data(sensor_fit, sensor_width, sensor_height)
            
#             def __init__(self, sensor_fit, sensor_width, sensor_height):
#                 self.camera = self.Camera(sensor_fit, sensor_width, sensor_height)
        
#         def __init__(self, region_size, output_size, sensor_size, sensor_fit):
#             self.region = self.Region(region_size[0], region_size[1])
#             self.scene = self.Scene(output_size[0], output_size[1])
#             self.space_data = self.SpaceData(sensor_fit, sensor_size[0], sensor_size[1])
    
#     context = MockContext(region_size, output_size, sensor_size, fit_mode)

#     cameraframe = vl_coord_utils.get_camera_frame(context)
    
#     # print(f"{fit_mode:10s}, {region_size}, {output_size}, {sensor_size} {result}")
    
#     print(cameraframe)

#     # assert pytest.approx(project_result[0], rel=1e-3) == region_coords[0]
#     # assert pytest.approx(project_result[1], rel=1e-3) == region_coords[1]


# if __name__ == "__main__":
#     pytest.main([__file__, "-v", "-s"])