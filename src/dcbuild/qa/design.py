"""Conservative door optics before the scene/occlusion study (SI and degrees)."""
import math

import numpy as np

from ..layout import NORMALS


def door_optics(plan, *, external=False):
    """Check the whole inset face, including corners beyond the sampled grid.

    Independent plane model: H / (2 d tan(hfov/2)). This is only optical
    feasibility; the family runner is required to establish unobstructed rays.
    External bullets use 125 px/m and their declared range. Check the primary
    door only: a shared approach supplements that door's own close bullet.
    """
    result = {}
    elevations = {s.id: s.elevation for s in plan.storeys}
    doors = {d.id: d for d in plan.doors}
    for camera in plan.cameras:
        if not camera.id.startswith('sec.cam.ext.' if external else 'sec.cam.door.'):
            continue
        door = doors[camera.targets[0]]
        typ = plan.security['camera_types'][camera.type]
        normal = np.array([*NORMALS[door.approach_normal], 0.])
        across = np.array([-normal[1], normal[0], 0.])
        centre = np.array([*door.pos, elevations[door.storey]]) + normal * .15
        points = np.array([centre + across*x + [0, 0, z]
                           for x in (-door.width/2+.1, door.width/2-.1)
                           for z in (.3, min(door.height, 2.1))])
        origin = np.array(camera.pos) + typ['offset']
        pan, tilt = map(math.radians, (camera.pan, camera.tilt))
        forward = np.array([math.cos(pan)*math.cos(tilt), math.sin(pan)*math.cos(tilt), -math.sin(tilt)])
        right = np.array([math.sin(pan), -math.cos(pan), 0.])
        up = np.cross(right, forward)
        f0, f1 = typ['focal_range']
        focal = camera.focal_length
        def tangent(angles):
            widths = [2*f*math.tan(math.radians(a)/2) for f,a in zip((f0,f1), angles)]
            width = widths[0] if f0 == f1 else widths[0]+(widths[1]-widths[0])*(focal-f0)/(f1-f0)
            return width/(2*focal)
        tx, ty = tangent(typ['hfov_range']), tangent(typ['vfov_range'])
        vectors = points-origin
        distance = np.linalg.norm(vectors, axis=1)
        depth = vectors@forward
        inside = (depth>0) & (abs(vectors@right)<=tx*depth) & (abs(vectors@up)<=ty*depth)
        density = typ['pixels'][0]/(2*distance*tx)
        result[camera.id] = dict(maxDistance=float(max(distance)), minDensity=float(min(density)),
                                 inside=bool(all(inside)),
                                 passed=bool(all(inside) and max(distance)<=(camera.range if external else min(3.,camera.range))
                                             and min(density)>=(125 if external else 250) and f0<=focal<=f1))
    return result
