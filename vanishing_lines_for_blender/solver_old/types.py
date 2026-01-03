from enum import IntEnum
from typing import Tuple
from dataclasses import dataclass

#########
# TYPES #
#########
Point2 = Tuple[float, float]
Point3 = Tuple[float, float, float]
Line2 = Tuple[Point2, Point2] # two endpoints
Line3 = Tuple[Point3, Point3] # two endpoints
Ray2 = Tuple[Point2, Point2] # origin, direction
Ray3 = Tuple[Point3, Point3] # origin, direction
Plane3 = Tuple[Point3, Point3]  # point, normal


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
    Screen = 1
    X_Axis = 2
    Y_Axis = 3
    Z_Axis = 4

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
    def size(self) -> Tuple[float, float]:
        return self.width, self.height

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def aspect(self) -> float:
        return self.width / self.height
    
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.width
        yield self.height