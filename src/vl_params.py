# type: ignore
import bpy


class Point(bpy.types.PropertyGroup):
    x: bpy.props.FloatProperty(name="x", default=0.0)
    y: bpy.props.FloatProperty(name="y", default=0.0)


class Line(bpy.types.PropertyGroup):
    start: bpy.props.PointerProperty(name="start", type=Point)
    end: bpy.props.PointerProperty(name="end", type=Point)


class VLSettings(bpy.types.PropertyGroup):
    points_index: bpy.props.IntProperty(name="Active Point Index", default=0)
    origin: bpy.props.PointerProperty(name="origin", type=Point)
    first_vanishing_lines: bpy.props.CollectionProperty(
        name="first_vanishing_lines",
        type=Line
    )
    second_vanishing_lines: bpy.props.CollectionProperty(
        name="second_vanishing_lines", 
        type=Line
    )
    
    points: bpy.props.CollectionProperty(name="points", type=Point)
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Vanishing line mode",
        items=[
            ('ONE_POINT', "1-Point", "Use 1-point perspective"),
            ('TWO_POINT', "2-Point", "Use 2-point perspective"),
        ],
        default='TWO_POINT'
    )
    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        description="Enable quad mode for 2-point perspective",
        default=False
    )
    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        description="Scale of the scene for vanishing lines",
        default=1.0,
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
    bpy.types.Scene.vl_settings = bpy.props.PointerProperty(type=VLSettings)
    
def unregister():
    if hasattr(bpy.types.Scene, 'vl_settings'):
        del bpy.types.Scene.vl_settings

    bpy.utils.unregister_class(Point)
    bpy.utils.unregister_class(Line)
    bpy.utils.unregister_class(VLSettings)