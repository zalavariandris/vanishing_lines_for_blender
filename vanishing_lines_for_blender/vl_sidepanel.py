import bpy


from . import vl_utils
from . import vl_props


class AXIS_MT_custom_menu(bpy.types.Menu):
    bl_label = "Select Axis Alignment"
    bl_idname = "AXIS_MT_custom_menu"

    def draw(self, context):
        layout = self.layout
        assert layout is not None, "Layout is None in VL Context Menu"
        # 'vl' represents wherever your property is stored
        vl = vl_props.get_current(context)
        
        items = [
            ('X+Y-', "X+ Y-", ""), ('X-Y-', "X- Y-", ""),
            ('X+Y+', "X+ Y+", ""), ('X-Y+', "X- Y+", ""),
            ('X+Z-', "X+ Z-", ""), ('X-Z-', "X- Z-", ""),
            ('X+Z+', "X+ Z+", ""), ('X-Z+', "X- Z+", ""),

            ('Y+X-', "Y+ X-", ""), ('Y-X-', "Y- X-", ""),
            ('Y+X+', "Y+ X+", ""), ('Y-X+', "Y- X+", ""),
            ('Y+Z-', "Y+ Z-", ""), ('Y-Z-', "Y- Z-", ""),
            ('Y+Z+', "Y+ Z+", ""), ('Y-Z+', "Y- Z+", ""),
            
            ('Z+X-', "Z+ X-", ""), ('Z-X-', "Z- X-", ""),
            ('Z+X+', "Z+ X+", ""), ('Z-X+', "Z- X+", ""),
            ('Z+Y-', "Z+ Y-", ""), ('Z-Y-', "Z- Y-", ""),
            ('Z+Y+', "Z+ Y+", ""), ('Z-Y+', "Z- Y+", "")
        ]

        # Use a column to contain the grid
        main_col = layout.column(align=True)

        for i in range(0, len(items), 2):
            row_nr = i // 2
            col_nr = i % 2
            # Visual grouping for X, Y, and Z sections

            if row_nr%4==0 and row_nr > 0:
                main_col.separator(factor=1.0) # Smaller gap between rows within a group
                # if col_nr % 2 == 1:
                #     main_col.label(text="+")  # Empty label for spacing
                # else:
                #     main_col.label(text="-")  # Empty label for spacing
            
            row = main_col.row(align=True)
            # This creates the toggle buttons inside the menu
            row.prop_enum(vl, "axes", value=items[i][0])
            row.prop_enum(vl, "axes", value=items[i+1][0])


class VIEW_PT_VanishingLinesPanel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Vanishing Lines"
    bl_idname = "VIEW_PT_VanishingLinesPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VL'

    @classmethod
    def poll(cls, context):
        return True
        vl = vl_props.get_current(context)
        if not vl.active:
            return False

        if not context.area.spaces.active.region_3d.view_perspective == 'CAMERA':
            return
        
        return True

    def draw(self, context):
        vl = vl_props.get_current(context)
        # if not vl.active:
        #     return
        
        # if not context.area.spaces.active.region_3d.view_perspective == 'CAMERA':
        #     return
        
        layout = self.layout

        assert layout is not None, "Layout is None in VL Context Menu"
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.
        
        layout.label(text="Mode", icon='VIEW_PERSPECTIVE')
        layout.prop_tabs_enum(vl, 'mode')

        layout.separator()
        layout.label(text="Settings", icon='SETTINGS')

        row = layout.row()
        row.enabled = vl.mode in {'ONE_POINT'}
        row.prop(vl, 'fovx')
        
        row = layout.row()
        row.enabled = vl.mode in {'TWO_POINT', 'THREE_POINT'}
        row.prop(vl, 'quad_mode')

        row = layout.row()
        row.enabled = vl.mode in {'ONE_POINT', 'TWO_POINT'}

        layout.separator()
        # layout.label(text="Axes", icon='AXIS_TOP')
        # layout.label(text="Axes", icon='EMPTY_DATA')
        layout.label(text="Axes", icon='EMPTY_AXIS')
        # layout.label(text="Axes", icon='EMPTY_ARROWS')
        first_axis_row = layout.row()
        first_axis_row.prop(vl, 'first_axis')
        first_axis_row.prop(vl, 'first_axis_sign', text="")

        second_axis_row = layout.row()
        second_axis_row.prop(vl, 'second_axis')
        second_axis_row.prop(vl, 'second_axis_sign', text="")
        layout.separator()
        layout.label(text="Size", icon='DRIVER_DISTANCE')

        layout.prop(vl, 'reference_scale_mode')

        layout.prop(vl, 'reference_scene_scale')
        col = layout.column()
        col.enabled = vl.reference_scale_mode != 'ORIGIN'
        col.prop(vl, 'reference_screen_segment', index=0)
        col.prop(vl, 'reference_screen_segment', index=1)

def register():
    bpy.utils.register_class(AXIS_MT_custom_menu)
    bpy.utils.register_class(VIEW_PT_VanishingLinesPanel)

def unregister():
    bpy.utils.unregister_class(VIEW_PT_VanishingLinesPanel)
    bpy.utils.unregister_class(AXIS_MT_custom_menu)