from .model import *
from .objects import *
from .config import APOLLO_CONFIG
from z3 import *

class APIHandler:
    def __init__(self):
        pass

    def _api_list(self):
        res = []
        for name in dir(self):
            func = getattr(self, name)
            if not name.startswith("_") and callable(func):
                res.append(name)
        return res

    def _call(self, name, args):
        if not name.startswith("_") and name in dir(self):
            return getattr(self, name)(*args)

    @staticmethod
    def inside(a, b):
        if isinstance(a, Point) and isinstance(b, Line):
            return is_point_on_line(a, b)
        elif isinstance(a, Point) and isinstance(b, Area):
            # avoid exists
            return sim_is_point_in_area(a, b)
            # return is_point_in_area(a, b)
        elif isinstance(a, Line) and isinstance(b, Area):
            return is_line_in_area(a, b)
        elif isinstance(a, Area) and isinstance(b, Area):
            return is_area_in_area(a, b)
        else:
            raise Exception("wrong constraint operator {}".format("in"))

    @staticmethod
    def cross(a, b):
        if isinstance(a, Line) and isinstance(b, Line):
            return is_two_lines_cross(a, b)
        elif isinstance(a, Area) and isinstance(b, Area):
            # avoid exists
            return sim_is_two_areas_cross(a, b)
            # return is_two_areas_cross(a, b)
        elif isinstance(a, Line) and isinstance(b, Area):
            return is_line_cross_area(a, b)
        elif isinstance(a, Area) and isinstance(b, Line):
            return is_line_cross_area(b, a)
        else:
            raise Exception("wrong constraint operator {}".format("cross"))

    @staticmethod
    def is_color(traffic_light: TrafficLight, color: str):
        if not (isinstance(traffic_light, TrafficLight) and isinstance(color, str) and color in ["red", "yellow", "green", "unknown"]):
            raise Exception("wrong constraint operator {}".format("is_color"))
        ret = is_color(traffic_light.color, color)
        if ret is None:
            raise Exception("wrong constraint operator {}".format("is_color"))
        return ret

    @staticmethod
    def is_direction(lane: Lane, direction: str):
        if not (isinstance(lane, Lane) and isinstance(direction, str) and direction in ["left", "straight", "right"]):
            raise Exception("wrong constraint operator {}".format("is_direction"))
        ret = is_direction(lane.turn, direction)
        if ret is None:
            raise Exception("wrong constraint operator {}".format("is_direction"))
        return ret

    @staticmethod
    def _st_location(ego: Vehicle, obs: MobileObject, flag=0):
        if flag == 0:
            t = (- ego.size.l - obs.size.l - obs.pos.l) / obs.v.l
        elif flag == 1:
            t = (ego.size.l + obs.size.l - obs.pos.l) / obs.v.l
        else:
            return None
        return t, ego.pos.s + ego.v.s * t, obs.pos.s + obs.v.s * t

    def st_cross(self, ego: Vehicle, obs: MobileObject, start_s=None, end_s=None):
        a, ea, va = self._st_location(ego, obs, 0)
        b, eb, vb = self._st_location(ego, obs, 1)
        res = And(
            Or(
                And(va <= ea + ego.size.s + obs.size.s,
                    va >= ea - ego.size.s - obs.size.s),
                And(vb <= eb + ego.size.s + obs.size.s,
                    vb >= eb - ego.size.s - obs.size.s)
            ),
            Or(
                And(obs.pos.l < 0, obs.v.l > 0),
                And(obs.pos.l > 0, obs.v.l < 0)
            )
        )
        if not start_s is None and not end_s is None:
            res = Or(res, And(And(va + ego.size.s >= start_s, va - ego.size.s <= end_s), And(vb + ego.size.s >= start_s, vb - ego.size.s <= end_s)))
        return res

    def st_above(self, ego: Vehicle, obs: MobileObject, start_s=None, end_s=None):
        a, ea, va = self._st_location(ego, obs, 0)
        b, eb, vb = self._st_location(ego, obs, 1)
        res = And(
            And(
                va <= ea - ego.size.s - obs.size.s,
                vb <= eb - ego.size.s - obs.size.s
            ),
            Or(
                And(obs.pos.l < 0, obs.v.l > 0),
                And(obs.pos.l > 0, obs.v.l < 0)
            )
        )
        if not start_s is None and not end_s is None:
            res = Or(res, And(And(va + ego.size.s >= start_s, va - ego.size.s <= end_s), And(vb + ego.size.s >= start_s, vb - ego.size.s <= end_s)))
        return res

    def st_below(self, ego: Vehicle, obs: MobileObject, start_s=None, end_s=None):
        a, ea, va = self._st_location(ego, obs, 0)
        b, eb, vb = self._st_location(ego, obs, 1)
        res = And(
            And(
                va >= ea + ego.size.s + obs.size.s,
                vb >= eb + ego.size.s + obs.size.s
            ),
            Or(
                And(obs.pos.l < 0, obs.v.l > 0),
                And(obs.pos.l > 0, obs.v.l < 0)
            )
        )
        if not start_s is None and not end_s is None:
            res = Or(res, And(And(va + ego.size.s >= start_s, va - ego.size.s <= end_s), And(vb + ego.size.s >= start_s, vb - ego.size.s <= end_s)))
        return res

    @staticmethod
    def is_approaching(ego: Vehicle, stop_line: Real):
        return And(
            ego.end_s < stop_line - APOLLO_CONFIG["max_valid_stop_distance"],
            ego.arrive_time < 0
        )

    @staticmethod
    def is_waiting(ego: Vehicle, stop_line: Real):
        return And(
            ego.end_s <= stop_line,
            ego.end_s >= stop_line - APOLLO_CONFIG["max_valid_stop_distance"],
            ego.arrive_time >= 0
        )
    
    @staticmethod
    def is_passed(ego: Vehicle, stop_line: Real):
        return And(
            ego.end_s > stop_line,
            ego.arrive_time > 0
        )

    @staticmethod
    def is_int_val(x, v: int):
        return is_int_val(x, v)

    def is_yield(self, ego: Vehicle, obs: MobileObject, start_s=None, end_s=None):
        return self.st_cross(ego, obs, start_s, end_s)
