Apollo+LLVM Notes
===

## Tips

- ***!!! Do not use `dev_start.sh` to start dev docker after rebooting the machine***

    For the first time of starting Apollo dev docker, you can use `bash docker/scripts/dev_start.sh`. However, after rebooting, if you still use `dev_start.sh`, you will lose all previous modifications within the docker, because the dev docker container will be deleted. Using the following commands can avoid such issue.

    **Apollo 3.0**

    ```bash
    docker run -it -d --rm --name apollo_localization_volume apolloauto/apollo:localization_volume-x86_64-latest
    docker run -it -d --rm --name apollo_yolo3d_volume apolloauto/apollo:yolo3d_volume-x86_64-latest
    docker run -it -d --rm --name apollo_map_volume-sunnyvale_big_loop apolloauto/apollo:map_volume-sunnyvale_big_loop-latest
    docker run -it -d --rm --name apollo_map_volume-sunnyvale_loop apolloauto/apollo:map_volume-sunnyvale_loop-latest

    # Make sure that you can see `apollo_dev` in `docker ps -a` as `EXITED`
    docker start apollo_dev

    bash docker/scripts/dev_into.sh
    ```

    **Apollo 5.0**

    ```bash
    # Copy `dev_restart.sh` in this directory to Apollo's root directory
    cp dev_restart.sh <path to apollo>/docker/scripts

    # Make sure that you execute the following commands in Apollo's root directory
    cd <path to apollo>
    bash docker/scripts/dev_restart.sh

    bash docker/scripts/dev_into.sh
    ```

- May need to delete inconsistent `gtest` header file
    ```bash
    sudo mv /usr/include/gtest /usr/include/gtest_bak
    ```

## Compile Apollo using LLVM

(All following commands are assumed to be executed in Apollo dev docker)

1. Install LLVM

    **LLVM 3.4**

    ```bash
    # LLVM 3.4
    sudo apt install llvm-3.4 llvm-3.4-dev clang-3.4 libclang-3.4-dev

    # Create soft links
    sudo ln -sf /usr/bin/llvm-config-3.4 /usr/bin/llvm-config
    sudo ln -sf /usr/bin/llvm-link-3.4 /usr/bin/llvm-link
    ```

    **LLVM 8 (Recommended)**

    ```bash
    # LLVM 8
    sudo apt install llvm-8 llvm-8-dev clang-8 libclang-8-dev

    # Create soft links
    sudo ln -sf /usr/bin/llvm-config-8 /usr/bin/llvm-config
    sudo ln -sf /usr/bin/llvm-link-8 /usr/bin/llvm-link
    ```

2. Install `whole-program-llvm`

    ```bash
    sudo pip install wllvm
    ```

3. Copy `wllvm` directory to `/apollo/tools`

    ```bash
    cp -r wllvm /apollo/tools
    ```

4. Before compiling (Apollo 5.0 only)

    1. Modify `modules/planning/reference_line/spiral_problem_interface.h`

        Change `constexpr static size_t N = 10;` at line 140 from `private` to `public`.

    2. Modify `cyber/scheduler/policy/classic_context.cc`

        Add `alignas(CACHELINE_SIZE)` for line 32~35, see the following:

        ```c++
        alignas(CACHELINE_SIZE) GRP_WQ_MUTEX ClassicContext::mtx_wq_;
        alignas(CACHELINE_SIZE) GRP_WQ_CV ClassicContext::cv_wq_;
        alignas(CACHELINE_SIZE) RQ_LOCK_GROUP ClassicContext::rq_locks_;
        alignas(CACHELINE_SIZE) CR_GROUP ClassicContext::cr_group_;
        ```

    3. Disable compiler options

        Comment out Line 65~Bottom in `tools/bazel.rc`.
5. Compile Apollo

    ```bash
    cd /apollo
    mkdir wllvm_bc  # This directory will contain all seperate bitcode files
    bash apollo.sh build --copt=-mavx2 --cxxopt=-mavx2 --copt=-mno-sse3 --crosstool_top=tools/wllvm:toolchain
    ```

    Those `copt` and `cxxopt` can be removed, if your machine supports the corresponding instruction sets.

6. Or compile single module (e.g., `planning` module)

    ```bash
    ## Apollo 3.0
    bazel build --define ARCH=x86_64 --define CAN_CARD=fake_can --cxxopt=-DUSE_ESD_CAN=false --copt=-mavx2 --copt=-mno-sse3 --cxxopt=-DCPU_ONLY --crosstool_top=tools/wllvm:toolchain //modules/planning:planning --compilation_mode=dbg

    ## Apollo 5.0
    bash apollo.sh build_planning --cxxopt=-mavx2 --copt=-mno-sse3 --crosstool_top=tools/wllvm:toolchain  # recommended

    # Or
    bazel build --ram_utilization_factor 80 --define ARCH=x86_64 --define CAN_CARD=fake_can --cxxopt=-DUSE_ESD_CAN=false --copt=-mavx2 --copt=-mno-sse3 --cxxopt=-DCPU_ONLY --experimental_multi_threaded_digest --crosstool_top=tools/wllvm:toolchain --compilation_mode=dbg //modules/planning:libplanning_component.so
    ```

6. Extract bitcode file (e.g., `planning` module)

    **Apollo 3.0**

    ```bash
    cd /apollo/bazel-bin/modules/planning
    extract-bc planning

    # Check output
    file planning.bc
    llvm-dis planning.bc
    ```

    **Apollo 3.5 & 5.0**

    ```bash
    sudo apt install python3-pip
    sudo pip3 install sh
    python3 ApolloBitcodeExtractor.py
    ```

    Usage of `ApolloBitcodeExtractor.py`:

    ```
    usage: ApolloBitcodeExtractor.py [-h] [-t TARGET] [-p PROJECT] [-o OUTPUT]

    Apollo LLVM bitcode extractor for any Bazel targets

    optional arguments:
      -h, --help            show this help message and exit
      -t TARGET, --target TARGET
                            A Bazel build target (default:
                            //modules/planning:libplanning_component.so)
      -p PROJECT, --project PROJECT
                            The root directory of a Bazel project (default:
                            /apollo)
      -o OUTPUT, --output OUTPUT
                            The name of the output bitcode (default: output.bc)
    ```
