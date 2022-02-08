from z3 import *
from .model import *
from .objects import *
from .scenarios import *
from .api import *
from .config import APOLLO_CONFIG
from .sally import generate_sally_input, execute_sally
from .util import count_operator, get_ast_depth

import logging
import re
import os


class VariableController:
    def __init__(self, action_mode=0, scenario_type="", enable_model_checker=False, sally_output=None):
        # space -> name -> value
        # space <= [code, model, user]
        # name <= string
        self.var_map = {
            "code": {},
            "model": {},
            "user": {}
        }
        # space -> list of constraints
        # space <= [code, model, user]
        # constraint <= boolean expression
        self.constraints = {
            "code": [],
            "model": [],
            "user": []
        }
        
        self.scenario = None
        self.action_mode = action_mode
        self.scenario_type = scenario_type
        self.api = APIHandler()
        self.enable_model_checker = enable_model_checker
        self.sally_output = sally_output
        # init
        self.build()

    @property
    def vars(self):
        res = {}
        res.update(self.var_map["code"])
        res.update(self.var_map["model"])
        res.update(self.var_map["user"])
        return res

    def get_var(self, space, name):
        if space != None:
            if isinstance(self.var_map, dict) and space in self.var_map and name in self.var_map[space]:
                return self.var_map[space][name]
            else:
                raise Exception("{} not found".format(name))
        else:
            if not isinstance(self.var_map, dict):
                raise Exception("{} not found".format(name))
            for s in ["code", "model", "user"]:
                if s in self.var_map and name in self.var_map[s]:
                    return self.var_map[s][name]
            raise Exception("{} not found".format(name))

    def is_space(self, space):
        return isinstance(self.var_map, dict) and space in self.var_map and isinstance(self.constraints, dict) and space in self.constraints

    def build(self):
        self._build_model_space()
        self._build_code_space()
        self._build_user_space()

    def build_var(self, space, value, name=None):
        if not self.is_space(space):
            raise Exception("Space not found")
        # TODO: check value type here
        if name is None or name == "":
            name = str(value)
        if name in self.var_map[space]:
            logging.warning(
                "Variable {} of space {} already exists. Overwritting.".format(name, space))
        self.var_map[space][name] = value

    def add_constraint(self, space, constraint):
        if not self.is_space(space):
            raise Exception("Space not found")
        self.constraints[space].append(constraint)

    def solve(self):
        # number of operators
        logging.info("Number of operators - model: {} code: {} user: {}".format(count_operator(And(*self.constraints["model"])),
                                                                                count_operator(Or(*self.constraints["code"])),
                                                                                count_operator(Or(*self.constraints["user"]))))
        logging.info("Depth of ast - model: {} code: {} user: {}".format(get_ast_depth(And(*self.constraints["model"])),
                                                                         get_ast_depth(Or(*self.constraints["code"])),
                                                                         get_ast_depth(Or(*self.constraints["user"]))))
        if self.enable_model_checker:
            return self.solve_model_checker()
        else:
            return self.solve_smt_solver()

    def solve_model_checker(self):
        generate_sally_input(self)
        return execute_sally(self)

    def solve_smt_solver(self):
        s = Solver()

        if self.action_mode == 0:
            query = And(Not(Or(*self.constraints["code"])), And(*self.constraints["model"]), Or(*self.constraints["user"]))
        elif self.action_mode == 1:
            query = And(Or(*self.constraints["code"]), And(*self.constraints["model"]), Or(*self.constraints["user"]))
        else:
            raise Exception("Wrong action mode")

        # number of operators
        logging.info("Number of operators total: {}".format(count_operator(query)))
        logging.info("Depth of ast total: {}".format(get_ast_depth(query)))

        s.add(query)
        result = s.check()
        logging.info(result)

        data = {"common": {}}
        if result == sat:
            model = s.model()
            logging.info("user policy - code policy > 0, violation found")
            logging.info(model)
            # write to data
            for name in model:
                written = False
                if isinstance(model[name], BoolRef):
                    _value = is_true(model[name])
                elif is_int_value(model[name]):
                    _value = model[name].as_long()
                elif is_rational_value(model[name]):
                    _value = float(model[name].numerator_as_long()) / \
                        float(model[name].denominator_as_long())
                else:
                    continue
                props = str(name).split(".")
                if len(props) > 1:
                    full_name = props[0].split('-')
                    if len(full_name) == 1:
                        _label, _id = full_name[0], ""
                    elif len(full_name) == 2:
                        _label, _id = full_name[0], full_name[1]
                    else:
                        _label = None
                    if not _label is None:
                        if _label not in data:
                            data[_label] = {}
                        if _id not in data[_label]:
                            data[_label][_id] = {}
                        data[_label][_id][".".join(props[1:])] = _value
                        written = True
                if not written:
                    data["common"][str(name)] = _value
        else:
            logging.info("no violation found")
        return data

    def _build_model_space(self):
        # configure this
        if self.scenario_type == "crosswalk":
            self.scenario = CrosswalkScenario()
        elif self.scenario_type == "crosswalk_intersection":
            self.scenario = CrosswalkIntersectionScenario()
        elif self.scenario_type in ["intersection", "bare_intersection"]:
            self.scenario = IntersectionScenario()
        elif self.scenario_type == "traffic_light":
            self.scenario = TrafficLightIntersectionScenario()
        elif self.scenario_type == ["traffic_light_protected", "traffic_light_unprotected_left_turn", "traffic_light_unprotected_left_turn"]:
            self.scenario = TrafficLightIntersectionScenario()
        elif self.scenario_type == "stop_sign":
            self.scenario = StopSignIntersectionScenario()
        else:
            self.scenario = FullScenario()

        self.scenario = self.scenario.get_scenario()
        
        for name, var in self.scenario.get_variables():
            self.build_var("model", var, name)
        for c in self.scenario.get_constraints():
            self.add_constraint("model", c)
  
    def _build_code_space(self):
        # TODO: provide user interface for the variable mapping

        v = self.scenario.ego_vehicle
        d = self.scenario.get_objects(Destination)[0]

        # basic variables
        self.build_var("code", v.end_s, "apollo::planning::ReferenceLineInfo.AdcSlBoundary.end_s")
        self.build_var("code", v.start_s, "apollo::planning::ReferenceLineInfo.AdcSlBoundary.start_s")
        if self.sally_output:
            self.build_var("model", Int("violation_counter"))
        # config
        for c in APOLLO_CONFIG:
            self.build_var("model", APOLLO_CONFIG[c], c)
        # destination
        self.build_var("code", And(d.pos.s - v.pos.s < 10, d.pos.s - v.pos.s > -10, d.pos.l - v.pos.l < 10, d.pos.l - v.pos.l > 10), "is_near_destination")
        self.build_var("code", False, "has_passed_destination")
        
        # keep_clear
        if self.scenario_type != "crosswalk":
            i = self.scenario.get_object("intersection")
            e = self.scenario.get_object("vehicle")
            p = self.scenario.get_object("pedestrian")

            self.build_var("code", sim_is_two_areas_cross(v.boundary, i.boundary), "apollo::planning::STBoundary.IsEmpty")
            self.build_var("code", 1, "apollo::planning::STBoundary.max_s")
            self.build_var("code", 1, "apollo::planning::STBoundary.max_t")
            self.build_var("code", 1, "apollo::planning::STBoundary.min_t")
            self.build_var("code", 0, "apollo::common::SpeedPoint.t")
            self.build_var("code", False, "apollo::planning::Obstacle.HasLongitudinalDecision")
            self.build_var("code", False, "apollo::planning::Obstacle.IsVirtual")
            self.build_var("code", False, "apollo::planning::SpeedDecider.CheckStopForPedestrian")
            self.build_var("code", 0, "FLAGS_use_st_drivable_boundary")
            self.build_var("code", 5, "apollo::planning::STBoundary.boundary_type")
            self.build_var("code", True, "_ZSteqIcEN9__gnu_cxx11__enable_ifIXsr9__is_charIT_EE7__valueEbE6__typeERKSbIS2_St11char_traitsIS2_ESaIS2_EESA_")
            self.build_var("code", And(is_line_cross_area(v.trajectory, e.boundary), v.v.s > e.v.s), "apollo::planning::Obstacle.IsBlockingObstacle")
            self.build_var("code", e.start_s, "apollo::planning::Obstacle.PerceptionSLBoundary.start_s")
            self.build_var("code", i.end_s, "apollo::planning::Obstacle.PerceptionSLBoundary.end_s")
            self.build_var("code", e.size.s * 2, "apollo::common::VehicleConfig.GetConfig.vehicle_param.length")
            self.build_var("code", False, "apollo::planning::SpeedDecider.CheckIsFollow")
            self.build_var("code", False, "apollo::planning::SpeedDecider.IsFollowTooClose")
            self.build_var("code", sim_is_two_areas_cross(e.boundary, self.scenario.lane_boundary), "apollo::planning::ReferenceLine.IsOnLane")

        # traffic_rule/crosswalk
        if self.scenario_type in ["crosswalk", "crosswalk_intersection"]:
            p = self.scenario.get_object("pedestrian")
            c = self.scenario.get_object("crosswalk")

            self.build_var("code", c.end_s, "struct.apollo::hdmap::PathOverlap.end_s")
            self.build_var("code", APOLLO_CONFIG["crosswalk.min_pass_s_distance"], "apollo::planning::TrafficRule.config_.crosswalk.min_pass_s_distance")
            self.build_var("code", p.pos.l * p.pos.l, "min")
            self.build_var("code", APOLLO_CONFIG["crosswalk.stop_loose_l_distance"]**2, "apollo::planning::TrafficRule.config_.crosswalk.stop_loose_l_distance")
            self.build_var("code", APOLLO_CONFIG["crosswalk.stop_strict_l_distance"]**2, "apollo::planning::TrafficRule.config_.crosswalk.stop_strict_l_distance")
            self.build_var("code", Not(self.api.st_cross(v, p)), "apollo::planning::Obstacle.reference_line_st_boundary.IsEmpty")
            # TODO: decelaration limit
            self.build_var("code", v.velocity / 2 / (c.start_s - v.end_s), "GetADCStopDeceleration")
            # self.build_var("code", 0, "GetADCStopDeceleration")
            self.build_var("code", APOLLO_CONFIG["max_stop_deceleration"], "apollo::planning::TrafficRule.config_.crosswalk.max_stop_deceleration")
            self.build_var("code", True, "apollo::planning::Crosswalk.FindCrosswalks")
            self.build_var("code", sim_is_two_areas_cross(p.boundary, self.scenario.road_boundary), "apollo::planning::ReferenceLine.IsOnRoad")
            self.build_var("code", p.pos.s, "apollo::common::SLPoint.s")
            self.build_var("code", c.start_s, "struct.apollo::hdmap::PathOverlap.start_s132")
            self.build_var("code", 1, "apollo::perception::PerceptionObstacle.type")
            self.build_var("code", -p.pos.l * p.v.l, "apollo::common::math::Vec2d.InnerProd")
            self.build_var("code", p.velocity, "apollo::perception::PerceptionObstacle.velocity.x.hypot")
            self.build_var("code", sim_is_two_areas_cross(p.boundary, self.scenario.lane_boundary), "apollo::planning::ReferenceLine.IsOnLane")
            # TODO: wait time (ignored)
            self.build_var("code", 0, "NowInSeconds")
            self.build_var("code", APOLLO_CONFIG["crosswalk.stop_timeout"], "apollo::planning::TrafficRule.config_.crosswalk.stop_timeout")
            # A sample of API
            self.build_var("code", lambda x, y: sim_is_point_in_area(y, x), "apollo::common::math::Polygon2d.IsPointIn")
            self.build_var("code", c.boundary, "apollo::common::math::Polygon2d")
            self.build_var("code", p.pos, "apollo::common::math::Vec2d")

            # # autoware
            # self.build_var("code", True, "vs_info.getSetPose")
            # self.build_var("code", True, "vs_path.getSetPath")
            # self.build_var("code", 1, "vs_path.getPrevWaypointsSize")
            # self.build_var("code", False, "points.empty")
            # self.build_var("code", 0, "vs_info.getDetectionResultByOtherNodes")
            # self.build_var("code", 0, "closest_waypoint")
            # self.build_var("code", 0, "vs_info.getDecelerationRange")
            # self.build_var("code", c.start_s, "crosswalk.getDetectionWaypoint")
            # self.build_var("code", 60, "STOP_SEARCH_DISTANCE")
            # self.build_var("code", sim_is_two_areas_cross(p.boundary, c.boundary), "crossWalkDetection")
            # self.build_var("code", Or(sim_is_two_areas_cross(p.boundary, c.boundary), And(p.pos.l * p.pos.l < 4, p.pos.s < 60)), "stop_obstacle_waypoint")
            # self.build_var("code", And(p.pos.l * p.pos.l >= 4, p.pos.l * p.pos.l < 16, p.pos.s < 60), "decelerate_obstacle_waypoint")
            # self.build_var("code", 1, "getPlaneDistance")


        # traffic_rule/traffic_light
        if self.scenario_type in ["traffic_light", "traffic_light_protected", "traffic_light_unprotected_left_turn", "traffic_light_unprotected_right_turn"]:
            t = self.scenario.get_object("traffic_light-main")
            i = self.scenario.get_object("intersection")

            # manually added
            self.build_var("model", Bool("overlap_finished"), "overlap_finished")

            self.build_var("code", True, "apollo::planning::TrafficRule.config_.traffic_light.enabled")
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s56")
            self.build_var("code", i.end_s, "struct.apollo::hdmap::PathOverlap.end_s")
            self.build_var("code", t.color, "apollo::perception::TrafficLight.color")
            self.build_var("code", APOLLO_CONFIG["max_stop_deceleration"], "apollo::planning::TrafficRule.config_.traffic_light.max_stop_deceleration")
            self.build_var("code", v.velocity / 2 / (i.start_s - v.end_s), "GetADCStopDeceleration")
            # some checks cannot be interpreted
            self.build_var("code", 0, "llvm.fabs.f64")

        if self.scenario_type == "traffic_light_protected":
            t = self.scenario.get_object("traffic_light-self")
            i = self.scenario.get_object("intersection")

            self.build_var("model", Int("scenario_stage"), "scenario_stage")

            self.build_var("code", i.end_s + v.size.s > 0, "GetOverlapOnReferenceLine")
            self.build_var("code", i.end_s + v.size.s > 0, "apollo::planning::ReferenceLineInfo.GetOverlapOnReferenceLine")
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s24")
            self.build_var("code", APOLLO_CONFIG["max_valid_stop_distance"], "apollo::planning::scenario::traffic_light::TrafficLightProtectedStageApproach.scenario_config_.max_valid_stop_distance")

        if self.scenario_type == "traffic_light_unprotected_left_turn":
            t = self.scenario.get_object("traffic_light-self")
            i = self.scenario.get_object("intersection")

            self.build_var("model", Int("scenario_stage"), "scenario_stage")

            self.build_var("code", i.end_s + v.size.s > 0, "GetOverlapOnReferenceLine")
            self.build_var("code", True, "apollo::planning::scenario::Stage.config_.enabled")
            self.build_var("code", i.end_s + v.size.s > 0, "apollo::planning::ReferenceLineInfo.GetOverlapOnReferenceLine")
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s32")
            self.build_var("code", i.end_s, "struct.apollo::hdmap::PathOverlap.end_s60")
            self.build_var("code", APOLLO_CONFIG["max_valid_stop_distance"], "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedLeftTurnStageApproach.scenario_config_.max_valid_stop_distance")

        if self.scenario_type == "traffic_light_unprotected_right_turn":
            t = self.scenario.get_object("traffic_light-self")
            i = self.scenario.get_object("intersection")

            self.build_var("model", Int("scenario_stage"), "scenario_stage")

            self.build_var("code", i.end_s + v.size.s > 0, "GetOverlapOnReferenceLine")
            self.build_var("code", i.end_s + v.size.s > 0, "apollo::planning::ReferenceLineInfo.GetOverlapOnReferenceLine")
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s24")
            self.build_var("code", APOLLO_CONFIG["max_valid_stop_distance"], "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.scenario_config_.max_valid_stop_distance")
            self.build_var("code", False, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.CheckTrafficLightNoRightTurnOnRed")
            self.build_var("code", APOLLO_CONFIG["min_pass_s_distance"], "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.scenario_config_.min_pass_s_distance")
            self.build_var("code", True, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.scenario_config_.enable_right_turn_on_red")
            self.build_var("code", 0, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.GetContext.stop_start_time")
            self.build_var("code", v.arrive_time, "NowInSeconds")
            self.build_var("code", 0, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.GetContext.stop_start_time65")
            self.build_var("code", APOLLO_CONFIG["unprotected_right_turn.stop_duration_sec"], "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.scenario_config_.red_light_right_turn_stop_duration_sec")

        if self.scenario_type == "bare_intersection":
            i = self.scenario.get_object("intersection")

            self.build_var("model", Int("scenario_stage"), "scenario_stage")

            self.build_var("code", i.end_s + v.size.s > 0, "GetOverlapOnReferenceLine")
            self.build_var("code", i.end_s + v.size.s > 0, "apollo::planning::ReferenceLineInfo.GetOverlapOnReferenceLine")
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s")
            self.build_var("code", False, "apollo::planning::Obstacle.IsVirtual")
            self.build_var("code", False, "apollo::planning::Obstacle.IsStatic")
            self.build_var("code", True, "apollo::planning::scenario::bare_intersection::BareIntersectionUnprotectedStageApproach.scenario_config_.enable_explicit_stop")
            # TODO: all_far_away
            self.build_var("code", 4, "apollo::planning::Obstacle.reference_line_st_boundary.min_t")
            self.build_var("code", 0, "apollo::planning::STPoint.s")
            self.build_var("code", 4, "apollo::planning::Obstacle.reference_line_st_boundary.min_s")
            self.build_var("code", 0, "var")

        if self.scenario_type == "stop_sign":
            s = self.scenario.get_object("stop_sign")
            i = self.scenario.get_object("intersection")
            e = self.scenario.get_object("vehicle")
            
            self.build_var("model", Int("scenario_stage"), "scenario_stage")
            self.build_var("model", Bool("overlap_finished"), "overlap_finished")
            self.build_var("model", Bool("watch_vehicles.empty"), "watch_vehicles.empty")

            self.build_var("code", i.end_s + v.size.s > 0, "GetOverlapOnReferenceLine")
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s")
            # duplication
            self.build_var("code", i.start_s, "struct.apollo::hdmap::PathOverlap.start_s18")
            self.build_var("code", v.velocity, "Instance.linear_velocity")
            self.build_var("code", APOLLO_CONFIG["max_abs_speed_when_stopped"], "GetConfig.vehicle_param.max_abs_speed_when_stopped")
            self.build_var("code", APOLLO_CONFIG["max_valid_stop_distance"], "apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.scenario_config_.max_valid_stop_distance")
            self.build_var("code", 1, "apollo::perception::PerceptionObstacle.type")
            self.build_var("code", 0, "GetNearestLaneWithHeading")
            self.build_var("code", True, "GetObjectOverlapInfo")

            self.build_var("code", e.stop_line, "apollo::hdmap::ObjectOverlapInfo.lane_overlap_info.start_s")
            self.build_var("code", e.size.s * 2, "apollo::perception::PerceptionObstacle.length")
            self.build_var("code", 5, "apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.scenario_config_.watch_vehicle_max_valid_stop_distance")

            self.build_var("code", True, "FindPerceptionObstacle")
            self.build_var("code", z3_abs(e.stop_line), "DistanceXY")

            self.build_var("code", True, "apollo::planning::scenario::Stage.config_.enabled")
            self.build_var("code", True, "apollo::planning::TrafficRule.config_.stop_sign.enabled")
            self.build_var("code", 1, "apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.scenario_config_.stop_duration_sec")
            # -- skip wait timeout
            self.build_var("code", 0, "NowInSeconds")
            self.build_var("code", 1, "apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.GetContext.stop_start_time")
            # --
            self.build_var("code", i.end_s, "struct.apollo::hdmap::PathOverlap.end_s")
            self.build_var("code", True, "FindTask")
            self.build_var("code", 100, "apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.scenario_config_.stop_timeout_sec")
            self.build_var("code", True, "__dynamic_cast")
            self.build_var("code", APOLLO_CONFIG["creep_distance"], "FindCreepDistance")
            self.build_var("code", 2, "apollo::perception::LightStatus.max_valid_stop_distance")

        if self.scenario_type in ["traffic_light_unprotected_left_turn", "traffic_light_unprotected_right_turn", "stop_sign"]:
            i = self.scenario.get_object("intersection")
            e = self.scenario.get_object("vehicle")
            a, ea, va = self.api._st_location(v, e, 0)
            b, eb, vb = self.api._st_location(v, e, 1)

            # creep
            self.build_var("code", True, "apollo::planning::scenario::Stage.config_.enabled")
            self.build_var("code", True, "apollo::planning::scenario::Stage.FindTask")
            self.build_var("code", True, "__dynamic_cast")
            self.build_var("code", APOLLO_CONFIG["creep_distance"], "apollo::planning::CreepDecider.FindCreepDistance")
            self.build_var("code", APOLLO_CONFIG["max_valid_stop_distance"], "apollo::perception::LightStatus.max_valid_stop_distance")
            self.build_var("code", v.end_s, "struct.apollo::hdmap::PathOverlap.end_s60")
            self.build_var("code", APOLLO_CONFIG["creep_distance"], "apollo::planning::CreepDecider.7505.FindCreepDistance")
            self.build_var("code", 0, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.GetContext.creep_start_time")
            self.build_var("code", Real("apollo::planning::scenario::traffic_light::TrafficLightUnprotectedRightTurnStageCreep.scenario_config_.creep_timeout_sec"))
            self.build_var("code", False, "apollo::planning::Obstacle.IsStatic")
            self.build_var("code", z3_min(a,b), "apollo::perception::LightStatus.min_boundary_t")
            self.build_var("code", z3_min(a,b), "apollo::planning::Obstacle.reference_line_st_boundary.min_t")
            self.build_var("code", z3_min(ea, eb), "apollo::planning::STPoint.s")
            self.build_var("code", 0, "apollo::perception::LightStatus.ignore_max_st_min_t")
            self.build_var("code", z3_min(ea, eb), "apollo::planning::Obstacle.reference_line_st_boundary.min_s")
            self.build_var("code", 0, "apollo::perception::LightStatus.ignore_min_st_min_s")
            self.build_var("code", 0, "apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.GetContext.creep_start_time")
            self.build_var("code", Real("apollo::planning::scenario::stop_sign::StopSignUnprotectedStageCreep.scenario_config_.creep_timeout_sec"))
            self.build_var("code", v.arrive_time, "NowInSeconds")
            self.build_var("code", 0, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedLeftTurnStageApproach.GetContext.creep_start_time")
            self.build_var("code", 10, "apollo::planning::scenario::traffic_light::TrafficLightUnprotectedLeftTurnStageApproach.scenario_config_.creep_timeout_sec")

    def _build_user_space(self):
        pass

    def post_build(self):
        if self.scenario_type == "traffic_light_protected":
            self.build_var("model", And(
                Not(And(
                    Not(self.get_var("code", "scenarios-traffic_light-protected-entry"))
                )),
                Not(And(
                    self.get_var("code", "scenarios-traffic_light-protected-entry"), 
                    Not(self.get_var("code", "scenarios-traffic_light-protected-approach-finish_scenario")),
                    Not(self.get_var("code", "scenarios-traffic_light-protected-approach-finish_stage"))
                )),
                Or(
                    And(
                        self.get_var("code", "scenarios-traffic_light-protected-approach-finish_stage"),
                        Not(self.get_var("code", "scenarios-traffic_light-protected-cruise-finish_scenario"))
                    ),
                    And(
                        self.get_var("code", "scenarios-traffic_light-protected-cruise-finish_scenario")
                    )
                )
            ), "overlap_finished")

        elif self.scenario_type == "traffic_light_unprotected_left_turn":
            self.build_var("model", And(
                Not(And(
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-entry"))
                )),
                Not(And(
                    self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-entry"), 
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-approach-finish_scenario")),
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-approach-finish_stage"))
                )),
                And(
                    self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-approach-finish_stage"),
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-creep-finish_scenario")),
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-creep-finish_stage"))
                ),
                And(
                    self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-creep-finish_stage"),
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-cruise-finish_scenario"))
                ),
                And(
                    self.get_var("code", "scenarios-traffic_light-unprotected_left_turn-cruise-finish_scenario")
                )
            ), "overlap_finished")

        elif self.scenario_type == "traffic_light_unprotected_right_turn":
            pass
            self.build_var("model", And(
                Not(And(
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-entry"))
                )),
                Not(And(
                    self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-entry"), 
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-stop-finish_scenario")),
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-stop-finish_stage")),
                    Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-stop-finish_stage"))
                )),
                Or(
                    And(
                        And(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-stop-finish_stage"), self.get_var("model", "vehicle-ego.v.s") < 5),
                        Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-creep-finish_scenario")),
                        Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-creep-finish_stage"))
                    ),
                    And(
                        self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-creep-finish_stage"),
                        Not(self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-cruise-finish_scenario"))
                    ),
                    And(
                        self.get_var("code", "scenarios-traffic_light-unprotected_right_turn-cruise-finish_scenario")
                    )
                )
            ), "overlap_finished")

        elif self.scenario_type == "bare_intersection":
            self.build_var("model", And(
                Not(And(
                    Not(self.get_var("code", "scenarios-bare_intersection-unprotected-entry"))
                )),
                Not(And(
                    self.get_var("code", "scenarios-bare_intersection-unprotected-entry"), 
                    Not(self.get_var("code", "scenarios-bare_intersection-unprotected-approach-finish_scenario")),
                    Not(self.get_var("code", "scenarios-bare_intersection-unprotected-approach-finish_stage"))
                )),
                Or(
                    And(
                        self.get_var("code", "scenarios-bare_intersection-unprotected-approach-finish_stage"),
                        Not(self.get_var("code", "scenarios-bare_intersection-unprotected-cruise-finish_scenario"))
                    ),
                    And(
                        self.get_var("code", "scenarios-bare_intersection-unprotected-cruise-finish_scenario")
                    )
                )
            ), "overlap_finished")

        elif self.scenario_type == "stop_sign":
            self.build_var("model", And(
                Not(And(
                    Not(self.get_var("code", "scenarios-stop_sign-unprotected-entry"))
                )),
                Not(And(
                    self.get_var("code", "scenarios-stop_sign-unprotected-entry"), 
                    Not(self.get_var("code", "scenarios-stop_sign-unprotected-pre_stop-finish_scenario")),
                    Not(self.get_var("code", "scenarios-stop_sign-unprotected-pre_stop-finish_stage"))
                )),
                Not(And(
                    self.get_var("code", "scenarios-stop_sign-unprotected-pre_stop-finish_stage"),
                    Not(self.get_var("code", "scenarios-stop_sign-unprotected-stop-finish_scenario")),
                    Not(self.get_var("code", "scenarios-stop_sign-unprotected-stop-finish_stage"))
                )),
                Or(
                    And(
                        self.get_var("code", "scenarios-stop_sign-unprotected-stop-finish_stage"),
                        Not(self.get_var("code", "scenarios-stop_sign-unprotected-creep-finish_scenario")),
                        Not(self.get_var("code", "scenarios-stop_sign-unprotected-creep-finish_stage"))
                    ),
                    And(
                        self.get_var("code", "scenarios-stop_sign-unprotected-creep-finish_stage"),
                        Not(self.get_var("code", "scenarios-stop_sign-unprotected-cruise-finish_scenario"))
                    ),
                    And(
                        self.get_var("code", "scenarios-stop_sign-unprotected-cruise-finish_scenario")
                    )
                )
            ), "overlap_finished")

            self.build_var("model", And(
                self.get_var("code", "scenarios-stop_sign-unprotected-pre_stop-add_watch_vehicle"),
                Not(
                    self.get_var("code", "scenarios-stop_sign-unprotected-stop-remove_watch_vehicle")
                )
            ), "watch_vehicles.empty")
