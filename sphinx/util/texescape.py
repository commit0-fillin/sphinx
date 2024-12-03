"""TeX escaping helper."""
from __future__ import annotations
import re
tex_replacements = [('$', '\\$'), ('%', '\\%'), ('&', '\\&'), ('#', '\\#'), ('_', '\\_'), ('{', '\\{'), ('}', '\\}'), ('\\', '\\textbackslash{}'), ('~', '\\textasciitilde{}'), ('^', '\\textasciicircum{}'), ('[', '{[}'), (']', '{]}'), ('✓', '\\(\\checkmark\\)'), ('✔', '\\(\\pmb{\\checkmark}\\)'), ('✕', '\\(\\times\\)'), ('✖', '\\(\\pmb{\\times}\\)'), ('\ufeff', '{}'), ('⎽', '\\_'), ('ℯ', 'e'), ('ⅈ', 'i')]
ascii_tex_replacements = [('-', '\\sphinxhyphen{}'), ("'", '\\textquotesingle{}'), ('`', '\\textasciigrave{}'), ('<', '\\textless{}'), ('>', '\\textgreater{}')]
unicode_tex_replacements = [('¶', '\\P{}'), ('§', '\\S{}'), ('€', '\\texteuro{}'), ('∞', '\\(\\infty\\)'), ('±', '\\(\\pm\\)'), ('→', '\\(\\rightarrow\\)'), ('‣', '\\(\\rightarrow\\)'), ('–', '\\textendash{}'), ('⁰', '\\(\\sp{\\text{0}}\\)'), ('¹', '\\(\\sp{\\text{1}}\\)'), ('²', '\\(\\sp{\\text{2}}\\)'), ('³', '\\(\\sp{\\text{3}}\\)'), ('⁴', '\\(\\sp{\\text{4}}\\)'), ('⁵', '\\(\\sp{\\text{5}}\\)'), ('⁶', '\\(\\sp{\\text{6}}\\)'), ('⁷', '\\(\\sp{\\text{7}}\\)'), ('⁸', '\\(\\sp{\\text{8}}\\)'), ('⁹', '\\(\\sp{\\text{9}}\\)'), ('₀', '\\(\\sb{\\text{0}}\\)'), ('₁', '\\(\\sb{\\text{1}}\\)'), ('₂', '\\(\\sb{\\text{2}}\\)'), ('₃', '\\(\\sb{\\text{3}}\\)'), ('₄', '\\(\\sb{\\text{4}}\\)'), ('₅', '\\(\\sb{\\text{5}}\\)'), ('₆', '\\(\\sb{\\text{6}}\\)'), ('₇', '\\(\\sb{\\text{7}}\\)'), ('₈', '\\(\\sb{\\text{8}}\\)'), ('₉', '\\(\\sb{\\text{9}}\\)')]
tex_replace_map: dict[int, str] = {}
_tex_escape_map: dict[int, str] = {}
_tex_escape_map_without_unicode: dict[int, str] = {}
_tex_hlescape_map: dict[int, str] = {}
_tex_hlescape_map_without_unicode: dict[int, str] = {}

def escape(s: str, latex_engine: str | None=None) -> str:
    """Escape text for LaTeX output."""
    if latex_engine == 'platex':
        escape_map = _tex_escape_map_without_unicode
    else:
        escape_map = _tex_escape_map
    return ''.join(escape_map.get(ord(c), c) for c in s)

def hlescape(s: str, latex_engine: str | None=None) -> str:
    """Escape text for LaTeX highlighter."""
    if latex_engine == 'platex':
        escape_map = _tex_hlescape_map_without_unicode
    else:
        escape_map = _tex_hlescape_map
    return ''.join(escape_map.get(ord(c), c) for c in s)

def escape_abbr(text: str) -> str:
    """Adjust spacing after abbreviations. Works with @ letter or other."""
    return re.sub(r'\.(?=\s|$)', r'.\@{}', text)
