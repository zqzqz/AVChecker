from .model import *
from z3 import *

def split_obj_name(str_name):
    pass

def assemble_obj_name(json_name):
    pass


class ModelObject:
    def __init__(self, prefix="", label="", suffix=""):
        self.prefix = prefix
        self.label = label
        self.suffix = suffix
        self.name = self.obj_name(self.prefix, self.label, self.suffix)
        self.constraints = []

    def z3_name(self, var_name):
        return "{}.{}".format(self.name, var_name)

    def obj_name(self, prefix="", label="", suffix=""):
        name = prefix
        if name == "":
            name = "{}".format(label)
        elif label != "":
            name = "{}-{}".format(name, label)
        if suffix != "":
            name = "{}[{}]".format(name, suffix)
        return name

    def add_constraint(self, c):
        self.constraints.append(c)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def get_variables(self, obj=None, prefix=None):
        if obj is None:
            obj = self
        if prefix is None:
            prefix = obj.name
        for a in dir(obj):
            attr = getattr(obj, a)
            if not a.startswith("__") and not callable(attr):
                if a not in ["name", "constraints"]:
                    yield "{}.{}".format(prefix, a), attr
            if isinstance(attr, BaseModel) or isinstance(attr, ModelObject):
                for a, attr in self.get_variables(obj=attr, prefix="{}.{}".format(prefix, a)):
                    yield a, attr


class Road(ModelObject):
    def __init__(self, label=""):
        super().__init__("", label)

        self.way_id = Real(self.z3_name("way_id"))
        # TODO: road_id and lane_id are not used
        self.road_id = Real(self.z3_name("road_id"))
        # way id of destination way
        self.turn = Real(self.z3_name("turn"))
        self.left_width = Real(self.z3_name("left_width"))
        self.right_width = Real(self.z3_name("right_width"))
        self.add_constraint(And(self.left_width > 0, self.left_width < 10, self.right_width > 0, self.right_width < 10))


class Lane(ModelObject):
    def __init__(self, label=""):
        super().__init__("", label)

        self.way_id = Real(self.z3_name("way_id"))
        # TODO: road_id and lane_id are not used
        self.road_id = Real(self.z3_name("road_id"))
        self.lane_id = Real(self.z3_name("lane_id"))
        # way id of destination way
        self.turn = Real(self.z3_name("turn"))
        self.left_width = Real(self.z3_name("left_width"))
        self.right_width = Real(self.z3_name("right_width"))
        self.add_constraint(And(self.left_width > 0, self.left_width < 10, self.right_width > 0, self.right_width < 10))


class StaticObject(ModelObject):
    def __init__(self, prefix="", label="", suffix=""):
        super().__init__(prefix, label, suffix)

        self.pos = Point(Real(self.z3_name("pos.l")),
                         Real(self.z3_name("pos.s")))
        self.size = Point(Real(self.z3_name("size.l")),
                          Real(self.z3_name("size.s")))
        self.boundary = CenterArea(self.pos, self.size)

        self.start_l = self.pos.l - self.size.l
        self.end_l = self.pos.l + self.size.l
        self.start_s = self.pos.s - self.size.s
        self.end_s = self.pos.s + self.size.s

        self.add_constraint(And(self.size.l > 0, self.size.s > 0))


class MobileObject(StaticObject):
    def __init__(self, prefix="", label="", suffix=""):
        super().__init__(prefix, label, suffix)

        self.v = Point(Real(self.z3_name("v.l")),
                       Real(self.z3_name("v.s")))
        self.velocity = self.v.l * self.v.l + self.v.s * self.v.s
        self.finite_trajectory = get_trajectory(
            self.pos, self.v, 7, self.z3_name("finite_trajectory"))
        self.trajectory = get_trajectory(
            self.pos, self.v, -1, self.z3_name("trajectory"))


class Pedestrian(MobileObject):
    def __init__(self, label="", suffix=""):
        super().__init__("pedestrian", label, suffix)

        self.add_constraint(And(self.size.l == 0.5, self.size.s == 0.5))
        self.add_constraint(self.velocity <= 5)


class Bicycle(MobileObject):
    def __init__(self, label="", suffix=""):
        super().__init__("bicycle", label, suffix)

        self.add_constraint(And(self.size.l == 0.5, self.size.s == 0.5))
        self.add_constraint(self.velocity <= 5)


class Vehicle(MobileObject):
    def __init__(self, label="", suffix=""):
        super().__init__("vehicle", label, suffix)

        self.add_constraint(And(self.size.l == 2, self.size.s == 2))
        self.add_constraint(self.velocity <= 100)

        self.lane = Lane(self.z3_name("lane"))
        self.arrive_time = Real(self.z3_name("arrive_time"))
        self.stop_line = Real(self.z3_name("stop_line"))
        self.add_constraint(Or(And(self.arrive_time == 0, self.stop_line == 0),
                               And(self.arrive_time > 0, self.stop_line < 0),
                               And(self.arrive_time < 0, self.stop_line > 0)))
        self.length = Real(self.z3_name("length"))
        self.add_constraint(self.length == 2)


class Destination(StaticObject):
    def __init__(self, label=""):
        super().__init__("destination", label)
        self.add_constraint(And(self.size.l == 2, self.size.s == 2))


class Crosswalk(StaticObject):
    def __init__(self, label=""):
        super().__init__("crosswalk", label)

        self.add_constraint(And(self.size.s == 2, self.size.l >= 5))
        self.add_constraint(And(self.pos.s >= 5, self.pos.s < 50))
        self.add_constraint(self.start_l * self.end_l <= 0)


class TrafficLight(StaticObject):
    def __init__(self, label=""):
        super().__init__("traffic_light", label)

        # color: =3 green; =2 yellow; =1 red =0 unknown;
        self.color = Real(self.z3_name("color"))
        self.add_constraint(And(self.size.s >= 10, self.size.l >= 5))
        self.add_constraint(And(self.pos.s >= -50, self.pos.s < 50))
        self.add_constraint(And(self.color >= 0, self.color <= 3))
        self.add_constraint(self.start_l * self.end_l <= 0)


class StopSign(StaticObject):
    def __init__(self, label=""):
        super().__init__("stop_sign", label)

        self.add_constraint(And(self.size.s >= 10, self.size.l >= 5))
        self.add_constraint(And(self.pos.s >= -50, self.pos.s < 50))
        self.add_constraint(self.start_l * self.end_l <= 0)


class YieldSign(StaticObject):
    def __init__(self, label=""):
        super().__init__("yield_sign", label)

        self.add_constraint(self.start_l * self.end_l <= 0)


class Intersection(StaticObject):
    def __init__(self, label=""):
        super().__init__("intersection", label)

        self.add_constraint(And(self.size.s >= 10, self.size.l >= 5))
        self.add_constraint(And(self.pos.s >= -50, self.pos.s < 50))
        self.add_constraint(self.start_l * self.end_l <= 0)
