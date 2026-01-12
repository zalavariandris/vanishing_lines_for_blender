import math
import bpy
import gpu
from typing import Literal
from gpu_extras.batch import batch_for_shader

from typing import List, Tuple
import blf

# Constants at module level
DEFAULT_FONT_SIZE = 12
ANNOTATION_OFFSET_X = 3
ANNOTATION_OFFSET_Y = 3
DEFAULT_FONT_ID = 0


class OverlayPainter:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')

        self._point_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }

        self._line_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }

        self._annotations: List[Tuple[Tuple[float, float], str, Tuple[float, float, float, float], float]] = []

    def clear(self) -> None:
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

    def draw(self) -> None:
        gpu.state.blend_set('ALPHA')

        # Render points
        point_batch = batch_for_shader(
            self.shader, 
            'POINTS', 
            self._point_attributes
        )
        point_batch.draw(self.shader)

        # Render lines
        lines_batch = batch_for_shader(
            self.shader,
            'LINES',
            self._line_attributes
        )
        lines_batch.draw(self.shader)

        # Render annotations
        blf.enable(DEFAULT_FONT_ID, blf.ROTATION)
        for pos, text, color, angle in self._annotations:
            w, _ = blf.dimensions(DEFAULT_FONT_ID, text)
            x, y = pos
            # Center text along angle
            x = x - (w / 2) * math.cos(angle)
            y = y - (w / 2) * math.sin(angle)
            blf.position(DEFAULT_FONT_ID, x + ANNOTATION_OFFSET_X, y + ANNOTATION_OFFSET_Y, 0)
            blf.rotation(DEFAULT_FONT_ID, angle)
            blf.size(DEFAULT_FONT_ID, DEFAULT_FONT_SIZE)
            blf.color(DEFAULT_FONT_ID, *color)
            blf.draw(DEFAULT_FONT_ID, f"{text}")

        # Reset rotation
        blf.rotation(DEFAULT_FONT_ID, 0)
        blf.disable(DEFAULT_FONT_ID, blf.ROTATION)

