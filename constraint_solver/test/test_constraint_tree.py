import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from av_solver.variable_controller import VariableController
from av_solver.constraint_tree import Node, ConstraintTree
from av_solver.util import get_ast_depth, count_operator
import logging

logging.basicConfig(level=logging.DEBUG)

def test():
    var_control = VariableController()
    tree = ConstraintTree(var_control)
    tree.build("and(is_waiting(vehicle-ego,intersection.start_s),is_yield(vehicle-ego,vehicle,intersection.start_s,intersection.end_s),is_yield(vehicle-ego,pedestrian,intersection.start_s,intersection.end_s))")
    print(tree.constraint)
    print(count_operator(tree.constraint))
    print(get_ast_depth(tree.constraint))

if __name__ == "__main__":
    test()