import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from av_solver.variable_controller import VariableController
import logging

logging.basicConfig(level=logging.DEBUG)


def test():
    controller = VariableController()
    controller.add_constraint("code", controller.get_var("code", "is_path_cross"))
    controller.add_constraint("user", controller.get_var("user", "is_pedestrian_on_crosswalk"))
    controller.solve()

if __name__ == "__main__":
    test()
