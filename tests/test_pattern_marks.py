import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PatternMarks import add_mark


class Obj:
    def __init__(self, name):
        self.Name = name
        self.Label = name

    def addProperty(self, _type, name, _group):
        setattr(self, name, None)
        return self


class Doc:
    def __init__(self):
        self.Objects = []

    def addObject(self, _type, name):
        obj = Obj(name)
        self.Objects.append(obj)
        return obj


def test_add_mark_persists_semantic_reference():
    doc = Doc()
    mark = add_mark(doc, "Notch", "pattern-piece-1", "bottom", 0.25)
    assert mark.PatternMarkType == "Notch"
    assert mark.PieceId == "pattern-piece-1"
    assert mark.SegmentId == "bottom"
    assert mark.Position == 0.25
    assert mark.Depth == 3.0


def test_add_mark_rejects_invalid_position():
    try:
        add_mark(Doc(), "Notch", "piece", "bottom", 1.1)
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("invalid mark position should fail")


if __name__ == "__main__":
    test_add_mark_persists_semantic_reference()
    test_add_mark_rejects_invalid_position()
    print("Pattern mark tests passed")
