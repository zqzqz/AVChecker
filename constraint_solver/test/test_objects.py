import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from av_solver.objects import *
from av_solver.util import *
import logging
from z3 import *

logging.basicConfig(level=logging.DEBUG)

def test():
    objs = [Road(""), Lane(""), Vehicle(""), Pedestrian(""), Bicycle(""), Crosswalk(""), StopSign(""), TrafficLight(""), Intersection("")]
    for obj in objs:
        logging.warn("{} -- var: {}, op: {}, depth: {}".format(
            obj.name,
            count_base_variable(obj.get_variables()),
            count_operator(And(*obj.constraints)),
            get_ast_depth(And(*obj.constraints))
        ))

if __name__ == "__main__":
    test()