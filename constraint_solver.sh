# set -e

source config.sh

DIR=$(dirname $0)
WORKDIR=${DIR}/constraint_solver
OUTPUT_DIR=data/case

cd $WORKDIR

if [ ! -d $OUTPUT_DIR ]; then
    mkdir -p $OUTPUT_DIR
fi

# # crosswalk
# $PYTHON_BIN -m av_solver --case crosswalk_1 --scenario crosswalk --action 0
# $PYTHON_BIN -m av_solver --case crosswalk_2 --scenario crosswalk --action 1
# $PYTHON_BIN -m av_solver --case crosswalk_3 --scenario crosswalk --action 0
# $PYTHON_BIN -m av_solver --case crosswalk_4 --scenario crosswalk_intersection --action 0
# $PYTHON_BIN -m av_solver --case crosswalk_5 --scenario crosswalk --action 1

# # intersection
# $PYTHON_BIN -m av_solver --case intersection_1 --scenario traffic_light_unprotected_left_turn --action 1
# $PYTHON_BIN -m av_solver --case intersection_2 --scenario traffic_light_unprotected_left_turn --action 0
# $PYTHON_BIN -m av_solver --case intersection_3 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_3.1 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_3.2 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_6 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_6.1 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_6.2 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_7 --scenario traffic_light_protected --action 0
# $PYTHON_BIN -m av_solver --case intersection_8 --scenario traffic_light_unprotected_right_turn --action 0
# $PYTHON_BIN -m av_solver --case intersection_8.1 --scenario traffic_light_unprotected_right_turn --action 0
# $PYTHON_BIN -m av_solver --case intersection_8.2 --scenario traffic_light_unprotected_right_turn --action 0
# $PYTHON_BIN -m av_solver --case intersection_9 --scenario traffic_light --action 0
# $PYTHON_BIN -m av_solver --case intersection_10 --scenario traffic_light --action 0
# $PYTHON_BIN -m av_solver --case intersection_12 --scenario traffic_light --action 1
# $PYTHON_BIN -m av_solver --case intersection_13 --scenario traffic_light --action 1
# $PYTHON_BIN -m av_solver --case intersection_14 --scenario traffic_light --action 1
# $PYTHON_BIN -m av_solver --case intersection_15 --scenario traffic_light --action 1
# $PYTHON_BIN -m av_solver --case intersection_19 --scenario bare_intersection --action 0

# # traffic light
# $PYTHON_BIN -m av_solver --case traffic_light_1 --scenario traffic_light --action 0
# $PYTHON_BIN -m av_solver --case traffic_light_2 --scenario traffic_light --action 0
# $PYTHON_BIN -m av_solver --case traffic_light_7 --scenario traffic_light --action 0
# $PYTHON_BIN -m av_solver --case traffic_light_8 --scenario traffic_light --action 0

# # stop sign
# $PYTHON_BIN -m av_solver --case stop_sign_5 --scenario stop_sign --action 0
# $PYTHON_BIN -m av_solver --case stop_sign_6 --scenario stop_sign --action 0
# $PYTHON_BIN -m av_solver --case stop_sign_10 --scenario stop_sign --action 1

# $PYTHON_BIN -m av_solver --case crosswalk_case5 --scenario crosswalk --action 1
# $PYTHON_BIN -m av_solver --case stop_sign_case4 --scenario stop_sign --action 0
# $PYTHON_BIN -m av_solver --case intersection_case1 --scenario bare_intersection --action 0
# $PYTHON_BIN -m av_solver --case intersection_case6 --scenario traffic_light_unprotected_right_turn --action 0

# $PYTHON_BIN -m av_solver --case crosswalk_1 --code data/code/code_crosswalk_autoware --scenario crosswalk --action 0
# $PYTHON_BIN -m av_solver --case crosswalk_3 --code data/code/code_crosswalk_autoware --scenario crosswalk --action 0
# $PYTHON_BIN -m av_solver --case crosswalk_4 --code data/code/code_crosswalk_autoware --scenario crosswalk --action 0


cd -
