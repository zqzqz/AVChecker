from z3 import *
from .model import *
from .objects import *
from .config import FRAME_CONFIG, APOLLO_CONFIG


class Scenario:
    def __init__(self, configs={}):
        # name => object
        self.objects = {}
        # array of z3 expressions
        self.constraints = []
        # TODO: config: not leveraged
        self.configs = configs

        # init the ego vehicle (i.e., AV)
        ego = Vehicle("ego")
        ego.add_constraint(And(ego.pos.l == 0, ego.pos.s == 0))
        ego.add_constraint(And(ego.v.l == 0, ego.v.s > 0))
        self.add_object(ego)
        self.add_object(Destination(""))

        # Road and lane
        self.add_object(Lane(""))
        self.lane_left_width = Real("lane_left_width")
        self.lane_right_width = Real("lane_right_width")

        self.lane_boundary = SimArea(-self.lane_left_width, None, self.lane_right_width, None)
        self.add_constraint(And(self.lane_left_width > 0, self.lane_right_width >
                                0, self.lane_left_width + self.lane_right_width >= 3.3))

        self.add_object(Road(""))
        self.road_left_width = Real("road_left_width")
        self.road_right_width = Real("road_right_width")

        self.road_boundary = SimArea(-self.road_left_width, None, self.road_left_width, None)
        self.add_constraint(self.road_left_width > self.lane_left_width)
        self.add_constraint(self.road_right_width > self.lane_right_width)
        self.add_constraint(And(self.road_left_width > 0, self.road_right_width >
                                0, self.road_left_width + self.road_right_width >= 9.9))

    def get_scenario(self):
        self.add_frames()
        return self

    def add_frames(self):
        if not FRAME_CONFIG["enable"]:
            return
        steps = FRAME_CONFIG["steps"]
        interval = FRAME_CONFIG["interval"]
        new_objs = []
        for name in self.objects:
            obj = self.objects[name]
            if isinstance(obj, MobileObject):
                prev_obj = obj
                for step in range(1, steps+1):
                    new_obj = obj.__class__(obj.label, -step*interval)
                    # add constraints on two frames
                    self._add_frame_constraints(prev_obj, new_obj, interval)
                    new_objs.append(new_obj)
                    prev_obj = new_obj
        
        # add all new objects to self.objects
        for obj in new_objs:
            self.add_object(obj)

    def _add_frame_constraints(self, prev_obj, new_obj, interval):
        assert(isinstance(prev_obj, MobileObject) and isinstance(new_obj, MobileObject))
        # TODO: add constraints through self.add_constraints
        predict_area = CenterArea(Point(prev_obj.pos.l - interval * prev_obj.v.l, prev_obj.pos.s - interval * prev_obj.v.s), 
                                  Point(interval * 2, interval * 2))
        velocity_range = 1 * interval
        # pos
        self.add_constraint(is_point_in_area(new_obj.pos, predict_area))
        # v
        self.add_constraint(And(prev_obj.v.l - new_obj.v.l < velocity_range,
                                prev_obj.v.l - new_obj.v.l > -velocity_range,
                                prev_obj.v.s - new_obj.v.s < velocity_range,
                                prev_obj.v.s - new_obj.v.s > -velocity_range))

        if isinstance(prev_obj, Vehicle):
            # arrive time
            # self.add_constraint(prev_obj.arrive_time == new_obj.arrive_time + interval)
            # self.add_constraint((prev_obj.stop_line - new_obj.stop_line) ** 2 == (interval ** 2) * prev_obj.velocity)
            self.add_constraint(prev_obj.stop_line - new_obj.stop_line == interval * prev_obj.velocity)
            # lane
            # TODO: cannot set this!
            self.add_constraint(And(prev_obj.lane.way_id == new_obj.lane.way_id,
                                    prev_obj.lane.turn == new_obj.lane.turn))


    def add_object(self, obj, name=None):
        if name is None:
            self.objects[obj.name] = obj
        else:
            self.objects[name] = obj

    def add_constraint(self, c):
        self.constraints.append(c)

    @property
    def ego_vehicle(self):
        return self.objects["vehicle-ego"]

    def is_ego(self, obj):
        return isinstance(obj, Vehicle) and obj.name == "vehicle-ego"

    def get_object(self, name):
        if name in self.objects:
            return self.objects[name]
        raise Exception("Not found")

    def get_objects(self, classtype):
        results = []
        for name in self.objects:
            if isinstance(self.objects[name], classtype):
                results.append(self.objects[name])
        return results

    def get_variables(self):
        for a in dir(self):
            if not a.startswith("__") and not callable(getattr(self, a)):
                if a not in ["objects", "constraints", "configs"]:
                    yield a, getattr(self, a)
        for name in self.objects:
            obj = self.objects[name]
            yield name, obj
            for n, v in obj.get_variables():
                yield n, v

    def get_constraints(self):
        for c in self.constraints:
            yield c
        for name in self.objects:
            obj = self.objects[name]
            for c in obj.constraints:
                yield c


class CrosswalkScenario(Scenario):
    def __init__(self, configs=None):
        super().__init__(configs)

        self.add_object(Crosswalk(""))
        self.add_object(Pedestrian(""))
        self.add_object(Vehicle("") )


class TrafficLightScenario(Scenario):
    def __init__(self, configs=None):
        super().__init__(configs)

        i = Intersection("")
        self.intersection = i
        self.add_object(i)
        self.add_object(TrafficLight("self"))
        self.add_object(Vehicle("") )
        self.add_object(StopSign(""))
        self.add_object(TrafficLight("main"))


class StopSignScenario(Scenario):
    def __init__(self, configs=None):
        super().__init__(configs)

        self.add_object(Pedestrian(""))
        self.add_object(Vehicle("") )
        self.add_object(StopSign(""))


# currently only support 4-way intersection
class IntersectionScenario(Scenario):
    def __init__(self, configs=None):
        super().__init__(configs)

        i = Intersection("")
        self.intersection = i
        self.add_object(i)
        self.add_object(Vehicle("") )
        self.add_object(Pedestrian(""))
        self.add_constraint(self.ego_vehicle.lane.way_id == 0)
        self.add_constraint(self.ego_vehicle.stop_line == self.intersection.start_s)

        ego = self.ego_vehicle
        vl = self.get_objects(Vehicle)
        for v in vl:
            # restrict the number of ways
            self.add_constraint(And(v.lane.way_id >= 0, v.lane.way_id < 4))
            
            if v != ego:
                # restrict the relation between arrive time and SL location
                self.add_constraint(Or(
                    And(
                        v.stop_line >= 0,
                        Or(
                            And(
                                is_int_val(v.lane.way_id, 1),
                                v.end_l < i.start_l
                            ),
                            And(
                                is_int_val(v.lane.way_id, 2),
                                v.start_s < i.end_s
                            ),
                            And(
                                is_int_val(v.lane.way_id, 1),
                                v.end_l > i.start_l
                            ),
                            And(
                                is_int_val(v.lane.way_id, 0),
                                v.end_s < i.start_s
                            )
                        )
                    ),
                    v.stop_line < 0
                ))
                # restrict the relation between turn direction and SL location
                self.add_constraint(Or(
                    And(
                        Or(
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 1), is_direction(v.lane.turn, "right")),
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 1), is_direction(v.lane.turn, "right")),
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 2), Not(is_direction(v.lane.turn, "left"))),
                            And(is_direction(ego.lane.turn, "right"), is_int_val(
                                v.lane.way_id, 1), Not(is_direction(v.lane.turn, "straight"))),
                            And(is_direction(ego.lane.turn, "right"), is_int_val(
                                v.lane.way_id, 2), Not(is_direction(v.lane.turn, "left"))),
                            And(is_direction(ego.lane.turn, "right"),
                                is_int_val(v.lane.way_id, 3))
                        ),
                        v.pos.l < 0, v.v.l == 0
                    ),
                    And(
                        Or(
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 1), is_direction(v.lane.turn, "left")),
                            And(is_direction(ego.lane.turn, "right"), is_int_val(
                                v.lane.way_id, 1), is_direction(v.lane.turn, "straight")),
                            And(is_direction(ego.lane.turn, "right"), is_int_val(
                                v.lane.way_id, 2), is_direction(v.lane.turn, "left"))
                        ),
                        v.pos.l <= 0, v.v.l >= 0
                    ),
                    And(
                        Or(
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 1), Not(is_direction(v.lane.turn, "right"))),
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 1), is_direction(v.lane.turn, "straight")),
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 2), is_direction(v.lane.turn, "left"))
                        ),
                        v.v.l > 0
                    ),
                    And(
                        Or(
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 2), is_direction(v.lane.turn, "straight")),
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 3), is_direction(v.lane.turn, "straight")),
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 3), Not(is_direction(v.lane.turn, "right")))
                        ),
                        v.v.l < 0
                    ),
                    And(
                        Or(
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 2), is_direction(v.lane.turn, "right")),
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 3), is_direction(v.lane.turn, "straight")),
                            And(is_direction(ego.lane.turn, "straight"), is_int_val(
                                v.lane.way_id, 3), Not(is_direction(v.lane.turn, "right")))
                        ),
                        v.pos.l >= 0, v.v.l <= 0
                    ),
                    And(
                        Or(
                            And(is_direction(ego.lane.turn, "left"), is_int_val(
                                v.lane.way_id, 2), is_direction(v.lane.turn, "left"))
                        ),
                        v.pos.l > 0, v.v.l == 0
                    )
                ))


class CrosswalkIntersectionScenario(IntersectionScenario):
    def __init__(self, configs=None):
        super(CrosswalkIntersectionScenario, self).__init__(configs)
        self.add_object(Crosswalk(""))


class StopSignIntersectionScenario(IntersectionScenario, StopSignScenario):
    def __init__(self, configs=None):
        super(StopSignIntersectionScenario, self).__init__(configs)

        self.stop_duration_sec = 2
        self.stop_timeout_sec = 10


class TrafficLightIntersectionScenario(IntersectionScenario, TrafficLightScenario):
    def __init__(self, configs=None):
        super(TrafficLightIntersectionScenario, self).__init__(configs)


class FullScenario(IntersectionScenario, TrafficLightScenario, StopSignScenario, CrosswalkScenario):
    def __init__(self, configs=None):
        super(FullScenario, self).__init__(configs)
        self.add_object(Vehicle("1"))
        self.add_object(Bicycle(""))
