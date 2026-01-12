import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock Blender modules before any imports
sys.modules['bpy'] = MagicMock()
sys.modules['bpy.types'] = MagicMock()
sys.modules['bpy.props'] = MagicMock()
sys.modules['gpu'] = MagicMock()
sys.modules['gpu.shader'] = MagicMock()
sys.modules['gpu_extras'] = MagicMock()
sys.modules['gpu_extras.batch'] = MagicMock()
sys.modules['blf'] = MagicMock()
sys.modules['mathutils'] = MagicMock()
sys.modules['bpy_extras'] = MagicMock()
sys.modules['bpy_extras.view3d_utils'] = MagicMock()

# Add the vanishing_lines_for_blender directory to Python path
# This allows importing core as a standalone module
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MockContext:
    """Mock Blender context for testing coordinate transformations"""
    def __init__(self, 
            region_size, 
            output_size=(1920, 1080),
            sensor_fit='AUTO', 
            sensor_width=36.0, 
            sensor_height=24.0,
            view_camera_zoom=-6.109, 
            view_camera_offset=(-0.07, -0.03)
        ):
        # Create nested mock structure
        self.region = type('Region', (), {
            'width': region_size[0],
            'height': region_size[1]
        })()
        
        self.scene = type('Scene', (), {
            'render': type('Render', (), {
                'resolution_x': output_size[0],
                'resolution_y': output_size[1]
            })()
        })()
        
        self.space_data = type('SpaceData', (), {
            'region_3d': type('RegionView3D', (), {
                'view_perspective': 'CAMERA',
                'view_camera_zoom': view_camera_zoom,
                'view_camera_offset': view_camera_offset
            })(),
            'camera': type('Object', (), {
                'data': type('Camera', (), {
                    'sensor_fit': sensor_fit,
                    'sensor_width': sensor_width,
                    'sensor_height': sensor_height
                })()
            })()
        })()
