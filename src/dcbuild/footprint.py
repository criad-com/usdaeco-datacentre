"""Orthogonal room footprints: rectangles by default, polygons for local edits."""


def vertices(space):
    return space.footprint or [(space.x, space.y), (space.x + space.w, space.y),
                               (space.x + space.w, space.y + space.d), (space.x, space.y + space.d)]


def area(points):
    return abs(sum(a[0]*b[1] - b[0]*a[1] for a, b in zip(points, points[1:]+points[:1]))) / 2


def contains(points, x, y):
    inside = False
    for a, b in zip(points, points[1:]+points[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside
