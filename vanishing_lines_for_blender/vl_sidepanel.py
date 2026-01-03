import bpy

from . import vl_panel_components
from . import vl_utils

################
# VL SIDEPANEL #
################

OPERATOR_ID_START = "view.vanishing_lines_operator"
OPERATOR_ID_STOP = "view.vanishing_lines_stop_operator"
OPERATOR_CLASS_NAME = "VIEW_OT_vanishing_lines_operator"

class VIEW_PT_VanishingLinesPanel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Vanishing Lines"
    bl_idname = "VIEW_PT_VanishingLinesPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VL'

    def draw(self, context):
        #################
        # ACTIVE CAMERA #
        #################
        camera = vl_utils.get_calibration_camera(context)

        if camera is None:
            self.layout.label(text="Calibration uses the view's local camera or the active scene camera, but none is set.", icon='ERROR')
            return 
        elif context.scene.camera == camera:
            self.layout.label(text=f"Using scene's camera: {camera.name}", icon='CAMERA_DATA')
        elif vl_utils.get_view_camera(context) == camera:
            self.layout.label(text=f"Using view's local camera: {camera.name}", icon='CAMERA_DATA')
        
    
        is_modal_running = vl_utils.is_operator_running(OPERATOR_CLASS_NAME)

        control_row = self.layout.row()
        if not is_modal_running:
            control_row.operator(OPERATOR_ID_START, text=f"Start Calibrating '{camera.name}'", icon='PLAY')
        else:
            control_row.operator(OPERATOR_ID_STOP, text="Stop", icon='SNAP_FACE')

        # col = self.layout.column()
        # col.use_property_split = True
        # col.use_property_decorate = False
        
        # col.prop(camera.data.vl_settings, "update_strategy", text="Update")
        
        self.layout.separator()
        
        vl_panel_components.draw_background_images_panel(self.layout, camera)
        vl_panel_components.draw_solver_panel(self.layout, camera)
        vl_panel_components.draw_reference_distance_panel(self.layout, camera)
        vl_panel_components.draw_axis_assignment_panel(self.layout, camera)
        vl_panel_components.draw_coordinates_panel(self.layout, camera)

        # header, coordinates_panel = self.layout.panel("all_icons", default_closed=True)
        # header.label(text="blender Icons")
        # if coordinates_panel:
        #     vl_view.draw_all_icons(coordinates_panel)


######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(VIEW_PT_VanishingLinesPanel)
    
def unregister():
    bpy.utils.unregister_class(VIEW_PT_VanishingLinesPanel)

if __name__ == "__main__":
    register()
