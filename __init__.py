from .src import vl_params
from .src import vl_op
from .src import vl_sidepanel

def register():
    vl_params.register()
    vl_op.register()
    vl_sidepanel.register()

def unregister():
    vl_sidepanel.unregister()
    vl_op.unregister()
    vl_params.unregister()