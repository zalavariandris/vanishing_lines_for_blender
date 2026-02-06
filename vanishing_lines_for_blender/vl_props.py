from typing import Literal, Tuple
import bpy
from . import solver
import mathutils
import math

import glm
    
from . import vl_utils

def trigger_autosolve(self, context):
    vl:VLProps = get_current(context)
    if vl.auto_solve:
        solve(vl)

def trigger_autounsolve(self, context):
    vl:VLProps = get_current(context)
    if vl.auto_solve:
        unsolve(vl)
        # solve(vl) # TODO:    trigger solve, to update redraw. THIS is a HACK, we should refactor the widget system to seperate paint from interaction, by making the widgets persistent

def on_fovx_update(self, context):
    vl:VLProps = get_current(context)
    if vl.mode == 'ONE_POINT':
        if vl.auto_solve:
            solve(vl)

class VLLineProp(bpy.types.PropertyGroup):
    """A line defined by start and end points in normalized image space."""
    start: bpy.props.FloatVectorProperty(
        name="Start",
        size=2,
        subtype='COORDINATES',
        default=(0.0, 0.0),
        description="Start point of the line.",
        update=trigger_autosolve
    ) # type: ignore

    end: bpy.props.FloatVectorProperty(
        name="End",
        size=2,
        subtype='COORDINATES',
        default=(0.0, 0.0),
        description="End point of the line.",
        update=trigger_autosolve
    ) # type: ignore


class VLProps(bpy.types.PropertyGroup):
    active: bpy.props.BoolProperty(
        name="Active",
        default=False,
        description="Enable vanishing line based camera calibration",
        options=set(),

    ) # type: ignore

    auto_solve: bpy.props.BoolProperty(
        name="Auto Solve",
        default=True,
        options=set(),
        description="Automatically solve camera parameters when properties change"
    ) # type: ignore

    camera_object: bpy.props.PointerProperty(
        name="Camera Object",
        type=bpy.types.Object,
        description="Reference to a Blender camera object"
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
        update=trigger_autosolve
    ) # type: ignore

    fovx: bpy.props.FloatProperty(
        name="Horizontal FOV",
        default=math.radians(50.0),
        min=math.radians(1.0),
        max=math.radians(179.0),
        description="Horizontal field of view", 
        options=set(),
        subtype='ANGLE',
        update=on_fovx_update
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
        update=trigger_autosolve
    ) # type: ignore

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
        description="Use quadrilateral corners to define second vanishing point", 
        options=set(),
        update=trigger_autosolve
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
        options=set(),
        update=trigger_autosolve
    ) # type: ignore

    reference_screen_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
        description="Start and end points of the reference distance segment for scale measurement", 
        options=set(),
        update=trigger_autosolve
    ) # type: ignore

    axes: bpy.props.EnumProperty(
        name="Axes",
        items=[
            ('X+Y-', "X+ Y-", ""),  ('X-Y-', "X- Y-", ""),
            ('X+Y+', "X+ Y+", ""),  ('X-Y+', "X- Y+", ""),
            ('X+Z-', "X+ Z-", ""),  ('X-Z-', "X- Z-", ""),
            ('X+Z+', "X+ Z+", ""),  ('X-Z+', "X- Z+", ""),

            ('Y+X-', "Y+ X-", ""),  ('Y-X-', "Y- X-", ""),
            ('Y+X+', "Y+ X+", ""),  ('Y-X+', "Y- X+", ""),
            ('Y+Z-', "Y+ Z-", ""),  ('Y-Z-', "Y- Z-", ""),
            ('Y+Z+', "Y+ Z+", ""),  ('Y-Z+', "Y- Z+", ""),
            
            ('Z+X-', "Z+ X-", ""),  ('Z-X-', "Z- X-", ""),
            ('Z+X+', "Z+ X+", ""),  ('Z-X+', "Z- X+", ""),
            ('Z+Y-', "Z+ Y-", ""),  ('Z-Y-', "Z- Y-", ""),
            ('Z+Y+', "Z+ Y+", ""),  ('Z-Y+', "Z- Y+", "")
        ],
        default='Y+X-',
        description="Order of axes for vanishing points", 
        options=set(),
        # update=on_prop_update
    ) # type: ignore

    first_axis: bpy.props.EnumProperty(
        name="First Axis",
        items=[
            ('X', "X", "Positive X axis direction"),
            ('Y', "Y", "Positive Y axis direction"),
            ('Z', "Z", "Positive Z axis direction")
            # ('X-', "X-", "Negative X axis direction"),
            # ('Y-', "Y-", "Negative Y axis direction"),
            # ('Z-', "Z-", "Negative Z axis direction")
        ],
        default='Y',
        description="First vanishing point axis orientation", 
        options=set(),
        update=trigger_autounsolve
    ) # type: ignore

    first_axis_sign: bpy.props.EnumProperty(
        name="First Axis Sign",
        items=[
            ('POSITIVE', "+", "Positive direction"),
            ('NEGATIVE', "-", "Negative direction")
        ],
        default='POSITIVE',
        description="Sign of the first vanishing point axis orientation", 
        options=set(),
        update=trigger_autosolve
    ) # type: ignore

    second_axis: bpy.props.EnumProperty(
        name="Second Axis",
        items=[
            ('X', "X", "Positive X axis direction"),
            ('Y', "Y", "Positive Y axis direction"),
            ('Z', "Z", "Positive Z axis direction")
            # ('X-', "X-", "Negative X axis direction"),
            # ('Y-', "Y-", "Negative Y axis direction"),
            # ('Z-', "Z-", "Negative Z axis direction")
        ],
        default='X',
        description="Second vanishing point axis orientation", 
        options=set(),
        update=trigger_autounsolve
    ) # type: ignore

    second_axis_sign: bpy.props.EnumProperty(
        name="Second Axis Sign",
        items=[
            ('POSITIVE', "+", "Positive direction"),
            ('NEGATIVE', "-", "Negative direction")
        ],
        default='NEGATIVE',
        description="Sign of the second vanishing point axis orientation",
        options=set(),
        update=trigger_autosolve
    ) # type: ignore

    anchor_screen: bpy.props.FloatVectorProperty(
        name="Anchor",
        size=2,
        default=(0.0, 0.0),
        description="Anchor point for reference measurements in normalized image space", 
        options=set(),
        update=trigger_autosolve
    ) # type: ignore

    anchor_world: bpy.props.FloatVectorProperty(
        name="Anchor World",
        size=3,
        unit='LENGTH',
        subtype='XYZ',
        default=(0.0, 0.0, 0.0),
        description="Anchor point in world space for reference measurements", 
        options=set(),
        update=trigger_autosolve
    ) # type: ignore
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        description="Principal point (optical center) in normalized image space", 
        options=set(),
        update=trigger_autosolve
    ) # type: ignore

    x_vanishing_lines: bpy.props.CollectionProperty(
        type=VLLineProp, 
        options=set()) # type: ignore
    
    y_vanishing_lines: bpy.props.CollectionProperty(
        type=VLLineProp, 
        options=set()) # type: ignore

    z_vanishing_lines: bpy.props.CollectionProperty(
        type=VLLineProp, 
        options=set()) # type: ignore

    error_message: bpy.props.StringProperty(
        name="Error Message",
        default="", 
        options=set()
    ) # type: ignore



def ensure_vanishing_lines(vl:VLProps):
    """Ensure there is at least one line in each vanishing line collection."""
    if len(vl.y_vanishing_lines) == 0:
        item = vl.y_vanishing_lines.add()
        item.start = (-0.2, -0.53)
        item.end =   ( 0.6,  0.12)

        item = vl.y_vanishing_lines.add()
        item.start = (-0.88, 0.0)
        item.end =   ( 0.09, 0.20)

    if len(vl.x_vanishing_lines) == 0:
        item = vl.x_vanishing_lines.add()
        item.start =  (0.22, -0.48)
        item.end =   (-0.80,  0.05)

        item = vl.x_vanishing_lines.add()
        item.start =  (0.65, 0.05)
        item.end =   (-0.10, 0.20)

    if len(vl.z_vanishing_lines) == 0:
        item = vl.z_vanishing_lines.add()
        item.start = (-0.3, -0.52)
        item.end =   (-0.4, 0.5)

        item = vl.z_vanishing_lines.add()
        item.start = (0.3, -0.52)
        item.end =   (0.4, 0.5)

# -- conversion between VLProps and solver types --


def solve(vl:VLProps):
    """update projection, and view matrix properties based on current properties."""
    print("[VLProps.solve] Solving camera parameters from vanishing lines...")
    compute_space = solver.types.Rect(-1,-1,2,2)
    try:
        # map props to solver
        mode = vl_utils.to_solver_mode(vl.mode)

        reference_axis = vl_utils.to_solver_reference_axis(vl.reference_scale_mode)

        first_axis = vl_utils.to_solver_axis(vl.first_axis, vl.first_axis_sign)
        second_axis = vl_utils.to_solver_axis(vl.second_axis, vl.second_axis_sign)

        first_prop, second_prop, third_prop = get_vanishing_line_prop_names_in_order(vl)
        second_vanishing_lines = [(line.start, line.end) for line in getattr(vl, second_prop)]
        if vl.quad_mode and mode in {solver.types.SolverMode.TwoVP, solver.types.SolverMode.ThreeVP}:
            first_line = getattr(vl, first_prop)[0]
            last_line =  getattr(vl, first_prop)[-1]

            second_vanishing_lines = [
                (first_line.start, last_line.start), (first_line.end, last_line.end)
            ]

        # if not vl.enable_manual_principal:
        #     vl.principal = compute_space.center

        if vl.reference_scene_scale < 0:
            print("[update_solve] Origin is behind the camera. Negative scene_scale:", vl.reference_scene_scale)

        if vl.mode == 'ONE_POINT':
            ... # TODO: query the fov from the camera?
            
        projection, view = solver.core.solve(
            mode = mode,
            viewport=compute_space,
            first_vanishing_lines= [(glm.vec2(*line.start), glm.vec2(*line.end)) for line in  getattr(vl, first_prop)],
            second_vanishing_lines=second_vanishing_lines,
            third_vanishing_lines= [(glm.vec2(*line.start), glm.vec2(*line.end)) for line in  getattr(vl, third_prop)],

            f = solver.utils.focal_length_from_fov(vl.fovx, compute_space.width), # used only in one point mode
            P = glm.vec2(0,0), # TODO: is [0], [1] necessary?
            anchor_screen = glm.vec2(*vl.anchor_screen),
            anchor_world = glm.vec3(*vl.anchor_world),

            reference_axis=reference_axis, 
            reference_screen_segment=(vl.reference_screen_segment[0], vl.reference_screen_segment[1]-vl.reference_screen_segment[0]), # TODO: make fist value configurable
            reference_world_size=vl.reference_scene_scale,

            first_axis=first_axis,
            second_axis=second_axis
        )

        if vl.mode in {'TWO_POINT', 'THREE_POINT'}:
            _, f = solver.utils.decompose_intrinsics(compute_space, projection)
            vl.fovx = solver.utils.fov_from_focal_length(f, compute_space.width)

        if (vl.camera_object 
            and isinstance(vl.camera_object, bpy.types.Object) 
            and vl.camera_object.data
            and isinstance(vl.camera_object.data, bpy.types.Camera)
        ):
            vl_utils.apply_solver_results_to_blender_camera(
                camera_object=vl.camera_object,
                projection=projection, #TODO: why do wee need to transpose here?
                view=view,
                compute_space=(-1,-1,2,2),
                fit_mode=vl.camera_object.data.sensor_fit
            )
        else:
            print("[VLProps.solve] No valid camera object assigned.")

        vl.error_message = ""

    except solver.exceptions.VanishingLinesError as e:
        print("[VLProps.solve] VanishingLinesError:", str(e))
        # Store error message in vanishing_lines.error_message
        error_type = type(e).__name__  # Gets 'ValueError' as a string
        error_message = str(e)         # Gets the actual message you wrote in 'raise'
        vl.error_message = f"{error_type}\n{error_message}"

    except Exception as e:
        import traceback
        traceback.print_exc()

# def unsolve(vl:VLProps):
#     if not (vl.camera_object 
#         and isinstance(vl.camera_object, bpy.types.Object) 
#         and vl.camera_object.data
#         and isinstance(vl.camera_object.data, bpy.types.Camera)
#     ):
#         print("[VLProps.unsolve] No valid camera object assigned.")
#         return

#     # store current autosolve state
#     previous_auto_solve  = vl.auto_solve
#     vl.auto_solve = False
    
#     viewport = solver.types.Rect(-1,-1,2,2)

#     # -- Adjust vanishing lines to current view and projection matrices --
#     glm_proj, glm_view = vl_utils.get_camera_matrices(vl.camera_object, solver.types.Rect(-1,-1,2,2))

#     vp1, vp2, vp3 = solver.utils.orientation_to_three_vanishing_points(
#         glm.mat3(glm_view), 
#         glm_proj, 
#         solver.types.Rect(-1,-1,2,2),
#         first_axis=vl_utils.to_solver_axis(vl.first_axis, vl.first_axis_sign),
#         second_axis=vl_utils.to_solver_axis(vl.second_axis, vl.second_axis_sign)
#     )

#     first_prop, second_prop, third_prop = get_vanishing_line_prop_names_in_order(vl)
#     for lines, vp in zip([getattr(vl, first_prop), getattr(vl, second_prop), getattr(vl, third_prop)], [vp1, vp2, vp3]):
#         for line in lines:
#             start, end = vl_utils.extend_line(mathutils.Vector(line.start), mathutils.Vector(line.end), mathutils.Vector(vp))
#             line.start = start.x, start.y
#             line.end = end.x, end.y


#     # --- Adjust axis signs, to match closest vanishing points ---
#     vl.first_axis_sign =  'NEGATIVE' if solver.utils.resolve_axis_flip(glm_view, vl.first_axis) else 'POSITIVE'
#     vl.second_axis_sign = 'NEGATIVE' if solver.utils.resolve_axis_flip(glm_view, vl.second_axis) else 'POSITIVE'

#     # -- adjust ANCHOR SCREEN --
#     anchor_screen:glm.vec2 = glm.project(
#         glm.vec3(vl.anchor_world.x, vl.anchor_world.y, vl.anchor_world.z), 
#         glm_view, glm_proj, tuple(viewport)
#     ).xy
#     vl.anchor_screen = (anchor_screen.x, anchor_screen.y)

#     # -- adjust REFERENCE SCENE SCALE --
#     anchor_world = glm.vec3(vl.anchor_world[0], vl.anchor_world[1], vl.anchor_world[2])
#     if vl.reference_scale_mode == 'ANCHOR':
#         # world distance from anchor
#         camera_location, camera_quat = solver.utils.decompose_extrinsics(glm_view)
#         anchor_distance = glm.length(anchor_world - camera_location)
#         vl.reference_scene_scale = anchor_distance
#     else:
#         match vl.reference_scale_mode:
#             case 'ANCHOR':
#                 assert False, "Should not reach here, handled above"
                
#             case 'SCREEN' | 'X_AXIS' | 'Y_AXIS' | 'Z_AXIS':
#                 match vl.reference_scale_mode:
#                     case 'X_AXIS':
#                         ref_axis_vec = glm.vec3(1, 0, 0)
#                     case 'Y_AXIS':
#                         ref_axis_vec = glm.vec3(0, 1, 0)
#                     case 'Z_AXIS':
#                         ref_axis_vec = glm.vec3(0, 0, 1)
#                     case 'SCREEN' | _:
#                         # Right vector is column 0 of the inverse view matrix
#                         ref_axis_vec = glm.vec3(glm.inverse(glm_view)[0])

#         # --- 2. Measure current world length on screen ---
#         A_screen = glm.project(anchor_world, glm_view, glm_proj, tuple(viewport)).xy
#         V_screen = glm.project(anchor_world + ref_axis_vec, glm_view, glm_proj, tuple(viewport)).xy
#         dir_screen = glm.normalize(V_screen - anchor_screen)

#         def get_world_pos(screen_pos):
#             ray = solver.utils.cast_ray(screen_pos, glm_view, glm_proj, tuple(viewport))
#             return solver.utils.closest_point_between_lines((glm.vec3(0,0,0), glm.vec3(0,0,0) + ref_axis_vec), ray)

#         reference_offset, reference_length = vl.reference_screen_segment
#         ref_start_world = get_world_pos(A_screen + dir_screen * reference_offset)
#         ref_end_world = get_world_pos(A_screen + dir_screen * (reference_offset + reference_length))
#         world_length = glm.length(ref_end_world - ref_start_world)

#         vl.reference_scene_scale = world_length

#     # restore autosolve state
#     vl.auto_solve = previous_auto_solve 

def unsolve(vl:VLProps):
    if not (vl.camera_object 
        and isinstance(vl.camera_object, bpy.types.Object) 
        and vl.camera_object.data
        and isinstance(vl.camera_object.data, bpy.types.Camera)
    ):
        print("[VLProps.unsolve] No valid camera object assigned.")
        return
    
    previous_auto_solve  = vl.auto_solve
    vl.auto_solve = False
    
    # -- unsolve --
    glm_proj, glm_view = vl_utils.get_camera_matrices(vl.camera_object, solver.types.Rect(-1,-1,2,2))
    unsolve_results = solver.core.unsolve(
        viewport = solver.types.Rect(-1,-1,2,2),
        projection = glm_proj,
        view = glm_view,
        anchor_world = glm.vec3(vl.anchor_world[0], vl.anchor_world[1], vl.anchor_world[2]),
        reference_axis = vl_utils.to_solver_reference_axis(vl.reference_scale_mode),
        reference_screen_segment = (vl.reference_screen_segment[0], vl.reference_screen_segment[1]),
        first_axis = vl_utils.to_solver_axis(vl.first_axis, vl.first_axis_sign),
        second_axis = vl_utils.to_solver_axis(vl.second_axis, vl.second_axis_sign)
    )

    # --align lines to vanishing points --
    first_prop, second_prop, third_prop = get_vanishing_line_prop_names_in_order(vl)
    for vanishing_lines, vanishing_point in [
        (getattr(vl, first_prop),  unsolve_results.vp1),
        (getattr(vl, second_prop), unsolve_results.vp2),
        (getattr(vl, third_prop),  unsolve_results.vp3)
    ]:
        new_lines = solver.utils.align_lines_to_vanishing_points(
            [(line.start, line.end) for line in vanishing_lines],
            vanishing_point
        )
        for i in range(len(vanishing_lines)):
            vanishing_lines[i].start = new_lines[i][0]
            vanishing_lines[i].end =   new_lines[i][1]

    # -- Set axis signs --
    vl.first_axis_sign =  'NEGATIVE' if unsolve_results.first_axis_flip else 'POSITIVE'
    vl.second_axis_sign = 'NEGATIVE' if unsolve_results.second_axis_flip else 'POSITIVE'

    # -- adjust ANCHOR SCREEN --
    vl.anchor_screen = unsolve_results.anchor_screen.x, unsolve_results.anchor_screen.y

    # -- adjust REFERENCE SCENE SCALE --
    vl.reference_scene_scale = unsolve_results.reference_scene_scale

    # restore autosolve state
    vl.auto_solve = previous_auto_solve

def get_current(context) -> VLProps:
    return context.window_manager.vanishing_lines

def get_vanishing_line_prop_names_in_order(vl:VLProps)->Tuple[str, str, str]:
    """Get the vanishing line properties corresponding to the first vanishing point, based on the selected axes."""
    axis_mapping = {
        'X': 'x_vanishing_lines',
        'Y': 'y_vanishing_lines',
        'Z': 'z_vanishing_lines'
    }
    third_axis = ({'X', 'Y', 'Z'} - {vl.first_axis, vl.second_axis}).pop()
    
    return axis_mapping[vl.first_axis], axis_mapping[vl.second_axis], axis_mapping[third_axis]

######################
# REGISTER FUNCTIONS #
######################
def register():
    print("Registering VLProps and Line")
    bpy.utils.register_class(VLLineProp)
    bpy.utils.register_class(VLProps)
    bpy.types.WindowManager.vanishing_lines = bpy.props.PointerProperty(type=VLProps, name="Vanishing Lines")
    
def unregister():
    if hasattr(bpy.types.WindowManager, 'vanishing_lines'):
        del bpy.types.WindowManager.vanishing_lines
    bpy.utils.unregister_class(VLProps)
    bpy.utils.unregister_class(VLLineProp)