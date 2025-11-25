import bpy


class CAMERA_PT_vanishing_lines(bpy.types.Panel):
    bl_label = "Custom Background Images"
    bl_idname = "CAMERA_PT_custom_bgimages"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"  # camera data tab

    @classmethod
    def poll(cls, context):
        return context.camera is not None

    def draw(self, context):
        ...
        # cam = context.camera
        # layout = self.layout

        # layout.label(text="Background Images:")

        # # Toggle for enabling background images
        # layout.prop(cam, "show_background_images", text="Enable Background Images")

        # if cam.show_background_images:
        #     for bg in cam.background_images:
        #         box = layout.box()
        #         row = box.row()
        #         row.prop(bg, "image", text="")
        #         row.prop(bg, "alpha", slider=True)
        #         row.operator("camera.remove_bg_image", text="", icon="X").bg_index = cam.background_images.values().index(bg)

        #         box.prop(bg, "display_depth", text="Depth")
        #         box.prop(bg, "frame_method")

        #         col = box.column(align=True)
        #         col.label(text="Transform:")
        #         col.prop(bg, "offset_x")
        #         col.prop(bg, "offset_y")
        #         col.prop(bg, "scale")
        #         col.prop(bg, "rotation")

        # layout.operator("camera.add_bg_image", icon="ADD")



def register():
    bpy.utils.register_class(CAMERA_PT_vanishing_lines)


def unregister():
    bpy.utils.unregister_class(CAMERA_PT_vanishing_lines)
