from . import vl_properties_camera
from . import vl_op_solve_orientation

def register():
    vl_properties_camera.register()
    vl_op_solve_orientation.register()

def unregister():
    vl_op_solve_orientation.unregister()
    vl_properties_camera.unregister()