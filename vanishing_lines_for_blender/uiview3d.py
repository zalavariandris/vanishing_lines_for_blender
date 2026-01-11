import math
from typing import Tuple, Callable

from . import vl_utils
from . import vl_coord_utils
from . draw_layer import DrawLayer
from pyglm import glm


# Constants
CLIP_NEAR = -1000.0
CLIP_FAR = 1000.0
DEFAULT_CLICK_THRESHOLD = 22.0
ANNOTATION_OFFSET_X = 5
TEXT_OFFSET_Y_BELOW = -15
TEXT_OFFSET_Y_ABOVE = 5
DIM_FACTOR_ACTIVE = 0.3
DIM_FACTOR_INACTIVE = 0.1

from typing import Any
SetterCallbackWithIndexType = Callable[[Any, Any, int,  Any], None]
SetterCallbackWithoutType =   Callable[[Any, Any, Any],       None]

GetterCallbackWithIndexType = Callable[[Any, Any, int], Tuple[float, float]]
GetterCallbackWithoutType =   Callable[[Any, Any],      Tuple[float, float]]

SetterCallbackType = SetterCallbackWithIndexType | SetterCallbackWithoutType
GetterCallbackType = GetterCallbackWithIndexType | GetterCallbackWithoutType

class _ControlPoint():
    def __init__(self, data:'bpy.types.ID', prop:str, index:int|None=None, *, 
            setter:SetterCallbackType|None=None, 
            getter:GetterCallbackType|None=None):
        self._data = data
        self._prop = prop
        self._index = index

        self._set_transform: SetterCallbackType
        if setter is None:
            if index is None:
                self._set_transform = lambda data, prop, value: setattr(data, prop, value)
            else:
                def indexed_setter(data, prop, idx:int, value:Any):
                    seq = list(getattr(data, prop))
                    seq[idx] = value
                    setattr(data, prop, seq)

                self._set_transform = indexed_setter
        else:
            self._set_transform = setter
        
        self._get_transform: GetterCallbackType
        if getter is None:
            if index is None:
                self._get_transform = lambda data, prop: getattr(data, prop)
            else:
                self._get_transform = lambda data, prop, idx: getattr(data, prop)[idx]
        else:
            self._get_transform = getter
        
    @property
    def value(self)->Tuple[float, float]:
        if self._index is None:
            return self._get_transform(self._data, self._prop)
        else:
            return self._get_transform(self._data, self._prop, self._index)
    
    @value.setter
    def value(self, value:Tuple[float, float] ):
        if self._index is None:
            self._set_transform(self._data, self._prop, value)
        else:
            self._set_transform(self._data, self._prop, self._index, value)
            


ControlIdType = Tuple['bpy.types.ID', str, int|None]

class UIView3D:
    def __init__(self):
        self._controls: dict[ControlIdType, _ControlPoint] = dict()
        self._draw_layer: DrawLayer = DrawLayer()

        # interaction
        self._active_id: ControlIdType|None = None
        self._hovered_id: ControlIdType|None = None

        # mouse dragging
        self._is_left_mouse_down = False
        self._mouse_down_pos: Tuple[float, float] = (0.0, 0.0)
        self._active_down_pos: Tuple[float, float] = (0.0, 0.0)

        # coordinate system
        self._view: glm.mat4 = glm.mat4(1.0)
        self._projection: glm.mat4 = glm.mat4(1.0)
        self._viewport: Tuple[int, int, int, int] = (0, 0, 1, 1)

    def begin(self):
        # self.uiview.update_viewport_state(context)
        self._draw_layer.clear()
        self._controls.clear()

    def end(self):
        self._draw_layer.draw()
    
    # Coordinate system
    def set_view(self, view:glm.mat4):
        self._view = view

    def set_projection(self, projection:glm.mat4):
        self._projection = projection

    def set_viewport(self, viewport:Tuple[int, int, int, int]):
        self._viewport = viewport

    def set_coordinate_system_to_camera_frame(self, context):
        # Set UIVIEW camera, so _compute space_ matches _camera frame_, respect to _sensor fit_
        camera_frame = vl_coord_utils.get_camera_frame(context)
        output_aspect = context.scene.render.resolution_x / context.scene.render.resolution_y
        sensor_fit = context.space_data.camera.data.sensor_fit
        
        # Determine orientation
        is_horizontal = {
            'AUTO': output_aspect >= 1.0,
            'HORIZONTAL': True,
            'VERTICAL': False
        }[sensor_fit]
        
        # Single calculation path
        if is_horizontal:
            x, y = -1, -1 + (2-2/output_aspect)/2
            w, h = 2, 2/output_aspect
        else:
            x, y = -1+ (2-2*output_aspect)/2, -1
            w, h = 2*output_aspect, 2
        
        self.set_projection(glm.orthoLH(x, x+w, y, y+h, CLIP_NEAR, CLIP_FAR))
        self.set_viewport(camera_frame)

    def project(self, coord:Tuple[float, float]) -> Tuple[float, float]:
        region = glm.project(glm.vec3(coord[0], coord[1], 0), 
            self._view, 
            self._projection, 
            glm.vec4(*self._viewport))
                             
        return region.x, region.y
    
    def unproject(self, coord:Tuple[float, float]) -> Tuple[float, float]:
        world_space = glm.unProject(glm.vec3(coord[0], coord[1], 0), 
            self._view, 
            self._projection, 
            glm.vec4(*self._viewport))
        
        return world_space.x, world_space.y
    
    # Event Handling
    def event(self, context, event:'bpy.types.Event')->bool:
        ###
        # Event Helpers
        ###
        # print("Event:", event.type, event.value)
        area: 'bpy.types.Area'|None = context.area
        if area is None:
            return False
        
        region: 'bpy.types.Region'|None = context.region
        if region is None:
            return False

        ###
        #  HANDLE MOUSE EVENTS
        ###


        """Mouse Events"""

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            """Wheel Events"""
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            return False

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._is_left_mouse_down = True
            self._mouse_down_pos = (event.mouse_region_x, event.mouse_region_y)

            # activate cp under mouse
            self._active_id = self.get_closest_id(event.mouse_region_x, event.mouse_region_y)

            if self._active_id is not None:
                # store a _copy_ of the control position at mouse down
                position:Tuple[float, float] = tuple(self._controls[self._active_id].value)
                self._active_down_pos = position
            # else:
            #     self._active_down_pos = None

            # trigger redraw
            if area.type == 'VIEW_3D':
                area.tag_redraw()

            if self._active_id is not None:
                return False
            else:
                return False
        
        elif event.type == 'MOUSEMOVE':
            if not self._is_left_mouse_down:
                """Mouse Move"""
                # update hover
                new_hovered_id = self.get_closest_id(event.mouse_region_x, event.mouse_region_y)

                if new_hovered_id != self._hovered_id:
                    self._hovered_id = new_hovered_id

                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

                if self._hovered_id is not None:
                    return False
                else:
                    return False

            elif self._active_id is not None:
                """Mouse Drag"""
                # move active control point
                mouse_x_unproj, mouse_y_unproj = self.unproject((event.mouse_region_x, event.mouse_region_y))
                mouse_down_x_unproj, mouse_down_y_unproj = self.unproject(self._mouse_down_pos)

                mouse_unproj_delta_x = mouse_x_unproj - mouse_down_x_unproj
                mouse_unproj_delta_y = mouse_y_unproj - mouse_down_y_unproj

                new_x_unproj = self._active_down_pos[0] + mouse_unproj_delta_x
                new_y_unproj = self._active_down_pos[1] + mouse_unproj_delta_y

                self._controls[self._active_id].value = (new_x_unproj, new_y_unproj)
                # self.set_control_point(self._active_name, (mouse_x_unproj, mouse_y_unproj))
                # self.update_solve(context)

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return True
            else:
                return False
            
        elif self._is_left_mouse_down and event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._is_left_mouse_down = False
            """Mouse Release Event"""
            if self._active_id is not None:
                self._active_id = None

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return False
            else:
                return False

        return False

    # GUI
    def get_closest_id(self, mouse_region_x: float, mouse_region_y: float, threshold:float=DEFAULT_CLICK_THRESHOLD) -> ControlIdType|None:
        closest_key:ControlIdType|None = None
        closest_dist_sq = threshold * threshold

        for control_id, control_point in self._controls.items():
            P = (self.project(control_point.value))
            dist_sq = (P[0] - mouse_region_x) ** 2 + (P[1] - mouse_region_y) ** 2
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest_key = control_id

        return closest_key
   
    def is_item_hovered(self):
        last_id = next(reversed(self._controls))
        return self._hovered_id == last_id
    
    def is_item_active(self):
        last_id = next(reversed(self._controls))
        return self._active_id == last_id

    # Widgets
    def prop_point(self, data:'bpy.types.ID', prop:str, index:int|None=None, *,
        text:str|None=None,
        color=(1.0,0.5,0.0,1.0),
        set_transform:Callable|None=None, 
        get_transform:Callable|None=None
    ) -> _ControlPoint:
        assert self._draw_layer is not None, "Draw layer not initialized"
        control_id = (data, prop, index)
        if control_id not in self._controls:
            self._controls[control_id] = _ControlPoint(data, prop, index=index, setter=set_transform, getter=get_transform)

        text = text if text is not None else f"{prop}"
        cp = self._controls[control_id]
        P = self.project(cp.value)
        is_active = (self._active_id == control_id)
        is_hovered = (self._hovered_id == control_id)

        point_render_color = color
        if is_active or is_hovered:
            point_render_color = (1.0, 1.0, 1.0, 1.0)
            self._draw_layer.add_annotation(
                (P[0] + ANNOTATION_OFFSET_X, P[1] + TEXT_OFFSET_Y_BELOW), 
                f"({cp.value[0]:.2f}, {cp.value[1]:.2f})",
                color=(1,1,1,1))

        self._draw_layer.add_point(
            P,
            point_render_color)

        
        self._draw_layer.add_annotation(
            (P[0] + ANNOTATION_OFFSET_X, P[1] + TEXT_OFFSET_Y_ABOVE),
            text,
            color=(1,1,1,1))
        
        return self._controls[control_id]
    
    def prop_line(self, data:'bpy.types.ID', *, start_prop:str='start', end_prop:str='end', 
        color=(0.8,0.8,0.8,1.0)
    ):
        assert self._draw_layer is not None, "Draw layer not initialized"
        start_cp = self.prop_point(data, start_prop, color=color)
        end_cp = self.prop_point(data, end_prop, color=color)

        P_start = self.project(start_cp.value)
        P_end = self.project(end_cp.value)

        self._draw_layer.add_line(
            P_start,
            P_end,
            color=color)
        
    def prop_distance(self, data:'bpy.types.ID', prop:str, *,
        origin:Tuple[float, float], 
        direction:Tuple[float, float]=(1,0), 
        text:str="",
        color=(0.0,0.5,1.0,1.0),
    ):
        
        def set_transform(data:'bpy.types.ID', prop:str, P:Tuple[float, float]):
            P = glm.vec2(P[0], P[1])
            O = glm.vec2(origin[0], origin[1])
            dir = glm.normalize(glm.vec2(direction[0], direction[1]))
            distance = glm.dot(P - O, dir)
            setattr(data, prop, distance)

        def get_transform(data:'bpy.types.ID', prop:str) -> Tuple[float, float]:
            distance = getattr(data, prop)

            # set direction magnitude
            dx, dy = direction
            l = (dx**2 + dy**2)**0.5
            dx, dy = dx/l*distance, dy/l*distance

            # get origin
            Ox, Oy = origin

            # set point position
            Px = Ox + dx
            Py = Oy + dy

            return Px, Py
        
        self.prop_point(data, prop, text=text, color=color, 
                        set_transform=set_transform,
                        get_transform=get_transform)
        
        if self.is_item_active() or self.is_item_hovered():
            render_color  = vl_utils.dim_color(color, DIM_FACTOR_ACTIVE)
        else:
            render_color  = vl_utils.dim_color(color, DIM_FACTOR_INACTIVE)
        
        self._draw_layer.add_line(
            self.project(origin),
            self.project(get_transform(data, prop)),
            color=render_color) # type: ignore
    
    def prop_distance_segment(self, data:'bpy.types.ID', prop:str, *, 
        origin:Tuple[float, float], 
        direction:Tuple[float, float]=(1,0),
        text:str|None=None,
        color=(0.0,0.5,1.0,1.0),
    ):

        text = text if text is not None else f"{prop}"
        
        def setter(data:'bpy.types.ID', prop:str, index:int, P:Tuple[float, float]):
            P = glm.vec2(P[0], P[1])
            O = glm.vec2(origin[0], origin[1])
            dir = glm.normalize(glm.vec2(direction[0], direction[1]))
            end_distance = glm.dot(P - O, dir)
            segment = list([_ for _ in getattr(data, prop)])
            segment[index] = end_distance
            setattr(data, prop, segment)

        def getter(data:'bpy.types.ID', prop:str, index:int) -> Tuple[float, float]:
            segment = getattr(data, prop)
            end_distance = segment[index]

            # set direction magnitude
            dx, dy = direction
            l = (dx**2 + dy**2)**0.5
            dx, dy = dx/l*end_distance, dy/l*end_distance

            # get origin
            Ox, Oy = origin

            # set point position
            Px = Ox + dx
            Py = Oy + dy

            return Px, Py
        
        highlight = False
        start_cp = self.prop_point(data, prop, index=0, text="", color=color, set_transform=setter, get_transform=getter)
        if self.is_item_active() or self.is_item_hovered():
            highlight = True
        end_cp =   self.prop_point(data, prop, index=1, text="", color=color, set_transform=setter, get_transform=getter)
        if self.is_item_active() or self.is_item_hovered():
            highlight = True

        P_start = self.project(start_cp.value)
        P_end =   self.project(end_cp.value)

        render_color  = color if highlight else vl_utils.dim_color(color, DIM_FACTOR_ACTIVE)
        self._draw_layer.add_line(
            P_start,
            P_end,
            color=render_color)
        


        angle = math.atan2(direction[1], direction[0])
        # make sure angle is between -pi/2 and pi/2 for better readability
        if angle > math.pi/2:
            angle -= math.pi
        elif angle < -math.pi/2:
            angle += math.pi

        self._draw_layer.add_annotation(
            ((P_start[0]+P_end[0])/2 + ANNOTATION_OFFSET_X, (P_start[1]+P_end[1])/2 - ANNOTATION_OFFSET_X),
            text,
            color=render_color,
            angle=angle)