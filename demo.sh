abspath=$(readlink -f "$0")
root=$(dirname $abspath)
analysis_result=${root}/demo/analysis_result.demo
constraint=${root}/demo/constraint.demo
case=${root}/demo/case.demo

export DEFAULT_BITCODE=test/apollo/demo.bc
export USE_DEFAULT=true
export DEBUG=true

cd static_analysis
echo "Building LLVM pass..."
make clean && make
echo "Build LLVM pass done."
echo "Doing program analysis on Apollo..."
bash run.sh test/traffic_rules/crosswalk 2> ${analysis_result}
echo "Extracted crosswalk related traffic rule from Apollo code."
line=$(grep -n "Final result:" ${analysis_result} | cut -d ":" -f 1)
sed -i "1,${line}d" ${analysis_result}
echo "Result written into ${analysis_result}."
cd -
cd constraint_solver
echo "Transforming analysis result into the input of constraint solver..."
python scripts/z3_parser.py ${analysis_result} ${constraint}
echo "Result written into ${constraint}"
echo "Verifying traffic rule 'Stop at a crosswalk if seeing a vehicle that has stopped behind an oncoming crosswalk'..."
python -m av_solver --code ${constraint} --spec data/spec/spec_crosswalk_1 --output ${case} --scenario crosswalk --action 0
echo "Violation case written into ${case}"
cd -
echo "done!"
