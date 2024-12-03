"""Measure document reading durations."""
from __future__ import annotations
import time
from itertools import islice
from operator import itemgetter
from typing import TYPE_CHECKING, cast
import sphinx
from sphinx.domains import Domain
from sphinx.locale import __
from sphinx.util import logging
if TYPE_CHECKING:
    from typing import TypedDict
    from docutils import nodes
    from sphinx.application import Sphinx

    class _DurationDomainData(TypedDict):
        reading_durations: dict[str, float]
logger = logging.getLogger(__name__)

class DurationDomain(Domain):
    """A domain for durations of Sphinx processing."""
    name = 'duration'

def on_builder_inited(app: Sphinx) -> None:
    """Initialize DurationDomain on bootstrap.

    This clears the results of the last build.
    """
    app.env.duration_data = {'reading_durations': {}}

def on_source_read(app: Sphinx, docname: str, content: list[str]) -> None:
    """Start to measure reading duration."""
    app.env.duration_data['reading_durations'][docname] = time.time()

def on_doctree_read(app: Sphinx, doctree: nodes.document) -> None:
    """Record a reading duration."""
    docname = app.env.docname
    start_time = app.env.duration_data['reading_durations'].get(docname)
    if start_time:
        duration = time.time() - start_time
        app.env.duration_data['reading_durations'][docname] = duration

def on_build_finished(app: Sphinx, error: Exception) -> None:
    """Display duration ranking on the current build."""
    if not error:
        durations = app.env.duration_data['reading_durations']
        sorted_durations = sorted(durations.items(), key=itemgetter(1), reverse=True)
        
        logger.info("Document reading durations:")
        for docname, duration in islice(sorted_durations, 10):  # Display top 10
            logger.info(f"{docname}: {duration:.2f} seconds")
