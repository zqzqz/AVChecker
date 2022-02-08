source config.sh

for target in "${targets[@]}"; do
    echo "Parsing ${target}"
    target_name=$(get_name $target)
    $PYTHON_BIN constraint_solver/scripts/z3_parser.py static_analysis/result/${target_name} constraint_solver/data/preload/${target_name}
done