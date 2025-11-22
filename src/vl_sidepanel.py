import bpy


###############
# VL OPERATOR #
###############
class VIEW_PT_vanishing_lines(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Vanishing Lines"
    bl_idname = "VIEW_PT_vanishing_lines"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VL'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Vanishing Lines")
        layout.operator("view.vanishing_lines_operator", text="Start Vanishing Lines")
        
        layout.separator()
        camera = context.scene.camera
        if camera is not None:
            layout.label(text=f"Active Camera: '{camera.name}'")
        else:
            layout.label(text="No active camera in the scene.")


        layout.prop(scene.vl_settings, "mode", text="Mode")

        mode = context.scene.vl_settings.mode
        if mode == 'ONE_POINT':
            layout.prop(camera.data, "lens", text="Focal Length")

        elif mode == 'TWO_POINT':
            row = layout.row()
            row.enabled = False
            row.prop(camera.data, "lens", text="Focal Length")
            layout.prop(scene.vl_settings, "quad_mode", text="Quad Mode")

        # vanishing lines

        header, group = layout.panel("vl line params")
        header.label(text="Vanisghing Line Coordinates")

        group.label(text="Y Axis")
        for i, line in enumerate(scene.vl_settings.first_vanishing_lines):
            col = group.column()
            row = col.row(align=True)
            row.prop(line.start, "x", text="Start X")
            row.prop(line.start, "y", text="Start Y")

            row = col.row(align=True)
            row.prop(line.end, "x", text="End X")
            row.prop(line.end, "y", text="End Y")

        group.separator()
        
        group.label(text="X Axis")
        for i, line in enumerate(scene.vl_settings.second_vanishing_lines):
            col = group.column()
            row = col.row(align=True)
            row.prop(line.start, "x", text="Start X")
            row.prop(line.start, "y", text="Start Y")

            row = col.row(align=True)
            row.prop(line.end, "x", text="End X")
            row.prop(line.end, "y", text="End Y")

######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(VIEW_PT_vanishing_lines)
    
def unregister():
    bpy.utils.unregister_class(VIEW_PT_vanishing_lines)