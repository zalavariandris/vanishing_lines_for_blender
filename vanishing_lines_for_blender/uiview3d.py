from typing import Tuple, Callable
from . import vl_utils
from . import vl_coord_utils
from . draw_layer import DrawLayer
from pyglm import glm
import bpy

class _ControlPoint():
    def __init__(self, data:bpy.types.ID, prop:str, *, 
            setter:Callable|None=None, 
            getter:Callable|None=None):
        self._data = data
        self._prop = prop


        if setter is None:
            self._setter = lambda data, prop, value: setattr(self._data, self._prop, value)
        else:
            self._setter = setter
        
        if getter is None:
            self._getter = lambda data, prop: getattr(self._data, self._prop)
        else:
            self._getter = getter
        
    @property
    def value(self):
        return self._getter(self._data, self._prop)
    
    @value.setter
    def value(self, value): # todo: we should use the actual _bpy prop_ type here, but how?
        self._setter(self._data, self._prop, value)

class UIView3D:
    def __init__(self):
        self._controls: dict[Tuple[bpy.types.ID, str], _ControlPoint] = dict()
        self._draw_layer: DrawLayer|None = DrawLayer()

        # interaction
        self._active_id: Tuple[bpy.types.ID, str]|None = None
        self._hovered_id: Tuple[bpy.types.ID, str]|None = None
        self._is_left_mouse_down = False

        self._view: glm.mat4 = glm.mat4(1.0)
        self._projection: glm.mat4 = glm.mat4(1.0)
        self._viewport: Tuple[int, int, int, int] = (0, 0, 1, 1)

    def render(self):
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
        camera_frame = vl_coord_utils.get_view_camera_frame_rect(context)
        output_aspect = context.scene.render.resolution_x / context.scene.render.resolution_y     
        match context.space_data.camera.data.sensor_fit:
            case 'AUTO':
                if output_aspect >= 1.0:
                    # horizontal
                    x, y = -1, -1 + (2-2/output_aspect)/2
                    w, h = 2, 2/output_aspect
                    self.set_projection(glm.orthoLH(x, x+w, y, y+h, -1000.0, 1000.0))
                    self.set_viewport(camera_frame)
                else:
                    # vertical
                    x, y = -1+ (2-2*output_aspect)/2, -1
                    w, h = 2*output_aspect, 2
                    self.set_projection(glm.orthoLH(x, x+w, y, y+h, -1000.0, 1000.0))
                    self.set_viewport(camera_frame)

            case 'HORIZONTAL':
                x, y = -1, -1 + (2-2/output_aspect)/2
                w, h = 2, 2/output_aspect
                self.set_projection(glm.orthoLH(x, x+w, y, y+h, -1000.0, 1000.0))
                self.set_viewport(camera_frame)

            case 'VERTICAL':
                x, y = -1+ (2-2*output_aspect)/2, -1
                w, h = 2*output_aspect, 2
                self.set_projection(glm.orthoLH(x, x+w, y, y+h, -1000.0, 1000.0))
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
    def event(self, context, event:bpy.types.Event):
        ###
        # Event Helpers
        ###
        # print("Event:", event.type, event.value)
        area: bpy.types.Area|None = context.area
        if area is None:
            return {'PASS_THROUGH'}
        
        region: bpy.types.Region|None = context.region
        if region is None:
            return {'PASS_THROUGH'}

        """Cancel on ESC or camera change"""
        if event.type in {'ESC'}:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            return {'FINISHED'}
        
        ###
        #  HANDLE MOUSE EVENTS
        ###
        MouseIsInArea = (
            event.mouse_region_x>0 and 
            event.mouse_region_x<area.width and 
            event.mouse_region_y>0 and 
            event.mouse_region_y<area.height
        )

        MouseIsInRegion = (
            0 <= event.mouse_region_x < region.width and
            0 <= event.mouse_region_y < region.height
        )

        """Mouse Events"""
        if not MouseIsInRegion:
            # self.report({'INFO'}, "mouse is not in area")
            return {'PASS_THROUGH'}
        
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            """Wheel Events"""
            if area.type == 'VIEW_3D':
                area.tag_redraw()
            return {'PASS_THROUGH'}

        if MouseIsInRegion and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._is_left_mouse_down = True

            # activate cp under mouse
            self._active_id = self.get_closest_id(event.mouse_region_x, event.mouse_region_y)    
            # trigger redraw
            if area.type == 'VIEW_3D':
                area.tag_redraw()

            if self._active_id is not None:
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
        
        elif MouseIsInRegion and event.type == 'MOUSEMOVE':
            if not self._is_left_mouse_down:
                """Mouse Move"""
                # update hover

                new_hovered_id = self.get_closest_id(event.mouse_region_x, event.mouse_region_y)

                if new_hovered_id != self._hovered_id:
                    self._hovered_id = new_hovered_id

                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

                if self._hovered_id is not None:
                    return {'RUNNING_MODAL'}
                else:
                    return {'PASS_THROUGH'}

            elif self._active_id is not None:
                """Mouse Drag"""
                # move active control point
                mouse_x_unproj, mouse_y_unproj = self.unproject((event.mouse_region_x, event.mouse_region_y))

                self._controls[self._active_id].value = (mouse_x_unproj, mouse_y_unproj)
                # self.set_control_point(self._active_name, (mouse_x_unproj, mouse_y_unproj))
                # self.update_solve(context)

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
            
        elif self._is_left_mouse_down and event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._is_left_mouse_down = False
            """Mouse Release Event"""
            if self._active_id is not None:
                self._active_id = None

                # trigger redraw
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    # GUI
    def get_closest_id(self, mouse_region_x: float, mouse_region_y: float, threshold:float=22.0) -> Tuple[bpy.types.ID, str]|None:
        closest_key:Tuple[bpy.types.ID, str]|None = None
        closest_dist_sq = threshold * threshold

        for control_id, control_point in self._controls.items():
            P = (self.project(control_point.value))
            dist_sq = (P[0] - mouse_region_x) ** 2 + (P[1] - mouse_region_y) ** 2
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest_key = control_id

        return closest_key
   
    def is_item_hovered(self):
        last_id = list(self._controls.keys())[-1]
        return self._hovered_id == last_id
    
    def is_item_active(self):
        last_id = list(self._controls.keys())[-1]
        return self._active_id == last_id

    # Widgets
    def prop_point(self, data:bpy.types.ID, prop:str, *,
        text:str="",
        color=(1.0,0.5,0.0,1.0),
        setter:Callable|None=None, 
        getter:Callable|None=None
    ) -> _ControlPoint:
        assert self._draw_layer is not None, "Draw layer not initialized"
        control_id = (data, prop)
        if control_id not in self._controls:
            self._controls[control_id] = _ControlPoint(data, prop, setter=setter, getter=getter)

        cp = self._controls[control_id]
        P = self.project(cp.value)
        is_active = (self._active_id == control_id)
        is_hovered = (self._hovered_id == control_id)

        point_color = color
        if is_active or is_hovered:
            point_color = (1.0, 1.0, 1.0, 1.0)
            self._draw_layer.add_text(
                (P[0]+5, P[1]-15), f"({cp.value[0]:.2f}, {cp.value[1]:.2f})",
                color=(1,1,1,1))

        self._draw_layer.add_point(
            P,
            point_color)

        self._draw_layer.add_text(
            (P[0]+5, P[1]+5),
            text,
            color=(1,1,1,1))
        
        return self._controls[control_id]
    
    def prop_line(self, data:bpy.types.ID, *, start_prop:str='start', end_prop:str='end', 
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
        
    def prop_distance(self, data:bpy.types.ID, prop:str, origin:Tuple[float, float], direction:Tuple[float, float]=(1,0), *,
        text:str="",
        color=(0.0,0.5,1.0,1.0),
    ) -> _ControlPoint:
        
        def setter(data:bpy.types.ID, prop:str, P:Tuple[float, float]):
            P = glm.vec2(P[0], P[1])
            O = glm.vec2(origin[0], origin[1])
            dir = glm.normalize(glm.vec2(direction[0], direction[1]))
            distance = glm.dot(P - O, dir)
            setattr(data, prop, distance)

        def getter(data:bpy.types.ID, prop:str) -> float:
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
                        setter=setter,
                        getter=getter)
        
        self._draw_layer.add_line(
            self.project(origin),
            self.project(getter(data, prop)),
            color=vl_utils.dim_color(color, 0.3) if self.is_item_active() or self.is_item_hovered() else vl_utils.dim_color(color, 0.1))
    
