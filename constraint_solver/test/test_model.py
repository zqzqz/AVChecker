import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from av_solver.model import *
import logging

logging.basicConfig(level=logging.DEBUG)

def test():
    cx = Real("cx")
    cy = Real("cy")
    c = Point(cx, cy, "c")
    def line0(x, y):
        return And(x == 0, y >= 0)
    l0 = Line(line0, "l0")
    def line1(x, y):
        return y == 1 - x
    l1 = Line(line1, "l1")
    cross = is_two_lines_cross(c, l0, l1)
    print(cross)
    solve(cross)
    solve(And(is_point_on_line(c, l0), is_point_on_line(c, l1)))

if __name__ == "__main__":
    test()