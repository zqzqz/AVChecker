DEFAULT_BITCODE=${DEFAULT_BITCODE:-"test/apollo/apollo5.5.bc"}
USE_DEFAULT=${USE_DEFAULT:-true}

if [ "${1}" = ""  ]; then
    echo "Input an argumet as the target test case"
    exit
fi

cpp_name=$(ls ${1}/*.cpp)
bc_name=$(ls ${1}/*.bc)
name=""
bitcode=$DEFAULT_BITCODE

if [ "$USE_DEFAULT" = false ]; then
    if [ "$cpp_name" != "" ]; then
        name="${cpp_name%%.*}"
        bash build_test.sh $name
    elif [ "$bc_name" != "" ]; then
        name="${bc_name%%.*}"
    fi

    if [ "$name" != "" ]; then
        bitcode=${name}.bc
    fi
fi

echo ${1} > config.tmp
opt -load ./traffic-rule-info.so -traffic-rule-info ${bitcode} -o /dev/null
