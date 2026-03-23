# Python Conventions — agent_tools/

All Python code in `agent_tools/` follows these conventions. Referenced by `sde`, `test-eng`, and `python-reviewer`.

## Style: PEP 8

Follow [PEP 8](https://peps.python.org/pep-0008/) with these project-specific additions.

## Naming

**DO:**
```python
def process_thumbnail(input_path: Path) -> Path:  # snake_case functions
    max_retries = 3                                 # snake_case variables
    DEFAULT_CODEC = "h264"                          # UPPER_SNAKE constants

class ThumbnailGenerator:                           # PascalCase classes
    pass
```

**DON'T:**
```python
def ProcessThumbnail(inputPath):    # camelCase / PascalCase functions
    maxRetries = 3                  # camelCase variables
    defaultCodec = "h264"           # camelCase constants
```

## Type Hints

**DO:**
```python
def resize_image(path: Path, width: int, height: int = 720) -> Image:
    """Resize image to target dimensions."""
    ...

def find_videos(content_dir: Path) -> list[Path]:
    return sorted(content_dir.glob("*.mp4"))

# Use Optional for nullable
def get_config(key: str) -> str | None:
    return os.getenv(key)
```

**DON'T:**
```python
def resize_image(path, width, height=720):  # no hints
    ...

def find_videos(content_dir):               # no return type
    return sorted(content_dir.glob("*.mp4"))
```

## Paths

**DO:**
```python
from pathlib import Path

output = content_dir / "assets" / "thumbnail.png"
videos = sorted(raw_dir.glob("*.mp4"))
if output.exists():
    output.unlink()
```

**DON'T:**
```python
import os

output = os.path.join(content_dir, "assets", "thumbnail.png")
videos = os.listdir(raw_dir)
output = content_dir + "/assets/" + "thumbnail.png"  # string concat
```

## Logging

**DO:**
```python
import logging

logger = logging.getLogger(__name__)

def run_pipeline(config: dict) -> None:
    logger.info("Starting pipeline", extra={"config_keys": list(config.keys())})
    try:
        result = execute(config)
        logger.info("Pipeline complete", extra={"status": result.status})
    except PipelineError as e:
        logger.error("Pipeline failed", extra={"error": str(e)})
        raise
```

**DON'T:**
```python
def run_pipeline(config):
    print("Starting pipeline")          # print instead of logging
    try:
        result = execute(config)
        print(f"Done: {result}")
    except Exception as e:
        print(f"Error: {e}")            # swallowed exception
```

## Error Handling

**DO:**
```python
# Catch specific exceptions, re-raise or handle
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    logger.error("Invalid JSON", extra={"error": str(e)})
    raise

# Guard with early returns
def process(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Missing: {path}")
    ...
```

**DON'T:**
```python
# Bare except
try:
    data = json.loads(raw)
except:
    pass

# Catching Exception and swallowing
try:
    data = json.loads(raw)
except Exception:
    data = {}  # silent fallback hides bugs
```

## Imports

**DO:**
```python
# stdlib
import logging
from pathlib import Path

# third-party
import PIL
from PIL import Image

# local
from .utils import resize
```

**DON'T:**
```python
from PIL import *              # wildcard imports
import os, sys, json           # multi-import on one line
```

## Docstrings

**DO:**
```python
def extract_frame(video_path: Path, timestamp: float) -> Image:
    """Extract a single frame from video at the given timestamp.

    Args:
        video_path: Path to source video file.
        timestamp: Time in seconds to extract frame from.

    Returns:
        PIL Image of the extracted frame.

    Raises:
        FileNotFoundError: If video_path does not exist.
    """
    ...
```

**DON'T:**
```python
def extract_frame(video_path, timestamp):
    # extracts frame            # comment instead of docstring
    ...

def extract_frame(video_path: Path, timestamp: float) -> Image:
    """This function extracts a frame."""  # vague, no args/returns
    ...
```

## Secrets

**DO:**
```python
api_key = os.getenv("SERVICE_API_KEY")
if not api_key:
    sys.exit("Error: SERVICE_API_KEY env var required")
```

**DON'T:**
```python
API_KEY = "sk-1234567890abcdef"                           # hardcoded
COLLECTION_ID = os.getenv("ID", "6909de531658318c10b3")   # hardcoded fallback
parser.add_argument("--api-token")                        # secrets via CLI args
```

## Size Limits

| Scope | Max Lines |
|-------|-----------|
| Function | 50 |
| Class | 300 |
| File | 500 |

Extract helpers, split modules, decompose classes when limits are hit.

## uv & Execution

**DO:**
```bash
uv run --directory agent_tools/<tool> python script.py
uv add --directory agent_tools/<tool> some-package
```

**DON'T:**
```bash
python3 agent_tools/<tool>/script.py                  # system python
agent_tools/<tool>/venv/bin/python script.py           # venv path
source agent_tools/<tool>/venv/bin/activate             # source activate
pip install some-package                                # system pip
```

## Testing Conventions

**DO:**
```python
# One concern per test, descriptive name
class TestResizeImage:
    def test_resize_landscape_returns_correct_dimensions(self, tmp_path: Path) -> None:
        img = create_test_image(tmp_path, width=1920, height=1080)
        result = resize_image(img, width=640)
        assert result.size == (640, 360)

    def test_resize_zero_width_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="width must be positive"):
            resize_image(img, width=0)

    @pytest.mark.parametrize("width,expected_height", [
        (1920, 1080),
        (1280, 720),
        (640, 360),
    ])
    def test_resize_preserves_aspect_ratio(self, width: int, expected_height: int) -> None:
        result = resize_image(landscape_img, width=width)
        assert result.size[1] == expected_height
```

```python
# Fixtures in conftest.py
@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    video = tmp_path / "test.mp4"
    video.write_bytes(b"\x00" * 1024)
    return video
```

**DON'T:**
```python
# Multiple concerns, bad name, no type hints
def test_stuff():
    assert resize(img, 640) is not None
    assert resize(img, 0) is None
    assert resize(img, -1) is None

# Real content folders
path = Path("content/2026-01-08-casino/raw_video/")

# Print instead of assert
def test_output():
    print(resize(img, 640))

# Tests that depend on each other
result = None
def test_step_1():
    global result
    result = create_something()

def test_step_2():
    process(result)  # depends on test_step_1 running first
```

| Rule | Detail |
|------|--------|
| Fixtures | `tmp_path` for files, `monkeypatch` for env vars, `conftest.py` for shared |
| Mocking | Mock at boundaries only (filesystem, APIs, subprocess, network) |
| Assertions | One concern per test, specific values, `pytest.raises` for exceptions |
| Naming | `test_<function>_<scenario>_<expected>` |
| Parametrize | Same logic, different inputs |
| Independence | No shared state, no order dependence |
| Test data | `test_content/` or `tmp_path`, NEVER real `content/` folders |
