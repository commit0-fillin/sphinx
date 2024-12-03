"""Docutils-native XML and pseudo-XML writers."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from docutils.writers.docutils_xml import Writer as BaseXMLWriter
if TYPE_CHECKING:
    from sphinx.builders import Builder

class XMLWriter(BaseXMLWriter):
    output: str

    def __init__(self, builder: Builder) -> None:
        super().__init__()
        self.builder = builder
        self.translator_class = lambda document: self.builder.create_translator(document)

class PseudoXMLWriter(BaseXMLWriter):
    supported = ('pprint', 'pformat', 'pseudoxml')
    'Formats this writer supports.'
    config_section = 'pseudoxml writer'
    config_section_dependencies = ('writers',)
    output: str
    'Final translated form of `document`.'

    def __init__(self, builder: Builder) -> None:
        super().__init__()
        self.builder = builder

    def supports(self, format: str) -> bool:
        """All format-specific elements are supported."""
        return True
