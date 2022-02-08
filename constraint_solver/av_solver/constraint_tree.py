from z3 import *
import argparse
import re
from .variable_controller import VariableController
from .objects import split_obj_name, assemble_obj_name
from .model import *
from .api import *
import logging


class Node:
    
    def __init__(self, value=None):
        self.value = value
        self.sons = []
        self.parent = None
        self.constraint = None

    def set_sons(self, sons):
        assert(isinstance(sons, list))
        for son in sons:
            assert(isinstance(son, Node))
        self.sons = sons

    def add_son(self, son):
        assert(isinstance(son, Node))
        self.sons.append(son)
        son.parent = self

    def set_parent(self, parent):
        assert(isinstance(parent, Node))
        self.parent = parent
        parent.sons.append(self)

    def remove(self):
        self.parent.sons.remove(self)

    def is_root(self):
        return self.parent == None

    def is_leaf(self):
        return len(self.sons) == 0

    def is_variable(self):
        return self.is_leaf()

    def is_operator(self):
        return not self.is_leaf()

    def walk(self, action, order=2):
        if order == 1:
            # Pre-Order Traversal
            action(self)
            for son in self.sons:
                son.walk(action, order)
        if order == 2:
            # Post-Order Traversal
            for son in self.sons:
                son.walk(action, order)
            action(self)

    def __repr__(self):
        return str(self.value)

    def printout(self, result=""):
        result += self.value
        if len(self.sons) > 0:
            result += "("
            for son in self.sons:
                result += son.printout()
                if son != self.sons[-1]:
                    result += ","
            result += ")"
        return result

    @property
    def args(self):
        res = []
        for s in self.sons:
            res.append(s.constraint)
        return res


class ConstraintTree:

    def __init__(self, var_control):
        self.root = Node("root")
        self.var_control = var_control
        self.api = APIHandler()
        self.operator_list = ["and", "or", "not", "==", ">", ">=", "<", "<=", "!=", "inside", "cross", "+", "-", "*", "/", "abs", "all", "any", "function"] + self.api._api_list()
        self.macro_list = ["red", "yellow", "green", "unknown", "left", "straight", "right"]
        # TODO: all / any logic for vehicles and pedestrians
        self.prefix_list = [] # ["vehicle", "pedestrian"]

    def _get_constraint(self, node):
        if not node.is_operator():
            return node.value
        if node.value == "root":
            return node.sons[0].constraint
        elif node.value == "and":
            return And(*[son.constraint for son in node.sons])
        elif node.value == "or":
            return Or(*[son.constraint for son in node.sons])
        elif node.value == "not":
            assert(len(node.sons) == 1)
            return Not(node.sons[0].constraint)
        elif node.value == "==":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint == node.sons[1].constraint
        elif node.value == "!=":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint != node.sons[1].constraint
        elif node.value == ">":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint > node.sons[1].constraint
        elif node.value == ">=":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint >= node.sons[1].constraint
        elif node.value == "<":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint < node.sons[1].constraint
        elif node.value == "<=":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint <= node.sons[1].constraint
        elif node.value == "+":
            assert(len(node.sons) >= 2)
            res = 0
            for s in node.sons:
                res = res + s.constraint
            return res
        elif node.value == "-":
            assert(len(node.sons) == 1 or len(node.sons) == 2)
            if len(node.sons) == 1:
                return -node.sons[0].constraint
            if len(node.sons) == 2:
                return node.sons[0].constraint - node.sons[1].constraint
        elif node.value == "*":
            assert(len(node.sons) >= 2)
            res = 1
            for s in node.sons:
                res = res * s.constraint
            return res
        elif node.value == "/":
            assert(len(node.sons) == 2)
            return node.sons[0].constraint / node.sons[1].constraint
        elif node.value == "abs":
            assert(len(node.sons) == 1)
            return z3_abs(node.sons[0].constraint)
        elif node.value == "function":
            assert(len(node.sons) > 0)
            # the first son should be a function call
            return node.sons[0].value(*[son.constraint for son in node.sons[1:]])
        else:
            return self.api._call(node.value, node.args)

    def _constraint_action(self, node):
        logging.debug("walking {} with sons {}".format(node, node.sons))
        node.constraint = self._get_constraint(node)

    def build(self, data):
        data = re.sub("\s+", "", data)
        token_list = re.split('(\(|\)|,)', data)
        # a fix
        token_list = list(filter(lambda x : x != "", token_list))
        # FSM and stack
        state = 0
        node_stack = [self.root]
        for token in token_list:
            logging.debug("parse {} with stack {}".format(token, node_stack))

            if len(node_stack) > 0:
                cur_node = node_stack[-1]
            else:
                cur_node = None
            
            if state == 0:
                if self.is_operator(token):
                    new_node = Node()
                    new_node.set_parent(cur_node)
                    new_node.value = token
                    node_stack.append(new_node)
                    state = 1
                elif self.is_literal(token):
                    son_node = Node()
                    son_node.set_parent(cur_node)
                    son_node.value = self.str_to_literal(token)
                    son_node.constraint = son_node.value
                    state = 2
                elif self.is_macro(token):
                    son_node = Node()
                    son_node.set_parent(cur_node)
                    son_node.value = token
                    son_node.constraint = son_node.value
                    state = 2
                elif self.is_var(token):
                    var = self.var_control.get_var(None, token)
                    son_node = Node()
                    son_node.set_parent(cur_node)
                    son_node.value = var
                    son_node.constraint = son_node.value
                    state = 2
                elif self.is_prefix(token):
                    son_node = Node()
                    son_node.set_parent(cur_node)
                    son_node.value = token
                    son_node.constraint = son_node.value
                    state = 2
                else:
                    raise Exception("build failed")
            elif state == 1:
                assert(token == "(")
                state = 0
            elif state == 2:
                if token == ",":
                    state = 0
                elif token == ")":
                    node_stack.pop()
                    state = 2
            else:
                raise Exception("build failed")

        self.root.walk(self._constraint_action)
        return simplify(self.constraint)
                
    def is_operator(self, data):
        return isinstance(data, str) and data in self.operator_list

    def is_var(self, data):
        return isinstance(data, str) and self.var_control.get_var(None, data) is not None

    def is_literal(self, data):
        return self.str_to_literal(data) != None

    def is_macro(self, data):
        return isinstance(data, str) and data in self.macro_list

    def is_prefix(self, data):
        return isinstance(data, str) and data in self.prefix_list

    def str_to_literal(self, data):
        if not isinstance(data, str):
            return None
        elif re.match("^[0-9]+$", data):
            return int(data)
        elif re.match("^[0-9]+\.[0-9]+$", data):
            return float(data)
        elif re.match("^(True|False)$", data):
            return data == "True"
        else:
            return None

    @property
    def constraint(self):
        assert(self.root != None)
        return self.root.constraint

    @property
    def op_count(self):
        count = 0
        stack = [self.root]
        while len(stack) > 0:
            node = stack.pop()
            if self.is_operator(node.value):
                count += 1
            for son in node.sons:
                stack.append(son)
        return count
