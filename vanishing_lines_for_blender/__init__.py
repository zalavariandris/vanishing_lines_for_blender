from . import vl_params
from . import vl_operator
from . import vl_utils
from . import vl_sidepanel
from . import vl_camera_panel

def register():
    print("registering vanishing_lines_for_blender...")
    vl_params.register()
    vl_operator.register()
    vl_sidepanel.register()
    vl_camera_panel.register()

def unregister():
    print("unregistering vanishing_lines_for_blender...")
    vl_camera_panel.unregister()
    vl_sidepanel.unregister()
    vl_operator.unregister()
    vl_params.unregister()