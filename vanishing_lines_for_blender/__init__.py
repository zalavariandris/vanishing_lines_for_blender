from . import vl_params
from . import vl_operators
from . import vl_utils
from . import vl_sidepanel
from . import vl_camera_panel

def register():
    vl_params.register()
    vl_operators.register()
    vl_sidepanel.register()
    vl_camera_panel.register()

def unregister():
    vl_camera_panel.unregister()
    vl_sidepanel.unregister()
    vl_operators.unregister()
    vl_params.unregister()