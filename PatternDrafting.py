"""Headless-safe helpers for interactive pattern drafting."""

def default_points(width, height):
    return ((0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height)))

def normalize_points(points):
    values = tuple((float(x), float(y)) for x, y in points)
    if len(values) != 4:
        raise ValueError("drafting boundary requires four points")
    return values

def serialize_points(points):
    return ";".join("%.9g,%.9g" % (x, y) for x, y in normalize_points(points))

def parse_points(value):
    if not value:
        return ()
    try:
        return normalize_points(tuple(tuple(float(v) for v in item.split(",")) for item in value.split(";")))
    except (TypeError, ValueError):
        raise ValueError("invalid drafting boundary")

def move_point(points, index, x, y):
    values = list(normalize_points(points))
    index = int(index)
    if not 0 <= index < len(values):
        raise IndexError("drafting point index out of range")
    values[index] = (float(x), float(y))
    return tuple(values)

def bounds(points):
    values = normalize_points(points)
    xs, ys = zip(*values)
    return min(xs), min(ys), max(xs), max(ys)

def seam_allowance_preview(points, allowance):
    x0, y0, x1, y1 = bounds(points)
    a = max(0.0, float(allowance))
    return ((x0-a, y0-a), (x1+a, y0-a), (x1+a, y1+a), (x0-a, y1+a))
