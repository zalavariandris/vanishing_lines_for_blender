from typing import Tuple
import bpy
from . import solver
import mathutils
import math

from pyglm import glm
    
from . import vl_utils


class VLLine(bpy.types.PropertyGroup):
    """A line defined by start and end points in normalized image space."""
    
    start: bpy.props.FloatVectorProperty(
        name="Start",
        size=2,
        subtype='COORDINATES',
        default=(0.0, 0.0),
        description="Start point of the line.",
    ) # type: ignore

    end: bpy.props.FloatVectorProperty(
        name="End",
        size=2,
        subtype='COORDINATES',
        default=(0.0, 0.0),
        description="End point of the line.",
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

    fovx: bpy.props.FloatProperty(
        name="Horizontal FOV",
        default=math.radians(50.0),
        min=1.0,
        max=179.0,
        description="Horizontal field of view in degrees", 
        options=set(),
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
        options=set()
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
        options=set()
    ) # type: ignore

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
        description="Use quadrilateral corners to define second vanishing point", 
        options=set()
    ) # type: ignore

    # enable_manual_principal: bpy.props.BoolProperty(
    #     name="Manual Principal Point",
    #     default=False,
    #     description="Manually set the principal point instead of using the image center", 
    #     options=set()
    # ) # type: ignore

    reference_scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        default=10.0,
        # min=0.01,
        # max=99999.0,
        unit='LENGTH',
        subtype='DISTANCE',
        description="Real-world size of the reference measurement for scale calibration", 
        options=set()
    ) # type: ignore

    reference_screen_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
        description="Start and end points of the reference distance segment for scale measurement", 
        options=set(),
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
        description="Second vanishing point axis orientation", 
        options=set()
    ) # type: ignore

    anchor_screen: bpy.props.FloatVectorProperty(
        name="Anchor",
        size=2,
        default=(0.0, 0.0),
        description="Anchor point for reference measurements in normalized image space", 
        options=set()
    ) # type: ignore

    anchor_world: bpy.props.FloatVectorProperty(
        name="Anchor World",
        size=3,
        unit='LENGTH',
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        description="Anchor point in world space for reference measurements", 
        options=set()
    ) # type: ignore
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        description="Principal point (optical center) in normalized image space", 
        options=set()
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

    def ensure_vanishing_lines(self):
        """Ensure there is at least one line in each vanishing line collection."""
        if len(self.first_vanishing_lines) == 0:
            item = self.first_vanishing_lines.add()
            item.start = (-0.2, -0.53)
            item.end =   ( 0.6,  0.12)

            item = self.first_vanishing_lines.add()
            item.start = (-0.88, 0.0)
            item.end =   ( 0.09, 0.20)

        if len(self.second_vanishing_lines) == 0:
            item = self.second_vanishing_lines.add()
            item.start =  (0.22, -0.48)
            item.end =   (-0.80,  0.05)

            item = self.second_vanishing_lines.add()
            item.start =  (0.65, 0.05)
            item.end =   (-0.10, 0.20)

        if len(self.third_vanishing_lines) == 0:
            item = self.third_vanishing_lines.add()
            item.start = (-0.3, -0.52)
            item.end =   (-0.4, 0.5)

            item = self.third_vanishing_lines.add()
            item.start = (0.3, -0.52)
            item.end =   (0.4, 0.5)

    def solve(self):
        """update projection, and view matrix properties based on current settings"""
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

    def unsolve(self):
        viewport = solver.types.Rect(-1,-1,2,2)

        # 1. adjust vanishing lines to current view and projection matrices
        glm_proj:glm.mat4 = glm.transpose(vl_utils.glm_from_blender_mat(self.proj_array))
        glm_view:glm.mat4 = glm.transpose(vl_utils.glm_from_blender_mat(self.view_array))
        axis_map = {
            'X+': solver.types.Axis.PositiveX,
            'Y+': solver.types.Axis.PositiveY,
            'Z+': solver.types.Axis.PositiveZ,
            'X-': solver.types.Axis.NegativeX,
            'Y-': solver.types.Axis.NegativeY,
            'Z-': solver.types.Axis.NegativeZ
        }

        new_first_lines, new_second_lines, new_third_lines = solver.utils.adjust_vanishing_lines_to_camera_orientation(
            [(line.start, line.end) for line in self.first_vanishing_lines],
            [(line.start, line.end) for line in self.second_vanishing_lines],
            [(line.start, line.end) for line in self.third_vanishing_lines],
            axis_map[self.first_axis],
            axis_map[self.second_axis],
            glm.mat3(glm_view),
            glm_proj,
        )

        for vl_setting_lines, new_lines in zip(
            [self.first_vanishing_lines, self.second_vanishing_lines, self.third_vanishing_lines],
            [new_first_lines, new_second_lines,new_third_lines]
        ):
            for i in range(len(vl_setting_lines)):
                vl_setting_lines[i].start = new_lines[i][0]
                vl_setting_lines[i].end =   new_lines[i][1]

        # 2. adjust ANCHOR SCREEN
        anchor_screen:glm.vec2 = glm.project(
            glm.vec3(self.anchor_world.x, self.anchor_world.y, self.anchor_world.z), 
            glm_view, glm_proj, tuple(viewport)
        ).xy
        self.anchor_screen = (anchor_screen.x, anchor_screen.y)

        # 3. adjust REFERENCE SCENE SCALE
        anchor_world = glm.vec3(self.anchor_world[0], self.anchor_world[1], self.anchor_world[2])
        match self.reference_scale_mode:
            case 'ANCHOR':
                # world distance from anchor
                camera_locationera_quat = solver.utils.decompose_extrinsics(glm_view)
                anchor_distance = glm.length(anchor_world - camera_locationera_quat.position)
            case 'SCREEN' | 'X_AXIS' | 'Y_AXIS' | 'Z_AXIS':
                match self.reference_scale_mode:
                    case 'X_AXIS':
                        ref_axis_vec = glm.vec3(1, 0, 0)
                    case 'Y_AXIS':
                        ref_axis_vec = glm.vec3(0, 1, 0)
                    case 'Z_AXIS':
                        ref_axis_vec = glm.vec3(0, 0, 1)
                    case 'SCREEN' | _:
                        # Right vector is column 0 of the inverse view matrix
                        ref_axis_vec = glm.vec3(glm.inverse(glm_view)[0])

        # --- 2. Measure current world length on screen ---
        A_screen = glm.project(anchor_world, glm_view, glm_proj, tuple(viewport)).xy
        V_screen = glm.project(anchor_world + ref_axis_vec, glm_view, glm_proj, tuple(viewport)).xy
        dir_screen = glm.normalize(V_screen - anchor_screen)

        def get_world_pos(screen_pos):
            ray = solver.utils.cast_ray(screen_pos, glm_view, glm_proj, tuple(viewport))
            return solver.utils.closest_point_between_lines((glm.vec3(0,0,0), glm.vec3(0,0,0) + ref_axis_vec), ray)

        reference_offset, reference_length = self.reference_screen_segment
        ref_start_world = get_world_pos(A_screen + dir_screen * reference_offset)
        ref_end_world = get_world_pos(A_screen + dir_screen * (reference_offset + reference_length))
        world_length = glm.length(ref_end_world - ref_start_world)

        self.reference_scene_scale = world_length

    def to_camera(self, camera_object: bpy.types.Object):
        if not isinstance(camera_object.data, bpy.types.Camera):
            return
        
        vl_utils.apply_solver_results_to_blender_camera(
            camera_object=camera_object,
            projection=glm.transpose(vl_utils.glm_from_blender_mat(self.proj_array)), #TODO: why do wee need to transpose here?
            view=      glm.transpose(vl_utils.glm_from_blender_mat(self.view_array)),
            compute_space=solver.types.Rect(-1,-1,2,2),
            fit_mode=camera_object.data.sensor_fit
        )

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