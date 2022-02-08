import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import logging
from av_solver.variable_controller import VariableController
from av_solver.constraint_tree import Node, ConstraintTree
import json

logging.basicConfig(level=logging.INFO)


def test():
    var_control = VariableController()
    code_tree = ConstraintTree(var_control, "code")
    with open(os.path.join(os.path.dirname(__file__), sys.argv[1]), "r") as f:
        constraint_str = f.read()
    code_tree.build(constraint_str)
    logging.debug("code side: {}".format(code_tree.constraint))

    user_tree = ConstraintTree(var_control, "user")
    with open(os.path.join(os.path.dirname(__file__), sys.argv[2]), "r") as f:
        constraint_str = f.read()
    user_tree.build(constraint_str)
    logging.debug("user side: {}".format(user_tree.constraint))

    data = var_control.solve()
    with open(sys.argv[3], "w") as f:
        json.dump(data, f, indent=2)

    for side in ["model", "code", "user"]:
        print("{}'s {}: {}".format(side, "variables", len(var_control.var_map[side])))
        print("{}'s {}: {}".format(side, "constraints", len(var_control.constraints[side])))

if __name__ == "__main__":
    test()
