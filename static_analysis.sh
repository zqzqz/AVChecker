source config.sh

cd static_analysis
make clean && make
for target in "${targets[@]}"; do
    echo "Analyzing $target..."
    result_name=$(get_name $target)
    time bash run.sh test/${target} 2> result.tmp
    rm result/${result_name}
    cp result.tmp result/${result_name}
done
cd -
