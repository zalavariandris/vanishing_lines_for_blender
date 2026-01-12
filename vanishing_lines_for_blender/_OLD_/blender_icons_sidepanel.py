import bpy

#################
# BLENDER ICONS #
#################
def draw_all_icons(layout):

    all_icons = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys()

    col = layout.column()
    for icon in all_icons:
        try:
            col.label(text=icon, icon=icon)
        except TypeError as e:
            print(f"Icon '{icon}' not found.")


class VIEW_PT_BlenderIcons(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Icons"
    bl_idname = "VIEW_PT_BlenderIcons"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Icons'

    def draw(self, context):
        draw_all_icons(self.layout)


######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(VIEW_PT_BlenderIcons)
    
def unregister():
    bpy.utils.unregister_class(VIEW_PT_BlenderIcons)

if __name__ == "__main__":
    register()
