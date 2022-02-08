import os

ROOT=os.path.join(os.path.abspath(os.path.dirname(__file__)), "../")

FRAME_CONFIG = {
    "enable": False,
    "steps": 2,
    "interval": 1
}

APOLLO_CONFIG = {
    "max_stop_deceleration": 10,
    "kPassStopLineBuffer": 0.3,
    "kCheckClearDistance": 5.0,
    "kStartWatchDistance": 2.0,
    "crosswalk.stop_strict_l_distance": 4,
    "crosswalk.stop_loose_l_distance": 6,
    "crosswalk.min_pass_s_distance": 0,
    "crosswalk.stop_timeout": 1000,
    # TODO
    "max_abs_speed_when_stopped": 5,
    "max_valid_stop_distance": 2,
    "min_pass_s_distance": 3,
    # scenarios
    "start_bare_intersection_scenario_distance": 25,
    "start_traffic_light_scenario_distance": 5,
    "start_stop_sign_scenario_distance": 4,
    "unprotected_right_turn.stop_duration_sec": 3,
    "unprotected_left_turn.stop_duration_sec": 3,
    "creep_distance": 2
}

SALLY_CONFIG = {
    "template_filename": os.path.join(ROOT, "data/sally/template.mcmt"),
    "main_filename": "data/sally/main.mcmt",
    "bin": "sally",
    "options": ['--engine', 'bmc', '--show-trace'],
    "def_label": "##DEFINITION##",
    "init_label": "##INIT##",
    "transition_label": "##TRANSITION##",
    "query_label": "##QUREY##"
}