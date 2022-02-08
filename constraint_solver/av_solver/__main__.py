import sys
import os
import re
import logging
import argparse
from .variable_controller import VariableController
from .constraint_tree import Node, ConstraintTree
from .util import get_ast_depth, count_operator
import json
import os
import time
from z3 import *

logging.basicConfig(level=logging.INFO)
workspace = os.path.abspath(os.path.dirname(__file__))

def main():
    parser = argparse.ArgumentParser(description='Solve constraints of decision making in Apollo')
    parser.add_argument('--action', type=int, default=0, help="Do action or do not action {0, 1}")
    parser.add_argument('--case', type=str, help="name of the case to test: accept spec_{case} and code_{case} as inputs and output case_{case}.json", default="")
    parser.add_argument('--datadir', type=str, help="directory containing specifications, code constraints and sample cases.", default=os.path.join(workspace, "../data"))
    parser.add_argument('--scenario', type=str, default="crosswalk", help="Scenario type {crosswalk, intersection, traffic_light, stop_sign}")
    parser.add_argument("--stateful", action='store_const', default=False, const=True, help="Enable model checker to handle stateful rules")
    # deprecated
    parser.add_argument('--code', type=str, help="filename containing policy extracted from Apollo code (split by comma)")
    parser.add_argument('--spec', type=str, help="filename containing user's policy")
    parser.add_argument('--output', type=str, help="filename of output test case")
    parser.add_argument('--sally', type=str, help="filename of output sally file")

    args = parser.parse_args()
    spec_input = args.spec if args.spec else os.path.join(args.datadir, "spec", "spec_{}".format(args.case))
    code_input = args.code if args.code else os.path.join(args.datadir, "code", "code_{}".format(args.case))
    case_output = args.output if args.output else os.path.join(args.datadir, "case", "case_{}".format(args.case))
    sally_output = args.sally if args.sally else os.path.join(args.datadir, "sally", "sally_{}".format(args.case))
    preload_input = os.path.join(args.datadir, "preload")

    # !!! Use model checker instead
    var_control = VariableController(action_mode=args.action, scenario_type=args.scenario, enable_model_checker=args.stateful, sally_output=sally_output)

    start = time.time()

    # preload code constraints
    if args.scenario == "crosswalk":
        preload_list = ["traffic_rules-crosswalk-stop", "stop-destination"]
    elif args.scenario == "traffic_light":
        preload_list = ["traffic_rules-traffic_light-stop", "stop-destination", "stop-keep_clear"]
    elif args.scenario == "crosswalk_intersection":
        preload_list = ["traffic_rules-crosswalk-stop", "stop-destination", "stop-keep_clear"]
    elif args.scenario == "stop_sign":
        preload_list = ["scenarios-stop_sign-unprotected-entry",
                        "scenarios-stop_sign-unprotected-creep-finish_scenario",
                        "scenarios-stop_sign-unprotected-creep-finish_stage",
                        "scenarios-stop_sign-unprotected-cruise-finish_scenario",
                        "scenarios-stop_sign-unprotected-pre_stop-add_watch_vehicle",
                        "scenarios-stop_sign-unprotected-pre_stop-finish_scenario",
                        "scenarios-stop_sign-unprotected-pre_stop-finish_stage",
                        "scenarios-stop_sign-unprotected-stop-finish_scenario",
                        "scenarios-stop_sign-unprotected-stop-finish_stage",
                        "scenarios-stop_sign-unprotected-stop-remove_watch_vehicle",
                        "traffic_rules-stop_sign-stop", "stop-destination", "stop-keep_clear"]
    elif args.scenario == "bare_intersection":
        preload_list = ["scenarios-bare_intersection-unprotected-entry",
                        "scenarios-bare_intersection-unprotected-approach-finish_stage",
                        "scenarios-bare_intersection-unprotected-approach-finish_scenario",
                        "scenarios-bare_intersection-unprotected-approach-stop",
                        "scenarios-bare_intersection-unprotected-cruise-finish_scenario",
                        "stop-destination", "stop-keep_clear"]
    elif args.scenario == "traffic_light_protected":
        preload_list = ["scenarios-traffic_light-protected-entry",
                        "scenarios-traffic_light-protected-approach-finish_stage",
                        "scenarios-traffic_light-protected-approach-finish_scenario",
                        "scenarios-traffic_light-protected-cruise-finish_scenario",
                        "traffic_rules-traffic_light-stop", "stop-destination", "stop-keep_clear"]
    elif args.scenario == "traffic_light_unprotected_left_turn":
        preload_list = ["scenarios-traffic_light-unprotected_left_turn-entry",
                        "scenarios-traffic_light-unprotected_left_turn-approach-finish_stage",
                        "scenarios-traffic_light-unprotected_left_turn-approach-finish_scenario",
                        "scenarios-traffic_light-unprotected_left_turn-creep-finish_stage",
                        "scenarios-traffic_light-unprotected_left_turn-creep-finish_scenario",
                        "scenarios-traffic_light-unprotected_left_turn-cruise-finish_scenario",
                        "traffic_rules-traffic_light-stop", "stop-destination", "stop-keep_clear"]
    elif args.scenario == "traffic_light_unprotected_right_turn":
        preload_list = ["scenarios-traffic_light-unprotected_right_turn-entry",
                        "scenarios-traffic_light-unprotected_right_turn-stop-finish_stage",
                        "scenarios-traffic_light-unprotected_right_turn-stop-finish_scenario",
                        "scenarios-traffic_light-unprotected_right_turn-creep-finish_stage",
                        "scenarios-traffic_light-unprotected_right_turn-creep-finish_scenario",
                        "scenarios-traffic_light-unprotected_right_turn-cruise-finish_scenario",
                        "traffic_rules-traffic_light-stop", "stop-destination", "stop-keep_clear"]

    constraint_strs = []

    post = False
    for filename in preload_list:
        if not filename.startswith("scenarios") and not post:
            var_control.post_build()
            post = True
        # experiment only
        if args.case.endswith("case4") and filename == "scenarios-stop_sign-unprotected-pre_stop-add_watch_vehicle":
            file_path = os.path.join(preload_input, "scenarios-stop_sign-unprotected-pre_stop-add_watch_vehicle-case4")
        elif args.case.endswith("case1") and filename == "scenarios-bare_intersection-unprotected-approach-finish_stage":
            file_path = os.path.join(preload_input, "scenarios-bare_intersection-unprotected-approach-finish_stage-case1")
        elif args.case.endswith("case5") and filename == "traffic_rules-crosswalk-stop":
            file_path = os.path.join(preload_input, "traffic_rules-crosswalk-stop-case5")
        else:
            file_path = os.path.join(preload_input, filename)
        if not os.path.isfile(file_path):
            continue
        with open(file_path, "r") as f:
            constraint_str = f.read()
        constraint_strs.append(constraint_str)
        tree = ConstraintTree(var_control)
        # try:
        c = tree.build(constraint_str)
        logging.info("preload {}".format(filename))
        # except Exception as e:
        #     logging.error("preload {} failed: {}".format(filename, e))
        #     continue
        var_control.build_var("code", c, filename)
            
    logging.error("code: {} spec: {}".format(code_input, spec_input))

    code_tree = ConstraintTree(var_control)
    with open(code_input, "r") as f:
        code_constraint_str = f.read()
    code_c = code_tree.build(code_constraint_str)
    var_control.add_constraint("code", code_c)
    logging.debug("code side: {}".format(code_tree.constraint))

    user_tree = ConstraintTree(var_control)
    with open(spec_input, "r") as f:
        user_constraint_str = f.read()
    user_c = user_tree.build(user_constraint_str)
    var_control.add_constraint("user", user_c)
    logging.debug("user side: {}".format(user_tree.constraint))

    
    data = var_control.solve()
    end = time.time()
    logging.info("time: {}".format(end-start))

    with open(case_output, "w") as f:
        if args.stateful:
            f.write(data)
        else:
            json.dump(data, f, indent=2)

    # statistics
    cnt = 0
    model_vars = var_control.var_map["model"]
    for var_name in model_vars:
        var = model_vars[var_name]
        if (isinstance(var, z3.BoolRef) or isinstance(var, z3.ArithRef)) and len(var.children()) == 0:
            cnt += 1
    logging.info("base variables: {}".format(cnt))
    for side in ["model", "code", "user"]:
        logging.info("{}'s {}: {}".format(side, "variables", len(var_control.var_map[side])))
        logging.info("{}'s {}: {}".format(side, "constraints", len(var_control.constraints[side])))

        if side in ["code", "user"]:
            logging.error("{}'s {}: {}".format(side, "op", count_operator(Or(*var_control.constraints[side]))))
            logging.error("{}'s {}: {}".format(side, "depth", get_ast_depth(Or(*var_control.constraints[side]))))

        if side == "code":
            anno = 0
            data = re.sub("\s+", "", ",".join(constraint_strs))
            token_list = re.split('(\(|\)|,)', data)
            counted = []
            for token in token_list:
                if token in var_control.var_map[side] and token not in counted:
                    counted.append(token)
                    anno += 1
            logging.error("{}'s {}: {}".format(side, "anno", anno))

        if side == "user":
            logging.error("spec op: {}".format(user_tree.op_count))


if __name__ == "__main__":
    main()