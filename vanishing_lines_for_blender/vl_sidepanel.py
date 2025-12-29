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

        # validate context
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
        header_row = header.row()
        header_row.alert = camera.data.vl_settings.error_message != ""
        header_row.label(text="Solver")
       
        if panel:
            panel.prop(camera.data.vl_settings, "solver_is_paused", text="Pause Solver")
            panel.separator()

            # panel.prop(camera.data.vl_settings, "compute_space", text="Compute Space")
            # panel.separator()
            panel.prop(camera.data.vl_settings, "mode", text="Mode")

            mode = camera.data.vl_settings.mode

            # match mode:
            #     case 'ONE_POINT':
            row = panel.row()
            row.enabled = mode == 'ONE_POINT'
            row.prop(camera.data, "lens", text="Focal Length")

            row = panel.row()
            row.enabled = mode in {'ONE_POINT', 'TWO_POINT'}
            row.prop(camera.data.vl_settings, "enable_manual_principal", text="Manual Principal Point")

            row = panel.row()
            row.enabled = mode in {'TWO_POINT', 'THREE_POINT'}

            panel.separator()

            if error_msg:=camera.data.vl_settings.error_message:
                error_row = panel.column()
                error_row.alert = camera.data.vl_settings.error_message != ""
                lines = str(error_msg).splitlines()
                for i, line in enumerate(lines):
                    line_row = error_row.row()
                    if i == 0:
                        line_row.label(text=line, icon='ERROR')
                    else:
                        line_row.label(text=line)
        
        ######################
        # REFERENCE DISTANCE #
        ######################
        header, panel = self.layout.panel("reference_distance", default_closed=False)
        header.label(text="Reference Distance")
        if panel:
            panel.prop(camera.data.vl_settings, "scene_scale_mode", text="Scale Mode")
            panel.prop(camera.data.vl_settings, "scene_scale", text="Scene Scale")

            row = panel.row()
            row.enabled = camera.data.vl_settings.scene_scale_mode != 'ORIGIN'
            row.prop(camera.data.vl_settings, "reference_distance", text="Reference Distance")
            panel.separator()

        ###################
        # AXIS ASSIGNMENT #
        ###################
        header, panel = self.layout.panel("axis_assignement", default_closed=True)
        header.label(text="Axis Assignement")

        if panel:
            # panel.prop(camera.data.vl_settings, "floor", text="Floor", expand=False)
            row = panel.row()
            row.prop(camera.data.vl_settings, "first_axis", text="First Axis", expand=False)
            row = panel.row()
            incompatible_second_axis = camera.data.vl_settings.first_axis[0] == camera.data.vl_settings.second_axis[0]
            row.alert = incompatible_second_axis
            row.prop(camera.data.vl_settings, "second_axis", text="Second Axis", expand=False)
            panel.separator()

            box = panel.row()
            box.label(text="First Axis")
            col = box.column(align=True)
            
            row = col.row(align=True)
            row.prop_enum(camera.data.vl_settings, "first_axis", "X-")
            row.prop_enum(camera.data.vl_settings, "first_axis", "X+")

            row = col.row(align=True)
            row.prop_enum(camera.data.vl_settings, "first_axis", "Y-")
            row.prop_enum(camera.data.vl_settings, "first_axis", "Y+")

            row = col.row(align=True)
            row.prop_enum(camera.data.vl_settings, "first_axis", "Z-")
            row.prop_enum(camera.data.vl_settings, "first_axis", "Z+")

            box = panel.row()
            box.label(text="Second Axis")
            col = box.column(align=True)
            
            row = col.row(align=True)
            row.enabled = not camera.data.vl_settings.first_axis.startswith("X")
            row.prop_enum(camera.data.vl_settings, "second_axis", "X-")
            row.prop_enum(camera.data.vl_settings, "second_axis", "X+")

            row = col.row(align=True)
            row.enabled = not camera.data.vl_settings.first_axis.startswith("Y")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Y-")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Y+")


            row = col.row(align=True)
            row.enabled = not camera.data.vl_settings.first_axis.startswith("Z")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Z-")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Z+")

            # col.prop_enum(camera.data.vl_settings, "second_axis", text="Second Axis", expand=False)
            # col.prop_enum(camera.data.vl_settings, "third_axis", text="Third Axis", expand=False)
            # row = panel.row(align=False)
            # row.prop(camera.data.vl_settings, "first_axis_assignment", text="1st Axis", expand=True)
            # row.prop(camera.data.vl_settings, "first_axis_sign", text="1st Sign", expand=True)
            # row = panel.row(align=True)
            # row.prop(camera.data.vl_settings, "second_axis_assignment", text="2nd Axis", expand=True)
            # panel.separator()

        ##################
        # CONTROL POINTS #
        ##################
        header, panel = self.layout.panel("control_points", default_closed=True)
        header.label(text="Coordinates")

        if panel:
            # origin
            row = panel.row(align=True)
            row.prop(camera.data.vl_settings, 'origin')

            # principal
            row = panel.row(align=True)
            row.prop(camera.data.vl_settings, "principal")

            for label, lines in [
                ("1st Axis", camera.data.vl_settings.first_vanishing_lines), 
                ("2nd Axis", camera.data.vl_settings.second_vanishing_lines),
                ("3rd Axis", camera.data.vl_settings.third_vanishing_lines),
            ]:
                panel.separator()
                # row = panel.row(align=True)
                # panel.label(text=label)
                for ln, line in enumerate(lines):
                    # line_box = panel.box()
                    row = panel.row(align=False)
                    # grid = line_box.grid_flow(row_major=True, columns=3, even_columns=False, even_rows=False, align=False)
                    row.label(text=f"{label}" if ln == 0 else "")
                    row.prop(line, 'start', text="")
                    row.prop(line, "end", text="")

            panel.separator()

        # #####################
        # # BACKGROUND IMAGES #
        # #####################
        # header, panel = self.layout.panel("Background_Images", default_closed=True)

        # header.prop(camera.data, "show_background_images", text="Background Images")
        
        # if panel:
        #     panel.label(text="See camera properties for more options.")
        #     # box = self.layout.box()
        #     for i, bg in enumerate(camera.data.background_images):
        #         box = self.layout.box()
        #         header, panel = box.panel(f"No{i}_vl_bg_image", default_closed=True)
        #         header.label(text=f"{bpy.path.basename(bg.image.filepath)}" if bg.image else "Not Set")
        #         # header.prop(bg, "show_expanded", text="", emboss=False, icon="TRIA_DOWN" if bg.show_expanded else "TRIA_RIGHT")
        #         header.prop(bg, "show_background_image", text="", icon="HIDE_ON" if bg.show_background_image else "HIDE_OFF", emboss=False)
        #         if panel:
        #             panel.prop(bg, "alpha", text="Opacity", slider=True)

        #     panel.separator()


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
