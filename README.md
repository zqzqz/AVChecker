# AVChecker

For compiling LLVM bitcode of Baidu Apollo, see `apollo_llvm_compile/README.md`.

For static analysis on Baidu Apollo LLVM bitcode, see `static_analysis/README.md`.

For SMT-based constraint solving, see `constraint_solver/README.md`

# Environment Requirements

* Apollo 5.5
* Python 3.6+ with package z3-solver (for constraint solver)
* LLVM 8 (for compiling bitcode and static analysis)

# Quick Start

A demo process checking crosswalk driving rules on Baidu Apollo 5.5.

```
bash demo.sh
```
