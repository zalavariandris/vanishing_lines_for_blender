import math
from typing import Literal, List, Tuple
from dataclasses import dataclass

# blender
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import blf
import mathutils

# third party
from pyglm import glm


# -- Constants --
DEFAULT_FONT_SIZE = 12
DEFAULT_FONT_ID = 0
ANNOTATION_OFFSET_X = DEFAULT_FONT_SIZE*2/3
ANNOTATION_OFFSET_Y = DEFAULT_FONT_SIZE*2/3


# -- Helpers --
def dim_color(color:mathutils.Vector, factor:float=0.18)->mathutils.Vector:
    assert isinstance(color, mathutils.Vector) and len(color) == 4, "Color must be a tuple/list of 4 floats (RGBA)"
    return mathutils.Vector((color[0], color[1], color[2], color[3]*factor))


# -- Classes --
@dataclass
class _Annotation:
    pos: mathutils.Vector
    text: str
    color: mathutils.Vector
    angle: float = 0.0


@dataclass
class _Marker:
    pos: mathutils.Vector
    color: mathutils.Vector
    shape: Literal['.', 'x']


@dataclass
class _Line:
    start: mathutils.Vector
    end: mathutils.Vector
    color: mathutils.Vector


class View3dPainter:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')
        self._markers: List[_Marker] = []
        self._lines: List[_Line] = []
        self._annotations: List[_Annotation] = []

    def clear(self) -> None:
        """Clear all stored drawing data."""
        self._markers.clear()
        self._lines.clear()
        self._annotations.clear()

    def add_line(self, start: mathutils.Vector, end: mathutils.Vector, color: mathutils.Vector) -> None:
        assert isinstance(start, mathutils.Vector) and len(start) == 2, "Position must be a 2D mathutils.Vector"
        assert isinstance(end, mathutils.Vector) and len(end) == 2, "Position must be a 2D mathutils.Vector"
        assert isinstance(color, mathutils.Vector) and len(color) == 4, "Color must be a tuple/list of 4 floats (RGBA)"

        self._lines.append(_Line(start, end, color))

    def add_rect(self, 
            pos: mathutils.Vector, 
            size: mathutils.Vector, 
            color: mathutils.Vector) -> None:
        assert isinstance(pos, mathutils.Vector) and len(pos) == 2, "Position must be a 2D mathutils.Vector"
        assert isinstance(size, mathutils.Vector) and len(size) == 2, "Size must be a 2D mathutils.Vector"
        assert isinstance(color, mathutils.Vector) and len(color) == 4, "Color must be a tuple/list of 4 floats (RGBA)"

        x0, y0 = pos.x, pos.y
        w, h = size.x, size.y
        x1, y1 = x0 + w, y0 + h

        self.add_line(mathutils.Vector((x0, y0)), mathutils.Vector((x1, y0)), color)  # top
        self.add_line(mathutils.Vector((x1, y0)), mathutils.Vector((x1, y1)), color)  # right
        self.add_line(mathutils.Vector((x1, y1)), mathutils.Vector((x0, y1)), color)  # bottom
        self.add_line(mathutils.Vector((x0, y1)), mathutils.Vector((x0, y0)), color)  # left

    def add_marker(self, pos: mathutils.Vector, color: mathutils.Vector, shape:Literal['.', 'x'] = '.') -> None:
        assert isinstance(pos, mathutils.Vector) and len(pos) == 2, "Position must be a 2D mathutils.Vector"
        assert isinstance(color, mathutils.Vector) and len(color) == 4, "Color must be a tuple/list of 4 floats (RGBA)"
        
        self._markers.append(_Marker(pos, color, shape))

    def add_annotation(self, pos: mathutils.Vector, text: str, color: mathutils.Vector, angle: float = 0.0) -> None:
        assert isinstance(pos, mathutils.Vector) and len(pos) == 2, "Position must be a 2D mathutils.Vector"
        assert isinstance(color, mathutils.Vector) and len(color) == 4, "Color must be a tuple/list of 4 floats (RGBA)"
        self._annotations.append(_Annotation(pos, text, color, angle))

    def _pixel_size(self, view:glm.mat4, projection:glm.mat4, viewport:Tuple[float, float, float, float], at:Tuple[float, float], pos=mathutils.Vector((0,0,0))) -> float:
        # Project the point and a slightly offset point
        def project(P:Tuple[float, float]) -> Tuple[float, float]:
            projected = glm.project(glm.vec3(P[0], P[1], 0), view, projection, glm.vec4(*viewport))
            return (projected.x, projected.y)
        
        p_mid = project(pos)
        p_offset = project((pos[0] + 0.01, pos[1])) # 0.01 is a small world-space delta

        dist_px = math.sqrt((p_offset[0] - p_mid[0])**2 + (p_offset[1] - p_mid[1])**2)
        world_delta = 0.01

        pixel_size = world_delta / (dist_px / 1.0)
        return pixel_size

    def draw(self, view:glm.mat4=glm.mat4(1), projection:glm.mat4=glm.mat4(1), viewport:Tuple[float, float, float, float]=(0, 0, 1, 1)) -> None:
        gpu.state.blend_set('ALPHA')

        from itertools import chain

        def to_columnar(list_of_structs, flatten=False):
            """
            Converts a List of Dictionaries (AoS) into a Dictionary of Lists (SoA).
            
            This is primarily used to format data for GPU shaders, where each dictionary key 
            represents a vertex attribute buffer.

            Args:
                list_of_structs (list[dict]): A list of dictionaries with identical keys.
                flatten (bool): If True, unpacks nested lists within the attributes. 
                    Useful for shapes where one object generates multiple vertices 
                    (e.g., a cross generating 4 vertices).

            Returns:
                dict: A dictionary where each key maps to a flat list of attribute values.

            Example:
                >>> data = [{'pos': [v1, v2], 'color': [c, c]}]
                >>> to_columnar(data, flatten=True)
                {'pos': [v1, v2], 'color': [c, c]}
            """
            if not list_of_structs:
                return {'pos': [], 'color': []}
            
            soa = {k: [d[k] for d in list_of_structs] for k in list_of_structs[0]}
            
            if flatten:
                # Unpack nested lists (e.g., [[p1, p2], [p3, p4]] -> [p1, p2, p3, p4])
                return {k: list(chain.from_iterable(v)) for k, v in soa.items()}
            
            return soa

        def _project(P:mathutils.Vector) -> mathutils.Vector:
            projected = glm.project(glm.vec3(P.x, P.y, 0), view, projection, glm.vec4(*viewport))
            return mathutils.Vector((projected.x, projected.y))
        
        # Render point markers
        # 1. Render Points
        dots = [{'pos': _project(m.pos), 'color': m.color} 
                for m in self._markers if m.shape == '.']
        if dots:
            batch_for_shader(self.shader, 'POINTS', content=to_columnar(dots)).draw(self.shader)

        # Render cross markers
        shape_size = DEFAULT_FONT_SIZE / 3
        
        crosses = [{
            'pos': [
                # _project((m.pos[0] - shape_size, m.pos[1] - shape_size)),
                # _project((m.pos[0] + shape_size, m.pos[1] + shape_size)),
                # _project((m.pos[0] - shape_size, m.pos[1] + shape_size)),
                # _project((m.pos[0] + shape_size, m.pos[1] - shape_size)),

                _project(mathutils.Vector((m.pos[0], m.pos[1]))) + mathutils.Vector((-shape_size ,- shape_size)),
                _project(mathutils.Vector((m.pos[0], m.pos[1]))) + mathutils.Vector((+shape_size ,+ shape_size)),
                _project(mathutils.Vector((m.pos[0], m.pos[1]))) + mathutils.Vector((-shape_size ,+ shape_size)),
                _project(mathutils.Vector((m.pos[0], m.pos[1]))) + mathutils.Vector((+shape_size ,- shape_size)),
            ], 
            'color': [m.color] * 4  # Creates [color, color, color, color]
        } for m in self._markers if m.shape == 'x']

        if crosses:
            # Use flatten=True because each entry has 4 vertices
            content = to_columnar(crosses, flatten=True)
            batch_for_shader(self.shader, 'LINES', content=content).draw(self.shader)
        # marker_cross_vertices:dict = {
        #     'pos': [],
        #     'color': []
        # }
        # for marker in filter(lambda marker: marker.shape == 'x', self._markers):
        #     shape_size = DEFAULT_FONT_SIZE / 3
        #     marker_cross_vertices["pos"].extend([
        #         (marker.pos[0] - shape_size, marker.pos[1] - shape_size),
        #         (marker.pos[0] + shape_size, marker.pos[1] + shape_size),
        #         (marker.pos[0] - shape_size, marker.pos[1] + shape_size),
        #         (marker.pos[0] + shape_size, marker.pos[1] - shape_size),
        #     ])
        #     marker_cross_vertices["color"].extend([marker.color, marker.color, marker.color, marker.color])

        # marker_cross_vertices['pos'] = list(map(_project, marker_cross_vertices['pos']))
        # cross_batch = batch_for_shader(
        #     self.shader,
        #     'LINES',
        #     content=marker_cross_vertices
        # )
        # cross_batch.draw(self.shader)

        
        # 2. Render Lines (Flattening logic)
        line_data = []
        for l in self._lines:
            p1, p2 = _project(l.start), _project(l.end)
            line_data.extend([{'pos': p1, 'color': l.color}, {'pos': p2, 'color': l.color}])
        
        if line_data:
            batch_for_shader(self.shader, 'LINES', content=to_columnar(line_data)).draw(self.shader)

        # # Render lines
        # line_vertices:dict = {
        #     'pos': [],
        #     'color': []
        # }
        # for line in self._lines:
        #     start, end, color = line.start, line.end, line.color
        #     line_vertices['pos'].extend([start, end])
        #     line_vertices['color'].extend([color, color])

        # line_vertices['pos'] = list(map(_project, line_vertices['pos']))
        # lines_batch = batch_for_shader(
        #     self.shader,
        #     'LINES',
        #     content=line_vertices
        # )
        # lines_batch.draw(self.shader)

        # Render annotations
        blf.enable(DEFAULT_FONT_ID, blf.ROTATION)
        blf.size(DEFAULT_FONT_ID, DEFAULT_FONT_SIZE)
        for annotation in self._annotations:
            w, _ = blf.dimensions(DEFAULT_FONT_ID, annotation.text)
            x, y = _project(annotation.pos)

            # Center text along angle
            x = x - (w / 2) * math.cos(annotation.angle)
            y = y - (w / 2) * math.sin(annotation.angle)
            x += ANNOTATION_OFFSET_X * math.cos(annotation.angle + math.pi/2)
            y += ANNOTATION_OFFSET_Y * math.sin(annotation.angle + math.pi/2)

            
            blf.position(DEFAULT_FONT_ID, x, y, 0)
            blf.rotation(DEFAULT_FONT_ID, annotation.angle)
            
            blf.color(DEFAULT_FONT_ID, *annotation.color)
            blf.draw(DEFAULT_FONT_ID, f"{annotation.text}")

        # Reset rotation
        blf.rotation(DEFAULT_FONT_ID, 0)
        blf.disable(DEFAULT_FONT_ID, blf.ROTATION)

