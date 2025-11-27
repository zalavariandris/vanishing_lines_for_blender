# type: ignore
import bpy


class Point(bpy.types.PropertyGroup):
    name="Point"
    x: bpy.props.FloatProperty(name="x", default=0.0)# is_animatable=False, subtype='PIXEL')
    y: bpy.props.FloatProperty(name="y", default=0.0)


class Line(bpy.types.PropertyGroup):
    name="Line"
    start: bpy.props.PointerProperty(name="start", type=Point)
    end: bpy.props.PointerProperty(name="end", type=Point)


class VLSettings(bpy.types.PropertyGroup):
    name="VL Settings"

    initialized: bpy.props.BoolProperty(name="Initialized", default=False, options={'HIDDEN'})

    origin: bpy.props.PointerProperty(name="origin", type=Point)

    enable_manual_principal: bpy.props.BoolProperty(
        name="Manual Principal Point",
        description="Set principal point manually",
        default=False
    )
    
    manual_principal: bpy.props.PointerProperty(name="manual_principal", type=Point)

    first_vanishing_lines: bpy.props.CollectionProperty(
        name="First Vanishing Lines",
        type=Line
    )

    second_vanishing_lines: bpy.props.CollectionProperty(
        name="Second Vanishing Lines", 
        type=Line
    )

    third_vanishing_lines: bpy.props.CollectionProperty(
        name="Third Vanishing Lines", 
        type=Line
    )
    
    mode: bpy.props.EnumProperty(
        name="Perspective Mode",
        description="Perspective Mode",
        items=[
            ('ONE_POINT',   "1-Point", "Use 1-point perspective"),
            ('TWO_POINT',   "2-Point", "Use 2-point perspective"),
            ('THREE_POINT', "3-Point", "Use 3-point perspective")
        ],
        default='THREE_POINT'
    )

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        description="Enable quad mode for 2-point perspective",
        default=False
    )

    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        description="Scale of the scene for vanishing lines",
        default=10.0,
        min=0.01,
        max=100.0
    )

######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(Point)
    bpy.utils.register_class(Line)
    bpy.utils.register_class(VLSettings)
    bpy.types.Camera.vl_settings = bpy.props.PointerProperty(type=VLSettings, name="VL Settings")
    
def unregister():
    if hasattr(bpy.types.Camera, 'vl_settings'):
        del bpy.types.Camera.vl_settings
    bpy.utils.unregister_class(Point)
    bpy.utils.unregister_class(Line)
    bpy.utils.unregister_class(VLSettings)