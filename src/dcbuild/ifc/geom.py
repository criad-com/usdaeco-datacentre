"""Pure geometry helpers (no ifcopenshell state).

Placements are authored as 4x4 matrices whose columns are the local X/Y/Z axes
and whose last column is the origin. Extruded profile representations are built
in a local frame and extrude along the local +Z axis, so the "run frames" below
point local +Z along the direction a tray/pipe/segment should run.
"""
from __future__ import annotations

import numpy as np


def matrix(x_axis, y_axis, z_axis, location=None) -> np.ndarray:
    """Build a 4x4 placement matrix from local axes (columns) + origin."""
    m = np.eye(4)
    m[:3, 0] = x_axis
    m[:3, 1] = y_axis
    m[:3, 2] = z_axis
    if location is not None:
        m[:3, 3] = location
    return m


# Identity-orientation frame (local axes == world axes).
Z_UP = matrix((1, 0, 0), (0, 1, 0), (0, 0, 1))

# Run frames: local +Z (the extrusion axis) points along world +X / +Y / -Z (and
# reversed variants for runs that travel -X / -Y).
X_RUN = matrix((0, 1, 0), (0, 0, 1), (1, 0, 0))
Y_RUN = matrix((-1, 0, 0), (0, 0, 1), (0, 1, 0))
X_RUN_NEG = matrix((0, -1, 0), (0, 0, 1), (-1, 0, 0))
Y_RUN_NEG = matrix((1, 0, 0), (0, 0, 1), (0, -1, 0))
Z_DOWN = matrix((1, 0, 0), (0, -1, 0), (0, 0, -1))

# Mount a face-fixed box with its depth along -Y (local +Z -> world -Y).
FACE_MINUS_Y = matrix((1, 0, 0), (0, 0, 1), (0, -1, 0))


def at(frame: np.ndarray, location) -> np.ndarray:
    """Return a copy of `frame` translated to `location`."""
    m = frame.copy()
    m[:3, 3] = location
    return m


def rot_z(degrees: float, location=None) -> np.ndarray:
    """Placement rotated `degrees` about world +Z (CCW), at `location`."""
    r = np.radians(degrees)
    c, s = np.cos(r), np.sin(r)
    return matrix((c, s, 0), (-s, c, 0), (0, 0, 1), location)


def frame_between(p1, p2) -> tuple[np.ndarray, float]:
    """Run frame + length for an axis-aligned segment p1 -> p2 (3D points).

    Local +Z points from p1 to p2; works for the six axis directions used by
    orthogonal routes (X/Y horizontal legs, vertical risers up/down).
    """
    d = np.asarray(p2, dtype=float) - np.asarray(p1, dtype=float)
    length = float(np.linalg.norm(d))
    if length < 1e-9:
        raise ValueError("zero-length segment")
    z = d / length
    up = np.array([0.0, 0.0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    x = np.cross(up, z)
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    return matrix(tuple(x), tuple(y), tuple(z), tuple(np.asarray(p1, dtype=float))), length
