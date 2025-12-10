from enum import IntEnum
import glm
from dataclasses import dataclass

#########
# TYPES #
#########
class Axis(IntEnum):
    PositiveX = 0
    NegativeX = 1
    PositiveY = 2
    NegativeY = 3
    PositiveZ = 4
    NegativeZ = 5

class EulerOrder(IntEnum):
    XYZ = 0
    XZY = 1
    YZX = 2
    YXZ = 3
    ZXY = 4
    ZYX = 5

class ReferenceAxis(IntEnum):
    Screen = 0
    X_Axis = 1
    Y_Axis = 2
    Z_Axis = 3

class SolverMode(IntEnum):
    OneVP =   0
    TwoVP =   1
    ThreeVP = 2

@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def size(self) -> glm.vec2:
        return glm.vec2(self.width, self.height)

    @property
    def center(self) -> glm.vec2:
        return glm.vec2(self.x + self.width / 2, self.y + self.height / 2)
    
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.width
        yield self.height