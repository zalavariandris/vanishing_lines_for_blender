import bpy


class CAMERA_PT_custom_panel(bpy.types.Panel):
    """Creates a custom panel in the Camera Data properties tab"""
    bl_label = "My Custom Camera Tools"
    bl_idname = "CAMERA_PT_custom_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"  # This puts it in the 'Data' tab (the green camera icon)

    @classmethod
    def poll(cls, context):
        # Only show this panel if the active object is a Camera
        return context.camera is not None

    def draw(self, context):
        layout = self.layout
        cam = context.camera

        layout.label(text="Camera Settings", icon='CAMERA_DATA')
        
        # Display existing camera properties
        layout.prop(cam, "lens")
        layout.prop(cam, "clip_start", text="Near Clip")
        
        layout.separator()
        
        # Example: Add a button (operator)
        layout.operator("render.render", text="Quick Render", icon='RENDER_STILL')

