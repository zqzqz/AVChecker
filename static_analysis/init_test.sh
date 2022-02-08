#!/bin/bash

TEST_PATH=$1

mkdir -p $TEST_PATH
touch ${TEST_PATH}/func.meta
touch ${TEST_PATH}/source.meta
touch ${TEST_PATH}/sink.meta
