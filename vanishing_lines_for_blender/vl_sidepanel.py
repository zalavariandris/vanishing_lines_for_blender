from email import header
import os
import bpy


################
# VL SIDEPANEL #
################
def get_scene_camera(context)-> bpy.types.Object|None:
    camera = context.scene.camera
    return camera


class CAMERA_OT_add_bg_image(bpy.types.Operator):
    bl_idname = "camera.add_bg_image"
    bl_label = "Add Background Image"

    def execute(self, context):
        cam = get_scene_camera(context)
        cam.data.background_images.new()

        # This forces the current area (the panel) to refresh immediately
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()

        return {'FINISHED'}

class CAMERA_OT_remove_bg_image(bpy.types.Operator):
    """Remove a specific background image from the camera"""
    bl_idname = "camera.remove_bg_image"
    bl_label = "Remove Background Image"
    bl_options = {'REGISTER', 'UNDO'}

    # This property will hold the index of the image to remove
    index: bpy.props.IntProperty()

    def execute(self, context):
        cam_data = get_scene_camera(context).data
        
        # Check if the index is valid before trying to remove
        if 0 <= self.index < len(cam_data.background_images):
            cam_data.background_images.remove(cam_data.background_images[self.index])

            # This forces the current area (the panel) to refresh immediately
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
        else:
            self.report({'WARNING'}, "Invalid background image index")
            
        return {'FINISHED'}
from pathlib import Path

def is_operator_running(op_idname):
    for op in bpy.context.window.modal_operators:
        if op.bl_idname == 'VIEW_OT_vanishing_lines_operator':
            return True
    return False



from . import vl_view

class VIEW_OT_VanishingLinesCancelOperator(bpy.types.Operator):
    bl_idname = "view.vanishing_lines_cancel_operator"
    bl_label = "Cancel Vanishing Lines Operator"

    def execute(self, context):
        for op in bpy.context.window.modal_operators:
            if op.bl_idname == 'VIEW_OT_vanishing_lines_operator':
                op.cancel(context)
                return {'FINISHED'}
        self.report({'WARNING'}, "No active Vanishing Lines Operator found")
        return {'CANCELLED'}

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

        # validate context
        camera = get_scene_camera(context)
        if camera is None:
            self.layout.label(text="No active camera in the scene.")
            return

        self.layout.label(text=f"{camera.name}", icon='CAMERA_DATA')

        if not is_operator_running("VIEW_OT_vanishing_lines_operator"):
            self.layout.operator("view.vanishing_lines_operator", text="Start Vanishing Lines", icon='PLAY')
            return
        
        self.layout.prop(camera.data.vl_settings, "solver_is_paused", text="Pause Solver", icon='PAUSE')
        self.layout.operator("screen.cancel_modal", text="Stop Operator")
        self.layout.operator("view.vanishing_lines_cancel_operator", text="Stop Vanishing Lines", icon='SNAP_FACE')

        # self.layout.operator("view.vanishing_lines_operator", text="Start Operator")
        # self.layout.operator("view.vanishing_lines_cancel_operator", text="Stop Operator")
        
        self.layout.separator()
        
        vl_view.draw_background_images_panel(self.layout, camera)
        vl_view.draw_solver_panel(self.layout, camera)
        vl_view.draw_reference_distance_panel(self.layout, camera)
        vl_view.draw_axis_assignment_panel(self.layout, camera)
        vl_view.draw_coordinates_panel(self.layout, camera)

        header, coordinates_panel = self.layout.panel("all_icons", default_closed=True)
        header.label(text="blender Icons")
        if coordinates_panel:
            vl_view.draw_all_icons(coordinates_panel)



######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(CAMERA_OT_add_bg_image)
    bpy.utils.register_class(CAMERA_OT_remove_bg_image)
    bpy.utils.register_class(VIEW_PT_VanishingLinesPanel)
    bpy.utils.register_class(VIEW_OT_VanishingLinesCancelOperator)
    
def unregister():
    bpy.utils.unregister_class(CAMERA_OT_remove_bg_image)
    bpy.utils.unregister_class(CAMERA_OT_add_bg_image)
    bpy.utils.unregister_class(VIEW_PT_VanishingLinesPanel)
    bpy.utils.unregister_class(VIEW_OT_VanishingLinesCancelOperator)

if __name__ == "__main__":
    register()
