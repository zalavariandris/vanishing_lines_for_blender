# type: ignore
import bpy


class Line(bpy.types.PropertyGroup):
    name="Line"
    start: bpy.props.FloatVectorProperty(
        name="start",
        size=2,
        default=(0.0, 0.0)
    )
    end: bpy.props.FloatVectorProperty(
        name="end",
        size=2,
        default=(0.0, 0.0)
    )


class VLSettings(bpy.types.PropertyGroup):
    name="VL Settings"

    initialized: bpy.props.BoolProperty(name="Initialized", default=False, options={'HIDDEN'})
    solver_is_paused: bpy.props.BoolProperty(name="Paused", default=False)

    # compute_space: bpy.props.FloatVectorProperty(
    #     name="Compute Space",
    #     description="Compute space rectangle (x, y, width, height)",
    #     size=4,
    #     default=(0.0, 0.0, 1920.0, 1080.0),
    #     # options={'HIDDEN'}
    # )

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

    enable_manual_principal: bpy.props.BoolProperty(
        name="Manual Principal Point",
        description="Set principal point manually",
        default=False
    )

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        description="Enable quad mode for 2-point perspective",
        default=False
    )

    scene_scale_mode: bpy.props.EnumProperty(
        name="Scene Scale Mode",
        description="Scene Scale Mode",
        items=[
            ('SCREEN', "Screen", "Use the screen plane for reference distance"),
            ('ORIGIN', "Origin", "Set the origin distance from the camera"),
            ('X_AXIS', "X Axis", "Use the X axis for reference distance"),
            ('Y_AXIS', "Y Axis", "Use the Y axis for reference distance"),
            ('Z_AXIS', "Z Axis", "Use the Z axis for reference distance")
        ],
        default='X_AXIS'
    )

    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        description="Scale of the scene for vanishing lines",
        default=10.0,
        min=0.01,
        max=100.0
    )

    reference_distance: bpy.props.FloatProperty(
        name="Reference distance",
        description="Reference distance",
        default=0.5
    )

    # Axis Assignement
    floor: bpy.props.EnumProperty(
        name="Ground Plane",
        items=[
            ('XY', "XY", ""),
            ('XZ', "XZ", ""),
            ('YZ', "YZ", "")
        ],
        default='XY'
    )
    
    first_axis: bpy.props.EnumProperty(
        name="First Axis",
        items=[
            ('X+', "X+", ""),
            ('X-', "X-", ""),
            ('Y+', "Y+", ""),
            ('Y-', "Y-", ""),
            ('Z+', "Z+", ""),
            ('Z-', "Z-", "")
        ],
        default='Y+'
    )

    second_axis: bpy.props.EnumProperty(
        name="Second Axis",
        items=[
            ('X+', "X+", ""),
            ('X-', "X-", ""),
            ('Y+', "Y+", ""),
            ('Y-', "Y-", ""),
            ('Z+', "Z+", ""),
            ('Z-', "Z-", "")
        ],
        default='X-'
    )

    # control points
    origin: bpy.props.FloatVectorProperty(
        name="Origin",
        size=2,
        default=(0.0, 0.0)
    )
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0)
    )

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

    error_message: bpy.props.StringProperty(
        name="Error Message",
        default=""
    )


######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(Line)
    bpy.utils.register_class(VLSettings)
    bpy.types.Camera.vl_settings = bpy.props.PointerProperty(type=VLSettings, name="VL Settings")
    
def unregister():
    if hasattr(bpy.types.Camera, 'vl_settings'):
        del bpy.types.Camera.vl_settings
    bpy.utils.unregister_class(Line)
    bpy.utils.unregister_class(VLSettings)