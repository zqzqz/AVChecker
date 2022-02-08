import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from av_solver.scenarios import *
from av_solver.util import *
import logging
from z3 import *

logging.basicConfig(level=logging.DEBUG)

def test():
    s = FullScenario()
    constraints = []
    for c in s.get_constraints():
        constraints.append(c)
    logging.warn("var: {}".format(count_base_variable(s.get_variables())))
    logging.warn("{}: {}".format("op", count_operator(And(*constraints))))
    logging.warn("{}: {}".format("depth", get_ast_depth(And(*constraints))))

if __name__ == "__main__":
    test()