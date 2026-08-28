import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternFeature import rectangle


def test_feature_outline_is_deterministic():
    first = rectangle(180, 120).sampled_outline()
    second = rectangle(180, 120).sampled_outline()
    assert first == second
    assert json.dumps(first, separators=(",", ":")) == json.dumps(second, separators=(",", ":"))


def test_feature_dimensions_are_positive():
    for dimensions in ((1, 1), (100, 60), (180, 120)):
        outline = rectangle(*dimensions).sampled_outline()
        assert len(outline) == 4
        assert max(x for x, _ in outline) == dimensions[0]
        assert max(y for _, y in outline) == dimensions[1]


def run():
    for name, fn in globals().copy().items():
        if name.startswith("test_"):
            fn()
    print("pattern feature tests passed")


if __name__ == "__main__":
    run()
