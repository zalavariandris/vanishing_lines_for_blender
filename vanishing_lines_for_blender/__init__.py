from . import vl_props
from . import vl_operators
from . import vl_sidepanel

def register():
    vl_props.register()
    vl_operators.register()
    vl_sidepanel.register()

def unregister():
    vl_sidepanel.unregister()
    vl_operators.unregister()
    vl_props.unregister()