from z3 import *
from .config import SALLY_CONFIG
from .util import count_operator

import os, re
import subprocess
import logging

def toSMT2Benchmark(f, status="unknown", name="benchmark", logic="QF_LIA"):
    v = (Ast * 0)()
    return Z3_benchmark_to_smtlib_string(f.ctx_ref(), name, logic, status, "", 0, v, f.as_ast())


def encode_smt2(token):
    if not token.replace('.', '').isdigit() and len(token) > 1:
        token = token.replace("-", "A")
        token = token.replace(".", "B")
        token = token.replace("_", "C")
    token = token.replace("stateB", "state.")
    token = token.replace("nextB", "next.")
    return token


def text_format(tokens):
    bracket_num = 0
    last_token = None
    result = ""
    for token in tokens:
        token = encode_smt2(token)
        if token == "(":
            bracket_num += 1
            if last_token == ")":
                result += "\n" + " " * bracket_num
            elif last_token is not None and last_token != "(":
                result += " "
        elif token == ")":
            bracket_num -= 1
        else:
            if last_token is not None and last_token not in ["("]:
                result += " "
        result += token
        last_token = token
        # temp fix
        if token == "or":
            result += " false"
    return result


def extract_assert(smt2):
    token_list = re.split('(\(|\)|,|\ |\n)', smt2)
    token_list = list(filter(lambda x : x != "" and x != " " and x != "\n", token_list))
    bracket_num = 0
    f = False
    res_token_list = []
    for token in token_list:
        if token.startswith("?x"):
            token = token.replace("?x", "a!")
        if token.startswith("$x"):
            token = token.replace("$x", "b!")
        if f:
            if token == "(":
                bracket_num += 1
            elif token == ")":
                bracket_num -= 1
            res_token_list.append(token)
            if bracket_num == 0:
                break
        if token == "assert":
            f = True
    return res_token_list


def write_file(filename, def_text, init_text, transition_text, query_text):
    with open(SALLY_CONFIG["template_filename"], "r") as f:
        file_text = f.read()
    file_text = file_text.replace(SALLY_CONFIG["def_label"], def_text)
    file_text = file_text.replace(SALLY_CONFIG["init_label"], init_text)
    file_text = file_text.replace(SALLY_CONFIG["transition_label"], transition_text)
    file_text = file_text.replace(SALLY_CONFIG["query_label"], query_text)
    with open(filename, "w") as f:
        f.write(file_text)


def generate_sally_input(var_control):
    # print(toSMT2Benchmark(And(Or(*var_control.constraints["code"]), Or(*var_control.constraints["user"]))))
    # def
    model_vars = var_control.var_map["model"]
    def_tokens = ["("]
    for var_name in model_vars:
        var = model_vars[var_name]
        if isinstance(var, z3.BoolRef):
            if len(var.children()) > 0:
                continue
            def_tokens += ["(", var_name, "Bool", ")"]
        elif isinstance(var, z3.ArithRef):
            if len(var.children()) > 0:
                continue
            if var.is_real():
                def_tokens += ["(", var_name, "Real", ")"]
            elif var.is_int():
                def_tokens += ["(", var_name, "Int", ")"]
    def_tokens.append(")")
    def_text = text_format(def_tokens)

    # init
    init_c = [And(*var_control.constraints["model"])]
    if var_control.scenario_type == "stop_sign":
        init_c.append(model_vars["scenario_stage"] == 1)
        init_c.append(model_vars["overlap_finished"] == False)
        init_c.append(model_vars["watch_vehicles.empty"] == True)
        init_c.append(model_vars["vehicle.stop_line"] > 0)
        init_c.append(model_vars["vehicle.arrive_time"] == 0)
        init_c.append(model_vars["vehicle-ego.arrive_time"] == 0)
        init_c.append(var_control.vars["scenarios-stop_sign-unprotected-entry"])
    elif var_control.scenario_type == "traffic_light_unprotected_left_turn":
        init_c.append(model_vars["scenario_stage"] == 1)
        init_c.append(model_vars["overlap_finished"] == False)
        init_c.append(model_vars["vehicle.arrive_time"] == 0)
        init_c.append(model_vars["vehicle-ego.arrive_time"] == 0)
        init_c.append(var_control.vars["scenarios-traffic_light-unprotected_left_turn-entry"])
    elif var_control.scenario_type == "traffic_light_unprotected_right_turn":
        init_c.append(model_vars["scenario_stage"] == 1)
        init_c.append(model_vars["overlap_finished"] == False)
        init_c.append(model_vars["vehicle.arrive_time"] == 0)
        init_c.append(model_vars["vehicle-ego.arrive_time"] == 0)
        init_c.append(var_control.vars["scenarios-traffic_light-unprotected_right_turn-entry"])
    elif var_control.scenario_type == "traffic_light_protected":
        init_c.append(model_vars["overlap_finished"] == False)
        init_c.append(model_vars["scenario_stage"] == 1)
        init_c.append(model_vars["vehicle-ego.arrive_time"] == 0)
        init_c.append(var_control.vars["scenarios-traffic_light-protected-entry"])
    elif var_control.scenario_type == "bare_intersection":
        init_c.append(model_vars["scenario_stage"] == 1)
        init_c.append(model_vars["vehicle.arrive_time"] == 0)
        init_c.append(model_vars["vehicle-ego.arrive_time"] == 0)
        init_c.append(var_control.vars["scenarios-bare_intersection-unprotected-entry"])
    if var_control.scenario_type in ["stop_sign", "traffic_light_unprotected_left_turn", "traffic_light_unprotected_right_turn", "traffic_light_protected", "bare_intersection"]:
        init_c.append(model_vars["violation_counter"] == 0)
    init_text = text_format(extract_assert(toSMT2Benchmark(And(*init_c))))

    # transition
    update_tokens = {}
    if var_control.scenario_type == "stop_sign":
        update_tokens["vehicle.stop_line"] = "( = next.vehicle.stop_line ( - state.vehicle.stop_line ( * 0.1 state.vehicle.v.s ) ) )".split(" ")
        update_tokens["vehicle-ego.v.s"] = ("( = next.vehicle-ego.v.s ( ite {} 0 1 ) )").format(
                            " ".join(extract_assert(toSMT2Benchmark(Or(*var_control.constraints["code"]))))
                        ).split(" ")
        update_tokens["vehicle-ego.arrive_time"] = "( = next.vehicle-ego.arrive_time ( ite ( = state.scenario_stage 2 ) ( + state.vehicle-ego.arrive_time 0.1 ) 0 ) )".split(" ")
        update_tokens["vehicle.arrive_time"] = "( = next.vehicle.arrive_time ( ite ( < ( - state.vehicle.stop_line state.vehicle.size.s ) 2 ) ( + state.vehicle.arrive_time 0.1 ) 0 ) )".split(" ")
        update_tokens["scenario_stage"] = ("( = next.scenario_stage ( ite ( or"
                        " ( and ( = state.scenario_stage 1 ) {} )"
                        " ( and ( = state.scenario_stage 2 ) {} )"
                        " ) 0 ( ite ( or"
                        " ( and ( = state.scenario_stage 1 ) {} )"
                        " ( and ( = state.scenario_stage 2 ) {} )"
                        " ) ( + state.scenario_stage 1 ) state.scenario_stage ) ) )"
                        ).format(
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-stop_sign-unprotected-pre_stop-finish_scenario"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-stop_sign-unprotected-stop-finish_scenario"]))),
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-stop_sign-unprotected-pre_stop-finish_stage"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-stop_sign-unprotected-stop-finish_stage"]))),
                        ).split(" ")
        update_tokens["watch_vehicles.empty"] = ("( = next.watch_vehicles.empty ( ite ( and ( = state.scenario_stage 1 ) {} ) false "
                        "( ite ( and ( = state.scenario_stage 2 ) {} ) true state.watch_vehicles.empty ) ) )"
                        ).format(
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-stop_sign-unprotected-pre_stop-add_watch_vehicle"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-stop_sign-unprotected-stop-remove_watch_vehicle"]))),
                        ).split(" ")
        update_tokens["overlap_finished"] = "( = next.overlap_finished ( ite ( > state.scenario_stage 2 ) true state.overlap_finished ) )".split(" ")
    elif var_control.scenario_type == "traffic_light_unprotected_left_turn":
        update_tokens["vehicle-ego.v.s"] = ("( = next.vehicle-ego.v.s ( ite {} 0 1 ) )").format(
                            " ".join(extract_assert(toSMT2Benchmark(Or(*var_control.constraints["code"]))))
                        ).split(" ")
        update_tokens["vehicle-ego.arrive_time"] = "( = next.vehicle-ego.arrive_time ( ite ( = state.scenario_stage 1 ) ( + state.vehicle-ego.arrive_time 0.1 ) 0 ) )".split(" ")
        update_tokens["scenario_stage"] = (
                        "( = next.scenario_stage"
                        " ( ite ( = state.scenario_stage 1 )"
                            " ( ite {}"
                                " ( ite {}"
                                    " ( ite ( > vehicle-ego.v.s 5.56 ) 3 2 )"
                                    " state.scenario_stage )"
                                " 0 )"
                            " state.scenario_stage ) )"
                        ).format(
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-traffic_light-unprotected_left_turn-approach-finish_scenario"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-traffic_light-unprotected_left_turn-approach-finish_stage"])))
                        ).split(" ")
        update_tokens["overlap_finished"] = "( = next.overlap_finished ( ite ( > state.scenario_stage 1 ) true state.overlap_finished ) )".split(" ")
    elif var_control.scenario_type == "traffic_light_unprotected_right_turn":
        update_tokens["vehicle-ego.v.s"] = ("( = next.vehicle-ego.v.s ( ite {} 0 1 ) )").format(
                            " ".join(extract_assert(toSMT2Benchmark(Or(*var_control.constraints["code"]))))
                        ).split(" ")
        update_tokens["vehicle-ego.arrive_time"] = "( = next.vehicle-ego.arrive_time ( ite ( = state.scenario_stage 1 ) ( + state.vehicle-ego.arrive_time 0.1 ) 0 ) )".split(" ")
        update_tokens["scenario_stage"] = (
                        "( = next.scenario_stage"
                        " ( ite ( = state.scenario_stage 1 )"
                            " ( ite {}"
                                " ( ite {}"
                                    " ( ite ( > vehicle-ego.v.s 3.0 ) 3 2 )"
                                    " state.scenario_stage )"
                                " 0 )"
                            " state.scenario_stage ) )"
                        ).format(
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-traffic_light-unprotected_right_turn-stop-finish_scenario"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-traffic_light-unprotected_right_turn-stop-finish_stage"])))
                        ).split(" ")
        update_tokens["overlap_finished"] = "( = next.overlap_finished ( ite ( > state.scenario_stage 1 ) true state.overlap_finished ) )".split(" ")
    elif var_control.scenario_type == "traffic_light_protected":
        update_tokens["vehicle-ego.v.s"] = ("( = next.vehicle-ego.v.s ( ite {} 0 1 ) )").format(
                            " ".join(extract_assert(toSMT2Benchmark(Or(*var_control.constraints["code"]))))
                        ).split(" ")
        update_tokens["vehicle-ego.arrive_time"] = "( = next.vehicle.arrive_time ( ite ( < ( - state.vehicle.stop_line state.vehicle.size.s ) 2 ) ( + state.vehicle.arrive_time 0.1 ) 0 ) )".split(" ")
        update_tokens["scenario_stage"] = (
                        "( = next.scenario_stage"
                        " ( ite ( = state.scenario_stage 1 )"
                            " ( ite {}"
                                " 0"
                                " ( ite {} 2 1 ) )"
                            " state.scenario_stage ) )"
                        ).format(
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-traffic_light-protected-approach-finish_scenario"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-traffic_light-protected-approach-finish_stage"])))
                        ).split(" ")
        update_tokens["overlap_finished"] = "( = next.overlap_finished ( ite ( > state.scenario_stage 1 ) true state.overlap_finished ) )".split(" ")
    elif var_control.scenario_type == "bare_intersection":
        update_tokens["vehicle-ego.v.s"] = ("( = next.vehicle-ego.v.s ( ite {} 0 1 ) )").format(
                            " ".join(extract_assert(toSMT2Benchmark(Or(*var_control.constraints["code"]))))
                        ).split(" ")
        update_tokens["vehicle-ego.arrive_time"] = "( = next.vehicle.arrive_time ( ite ( < ( - state.vehicle.stop_line state.vehicle.size.s ) 2 ) ( + state.vehicle.arrive_time 0.1 ) 0 ) )".split(" ")
        update_tokens["scenario_stage"] = (
                        "( = next.scenario_stage"
                        " ( ite ( = state.scenario_stage 1 )"
                            " ( ite {}"
                                " 0"
                                " ( ite {} 2 1 ) )"
                            " state.scenario_stage ) )"
                        ).format(
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-bare_intersection-unprotected-approach-finish_scenario"]))), 
                            " ".join(extract_assert(toSMT2Benchmark(var_control.vars["scenarios-bare_intersection-unprotected-approach-finish_stage"])))
                        ).split(" ")
    # violation counter
    if var_control.scenario_type in ["stop_sign", "traffic_light_unprotected_left_turn", "traffic_light_unprotected_right_turn", "traffic_light_protected", "bare_intersection"]:
        if var_control.action_mode == 0:
            query = And(Not(Or(*var_control.constraints["code"])), Or(*var_control.constraints["user"]))
        elif var_control.action_mode == 1:
            query = And(Or(*var_control.constraints["code"]), Or(*var_control.constraints["user"]))
        query_tokens = extract_assert(toSMT2Benchmark(query))
        update_tokens["violation_counter"] = "( = next.violation_counter ( ite {} ( + state.violation_counter 1 ) 0 ) )".format(" ".join(query_tokens)).split(" ")
    for var_name in model_vars:
        var = model_vars[var_name]
        if (isinstance(var, z3.BoolRef) or isinstance(var, z3.ArithRef)) and len(var.children()) == 0 and var_name not in update_tokens:
            if var_name.endswith("pos.s") and "ego" not in var_name:
                update_tokens[var_name] = "( = next.{} ( - state.{} ( * 0.1 state.vehicle-ego.v.s ) ) )".format(var_name, var_name).split(" ")
            elif var_name == "vehicle-ego.stop_line":
                update_tokens[var_name] = "( = next.{} ( - ( - state.intersection.pos.s ( * 0.1 state.vehicle-ego.v.s ) ) state.intersection.size.s ) )".format(var_name).split(" ")
            else:
                update_tokens[var_name] = "( = next.{} state.{} )".format(var_name, var_name).split(" ")

    trans_tokens = ["(", "and"]
    for u in update_tokens:
        trans_tokens += update_tokens[u]
    trans_tokens.append(")")
    for i in range(len(trans_tokens)):
        token = trans_tokens[i]
        if token not in ["(", ")", "+", "-", "*", "/", "<", "<=", "=", ">", ">=", "ite", "and", "or", "true", "false", "not", "let"] and not token.replace('.', '').isdigit() and len(token) > 1:
            if not (token.startswith("a!") or token.startswith("b!")) and not (token.startswith("next.") or token.startswith("state.")):
                trans_tokens[i] = "state." + token
    trans_text = text_format(trans_tokens)

    # query
    if var_control.action_mode == 0:
        query = And(
            Not(And(Not(Or(*var_control.constraints["code"])), Or(*var_control.constraints["user"]))),
            # And(*var_control.constraints["model"])
            True
        )
    elif var_control.action_mode == 1:
        query = query = And(
            Not(And(Or(*var_control.constraints["code"]), Or(*var_control.constraints["user"]))),
            # And(*var_control.constraints["model"])
            True
        )
    # number of operators
    logging.info("Number of operators total: {}".format(count_operator(query)))
    # query = (var_control.vars["scenario_stage"] < 3)
    # query = (var_control.vars["watch_vehicles.empty"] == True)
    # query = (var_control.vars["violation_counter"] < 2)
    # query = Not(Or(*var_control.constraints["code"]))

    query_tokens = extract_assert(toSMT2Benchmark(query))
    query_text = text_format(query_tokens)

    write_file(var_control.sally_output, def_text, init_text, trans_text, query_text)


def execute_sally(var_control):
    p = subprocess.Popen([SALLY_CONFIG["bin"]] + SALLY_CONFIG["options"] + [var_control.sally_output], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        logging.error(err)
    return out.decode('utf-8')