import math
import bpy
import gpu
from typing import Literal
from gpu_extras.batch import batch_for_shader

from typing import List, Tuple
import blf

from pyglm import glm

# Constants at module level
DEFAULT_FONT_SIZE = 12
DEFAULT_FONT_ID = 0
ANNOTATION_OFFSET_X = DEFAULT_FONT_SIZE*2/3
ANNOTATION_OFFSET_Y = DEFAULT_FONT_SIZE*2/3


class View3dPainter:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')

        self._point_attributes: dict[str, List[Tuple[float, float]]] = {
            "pos":   [],
            "color": [],
        }

        self._line_attributes: dict[str, List[Tuple[float, float]]] = {
            "pos":   [],
            "color": [],
        }

        self._annotations: List[Tuple[Tuple[float, float], str, Tuple[float, float, float, float], float]] = []

    def clear(self) -> None:
        """Clear all stored drawing data."""
        self._point_attributes['pos'].clear()
        self._point_attributes['color'].clear()
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

    def add_point(self, pos: Tuple[float, float], color: Tuple[float, float, float, float], shape:Literal['.', 'X'] = '.') -> None:
        match shape:
            case 'X' | 'x':
                offset = DEFAULT_FONT_SIZE / 3
                self.add_line(pos, (pos[0] + offset, pos[1] + offset), color)  # to top-right
                self.add_line(pos, (pos[0] - offset, pos[1] - offset), color)  # to bottom-left
                self.add_line(pos, (pos[0] + offset, pos[1] - offset), color)  # to bottom-right
                self.add_line(pos, (pos[0] - offset, pos[1] + offset), color)  # to top-left
            case '.':
                self._point_attributes['pos'].append(pos)
                self._point_attributes['color'].append(color)

    def add_annotation(self, pos: Tuple[float, float], text: str, color: Tuple[float, float, float, float], angle: float = 0.0) -> None:
        self._annotations.append((pos, text, color, angle))

    def draw(self, view:glm.mat4=glm.mat4(1), projection:glm.mat4=glm.mat4(1), viewport:Tuple[float, float, float, float]=(0, 0, 1, 1)) -> None:
        gpu.state.blend_set('ALPHA')

        def project(P:Tuple[float, float]) -> Tuple[float, float]:
            projected = glm.project(glm.vec3(P[0], P[1], 0), view, projection, glm.vec4(*viewport))
            return (projected.x, projected.y)

        point_batch = batch_for_shader(
            self.shader, 
            'POINTS', 
            content={
                "pos":   [project(p) for p in self._point_attributes['pos']],
                "color": self._point_attributes['color'],
            }
        )
        point_batch.draw(self.shader)

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

