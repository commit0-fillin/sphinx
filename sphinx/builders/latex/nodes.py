"""Additional nodes for LaTeX writer."""
from docutils import nodes

class captioned_literal_block(nodes.container):
    """A node for a container of literal_block having a caption."""
    
    def __init__(self, rawsource='', *children, **attributes):
        super().__init__(rawsource, *children, **attributes)
        self.caption = None

    def set_caption(self, caption):
        self.caption = caption

class footnotemark(nodes.Inline, nodes.Referential, nodes.TextElement):
    """A node represents ``\\footnotemark``."""
    
    def __init__(self, rawsource='', text='', *children, **attributes):
        super().__init__(rawsource, text, *children, **attributes)
        self.number = None

    def set_number(self, number):
        self.number = number

class footnotetext(nodes.General, nodes.BackLinkable, nodes.Element, nodes.Labeled, nodes.Targetable):
    """A node represents ``\\footnotetext``."""
    
    def __init__(self, rawsource='', *children, **attributes):
        super().__init__(rawsource, *children, **attributes)
        self.number = None
        self.text = None

    def set_number(self, number):
        self.number = number

    def set_text(self, text):
        self.text = text

class math_reference(nodes.Inline, nodes.Referential, nodes.TextElement):
    """A node for a reference for equation."""
    
    def __init__(self, rawsource='', text='', *children, **attributes):
        super().__init__(rawsource, text, *children, **attributes)
        self.equation_number = None
        self.target = None

    def set_equation_number(self, number):
        self.equation_number = number

    def set_target(self, target):
        self.target = target

class thebibliography(nodes.container):
    """A node for wrapping bibliographies."""
    
    def __init__(self, rawsource='', *children, **attributes):
        super().__init__(rawsource, *children, **attributes)
        self.entries = []

    def add_entry(self, entry):
        self.entries.append(entry)

    def get_entries(self):
        return self.entries
HYPERLINK_SUPPORT_NODES = (nodes.figure, nodes.literal_block, nodes.table, nodes.section, captioned_literal_block)
