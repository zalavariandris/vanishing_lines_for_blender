from dataclasses import dataclass
from enum import Enum
from typing import Tuple
from . import solver


__all__ = ['PrimaryPlane', 'PlaneSide', 'Handedness', 'PlaneBasedOrientation']


class PrimaryPlane(Enum):
    """The plane that contains the first two axes"""
    XY = "XY"
    XZ = "XZ"
    YZ = "YZ"


class PlaneSide(Enum):
    """Which side of the plane the camera is on (normal direction)"""
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"


class Handedness(Enum):
    """Rotation direction within the plane"""
    RIGHT = "RIGHT"
    LEFT = "LEFT"


class FlipAxis(Enum):
    """Whether the first axis is flipped"""
    NORMAL = "NORMAL"
    FLIPPED = "FLIPPED"


def plane_to_axes(primary_plane:PrimaryPlane, plane_side:PlaneSide, flip_axis:FlipAxis, handedness:Handedness) -> Tuple[solver.types.Axis, solver.types.Axis, solver.types.Axis]:
    """Convert to (first_axis, second_axis, third_axis) for solver"""
    
    # Base axes for each plane (canonical right-handed, positive normal)
    base_axes = {
        PrimaryPlane.XY: ('X', 'Y', 'Z'),
        PrimaryPlane.XZ: ('X', 'Z', 'Y'),
        PrimaryPlane.YZ: ('Y', 'Z', 'X'),
    }
    
    first_base, second_base, third_base = base_axes[primary_plane]
    
    # Determine signs
    first_positive = flip_axis == FlipAxis.NORMAL
    
    # Second axis sign depends on handedness and flip
    if handedness == Handedness.RIGHT:
        second_positive = flip_axis == FlipAxis.NORMAL
    else:
        second_positive = flip_axis == FlipAxis.FLIPPED
    
    # Third axis sign depends on plane side
    third_positive = plane_side == PlaneSide.POSITIVE
    
    # Swap first/second for left-handed
    if handedness == Handedness.LEFT:
        first_base, second_base = second_base, first_base
        first_positive, second_positive = second_positive, first_positive
    
    # Build axis enums
    def make_axis(base: str, positive: bool) -> solver.types.Axis:
        prefix = 'Positive' if positive else 'Negative'
        return getattr(solver.types.Axis, f"{prefix}{base}")
    
    return (
        make_axis(first_base, first_positive),
        make_axis(second_base, second_positive),
        make_axis(third_base, third_positive),
    )
    

def from_axes(first: solver.types.Axis, second: solver.types.Axis, third: solver.types.Axis) -> Tuple[PrimaryPlane, PlaneSide, FlipAxis, Handedness]:
    """Reverse-convert from signed axes to plane-based orientation"""
    
    def base_axis(axis: solver.types.Axis) -> str:
        return axis.name.replace('Positive', '').replace('Negative', '')
    
    def is_positive(axis: solver.types.Axis) -> bool:
        return 'Positive' in axis.name
    
    first_base = base_axis(first)
    second_base = base_axis(second)
    third_base = base_axis(third)
    
    first_pos = is_positive(first)
    second_pos = is_positive(second)
    third_pos = is_positive(third)
    
    # Determine plane from first two axes
    axes_set = frozenset([first_base, second_base])
    canonical_order = {
        frozenset(['X', 'Y']): (PrimaryPlane.XY, 'X', 'Y', 'Z'),
        frozenset(['X', 'Z']): (PrimaryPlane.XZ, 'X', 'Z', 'Y'),
        frozenset(['Y', 'Z']): (PrimaryPlane.YZ, 'Y', 'Z', 'X'),
    }
    
    if axes_set not in canonical_order:
        raise ValueError(f"Invalid axis combination: {first}, {second}")
    
    plane, canon_first, canon_second, canon_third = canonical_order[axes_set]
    
    # Verify third axis matches expected
    if third_base != canon_third:
        raise ValueError(f"Third axis {third} doesn't match plane {plane}")
    
    # Determine if axes are in canonical order (X before Y, X before Z, Y before Z)
    is_canonical_order = first_base == canon_first
    
    # Determine handedness using cross product rule
    # Right-hand rule: X×Y=+Z, X×Z=-Y, Y×Z=+X (for positive axes)
    # We compute expected third sign if right-handed, then compare
    cross_product_sign = {
        ('X', 'Y'): True,   # X × Y = +Z
        ('Y', 'X'): False,  # Y × X = -Z
        ('X', 'Z'): False,  # X × Z = -Y
        ('Z', 'X'): True,   # Z × X = +Y
        ('Y', 'Z'): True,   # Y × Z = +X
        ('Z', 'Y'): False,  # Z × Y = -X
    }
    
    # Expected third axis sign for right-handed system
    base_cross_positive = cross_product_sign[(first_base, second_base)]
    
    # Flip sign based on input axis signs: (±A) × (±B) = (±)(±)(A×B)
    expected_third_positive = base_cross_positive
    if not first_pos:
        expected_third_positive = not expected_third_positive
    if not second_pos:
        expected_third_positive = not expected_third_positive
    
    # Compare with actual third axis sign
    is_right_handed = (third_pos == expected_third_positive)
    handedness = Handedness.RIGHT if is_right_handed else Handedness.LEFT
    
    # Determine plane side from third axis sign
    plane_side = PlaneSide.POSITIVE if third_pos else PlaneSide.NEGATIVE
    
    # Determine flip from first axis sign (in canonical order) or second (if swapped)
    if is_canonical_order:
        flip = FlipAxis.NORMAL if first_pos else FlipAxis.FLIPPED
    else:
        flip = FlipAxis.NORMAL if second_pos else FlipAxis.FLIPPED
    
    return plane, plane_side, flip, handedness
    
    # @staticmethod
    # def default() -> 'PlaneBasedOrientation':
    #     """Return default orientation (XZ plane, +Y up, right-handed)"""
    #     return PlaneBasedOrientation(
    #         PrimaryPlane.XZ,
    #         PlaneSide.POSITIVE,
    #         Handedness.RIGHT,
    #         FlipAxis.NORMAL
    #     )