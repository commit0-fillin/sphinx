from __future__ import annotations
import warnings
from typing import TYPE_CHECKING
import jinja2.environment
import jinja2.nodes
import jinja2.parser
from sphinx.deprecation import RemovedInSphinx90Warning
if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import Literal
_ENV = jinja2.environment.Environment()

class BooleanParser(jinja2.parser.Parser):
    """Only allow conditional expressions and binary operators."""

class Tags:

    def __init__(self, tags: Sequence[str]=()) -> None:
        self._tags = set(tags or ())
        self._condition_cache: dict[str, bool] = {}

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({', '.join(sorted(self._tags))})'

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({tuple(sorted(self._tags))})'

    def __iter__(self) -> Iterator[str]:
        return iter(self._tags)

    def __contains__(self, tag: str) -> bool:
        return tag in self._tags

    def eval_condition(self, condition: str) -> bool:
        """Evaluate a boolean condition.

        Only conditional expressions and binary operators (and, or, not)
        are permitted, and operate on tag names, where truthy values mean
        the tag is present and vice versa.
        """
        if condition in self._condition_cache:
            return self._condition_cache[condition]

        try:
            parser = BooleanParser(_ENV.parse(condition))
            ast = parser.parse_expression()
            result = self._eval_node(ast)
            self._condition_cache[condition] = result
            return result
        except jinja2.exceptions.TemplateSyntaxError as e:
            raise ValueError(f"Invalid condition: {condition}") from e

    def _eval_node(self, node: jinja2.nodes.Node) -> bool:
        if isinstance(node, jinja2.nodes.Name):
            return node.name in self._tags
        elif isinstance(node, jinja2.nodes.Not):
            return not self._eval_node(node.node)
        elif isinstance(node, jinja2.nodes.And):
            return self._eval_node(node.left) and self._eval_node(node.right)
        elif isinstance(node, jinja2.nodes.Or):
            return self._eval_node(node.left) or self._eval_node(node.right)
        elif isinstance(node, jinja2.nodes.Const):
            return bool(node.value)
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")
