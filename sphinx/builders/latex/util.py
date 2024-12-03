"""Utilities for LaTeX builder."""
from __future__ import annotations
from docutils.writers.latex2e import Babel

class ExtBabel(Babel):
    cyrillic_languages = ('bulgarian', 'kazakh', 'mongolian', 'russian', 'ukrainian')

    def __init__(self, language_code: str, use_polyglossia: bool=False) -> None:
        self.language_code = language_code
        self.use_polyglossia = use_polyglossia
        self.supported = True
        super().__init__(language_code)

    def get_mainlanguage_options(self) -> str | None:
        """Return options for polyglossia's ``\\setmainlanguage``."""
        if not self.use_polyglossia:
            return None

        options = []
        
        if self.language_code == 'english':
            options.append('variant=american')
        elif self.language_code in self.cyrillic_languages:
            options.append('spelling=modern')
        elif self.language_code == 'greek':
            options.append('variant=monotonic')
        elif self.language_code == 'sanskrit':
            options.append('script=Devanagari')

        if options:
            return '[' + ','.join(options) + ']'
        else:
            return None
