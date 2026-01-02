import bpy


from . import vl_panel_components

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
        vl_panel_components.draw_solver_panel(layout, context.active_object)
        vl_panel_components.draw_reference_distance_panel(layout, context.active_object)
        vl_panel_components.draw_axis_assignment_panel(layout, context.active_object)
        vl_panel_components.draw_coordinates_panel(layout, context.active_object)

def register():
    bpy.utils.register_class(CAMERA_PT_custom_panel)

def unregister():
    bpy.utils.unregister_class(CAMERA_PT_custom_panel)