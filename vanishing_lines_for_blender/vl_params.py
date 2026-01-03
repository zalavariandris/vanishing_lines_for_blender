
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
    """A line defined by start and end points in normalized image space."""
    
    start: bpy.props.FloatVectorProperty(
        name="Start",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl,
        description="Start point of the line."
    ) # type: ignore

    end: bpy.props.FloatVectorProperty(
        name="End",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl,
        description="End point of the line."
    ) # type: ignore

def initialize_vl_settings(vl_settings: 'VLSettings')->None:
    if not vl_settings.initialized:
        vl_settings.origin =    (0.0, -0.25)
        vl_settings.principal = (0.0,  0.0)
        vl_settings.initialized = True

    if len(vl_settings.first_vanishing_lines) == 0:
        item = vl_settings.first_vanishing_lines.add()
        item.start = (-0.2, -0.53)
        item.end =   ( 0.6,  0.12)

        item = vl_settings.first_vanishing_lines.add()
        item.start = (-0.88, 0.0)
        item.end =   ( 0.09, 0.20)

    if len(vl_settings.second_vanishing_lines) == 0:
        item = vl_settings.second_vanishing_lines.add()
        item.start =  (0.22, -0.48)
        item.end =   (-0.80,  0.05)

        item = vl_settings.second_vanishing_lines.add()
        item.start =  (0.65, 0.05)
        item.end =   (-0.10, 0.20)

    if len(vl_settings.third_vanishing_lines) == 0:
        item = vl_settings.third_vanishing_lines.add()
        item.start = (-0.3, -0.52)
        item.end =   (-0.4, 0.5)

        item = vl_settings.third_vanishing_lines.add()
        item.start = (0.3, -0.52)
        item.end =   (0.4, 0.5)

class VLSettings(bpy.types.PropertyGroup):
    initialized: bpy.props.BoolProperty(
        name="Initialized", 
        default=False, 
        options={'HIDDEN'}
    ) # type: ignore

    mode: bpy.props.EnumProperty(
        name="Perspective Mode",
        items=[
            ('ONE_POINT',   "1-Point", "Find camera orientation."),
            ('TWO_POINT',   "2-Point", "Compute focal length from second vanishing point."),
            ('THREE_POINT', "3-Point", "Use the third vanishing point to find the principal point.")
        ],
        default='THREE_POINT',
        update=update_camera_vl,
        description="Number of vanishing points to use for camera calibration", 
        options=set()
    ) # type: ignore

    enable_manual_principal: bpy.props.BoolProperty(
        name="Manual Principal Point",
        default=False,
        update=update_camera_vl,
        description="Manually set the principal point instead of using the image center", 
        options=set()
    ) # type: ignore

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
        update=update_camera_vl,
        description="Use quadrilateral corners to define second vanishing point", 
        options=set()
    ) # type: ignore

    scene_scale_mode: bpy.props.EnumProperty(
        name="Scene Scale Mode",
        items=[
            ('SCREEN', "Screen", "Scale relative to screen space"),
            ('ORIGIN', "Origin", "Scale from origin point"),
            ('X_AXIS', "X Axis", "Scale along world X axis"),
            ('Y_AXIS', "Y Axis", "Scale along world Y axis"),
            ('Z_AXIS', "Z Axis", "Scale along world Z axis")
        ],
        default='X_AXIS',
        update=update_camera_vl,
        description="Method for determining scene scale reference", 
        options=set()
    ) # type: ignore

    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        default=10.0,
        min=0.01,
        max=99999.0,
        update=update_camera_vl,
        unit='LENGTH',
        subtype='DISTANCE',
        description="Real-world size of the reference measurement for scale calibration", 
        options=set()
    ) # type: ignore

    reference_distance_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
        update=update_camera_vl,
        description="Start and end points of the reference distance segment for scale measurement", 
        options=set()
    ) # type: ignore

    first_axis: bpy.props.EnumProperty(
        name="First Axis",
        items=[
            ('X+', "X+", "Positive X axis direction"),
            ('X-', "X-", "Negative X axis direction"),
            ('Y+', "Y+", "Positive Y axis direction"),
            ('Y-', "Y-", "Negative Y axis direction"),
            ('Z+', "Z+", "Positive Z axis direction"),
            ('Z-', "Z-", "Negative Z axis direction")
        ],
        default='Y+',
        update=update_camera_vl,
        description="First vanishing point axis orientation", 
        options=set()
    ) # type: ignore

    second_axis: bpy.props.EnumProperty(
        name="Second Axis",
        items=[
            ('X+', "X+", "Positive X axis direction"),
            ('X-', "X-", "Negative X axis direction"),
            ('Y+', "Y+", "Positive Y axis direction"),
            ('Y-', "Y-", "Negative Y axis direction"),
            ('Z+', "Z+", "Positive Z axis direction"),
            ('Z-', "Z-", "Negative Z axis direction")
        ],
        default='X-',
        update=update_camera_vl,
        description="Second vanishing point axis orientation", 
        options=set()
    ) # type: ignore

    origin: bpy.props.FloatVectorProperty(
        name="Origin",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl,
        description="Origin point for reference measurements in normalized image space", 
        options=set()
    ) # type: ignore
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        update=update_camera_vl,
        description="Principal point (optical center) in normalized image space", 
        options=set()
    ) # type: ignore

    # Collections: Note that 'update' on the collection itself 
    # only fires if the collection pointer changes.
    # The actual updates are driven by the 'Line' properties above.
    first_vanishing_lines: bpy.props.CollectionProperty(
        type=Line, 
        options=set()) # type: ignore
    second_vanishing_lines: bpy.props.CollectionProperty(
        type=Line, 
        options=set()) # type: ignore
    third_vanishing_lines: bpy.props.CollectionProperty(
        type=Line, 
        options=set()) # type: ignore

    update_strategy: bpy.props.EnumProperty(
        name="Update Strategy",
        items=[
            # ('MANUAL', "Manual", "Update manually"),
            ('ON_UI_CHANGE', "UI", "Update on user interface events"),
            ('ON_DEPSGRAPH_UPDATE', "Depsgraph", "Update on dependency graph changes")
            
        ],
        default='ON_UI_CHANGE',
        update=update_camera_vl, # TODO: this probably shoudl be empty
        description="Strategy for updating the solver when changes occur", 
        options=set()
    ) # type: ignore

    error_message: bpy.props.StringProperty(
        name="Error Message",
        default="",
        update=update_camera_vl, 
        options=set()
    ) # type: ignore
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
    bpy.utils.unregister_class(VLSettings)
    bpy.utils.unregister_class(Line)