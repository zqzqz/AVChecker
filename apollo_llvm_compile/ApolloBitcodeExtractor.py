#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Date    : 2019-07-13 12:18:39
# @Author  : Shengtuo Hu (h1994st@gmail.com)
# @Link    : https://shengtuo.me
# @Version : 1.0

import os
import sys
import argparse

import sh
extract_bc = sh.Command('extract-bc')
llvm_link = sh.Command('llvm-link')


# Empty function stub
def empty_func(*args, **kwargs):
    pass


def get_project_name(project_workspace_path):
    name = None

    # Function stubs
    def workspace(*args, **kwargs):
        nonlocal name
        name = kwargs.get('name')
    new_http_archive = empty_func
    new_local_repository = empty_func
    bind = empty_func
    new_git_repository = empty_func
    http_archive = empty_func
    load = empty_func
    grpc_deps = empty_func

    print('Before: %s' % name)
    print(project_workspace_path)
    with open(project_workspace_path, 'r') as fp:
        exec(fp.read())
    print('After: %s' % name)

    return name


def get_package_dependencies(package_name, base_path):
    package_dependencies = {}

    load = empty_func
    package = empty_func
    cpplint = empty_func
    cc_test = empty_func
    licenses = empty_func
    exports_files = empty_func
    config_setting = empty_func
    objc_library = empty_func
    genrule = empty_func
    internal_gen_well_known_protos_java = empty_func
    java_library = empty_func
    py_library = empty_func
    internal_copied_filegroup = empty_func
    py_proto_library = empty_func
    internal_protobuf_py_tests = empty_func
    proto_lang_toolchain = empty_func
    cuda_library = empty_func  # ???: maybe a potential target

    def glob(*args, **kwargs):
        return []
    select = glob

    def parse_target(*args, **kwargs):
        target_name = kwargs.get('name')
        if target_name is None:
            return
        package_dependencies[target_name] = {
            'srcs': kwargs.get('srcs'),
            'deps': kwargs.get('deps'),
            'type': kwargs.get('type')
        }

    def cc_library(*args, **kwargs):
        kwargs['type'] = 'lib'
        parse_target(*args, **kwargs)
    cc_proto_library = cc_library
    proto_library = cc_library

    def cc_binary(*args, **kwargs):
        kwargs['type'] = 'bin'
        parse_target(*args, **kwargs)

    def filegroup(*args, **kwargs):
        kwargs['type'] = 'filegroup'
        parse_target(*args, **kwargs)

    print('Read BUILD file: %s' % package_name)
    build_filepath = os.path.join(base_path, package_name[2:])
    build_filepath = os.path.join(build_filepath, 'BUILD')
    if not os.path.exists(build_filepath):
        build_filepath += '.bazel'
    assert os.path.exists(build_filepath), (
        'No Bazel BUILD file: %s' % build_filepath)

    with open(build_filepath, 'r') as fp:
        exec(fp.read())

    return package_dependencies


def extract(project_path='/apollo',
            target_name='//modules/planning:libplanning_component.so',
            output_name='output.bc'):
    # Check the existence of the project
    if not os.path.exists(project_path):
        print('No such project directory: %s' % project_path)
        sys.exit(1)

    # Check the existence of WORKSPACE file
    project_workspace_path = os.path.join(project_path, 'WORKSPACE')
    if not os.path.exists(project_workspace_path):
        print('No WORKSPACE file found in the project directory!')
        sys.exit(1)

    # Read WORKSPACE to get the project name
    project_name = get_project_name(project_workspace_path)
    print(project_name)
    base_path = os.path.join(project_path, 'bazel-%s' % project_name)
    # Check the existence of the working directory
    if not os.path.exists(base_path):
        print(base_path)
        print('Please build the project at first!')
        sys.exit(1)

    print('[+] Start collecting dependencies for target "%s"' % target_name)
    dependencies = {}
    targets = [target_name]
    output = set()
    visited = set()
    while len(targets) != 0:
        target = targets.pop(0)
        if target in visited:
            print('Visited "%s"' % target)
            continue

        # Some exceptions
        if target == '//external:gflags':
            print('Skip "%s"' % target)
            continue

        visited.add(target)
        print(target)

        # External target
        if target[0] == '@':
            target = '//external/' + target[1:]

        try:
            package_name, target_name = target.split(':', 1)
        except ValueError:
            print('Use default target name for "%s"' % target)
            package_name = target
            target_name = target.split('/')[-1]  # use default name

        if package_name not in dependencies:
            # Read BUILD file
            dependencies[package_name] = get_package_dependencies(
                package_name, base_path)
        package_dependencies = dependencies[package_name]

        assert (target_name in package_dependencies), (
            'No such target "%s" in "%s"' % (target_name, package_name))

        target_entry = package_dependencies[target_name]
        if target_entry['srcs'] is not None and \
           len(target_entry['srcs']) != 0:
            target_output_path = package_name[2:]
            target_output_name = target_name
            if target_entry['type'] == 'lib':
                target_output_name = 'lib' + target_output_name + '.so'
            target_output_path = os.path.join(
                target_output_path, target_output_name)
            output.add(target_output_path)

        if package_dependencies[target_name]['deps'] is None:
            continue

        # Post-processing
        for dep in package_dependencies[target_name]['deps']:
            if dep[0] == ':':  # omit the package name
                print('Dependency "%s" in current package "%s"' % (
                    dep, package_name))
                dep = package_name + dep
            elif dep[0] == '@':
                print('External dependency "%s"' % dep)
            elif dep[:2] != '//':  # omit the package name, without prefix ':'
                print('Dependency "%s" in current package "%s"' % (
                    dep, package_name))
                dep = package_name + ':' + dep
            targets.append(dep)
    # print(output)

    print('[+] Finish collecting dependencies!')

    # Extract bitcode
    print('[+] Start extracting all bitcode files')
    output_base_path = os.path.join(project_path, 'bazel-bin')
    bitcode_files = []
    print('%d in total' % len(output))
    for output_target in output:
        output_target_path = os.path.join(output_base_path, output_target)
        if not os.path.exists(output_target_path):
            print('"%s" not found' % output_target_path)
            continue
        print('Extract bitcode of "%s"' % output_target_path)
        extract_bc(output_target_path)
        bitcode_files.append(output_target_path + '.bc')
    print('[-] Finish extracting bitcode files!')

    # Link all bitcode files
    print('[+] Start linking all bitcode files')
    llvm_link('-o', output_name, *bitcode_files)
    print('[+] Finish linking bitcode files!')


if __name__ == '__main__':
    # Argument parser
    parser = argparse.ArgumentParser(
        description='Apollo LLVM bitcode extractor for any Bazel targets')

    # Options
    default_target = '//modules/planning:libplanning_component.so'
    parser.add_argument(
        '-t', '--target',
        default=default_target,
        help='A Bazel build target (default: %s)' % default_target)

    default_project_path = '/apollo'
    parser.add_argument(
        '-p', '--project',
        default=default_project_path,
        help='The root directory of a Bazel project (default: %s)' % (
            default_project_path))

    parser.add_argument(
        '-o', '--output',
        default='output.bc',
        help='The name of the output bitcode (default: output.bc)')

    (args, _) = parser.parse_known_args()

    extract(
        project_path=args.project,
        target_name=args.target,
        output_name=args.output)
