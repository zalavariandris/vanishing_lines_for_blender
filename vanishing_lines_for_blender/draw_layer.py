import math
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from typing import List, Tuple
import blf

class DrawLayer:
    def __init__(self):
        self.shader = gpu.shader.from_builtin('FLAT_COLOR')

        self._point_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }

        self._line_attributes = {
            "pos":   [],
            "color": [],
        }

        self._annotations = []

    def clear(self):
        self._point_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }
        self._line_attributes: dict[str, List[Tuple[float, ...]]] = {
            "pos":   [],
            "color": [],
        }
        self._annotations: List[Tuple[Tuple[float, float], str, Tuple[float, float, float, float]]] = []

    def add_line(self, start, end, color):
        self._line_attributes['pos'].append( start )
        self._line_attributes['color'].append( color )
        self._line_attributes['pos'].append( end )
        self._line_attributes['color'].append( color )

    def add_rect(self, 
            pos:Tuple[float, float], 
            size:Tuple[float, float], 
            color:Tuple[float, float, float, float]):
        
        x0, y0 = pos
        w, h = size
        x1, y1 = x0 + w, y0 + h

        self.add_line( (x0, y0), (x1, y0), color ) # top
        self.add_line( (x1, y0), (x1, y1), color ) # right
        self.add_line( (x1, y1), (x0, y1), color ) # bottom
        self.add_line( (x0, y1), (x0, y0), color ) # left

    def add_point(self, pos, color):
        self._point_attributes['pos'].append( pos )
        self._point_attributes['color'].append( color )

    def add_text(self, pos, text, color, angle=0.0):
            self._annotations.append( (pos, text, color, angle) )

    def draw(self):
        gpu.state.blend_set('ALPHA')

        # render points
        self.point_batch = batch_for_shader(
            self.shader, 
            'POINTS', 
            self._point_attributes
        )
        self.point_batch.draw(self.shader)

        self.lines_batch = batch_for_shader(
            self.shader,
            "LINES",
            self._line_attributes
        )

        self.lines_batch.draw(self.shader)

        # render annotations
        # blf.enable(0, blf.SHADOW)
        # blf.shadow(0, 5, (0, 0, 0, 0.5))
        blf.enable(0, blf.ROTATION)
        for pos, text, color, angle in self._annotations:
            font_id = 0
            w, _ = blf.dimensions(font_id, text)
            x, y = pos
            # center text, along angle
            x, y = x - (w/2) * math.cos(angle), y - (w/2) * math.sin(angle)
            blf.position(font_id, x+3, y+3, 0)
            blf.rotation(font_id, angle)
            blf.size(font_id, 12)
            blf.color(font_id, *color)
            blf.draw(font_id, f"{text}")

        # reset rotation
        blf.rotation(font_id, 0)
        blf.disable(0, blf.ROTATION)
        # blf.disable(0, blf.SHADOW)

