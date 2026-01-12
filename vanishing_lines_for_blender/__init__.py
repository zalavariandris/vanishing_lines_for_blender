from . import vl_params
from . import vanishing_lines_tool


def register():
    vl_params.register()
    vanishing_lines_tool.register()

def unregister():
    vanishing_lines_tool.unregister()
    vl_params.unregister()