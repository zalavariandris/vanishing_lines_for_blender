import math
from typing import Tuple, Callable

from . import vl_utils
from . import vl_coord_utils
from .view3d_painter import View3dPainter
from pyglm import glm


# Constants
CLIP_NEAR = -1000.0
CLIP_FAR = 1000.0
DEFAULT_CLICK_THRESHOLD = 22.0

DIM_FACTOR_ACTIVE = 0.3
DIM_FACTOR_INACTIVE = 0.1

from typing import Any
SetterCallbackWithIndexType = Callable[[Any, Any, int,  Any], None]
SetterCallbackWithoutType =   Callable[[Any, Any, Any],       None]

GetterCallbackWithIndexType = Callable[[Any, Any, int], Tuple[float, float]]
GetterCallbackWithoutType =   Callable[[Any, Any],      Tuple[float, float]]

SetterCallbackType = SetterCallbackWithIndexType | SetterCallbackWithoutType
GetterCallbackType = GetterCallbackWithIndexType | GetterCallbackWithoutType


ControlIdType = Tuple['bpy.types.ID', str, int|None]


class ControlPointWidget():
    def __init__(self, 
        data:'bpy.types.ID', 
        prop:str, *, 
        text:str|None=None,
        color:Tuple[float, float, float, float]=(1.0, 1.0, 1.0, 1.0),
        index:int|None=None, 
        setter:SetterCallbackType|None=None, 
        getter:GetterCallbackType|None=None
    ):
        
        # TODO: vallidate data structure

        # Store parameters
        self.data = data
        self.prop = prop
        self.index = index
        self.text = text if text is not None else f"{prop}"
        self.color = color

        # TODO: setter and getter transforms will not be needed, with the new widget system
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

    def manipulate(self, mouse_x, mouse_y, mouse_down_x, mouse_down_y, value_prev_press_x, value_prev_press_y):
        mouse_delta_x = mouse_x - mouse_down_x
        mouse_delta_y = mouse_y - mouse_down_y

        new_x_unproj = value_prev_press_x + mouse_delta_x
        new_y_unproj = value_prev_press_y + mouse_delta_y
        self.value = (new_x_unproj, new_y_unproj)

    def paint(self, painter:View3dPainter, hovered:bool=False, active:bool=False):
        text = self.text if self.text is not None else f"{self.prop}"

        P = self.value# self.project(cp.value)

        point_render_color = self.color
        if active or hovered:
            point_render_color = (1.0, 1.0, 1.0, 1.0)

        painter.add_point(
            P,
            point_render_color)


        painter.add_annotation(
            (self.value[0]+5, self.value[1]),
            text=text,
            color=point_render_color)
        
    def hit_test(self, mouse_x:float, mouse_y:float, threshold:float)->bool:
        P = self.value # self.project(self.value)
        dist_sq = (P[0] - mouse_x) ** 2 + (P[1] - mouse_y) ** 2
        return dist_sq < threshold **2

    @property
    def value(self)->Tuple[float, float]:
        if self.index is None:
            return self._get_transform(self.data, self.prop)
        else:
            return self._get_transform(self.data, self.prop, self.index)
    
    @value.setter
    def value(self, value:Tuple[float, float] ):
        if self.index is None:
            self._set_transform(self.data, self.prop, value)
        else:
            self._set_transform(self.data, self.prop, self.index, value)
            

class VanishingLineWidget:
    def __init__(self,
        data:'bpy.types.ID', 
        prop:str, *, 
        text:str|None=None,
        color:Tuple[float, float, float, float]=(1.0, 1.0, 1.0, 1.0),
        index:int|None=None
    ):
        self.data = data
        self.prop = prop
        self.index = index
        self.text = text if text is not None else f"{prop}"
        self.color = color

        # TODO: vallidate data structure


    def hit_test(self, mouse_x:float, mouse_y:float, threshold:float)->bool:
        return False

    def paint(self, painter:View3dPainter, hovered:bool=False, active:bool=False):
        if self.index is not None:
            start = getattr(self.data, self.prop)[self.index]['start']
            end = getattr(self.data, self.prop)[self.index]['end']
        else:
            start = getattr(self.data, self.prop)['start']
            end = getattr(self.data, self.prop)['end']

        painter.add_line(start, end, self.color)
        painter.add_point(start, self.color)
        painter.add_point(end, self.color)

    def manipulate(self, mouse_x, mouse_y, mouse_down_x, mouse_down_y, value_prev_press_x, value_prev_press_y):
        ...


class View3dGUI:
    def __init__(self):
        self._widgets: dict[ControlIdType, ControlPointWidget|VanishingLineWidget] = dict()
        self._painter: View3dPainter = View3dPainter()

        # interaction
        self._active_id: ControlIdType|None = None
        self._hovered_id: ControlIdType|None = None

        # mouse dragging
        self._is_left_mouse_down = False
        self._active_down_pos: Tuple[float, float] = (0.0, 0.0)

        # coordinate system
        self._view: glm.mat4 = glm.mat4(1.0)
        self._projection: glm.mat4 = glm.mat4(1.0)
        self._viewport: Tuple[int, int, int, int] = (0, 0, 1, 1)

    def begin(self):
        # self.uiview.update_viewport_state(context)
        self._painter.clear()
        self._widgets.clear()

    def end(self):
        pass
        # self._painter.draw(self._view, self._projection, self._viewport)

    def render(self):
        self._painter.draw(self._view, self._projection, self._viewport)
    
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

            # activate cp under mouse
            self._active_id = self.get_widget_under_mouse(event.mouse_region_x, event.mouse_region_y)

            if self._active_id is not None:
                # store a _copy_ of the control position at mouse down
                position:Tuple[float, float] = tuple(self._widgets[self._active_id].value)
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
                new_hovered_id = self.get_widget_under_mouse(event.mouse_region_x, event.mouse_region_y)

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
                

                mouse_x_unproj, mouse_y_unproj = self.unproject((event.mouse_x-context.region.x, event.mouse_y-context.region.y))
                mouse_prev_press_x_unproj, mouse_prev_press_y_unproj = self.unproject((event.mouse_prev_press_x-context.region.x, event.mouse_prev_press_y-context.region.y))
                control_point = self._widgets[self._active_id]

                control_point.manipulate( 
                    mouse_x_unproj, mouse_y_unproj, 
                    mouse_prev_press_x_unproj, mouse_prev_press_y_unproj, 
                    self._active_down_pos[0], self._active_down_pos[1])

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

    #######
    # GUI #
    #######
    # def get_closest_id(self, mouse_region_x: float, mouse_region_y: float, threshold:float=DEFAULT_CLICK_THRESHOLD) -> ControlIdType|None:
    #     closest_key:ControlIdType|None = None
    #     closest_dist_sq = threshold * threshold

    #     for control_id, control_point in reversed(self._controls.items()):
    #         P = (self.project(control_point.value))
    #         dist_sq = (P[0] - mouse_region_x) ** 2 + (P[1] - mouse_region_y) ** 2
    #         if dist_sq < closest_dist_sq:
    #             closest_dist_sq = dist_sq
    #             closest_key = control_id

    #     return closest_key
    
    def get_widget_under_mouse(self, mouse_region_x: float, mouse_region_y: float, threshold:float=DEFAULT_CLICK_THRESHOLD) -> ControlIdType|None:
        compute_space_threshold = 0.03 # TODO: make this scale with zoom level
        mouse_proj =self.unproject((mouse_region_x, mouse_region_y))
        print("Mouse proj:", mouse_proj)
        for control_id, control_point in reversed(self._widgets.items()):
            
            if control_point.hit_test(mouse_proj[0], mouse_proj[1], compute_space_threshold):
                return control_id

        return None
   
    def is_item_hovered(self):
        last_id = next(reversed(self._widgets))
        return self._hovered_id == last_id
    
    def is_item_active(self):
        last_id = next(reversed(self._widgets))
        return self._active_id == last_id

    # Widgets
    def add_widget(self, widget:ControlPointWidget|VanishingLineWidget) -> ControlPointWidget|VanishingLineWidget:
        control_id = (widget.data, widget.prop, widget.index)
        if control_id not in self._widgets:
            self._widgets[control_id] = widget

        is_active = (self._active_id == control_id)
        is_hovered = (self._hovered_id == control_id)

        control = self._widgets[control_id]
        control.paint(self._painter, hovered=is_hovered, active=is_active)

        return widget

    def prop_point(self, 
        data:'bpy.types.ID', 
        prop:str, 
        *,
        text:str|None=None,
        index:int|None=None,
        color=(1.0,0.5,0.0,1.0),

        set_transform:Callable|None=None, 
        get_transform:Callable|None=None
    ) -> ControlPointWidget:
        assert self._painter is not None, "Draw layer not initialized"
        control_id = (data, prop, index)
        if control_id not in self._widgets:
            self._widgets[control_id] = ControlPointWidget(data, 
                prop, 
                text=text,
                index=index,
                color=color, 
                setter=set_transform, 
                getter=get_transform)


        is_active = (self._active_id == control_id)
        is_hovered = (self._hovered_id == control_id)

        control = self._widgets[control_id]
        control.paint(self._painter, hovered=is_hovered, active=is_active)
        
        return self._widgets[control_id]
    
    def prop_line(self, data:'bpy.types.ID', *, start_prop:str='start', end_prop:str='end', 
        color=(0.8,0.8,0.8,1.0)
    ):
        assert self._painter is not None, "Draw layer not initialized"
        start_cp = self.prop_point(data, start_prop, text="", color=color)
        end_cp = self.prop_point(data, end_prop, text="", color=color)

        P_start = start_cp.value # self.project(start_cp.value)
        P_end = end_cp.value # self.project(end_cp.value)

        self._painter.add_line(
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
        
        self._painter.add_line(
            origin,
            get_transform(data, prop),
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

        P_start = start_cp.value
        P_end =   end_cp.value

        render_color  = color if highlight else vl_utils.dim_color(color, DIM_FACTOR_ACTIVE)
        self._painter.add_line(
            P_start,
            P_end,
            color=render_color)
        


        angle = math.atan2(direction[1], direction[0])
        # make sure angle is between -pi/2 and pi/2 for better readability
        if angle > math.pi/2:
            angle -= math.pi
        elif angle < -math.pi/2:
            angle += math.pi

        self._painter.add_annotation(
            ((P_start[0]+P_end[0])/2, (P_start[1]+P_end[1])/2),
            text,
            color=render_color,
            angle=angle)