clang -O0 -std=c++11 -c -emit-llvm ${1}.cpp -o ${1}.bc
llvm-dis ${1}.bc
