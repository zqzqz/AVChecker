targets=(
    "traffic_rules/crosswalk/stop"
    "traffic_rules/traffic_light/stop"
    "traffic_rules/stop_sign/stop"
    "scenarios/stop_sign/unprotected/pre_stop/finish_stage"
    "scenarios/stop_sign/unprotected/pre_stop/add_watch_vehicle"
    "scenarios/stop_sign/unprotected/stop/finish_stage"
    "scenarios/stop_sign/unprotected/stop/remove_watch_vehicle"
    "scenarios/stop_sign/unprotected/creep/finish_stage"
    "scenarios/bare_intersection/unprotected/approach/finish_stage"
    "scenarios/bare_intersection/unprotected/approach/stop"
    "scenarios/traffic_light/protected/approach/finish_stage"
    "scenarios/traffic_light/unprotected_left_turn/approach/finish_stage"
    "scenarios/traffic_light/unprotected_left_turn/creep/finish_stage"
    "scenarios/traffic_light/unprotected_right_turn/stop/finish_stage"
    "scenarios/traffic_light/unprotected_right_turn/creep/finish_stage"
    "deciders/speed_decider/stop"
)

export DEBUG=false
export USE_DEFAULT=true
export DEFAULT_BITCODE="test/apollo/apollo5.5.bc"

get_name()
{
    target=$1
    dir_names=(${target//\// })
    result_name=""
    for name in "${dir_names[@]}"; do
        if [ "$result_name" = "" ]; then
            result_name="${name}"
        else
            result_name="${result_name}-${name}"
        fi
    done
    echo $result_name
}

PYTHON_BIN=python
