from typing import Tuple, Callable
import math

import bpy

from . import vl_params
from . import solver
from .  import vl_params
from . import vl_utils

from . uiview3d import UIView3D

from pyglm import glm

import warnings

class VIEW_OT_VanishingLinesViewTool(bpy.types.Operator):
    bl_idname = "view.vanishing_lines_view_tool"
    bl_label = "Vanishing Lines View Tool"
    bl_options = {'REGISTER', 'UNDO'}

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

    enable_manual_principal: bpy.props.BoolProperty(
        name="Manual Principal Point",
        default=False,
        description="Manually set the principal point instead of using the image center", 
        options=set()
    ) # type: ignore

    quad_mode: bpy.props.BoolProperty(
        name="Quad Mode",
        default=False,
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
        description="Method for determining scene scale reference", 
        options=set()
    ) # type: ignore

    scene_scale: bpy.props.FloatProperty(
        name="Scene Scale",
        default=10.0,
        min=0.01,
        max=99999.0,
        unit='LENGTH',
        subtype='DISTANCE',
        description="Real-world size of the reference measurement for scale calibration", 
        options=set()
    ) # type: ignore

    reference_distance_segment: bpy.props.FloatVectorProperty(
        name="Reference Distance Segment",
        size=2,
        default=(0.0, 0.5),
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

    origin: bpy.props.FloatVectorProperty(
        name="Origin",
        size=2,
        default=(0.0, 0.0),
        description="Origin point for reference measurements in normalized image space", 
        options=set()
    ) # type: ignore
    
    principal: bpy.props.FloatVectorProperty(
        name="Principal",
        size=2,
        default=(0.0, 0.0),
        description="Principal point (optical center) in normalized image space", 
        options=set()
    ) # type: ignore

    # Collections: Note that 'update' on the collection itself 
    # only fires if the collection pointer changes.
    # The actual updates are driven by the 'Line' properties above.
    first_vanishing_lines: bpy.props.CollectionProperty(
        type=vl_params.Line, 
        options=set()) # type: ignore
    second_vanishing_lines: bpy.props.CollectionProperty(
        type=vl_params.Line, 
        options=set()) # type: ignore
    third_vanishing_lines: bpy.props.CollectionProperty(
        type=vl_params.Line, 
        options=set()) # type: ignore
    
    def invoke(self, context, event):
        vl_params.set_defaults(self)
        self.uiview = UIView3D()

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}
        # print("modal", event.type)
        return self.uiview.event(context, event)
    
    def view3d_draw(self, context):
        self.uiview.begin()
        x, y = 0, 0
        w, h = context.region.width, context.region.height
        region_aspect = w / h

        # get SpaceView3D
        space = context.space_data
        if not space or space.type != 'VIEW_3D':
            warnings.warn("Context is not a 3D Viewport!")
            return


        self.uiview.set_view(glm.mat4(1.0))
        if region_aspect >= 1.0:
            self.uiview.set_projection(glm.ortho(-1, 1, -1/region_aspect, 1/region_aspect, -1000.0, 1000.0))
        else:
            self.uiview.set_projection(glm.ortho(-1*region_aspect, 1*region_aspect, -1, 1, -1000.0, 1000.0))
        self.uiview.set_viewport((0, 0, w, h))
        ##

        GREEN = (0,1,0,1)
        RED = (1,0,0,1)
        BLUE = (0,0.3, 1.0, 1.0)
        YELLOW = (1,1,0,1)
        ORANGE = (1.0, 0.5, 0.0, 1.0)

        ###########################
        # Vanishing Line CONTROLS #
        ###########################
        _ = self.uiview.prop_point(self, "origin",    
            text="O",
            color=YELLOW)
        
        _ = self.uiview.prop_point(self, "principal", 
            text="P",
            color=YELLOW)
        
        def get_axis_color(axis:solver.types.Axis) -> Tuple[float, float, float, float]:
            match axis:
                case solver.types.Axis.PositiveX | solver.types.Axis.NegativeX:
                    return RED
                case solver.types.Axis.PositiveY | solver.types.Axis.NegativeY:
                    return GREEN
                case solver.types.Axis.PositiveZ | solver.types.Axis.NegativeZ:
                    return BLUE

        axes_mapping = {
            'X+': solver.types.Axis.PositiveX,
            'Y+': solver.types.Axis.PositiveY,
            'Z+': solver.types.Axis.PositiveZ,
            'X-': solver.types.Axis.NegativeX,
            'Y-': solver.types.Axis.NegativeY,
            'Z-': solver.types.Axis.NegativeZ
        }
        first_axis = axes_mapping[self.first_axis]
        second_axis = axes_mapping[self.second_axis]
        third_axis = solver.helpers.third_axis(first_axis, second_axis) # find third axis based on the first two

        if self.mode in {'ONE_POINT', 'TWO_POINT', 'THREE_POINT'}:
            # Draw first vanishing lines
            for line in self.first_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(first_axis))

        if self.mode in {'ONE_POINT'}:
            # Draw the horizontal line for the vp1 mode:
            self.uiview.prop_line(self.second_vanishing_lines[0], color=get_axis_color(second_axis))

        if self.mode in {'TWO_POINT', 'THREE_POINT'}:
            if self.quad_mode:
                first_line = self.first_vanishing_lines[ 0]
                last_line =  self.first_vanishing_lines[-1]
                
                for line_start, line_end in [(first_line.start, last_line.start), (first_line.end, last_line.end)]:
                    self.uiview._draw_layer.add_line(
                        self.uiview.project(line_start), 
                        self.uiview.project(line_end), 
                        get_axis_color(second_axis))
                    
            else:
                for line in self.second_vanishing_lines:
                    self.uiview.prop_line(line, color=get_axis_color(second_axis))

        if self.mode in {'THREE_POINT'}:
            for line in self.third_vanishing_lines:
                self.uiview.prop_line(line, color=get_axis_color(third_axis))

        ## draw compute space
        x_min, y_min = self.uiview.project((-1,-1))
        x_max, y_max = self.uiview.project((1, 1))
        self.uiview._draw_layer.add_rect(
            (x_min+10, y_min+10),
            (x_max - x_min-20, y_max - y_min-20),
            color=(0,1,1,1.0)
        )

        ## draw info
        self.uiview._draw_layer.add_annotation(
            pos=glm.vec2(100, 100),
            text="Info",
            color=glm.vec4(1.0, 1.0, 0.0, 1.0)
        )

        self.uiview.end()

        self.update_solve(context)

    def update_solve(self, context) -> set:
        compute_space = solver.types.Rect(-1,-1,2,2)

        try:
            # map props to solver
            mode = {
                "ONE_POINT":   solver.types.SolverMode.OneVP,
                "TWO_POINT":   solver.types.SolverMode.TwoVP,
                "THREE_POINT": solver.types.SolverMode.ThreeVP
            }[self.mode]

            reference_axis = {
                'ORIGIN': None,# TODO: ORIGIN option
                'SCREEN': solver.types.ReferenceAxis.Screen,
                'X_AXIS': solver.types.ReferenceAxis.X_Axis,
                'Y_AXIS': solver.types.ReferenceAxis.Y_Axis,
                'Z_AXIS': solver.types.ReferenceAxis.Z_Axis
            }[self.scene_scale_mode]

            first_axis = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }[self.first_axis]

            second_axis = {
                'X+': solver.types.Axis.PositiveX,
                'Y+': solver.types.Axis.PositiveY,
                'Z+': solver.types.Axis.PositiveZ,
                'X-': solver.types.Axis.NegativeX,
                'Y-': solver.types.Axis.NegativeY,
                'Z-': solver.types.Axis.NegativeZ
            }[self.second_axis]

            second_vanishing_lines = [(line.start, line.end) for line in self.second_vanishing_lines]
            if self.quad_mode and mode in {solver.types.SolverMode.TwoVP, solver.types.SolverMode.ThreeVP}:
                first_line = self.first_vanishing_lines[ 0]
                last_line =  self.first_vanishing_lines[-1]

                second_vanishing_lines = [
                    (first_line.start, last_line.start), (first_line.end, last_line.end)
                ]

            # if context.space_data.lock_camera
            # focal_length = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height
            match context.space_data.region_3d.view_perspective:
                case 'CAMERA':
                    camera_object = context.space_data.camera
                    focal_length = camera_object.data.lens / camera_object.data.sensor_width * compute_space.height

                case 'PERSP':
                    # print("compute for PERSP view")
                    region_aspect = context.region.width / context.region.height
                    if region_aspect >= 1.0:
                        focal_length = context.space_data.lens / 36.0 * compute_space.width
                    else:
                        print("compute for PERSP view - height")
                        focal_length = context.space_data.lens / 24.0 * compute_space.height

                case 'ORTHO':
                    context.space_data.region_3d.view_perspective = 'PERSP'
                    focal_length = context.space_data.lens / 36.0 * compute_space.height

            if not self.enable_manual_principal:
                self.principal = compute_space.center
            # print("compute:", compute_space)
            projection, view = solver.core.solve(
                mode = mode,
                viewport=compute_space,
                first_vanishing_lines= [(line.start, line.end) for line in  self.first_vanishing_lines],
                second_vanishing_lines=second_vanishing_lines,
                third_vanishing_lines= [(line.start, line.end) for line in  self.third_vanishing_lines],

                f = focal_length,
                P = (self.principal[0], self.principal[1]), # TODO: is [0], [1] necessary?
                O = (self.origin[0],    self.origin[1]),

                reference_axis=reference_axis, # TODO: make configurable
                reference_distance_segment=(self.reference_distance_segment[0], self.reference_distance_segment[1]-self.reference_distance_segment[0]), # TODO: make fist value configurable
                reference_world_size=self.scene_scale,

                first_axis=first_axis,
                second_axis=second_axis
            )

            ## apply solver results to blender view
            match context.space_data.region_3d.view_perspective:
                case 'CAMERA':
                    camera_object = context.space_data.camera
                    vl_utils.apply_solver_results_to_blender_camera(
                        projection=projection, 
                        view=view, 
                        camera_object=camera_object, 
                        compute_space=compute_space, 
                        fit_mode=camera_object.data.sensor_fit
                    )

                case 'PERSP':
                    # print("apply to PERSP view")
                    w = context.region.width
                    h = context.region.height

                    region_aspect = context.region.width / context.region.height

                    # projection = glm.perspective(math.radians(60.0), w/h, 0.1, 1000.0)
                    # view = glm.lookAt(
                    #     glm.vec3(1.0, -3.0, 1.0),
                    #     glm.vec3(0.0, 0.0, 0.0),
                    #     glm.vec3(0.0, 0.0, 1.0)
                    # )
                    
                    principal, focal_length = solver.utils.decompose_intrinsics((-1,-1,w,h), projection)

                    if region_aspect >= 1.0:
                        context.space_data.lens = focal_length*36 / context.region.width * 2 * region_aspect
                    else:
                        context.space_data.lens = focal_length*36 / context.region.height * 2

                    # # projection = glm.perspective(math.radians(10.0), w/h, 0.1, 1000.0)
                    context.space_data.region_3d.view_matrix = vl_utils.glm_to_blender_mat(view)
                    # context.space_data.region_3d.window_matrix = vl_utils.glm_to_blender_mat(projection)
                    # context.space_data.region_3d.perspective_matrix = vl_utils.glm_to_blender_mat(projection)
                    # context.space_data.region_3d.view_camera_offset = (100,1)
                    # context.space_data.region_3d.view_camera_zoom = 6
                case 'ORTHO':
                    assert False, "Should not reach here, ORTHO case handled above."

            self.error_message = ""
            # print(context.space_data.region_3d.view_camera_zoom)
            # space = context.space_data
            # assert space and space.type == 'VIEW_3D', "Context is not a 3D Viewport!"



            # print(
                # context.space_data.camera,
                # context.space_data.lock_camera,
                # context.space_data.lens,
                
                
                # context.space_data.region_3d.view_matrix,
                # context.space_data.region_3d.perspective_matrix,
                # context.space_data.region_3d.window_matrix,

                # context.space_data.region_3d.view_camera_zoom,
                # context.space_data.region_3d.view_camera_offset
            # )
            # context.space_data.camera
            # context.space_data.lock_camera
            # context.space_data.lens
            
            # context.space_data.region_3d.view_perspective:bool
            # context.space_data.region_3d.view_matrix
            # context.space_data.region_3d.perspective_matrix
            # context.space_data.region_3d.window_matrix

            # context.space_data.region_3d.view_camera_zoom
            # context.space_data.region_3d.view_camera_offset



            
                    
        except Exception as e:
            error_type = type(e).__name__  # Gets 'ValueError' as a string
            error_message = str(e)         # Gets the actual message you wrote in 'raise'
            self.error_message = f"{error_type}\n{error_message}"
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        return {'FINISHED'}

    # def execute(self, context):
    #     vl_settings = self
    #     ...
    
######################
def view_menu_func(self, context):
    self.layout.operator(VIEW_OT_VanishingLinesViewTool.bl_idname, text="Calibrate View with Vanishing Lines")

def rv3d_draw_function():
    # global draw_list
    """Wrapper function to call the draw_view method of the operator instance."""
    # print("rv3d_draw_function")
    if op:=vl_utils.get_running_operator_by_idname('VIEW_OT_vanishing_lines_view_tool'):
        op.view3d_draw(bpy.context)

draw_handler = None
def register():
    bpy.utils.register_class(VIEW_OT_VanishingLinesViewTool)
    bpy.types.VIEW3D_MT_view.append(view_menu_func)

    global draw_handler
    draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            rv3d_draw_function, 
            (), 
            'WINDOW', 
            'POST_PIXEL' # POST_VIEW | POS_PIXEL | ...
        )

def unregister():
    global draw_handler
    if draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None

    bpy.utils.unregister_class(VIEW_OT_VanishingLinesViewTool)
    bpy.types.VIEW3D_MT_view.remove(view_menu_func)

    
