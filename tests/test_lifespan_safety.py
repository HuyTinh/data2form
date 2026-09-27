import asyncio
from contextlib import chdir
from pathlib import Path
import tempfile
import unittest

import app


class ApplicationLifespanSafetyTests(unittest.TestCase):
    def test_startup_preserves_static_png_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            static_dir = Path(temp_dir) / "static"
            static_dir.mkdir()
            image = static_dir / "user-asset.png"
            image.write_bytes(b"not-a-favicon")

            async def run_lifespan():
                async with app.lifespan(app.app):
                    self.assertTrue(image.exists())

            with chdir(temp_dir):
                asyncio.run(run_lifespan())


if __name__ == "__main__":
    unittest.main()
