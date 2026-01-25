import math
import bpy
import gpu
from typing import Literal
from gpu_extras.batch import batch_for_shader

from typing import List, Tuple
import blf
import mathutils
from pyglm import glm

# Constants at module level
DEFAULT_FONT_SIZE = 12
DEFAULT_FONT_ID = 0
ANNOTATION_OFFSET_X = DEFAULT_FONT_SIZE*2/3
ANNOTATION_OFFSET_Y = DEFAULT_FONT_SIZE*2/3


class View3dPainter:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')

        self._points: List[Tuple[Tuple[float, float], Tuple[float, float, float, float], Literal['.', 'X']]] = []

        self._line_attributes: dict[str, List[Tuple[float, float]]] = {
            "pos":   [],
            "color": [],
        }

        self._annotations: List[Tuple[Tuple[float, float], str, Tuple[float, float, float, float], float]] = []

    def clear(self) -> None:
        """Clear all stored drawing data."""
        self._points.clear()
        self._line_attributes['pos'].clear()
        self._line_attributes['color'].clear()
        self._annotations.clear()

    def add_line(self, start: Tuple[float, float], end: Tuple[float, float], color: Tuple[float, float, float, float]) -> None:
        self._line_attributes['pos'].append(start)
        self._line_attributes['color'].append(color)
        self._line_attributes['pos'].append(end)
        self._line_attributes['color'].append(color)

    def add_rect(self, 
            pos: Tuple[float, float], 
            size: Tuple[float, float], 
            color: Tuple[float, float, float, float]) -> None:
        
        x0, y0 = pos
        w, h = size
        x1, y1 = x0 + w, y0 + h

        self.add_line((x0, y0), (x1, y0), color)  # top
        self.add_line((x1, y0), (x1, y1), color)  # right
        self.add_line((x1, y1), (x0, y1), color)  # bottom
        self.add_line((x0, y1), (x0, y0), color)  # left

    def add_point(self, pos: Tuple[float, float], color: Tuple[float, float, float, float], shape:Literal['.', 'x'] = '.') -> None:
        match shape:
            case 'x':
                self._points.append((pos, color, shape))
                offset = DEFAULT_FONT_SIZE / 3
            case '.':
                self._points.append((pos, color, shape))
            case _:
                raise ValueError(f"Unsupported shape '{shape}' for add_point. Use '.' or 'X'.")

    def add_annotation(self, pos: Tuple[float, float], text: str, color: Tuple[float, float, float, float], angle: float = 0.0) -> None:
        self._annotations.append((pos, text, color, angle))

    def pixel_size(self, view:glm.mat4, projection:glm.mat4, viewport:Tuple[float, float, float, float], at:Tuple[float, float], pos=mathutils.Vector((0,0,0))) -> float:
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

        def project(P:Tuple[float, float]) -> Tuple[float, float]:
            projected = glm.project(glm.vec3(P[0], P[1], 0), view, projection, glm.vec4(*viewport))
            return (projected.x, projected.y)
        
        # Render points with dot shape
        point_batch = batch_for_shader(
            self.shader, 
            'POINTS', 
            content={
                "pos":   [project(attr[0]) for attr in self._points if attr[2] == '.'],
                "color": [attr[1] for attr in self._points if attr[2] == '.' ],
            }
        )
        point_batch.draw(self.shader)

        # Render points with X shape
        x_content:dict = {
            'pos': [], 
            'color': []
        }
        for pos, color, shape in [attr for attr in self._points if attr[2] == 'x']:
            if shape == 'x':
                shape_size = DEFAULT_FONT_SIZE / 3
                P = project(pos)
                x_content["pos"].extend([
                    (P[0] - shape_size, P[1] - shape_size),
                    (P[0] + shape_size, P[1] + shape_size),
                    (P[0] - shape_size, P[1] + shape_size),
                    (P[0] + shape_size, P[1] - shape_size),
                ])
                x_content["color"].extend([color, color, color, color])
                
        x_batch = batch_for_shader(
            self.shader,
            'LINES',
            content=x_content
        )
        x_batch.draw(self.shader)

        # Render lines
        lines_batch = batch_for_shader(
            self.shader,
            'LINES',
            content={
                "pos":   [project(p) for p in self._line_attributes['pos']],
                "color": self._line_attributes['color'],
            }
        )
        lines_batch.draw(self.shader)

        # Render annotations
        blf.enable(DEFAULT_FONT_ID, blf.ROTATION)
        blf.size(DEFAULT_FONT_ID, DEFAULT_FONT_SIZE)
        for pos, text, color, angle in self._annotations:
            w, _ = blf.dimensions(DEFAULT_FONT_ID, text)
            x, y = project(pos)

            # Center text along angle
            x = x - (w / 2) * math.cos(angle)
            y = y - (w / 2) * math.sin(angle)
            x += ANNOTATION_OFFSET_X * math.cos(angle + math.pi/2)
            y += ANNOTATION_OFFSET_Y * math.sin(angle + math.pi/2)

            
            blf.position(DEFAULT_FONT_ID, x, y, 0)
            blf.rotation(DEFAULT_FONT_ID, angle)
            
            blf.color(DEFAULT_FONT_ID, *color)
            blf.draw(DEFAULT_FONT_ID, f"{text}")

        # Reset rotation
        blf.rotation(DEFAULT_FONT_ID, 0)
        blf.disable(DEFAULT_FONT_ID, blf.ROTATION)

