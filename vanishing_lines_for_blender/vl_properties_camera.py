from typing import Tuple
import bpy
from . import solver
import mathutils
import math

from pyglm import glm


def set_defaults(vl_settings: 'VLSettings')->None:
    # if not vl_settings.initialized:
    vl_settings.anchor_screen =    (0.0, -0.25)
    vl_settings.principal = (0.0,  0.0)
        # vl_settings.initialized = True

    vl_settings.first_vanishing_lines.clear()
    item = vl_settings.first_vanishing_lines.add()
    item.start = (-0.2, -0.53)
    item.end =   ( 0.6,  0.12)

    item = vl_settings.first_vanishing_lines.add()
    item.start = (-0.88, 0.0)
    item.end =   ( 0.09, 0.20)

    vl_settings.second_vanishing_lines.clear()
    item = vl_settings.second_vanishing_lines.add()
    item.start =  (0.22, -0.48)
    item.end =   (-0.80,  0.05)

    item = vl_settings.second_vanishing_lines.add()
    item.start =  (0.65, 0.05)
    item.end =   (-0.10, 0.20)

    vl_settings.third_vanishing_lines.clear()
    item = vl_settings.third_vanishing_lines.add()
    item.start = (-0.3, -0.52)
    item.end =   (-0.4, 0.5)

    item = vl_settings.third_vanishing_lines.add()
    item.start = (0.3, -0.52)
    item.end =   (0.4, 0.5)

def on_property_update(vl_settings, context):
    # print(f"Property updated, {vl_settings.id_data} re-solving...")
    camera_object = vl_settings.id_data
    if not isinstance(camera_object.data, bpy.types.Camera):
        return
    
    vl_settings = camera_object.vl_settings
    vl_settings.solve() 
    vl_settings.to_camera(camera_object) # TODO: if uncommented, than initial unsolve will be overridden...
    
from . import vl_utils

               
def unsolve(vl_settings, context):
    ...

class VLLine(bpy.types.PropertyGroup):
    """A line defined by start and end points in normalized image space."""
    
    start: bpy.props.FloatVectorProperty(
        name="Start",
        size=2,
        default=(0.0, 0.0),
        description="Start point of the line.",
        update=on_property_update
    ) # type: ignore

    end: bpy.props.FloatVectorProperty(
        name="End",
        size=2,
        default=(0.0, 0.0),
        description="End point of the line.",
        update=on_property_update
    ) # type: ignore


class VLSettings(bpy.types.PropertyGroup):
    proj_array: bpy.props.FloatVectorProperty(
        size=16, 
        subtype='MATRIX', 
        default=vl_utils.matrix_to_array(vl_utils.glm_to_blender_mat(glm.perspective(45.0, 1.0, 0.1, 100.0))), 
        options={'HIDDEN'}
    ) # type: ignore

    view_array: bpy.props.FloatVectorProperty(
        size=16,
        subtype='MATRIX',
        default=vl_utils.matrix_to_array(mathutils.Matrix.Identity(4)), 
        options={'HIDDEN'}
    ) # type: ignore

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
        default='TWO_POINT',
        description="Number of vanishing points to use for camera calibration", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    reference_scale_mode: bpy.props.EnumProperty(
        name="Scene Scale Mode",
        items=[
            ('SCREEN', "Screen", "Scale relative to screen space"),
            ('ANCHOR', "Anchor", "Scale from anchor point"),
            ('X_AXIS', "X Axis", "Scale along world X axis"),
            ('Y_AXIS', "Y Axis", "Scale along world Y axis"),
            ('Z_AXIS', "Z Axis", "Scale along world Z axis")
        ],
        default='SCREEN',
        description="Method for determining scene scale reference", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
        description="Use quadrilateral corners to define second vanishing point", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    # enable_manual_principal: bpy.props.BoolProperty(
    #     name="Manual Principal Point",
    #     default=False,
    #     description="Manually set the principal point instead of using the image center", 
    #     options=set()
    # ) # type: ignore

    fovx: bpy.props.FloatProperty(
        name="Horizontal FOV",
        default=math.radians(50.0),
        min=1.0,
        max=179.0,
        description="Horizontal field of view in degrees", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    reference_scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        default=10.0,
        # min=0.01,
        # max=99999.0,
        unit='LENGTH',
        subtype='DISTANCE',
        description="Real-world size of the reference measurement for scale calibration", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    reference_screen_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
        description="Start and end points of the reference distance segment for scale measurement", 
        options=set(),
        update=on_property_update
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
        description="First vanishing point axis orientation", 
        options=set(),
        update=on_property_update
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
        description="Second vanishing point axis orientation", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    anchor_screen: bpy.props.FloatVectorProperty(
        name="Anchor",
        size=2,
        default=(0.0, 0.0),
        description="Anchor point for reference measurements in normalized image space", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    anchor_world: bpy.props.FloatVectorProperty(
        name="Anchor World",
        size=3,
        unit='LENGTH',
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        description="Anchor point in world space for reference measurements", 
        options=set(),
        update=on_property_update
    ) # type: ignore
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        description="Principal point (optical center) in normalized image space", 
        options=set(),
        update=on_property_update
    ) # type: ignore

    first_vanishing_lines: bpy.props.CollectionProperty(
        type=VLLine, 
        options=set()) # type: ignore
    
    second_vanishing_lines: bpy.props.CollectionProperty(
        type=VLLine, 
        options=set()) # type: ignore

    third_vanishing_lines: bpy.props.CollectionProperty(
        type=VLLine, 
        options=set()) # type: ignore

    error_message: bpy.props.StringProperty(
        name="Error Message",
        default="", 
        options=set()
    ) # type: ignore

    def solve(self):
        compute_space = solver.types.Rect(-1,-1,2,2)
        try:
            # map props to solver
            mode = {
                "ONE_POINT":   solver.types.SolverMode.OneVP,
                "TWO_POINT":   solver.types.SolverMode.TwoVP,
                "THREE_POINT": solver.types.SolverMode.ThreeVP
            }[self.mode]

            reference_axis = {
                'ANCHOR': None,
                'SCREEN': solver.types.ReferenceAxis.Screen,
                'X_AXIS': solver.types.ReferenceAxis.X_Axis,
                'Y_AXIS': solver.types.ReferenceAxis.Y_Axis,
                'Z_AXIS': solver.types.ReferenceAxis.Z_Axis
            }[self.reference_scale_mode]

            axis_map = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }

            first_axis = axis_map[self.first_axis]
            second_axis = axis_map[self.second_axis]

            second_vanishing_lines = [(line.start, line.end) for line in self.second_vanishing_lines]
            if self.quad_mode and mode in {solver.types.SolverMode.TwoVP, solver.types.SolverMode.ThreeVP}:
                first_line = self.first_vanishing_lines[ 0]
                last_line =  self.first_vanishing_lines[-1]

                second_vanishing_lines = [
                    (first_line.start, last_line.start), (first_line.end, last_line.end)
                ]

            # if not vl_settings.enable_manual_principal:
            #     vl_settings.principal = compute_space.center

            if self.reference_scene_scale < 0:
                print("[update_solve] Origin is behind the camera. Negative scene_scale:", self.reference_scene_scale)

            projection, view = solver.core.solve(
                mode = mode,
                viewport=compute_space,
                first_vanishing_lines= [(glm.vec2(*line.start), glm.vec2(*line.end)) for line in  self.first_vanishing_lines],
                second_vanishing_lines=second_vanishing_lines,
                third_vanishing_lines= [(glm.vec2(*line.start), glm.vec2(*line.end)) for line in  self.third_vanishing_lines],

                f = solver.utils.focal_length_from_fov(self.fovx, compute_space.width), # used only in one point mode
                P = glm.vec2(0,0), # TODO: is [0], [1] necessary?
                anchor_screen = glm.vec2(*self.anchor_screen),
                anchor_world = glm.vec3(*self.anchor_world),

                reference_axis=reference_axis, 
                reference_screen_segment=(self.reference_screen_segment[0], self.reference_screen_segment[1]-self.reference_screen_segment[0]), # TODO: make fist value configurable
                reference_world_size=self.reference_scene_scale,

                first_axis=first_axis,
                second_axis=second_axis
            )

            bl_proj = vl_utils.glm_to_blender_mat(projection)
            bl_view = vl_utils.glm_to_blender_mat(view)
            self.proj_array = vl_utils.matrix_to_array(bl_proj)
            self.view_array = vl_utils.matrix_to_array(bl_view)
                    
            # Clear previous error message
            self.error_message = ""

        except solver.exceptions.VanishingLinesError as e:
            # Store error message in vl_settings
            error_type = type(e).__name__  # Gets 'ValueError' as a string
            error_message = str(e)         # Gets the actual message you wrote in 'raise'
            self.error_message = f"{error_type}\n{error_message}"

        except Exception as e:
            import traceback
            traceback.print_exc()

    def to_camera(self, camera_object: bpy.types.Object):
        if not isinstance(camera_object.data, bpy.types.Camera):
            return
        
        vl_utils.apply_solver_results_to_blender_camera(
            camera_object=camera_object,
            projection=glm.transpose(vl_utils.glm_from_blender_mat(self.proj_array)), #TODO: why do wee need to transpose here?
            view=glm.transpose(vl_utils.glm_from_blender_mat(self.view_array)),
            compute_space=solver.types.Rect(-1,-1,2,2),
            fit_mode=camera_object.data.sensor_fit
        )

    def unsolve(self):
        projection:glm.mat4 = glm.transpose(vl_utils.glm_from_blender_mat(self.proj_array))
        view:glm.mat4 =       glm.transpose(vl_utils.glm_from_blender_mat(self.view_array))
        
        axis_map = {
            'X+': solver.types.Axis.PositiveX,
            'Y+': solver.types.Axis.PositiveY,
            'Z+': solver.types.Axis.PositiveZ,
            'X-': solver.types.Axis.NegativeX,
            'Y-': solver.types.Axis.NegativeY,
            'Z-': solver.types.Axis.NegativeZ
        }
        
        # unsolve_result = solver.core.unsolve(
        #     viewport=solver.types.Rect(-1,-1,2,2),
        #     projection=projection,
        #     view=view,
        #     anchor_world=glm.vec3(self.anchor_world.x, self.anchor_world.y, self.anchor_world.z),
        #     reference_axis={
        #         'ANCHOR': None,
        #         'SCREEN': solver.types.ReferenceAxis.Screen,
        #         'X_AXIS': solver.types.ReferenceAxis.X_Axis,
        #         'Y_AXIS': solver.types.ReferenceAxis.Y_Axis,
        #         'Z_AXIS': solver.types.ReferenceAxis.Z_Axis
        #     }[self.reference_scale_mode],
        #     reference_screen_segment=(self.reference_screen_segment[0], self.reference_screen_segment[1]-self.reference_screen_segment
        # [0]),
        #     first_axis=axis_map[self.first_axis],
        #     second_axis=axis_map[self.second_axis]
        # )

        ###########
        # UNSOLVE #
        # #########

        # adjust vanishing lines
        viewport = solver.types.Rect(-1,-1,2,2)
        vp1, vp2, vp3 = solver.utils.orientation_to_three_vanishing_points(
            glm.mat3(view), 
            projection, 
            viewport=viewport, 
            first_axis=axis_map[self.first_axis], 
            second_axis=axis_map[self.second_axis]
        )

        vl_utils.adjust_vanishing_lines_to_matrices(
            self, 
            projection,
            view
        )

        # adjust anchor screen
        anchor_screen:glm.vec2 = glm.project(
            glm.vec3(self.anchor_world.x, self.anchor_world.y, self.anchor_world.z), 
            view, projection, tuple(viewport)
        ).xy

        self.anchor_screen = (anchor_screen.x, anchor_screen.y)

        # # adjust reference scene scale
        # match self.reference_scale_mode
        # glm.unproject()
        # reference_scene_scale

        # # 
        # fovx



######################
# REGISTER FUNCTIONS #
######################
def register():
    print("Registering VLSettings and Line")
    bpy.utils.register_class(VLLine)
    bpy.utils.register_class(VLSettings)
    bpy.types.Object.vl_settings = bpy.props.PointerProperty(type=VLSettings, name="VL Settings")
    
def unregister():
    if hasattr(bpy.types.Object, 'vl_settings'):
        del bpy.types.Object.vl_settings
    bpy.utils.unregister_class(VLSettings)
    bpy.utils.unregister_class(VLLine)