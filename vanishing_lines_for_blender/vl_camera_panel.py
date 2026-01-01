import bpy


from . import vl_view

class CAMERA_PT_custom_panel(bpy.types.Panel):
    bl_label = "Vanishing Lines"
    bl_idname = "CAMERA_PT_custom_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        # Check if there is an active object and if it's a camera
        return context.active_object and context.active_object.type == 'CAMERA'

    def draw(self, context):
        layout = self.layout
        # cam = context.camera

        layout.label(text=f"'{context.active_object.name}'", icon='CAMERA_DATA')

        vl_view.draw_solver_panel(layout, context.active_object)

def register():
    print("Registering camera panel...")
    bpy.utils.register_class(CAMERA_PT_custom_panel)

def unregister():
    print("Unregistering camera panel...")
    bpy.utils.unregister_class(CAMERA_PT_custom_panel)