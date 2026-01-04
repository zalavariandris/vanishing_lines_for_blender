from . import vl_params
from . import vl_operators
from . import vl_utils
from . import vl_sidepanel
from . import vl_camera_panel
from . import background_operators
from . import calibrate_view_tool

def register():
    background_operators.register()
    vl_params.register()
    vl_operators.register()
    vl_sidepanel.register()
    calibrate_view_tool.register()
    # vl_camera_panel.register()

def unregister():
    # vl_camera_panel.unregister()
    calibrate_view_tool.unregister()
    vl_sidepanel.unregister()
    vl_operators.unregister()
    vl_params.unregister()
    background_operators.unregister()