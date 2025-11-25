from . import vl_params
from . import vl_op
from . import vl_sidepanel
from . import camera_panel

def register():
    vl_params.register()
    vl_op.register()
    vl_sidepanel.register()
    camera_panel.register()

def unregister():
    camera_panel.unregister()
    vl_sidepanel.unregister()
    vl_op.unregister()
    vl_params.unregister()