class SolverError(ValueError):
    """Base class for exceptions in the solver module."""
    pass

class VanishingLinesError(SolverError):
    """Exception raised for errors related to vanishing lines."""
    pass

class AxisAssignmentError(SolverError):
    """Exception raised for errors in the axis assignments."""
    pass

