"""Assets adapter for sphinx.environment."""
from sphinx.environment import BuildEnvironment
from sphinx.util._pathlib import _StrPath

class ImageAdapter:

    def __init__(self, env: BuildEnvironment) -> None:
        self.env = env

    def get_original_image_uri(self, name: str) -> str:
        """Get the original image URI."""
        if name in self.env.images:
            return self.env.images[name][0]
        return name
