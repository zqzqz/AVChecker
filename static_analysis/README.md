# Analysis on Apollo

## Steps

* Data flow (`reaching-definitions`)
* Call graph (`control-dependency`)
* Control dependency (`control-dependency`)
* Program slicing (`control-dependency`)
* Symbolic execution(`traffic-rule-info`)

## Get started

* Install z3 c++ API (`libz3.a`) following instructions [here](https://github.com/Z3Prover/z3#building-z3-using-make-and-gccclang), remember to add `--staticlib` option while running `python scripts/mk_make.py`
* Prepare a test directory, containing
    * `func.meta`: Demangled function name to be analyzed (including the source function but excluding the sink function).
    * `sink.meta`: Sink function name.
    * `source.meta`: Source function name.
    * `{dirname}.cpp/.bc`: A cpp file or compiled LLVM bitcode file; the filename must be the same as the directory name.

* Compile the pass

```bash
make
```

One ENV variable: If `DEBUG` is set to true (default false), the pass will produce debug logs.

* Execute the pass

```bash
bash run.sh ${path_to_test_directory}
# e.g., bash run.sh test/crosswalk
```

Two extra ENV variables: `USE_DEFAULT` and `DEFAULT_BITCODE`. If `USE_DEFAULT` is set to true (default false), the pass will use the bitcode from the file identified by `DEFAULT_BITCODE` (default `test/apollo/apollo.bc`).

## TODOs

* Pointer Analysis

Currently, data dependency is performed based on reaching definition analysis, which can extract register read-write and store-load dependencies but not all memory dependencies.

```
%call61 = call %"struct.std::pair"* @_ZNSt6vectorISt4pairIPKN6apollo5hdmap11PathOverlapES_INSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEESaISB_EEESaISE_EE5beginEv(%"class.std::vector.8"* %46) #3
%coerce.dive62 = getelementptr inbounds %"class.__gnu_cxx::__normal_iterator.25", %"class.__gnu_cxx::__normal_iterator.25"* %__begin260, i32 0, i32 0
store %"struct.std::pair"* %call61, %"struct.std::pair"** %coerce.dive62, align 8
```

We assume some implicit data dependency with vector opeartions. Taking above LLVM code as an example, `%__begin260` is assigned as the begin iterator of the vector `%46`, but when performing bottom-up reaching definition, the definition of `%__begin260` in the second instruction refers to the allocation instruction rather than `%call61`.

We made a simple fix by setting `%coerce.dive62` as an alias of `%__begin260`.

Pointer analysis is a more standard way of handling above issues.

* Internal Calls

Some calls are not in the trace of call chains from source to sink, but they are critical for extracting path constraints. For example, `Crosswalk::MakeDecisions` calls `Crosswalk::CheckStopForObstacle` which determine whether the vehicle should stop before a specific obstacle.
Currently we manually configure which internal calls to analysis, compute path constraints from entry to return statement of such internal calls and load the symbolic return value to the caller function.

We only support internal functions with following features:
1. It has one return value and all parameters are const.
2. The function is called only once.

Though we haven't found cases we want to analyze beyond above restrictions, a general program analysis should handle various types of calls.

* Readable Symbols

We set the name of z3 variables as the name of LLVM variables. For some call chains of object property functions, e.g., `reference_line_info->AdcSlBoundary().start_s()`, we only got `start_s`.
We hope to extract the complete comprehensive name like `ReferenceLineInfo.AdcSlBoundary.start_s`.
To achieve this, data flow analysis is required.
