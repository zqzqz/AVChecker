from z3 import *

counter = 0


def get_nounce():
    global counter
    counter += 1
    return str(counter)


class BaseModel:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Point(BaseModel):
    def __init__(self, l, s, name=""):
        super().__init__(name)
        self.l = l
        self.s = s


class Line(BaseModel):
    def __init__(self, func, name=""):
        super().__init__(name)
        self.func = func

    def get(self, l, s):
        return self.func(l, s)


class Area(BaseModel):
    def __init__(self, func, name=""):
        super().__init__(name)
        self.func = func

    def get(self, l, s):
        return self.func(l, s)


class SimArea(Area):
    def __init__(self, start_l, start_s, end_l, end_s, name=""):
        self.start_l = start_l
        self.start_s = start_s
        self.end_l = end_l
        self.end_s = end_s
        def func(l, s):
            C = []
            if start_l is not None:
                C.append(l >= start_l)
            if start_s is not None:
                C.append(s >= start_s)
            if end_l is not None:
                C.append(l <= end_l)
            if end_s is not None:
                C.append(s <= end_s)
            return And(*C)
        super().__init__(func, name)


class BoundaryArea(SimArea):
    def __init__(self, start: Point, end: Point, name=""):
        super().__init__(start.l, start.s, end.l, end.s, name)


class CenterArea(BoundaryArea):
    def __init__(self, center: Point, boundary: Point, name=""):
        start = Point(center.l - boundary.l, center.s - boundary.s)
        end = Point(center.l + boundary.l, center.s + boundary.s)
        super().__init__(start, end, name)


def get_line_segment(p1, p2, name=""):
    def f(l, s):
        return And((p2.s - p1.s) * (p2.l - l) == (p2.s - s) * (p2.l - p1.l), Or(And(l <= p2.l, l >= p1.l), And(l >= p2.l, l <= p1.l)))
    return Line(f, name)


def get_square_distance(p1, p2):
    return (p2.l - p1.l) ** 2 + (p2.s - p1.s) ** 2


def get_ray(p, v, name=""):
    def f(l, s):
        return And(v.l * (s - p.s) == v.s * (l - p.l), v.s * (s - p.s) >= 0, v.l * (l - p.l) >= 0)
    return Line(f, name)


def get_limited_ray(p, v, length, name=""):
    def f(l, s):
        p2 = Point(l, s)
        return And(get_square_distance(p, p2) <= length ** 2, v.l * (s - p.s) == v.s * (l - p.l), v.s * (s - p.s) >= 0, v.l * (l - p.l) >= 0)
    return Line(f, name)


def get_trajectory(p, v, t, name=""):
    if t > 0:
        def f(l, s):
            p2 = Point(l, s)
            return And(get_square_distance(p, p2) <= (v.l * t) ** 2 + (v.s * t) ** 2, v.l * (s - p.s) == v.s * (l - p.l), v.s * (s - p.s) >= 0, v.l * (l - p.l) >= 0)
        return Line(f, name)
    else:
        return get_ray(p, v, name)


def z3_abs(v):
    return If(v >= 0, v, -v)


def z3_min(a, b):
    return If(a < b, a, b)


def z3_max(a, b):
    return If(a > b, a, b)


def is_color(x, color):
    if color == "green":
        return x == 3
    elif color == "yellow":
        return x == 2
    elif color == "red":
        return x == 1
    elif color == "unknown":
        return x <= 0
    else:
        return None


def is_direction(x, direction):
    if direction == "left":
        return x < 0
    elif direction == "straight":
        return x == 0
    elif direction == "right":
        return x > 0
    else:
        return None


def is_int_val(x, v):
    return And(x >= v, x < v + 1)


def is_point_on_line(p: Point, f: Line):
    name = str(p) + "_" + str(f) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return Exists([l, s], And(l == p.l, s == p.s, f.get(l, s)))


def is_point_in_area(p: Point, f: Area):
    name = str(p) + "_" + str(f) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return Exists([l, s], And(l == p.l, s == p.s, f.get(l, s)))


def sim_is_point_in_area(p: Point, f: SimArea):
    C = []
    if f.start_l is not None:
        C.append(p.l >= f.start_l)
    if f.start_s is not None:
        C.append(p.s >= f.start_s)
    if f.end_l is not None:
        C.append(p.s <= f.end_l)
    if f.end_s is not None:
        C.append(p.s <= f.end_s)
    return And(*C)


def is_two_lines_cross(f1: Line, f2: Line):
    name = str(f1) + "_" + str(f2) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return Exists([l, s], And(f1.get(l, s), f2.get(l, s)))


def is_two_areas_cross(f1: Area, f2: Area):
    name = str(f1) + "_" + str(f2) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return Exists([l, s], And(f1.get(l, s), f2.get(l, s)))


def sim_is_two_areas_cross(f1: SimArea, f2: SimArea):
    C = []
    if f1.start_l is not None and f2.end_l is not None:
        C.append(f1.start_l > f2.end_l)
    if f1.end_l is not None and f2.start_l is not None:
        C.append(f1.end_l < f2.start_l)
    if f1.start_s is not None and f2.end_s is not None:
        C.append(f1.start_s > f2.end_s)
    if f1.end_s is not None and f2.start_s is not None:
        C.append(f1.end_s < f2.start_s)
    return Not(Or(*C))


def is_line_cross_area(f1: Line, f2: Area):
    name = str(f1) + "_" + str(f2) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return Exists([l, s], And(f1.get(l, s), f2.get(l, s)))


def is_line_in_area(l: Line, a: Area):
    name = str(l) + "_" + str(a) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return ForAll([l, s], Implies(l.get(l, s), a.get(l, s)))


def is_area_in_area(a1: Area, a2: Area):
    name = str(a1) + "_" + str(a2) + get_nounce()
    l, s = Reals(name + "_l" + " " + name + "_s")
    return ForAll([l, s], Implies(a1.get(l, s), a2.get(l, s)))