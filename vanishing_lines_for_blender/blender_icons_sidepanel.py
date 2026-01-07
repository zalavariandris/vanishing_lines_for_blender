import bpy

from . import vl_panel_components
from . import vl_utils

#################
# BLENDER ICONS #
#################
class VIEW_PT_BlenderIcons(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Icons"
    bl_idname = "VIEW_PT_BlenderIcons"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Icons'

    def draw(self, context):
        header, coordinates_panel = self.layout.panel("all_icons", default_closed=True)
        header.label(text="blender Icons")
        if coordinates_panel:
            vl_panel_components.draw_all_icons(coordinates_panel)


######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(VIEW_PT_BlenderIcons)
    
def unregister():
    bpy.utils.unregister_class(VIEW_PT_BlenderIcons)

if __name__ == "__main__":
    register()
