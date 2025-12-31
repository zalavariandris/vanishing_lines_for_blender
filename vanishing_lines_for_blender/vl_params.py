# type: ignore
import bpy


def update_camera_vl(self, context):
    """
    Triggers a Depsgraph update by tagging the ID block (the Camera) as dirty.
    'self' refers to the PropertyGroup instance. 
    'self.id_data' refers to the Camera data-block it is attached to.
    """
    if self.id_data:
        self.id_data.update_tag()

class Line(bpy.types.PropertyGroup):
    # 'name' is built-in for PropertyGroups, no need to declare it as a string
    
    start: bpy.props.FloatVectorProperty(
        name="Start",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl
    )

    end: bpy.props.FloatVectorProperty(
        name="End",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl
    )

class VLSettings(bpy.types.PropertyGroup):
    initialized: bpy.props.BoolProperty(
        name="Initialized", 
        default=False, 
        options={'HIDDEN'}
    )
    
    solver_is_paused: bpy.props.BoolProperty(
        name="Paused", 
        default=False,
        update=update_camera_vl
    )

    mode: bpy.props.EnumProperty(
        name="Perspective Mode",
        items=[
            ('ONE_POINT',   "1-Point", "Use 1-point perspective"),
            ('TWO_POINT',   "2-Point", "Use 2-point perspective"),
            ('THREE_POINT', "3-Point", "Use 3-point perspective")
        ],
        default='THREE_POINT',
        update=update_camera_vl
    )

    enable_manual_principal: bpy.props.BoolProperty(
        name="Manual Principal Point",
        default=False,
        update=update_camera_vl
    )

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
        update=update_camera_vl
    )

    scene_scale_mode: bpy.props.EnumProperty(
        name="Scene Scale Mode",
        items=[
            ('SCREEN', "Screen", ""),
            ('ORIGIN', "Origin", ""),
            ('X_AXIS', "X Axis", ""),
            ('Y_AXIS', "Y Axis", ""),
            ('Z_AXIS', "Z Axis", "")
        ],
        default='X_AXIS',
        update=update_camera_vl
    )

    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        default=10.0,
        min=0.01,
        max=99999.0,
        update=update_camera_vl,
        unit='LENGTH',
        subtype='DISTANCE'
    )

    reference_distance: bpy.props.FloatProperty(
        name="Reference Distance",
        default=0.5,
        update=update_camera_vl
    )

    reference_distance_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
        update=update_camera_vl
    )

    first_axis: bpy.props.EnumProperty(
        name="First Axis",
        items=[(a, a, "") for a in ('X+', 'X-', 'Y+', 'Y-', 'Z+', 'Z-')],
        default='Y+',
        update=update_camera_vl
    )

    second_axis: bpy.props.EnumProperty(
        name="Second Axis",
        items=[(a, a, "") for a in ('X+', 'X-', 'Y+', 'Y-', 'Z+', 'Z-')],
        default='X-',
        update=update_camera_vl
    )

    origin: bpy.props.FloatVectorProperty(
        name="Origin",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl
    )
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl
    )

    # Collections: Note that 'update' on the collection itself 
    # only fires if the collection pointer changes.
    # The actual updates are driven by the 'Line' properties above.
    first_vanishing_lines: bpy.props.CollectionProperty(type=Line)
    second_vanishing_lines: bpy.props.CollectionProperty(type=Line)
    third_vanishing_lines: bpy.props.CollectionProperty(type=Line)

    error_message: bpy.props.StringProperty(
        name="Error Message",
        default="",
        update=update_camera_vl
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