from z3 import *

def count_operator(f):
    stack = [f]
    cnt = 0
    while len(stack) > 0:
        x = stack.pop()
        children = x.children()
        if len(children) > 0:
            cnt += 1
        for child in children:
            stack.append(child)
    return cnt

def get_ast_depth(f):
    children = f.children()
    cnt = 1
    if len(children) == 0:
        return cnt
    for child in children:
        cnt = max(cnt, get_ast_depth(child) + 1)
    return cnt

def count_base_variable(v):
    var_cnt = 0
    for name, var in v:
        if (isinstance(var, z3.BoolRef) or isinstance(var, z3.ArithRef)) and len(var.children()) == 0:
            var_cnt += 1
    return var_cnt