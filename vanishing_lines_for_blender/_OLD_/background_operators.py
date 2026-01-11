import bpy

from . import vl_utils


class CAMERA_OT_add_bg_image(bpy.types.Operator):
    bl_idname = "camera.add_bg_image"
    bl_label = "Add Background Image"

    def execute(self, context):
        cam = vl_utils.get_scene_camera(context)
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
    index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        cam_data = vl_utils.get_scene_camera(context).data
        
        # Check if the index is valid before trying to remove
        try:
            cam_data.background_images.remove(cam_data.background_images[self.index])

            # This forces the current area (the panel) to refresh immediately
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
        except IndexError:
            self.report({'WARNING'}, "Invalid background image index")
            
        return {'FINISHED'}
    
draw_handler = None
def register():
    global draw_handler
    bpy.utils.register_class(CAMERA_OT_add_bg_image)
    bpy.utils.register_class(CAMERA_OT_remove_bg_image)

def unregister():
    bpy.utils.unregister_class(CAMERA_OT_remove_bg_image)
    bpy.utils.unregister_class(CAMERA_OT_add_bg_image)