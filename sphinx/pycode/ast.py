"""Helpers for AST (Abstract Syntax Tree)."""
from __future__ import annotations
import ast
from typing import NoReturn, overload
OPERATORS: dict[type[ast.AST], str] = {ast.Add: '+', ast.And: 'and', ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^', ast.Div: '/', ast.FloorDiv: '//', ast.Invert: '~', ast.LShift: '<<', ast.MatMult: '@', ast.Mult: '*', ast.Mod: '%', ast.Not: 'not', ast.Pow: '**', ast.Or: 'or', ast.RShift: '>>', ast.Sub: '-', ast.UAdd: '+', ast.USub: '-'}

def unparse(node: ast.AST | None, code: str='') -> str | None:
    """Unparse an AST to string."""
    if node is None:
        return None
    visitor = _UnparseVisitor(code)
    return visitor.visit(node)

class _UnparseVisitor(ast.NodeVisitor):

    def __init__(self, code: str='') -> None:
        self.code = code
    for _op in OPERATORS:
        locals()[f'visit_{_op.__name__}'] = _visit_op

    def _visit_arg_with_default(self, arg: ast.arg, default: ast.AST | None) -> str:
        """Unparse a single argument to a string."""
        result = arg.arg
        if arg.annotation:
            result += ': ' + self.visit(arg.annotation)
        if default:
            result += ' = ' + self.visit(default)
        return result
