import os
import bpy


################
# VL SIDEPANEL #
################
class CAMERA_OT_add_bg_image(bpy.types.Operator):
    bl_idname = "camera.add_bg_image"
    bl_label = "Add Background Image"

    def execute(self, context):
        cam = context.camera
        cam.background_images.new()
        return {'FINISHED'}

class CAMERA_OT_remove_bg_image(bpy.types.Operator):
    bl_idname = "camera.remove_bg_image"
    bl_label = "Remove Background Image"

    bg_index: bpy.props.IntProperty()

    def execute(self, context):
        cam = context.camera
        cam.background_images.remove(cam.background_images[self.bg_index])
        return {'FINISHED'}

from pathlib import Path

def is_operator_running(op_idname):
    for op in bpy.context.window.modal_operators:
        if op.bl_idname == 'VIEW_OT_vanishing_lines_operator':
            return True
    return False

class VIEW_PT_vanishing_lines(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Vanishing Lines"
    bl_idname = "VIEW_PT_vanishing_lines"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VL'

    def draw(self, context):
        #################
        # ACTIVE CAMERA #
        #################
        camera = context.scene.camera
        if camera is None:
            self.layout.label(text="No active camera in the scene.")
            return
        
        self.layout.label(text=f"Active Camera: '{camera.name}'")

        if not is_operator_running("VIEW_OT_vanishing_lines_operator"):
            self.layout.operator("view.vanishing_lines_operator", text="Start Vanishing Lines")
            return

        ##########
        # SOLVER #
        ##########
        header, panel = self.layout.panel("solver", default_closed=False)
        header.label(text="Solver")
        if panel:
            panel.prop(camera.data.vl_settings, "scene_scale", text="Scene Scale")
            panel.prop(camera.data.vl_settings, "mode", text="Mode")

            mode = camera.data.vl_settings.mode

            match mode:
                case 'ONE_POINT':
                    panel.prop(camera.data, "lens", text="Focal Length")

                case 'TWO_POINT':
                    panel.prop(camera.data.vl_settings, "quad_mode", text="Quad Mode")
                    panel.prop(camera.data.vl_settings, "enable_manual_principal", text="Manual Principal Point")

                case 'THREE_POINT':
                    panel.prop(camera.data.vl_settings, "quad_mode", text="Quad Mode")
            
            panel.separator()
                

        ##################
        # CONTROL POINTS #
        ##################
        header, panel = self.layout.panel("control_points", default_closed=True)
        header.label(text="Coordinates")

        if panel:
            # origin
            row = panel.row(align=True)
            row.label(text="Origin")
            row.prop(camera.data.vl_settings.origin, "x", text="X")
            row.prop(camera.data.vl_settings.origin, "y", text="Y")

            # principal
            row = panel.row(align=True)
            row.label(text="Principal")
            row.prop(camera.data.vl_settings.manual_principal, "x", text="X")
            row.prop(camera.data.vl_settings.manual_principal, "y", text="Y")

            for label, lines in [("Y Axis", camera.data.vl_settings.first_vanishing_lines), ("X Axis", camera.data.vl_settings.second_vanishing_lines)]:
                panel.separator()
                panel.label(text=label)
                for line in lines:
                    line_box = panel.box()
                    # col = group.column(align=True)
                    grid = line_box.grid_flow(row_major=True, columns=3, even_columns=False, even_rows=False, align=True)
                    grid.label(text="start")
                    grid.prop(line.start, "x", text="X")
                    grid.prop(line.start, "y", text="Y")

                    grid.label(text="end")
                    grid.prop(line.end, "x", text="X")
                    grid.prop(line.end, "y", text="Y")

            panel.separator()

        #####################
        # BACKGROUND IMAGES #
        #####################
        header, panel = self.layout.panel("Background_Images", default_closed=True)

        header.prop(camera.data, "show_background_images", text="Background Images")
        
        if panel:
            panel.label(text="See camera properties for more options.")
            # box = self.layout.box()
            for i, bg in enumerate(camera.data.background_images):
                box = self.layout.box()
                header, panel = box.panel(f"No{i}_vl_bg_image", default_closed=True)
                header.label(text=f"{bpy.path.basename(bg.image.filepath)}" if bg.image else "Not Set")
                # header.prop(bg, "show_expanded", text="", emboss=False, icon="TRIA_DOWN" if bg.show_expanded else "TRIA_RIGHT")
                header.prop(bg, "show_background_image", text="", icon="HIDE_ON" if bg.show_background_image else "HIDE_OFF", emboss=False)
                if panel:
                    panel.prop(bg, "alpha", text="Opacity", slider=True)

            panel.separator()
                


######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(CAMERA_OT_add_bg_image)
    bpy.utils.register_class(CAMERA_OT_remove_bg_image)
    bpy.utils.register_class(VIEW_PT_vanishing_lines)
    
def unregister():
    bpy.utils.unregister_class(VIEW_PT_vanishing_lines)
    bpy.utils.unregister_class(CAMERA_OT_remove_bg_image)
    bpy.utils.unregister_class(CAMERA_OT_add_bg_image)
