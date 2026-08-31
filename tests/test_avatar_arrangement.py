import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from AvatarArrangement import ARRANGEMENT_POINT_NAMES, arrangement_point_map, arrangement_points_from_landmarks


def test_arrangement_points_are_stable_and_landmark_backed():
    landmarks = [
        "knee_right|55,0,400", "unknown|0,0,0", "waist|0,0,900",
        "shoulder_left|-210,0,1050", "neck|0,0,1150", "malformed",
        "hip|0,0,700", "shoulder_right|210,0,1050", "chest|0,0,980",
        "knee_left|-55,0,400",
    ]
    points = arrangement_points_from_landmarks(landmarks)
    assert [record.split("|", 1)[0] for record in points] == list(ARRANGEMENT_POINT_NAMES)
    assert arrangement_point_map(points)["shoulder_left"] == "-210,0,1050"
    assert arrangement_point_map(points)["knee_right"] == "55,0,400"


def test_arrangement_points_ignore_unknown_and_malformed_records():
    assert arrangement_points_from_landmarks(["unknown|1,2,3", "bad"]) == []
    assert arrangement_point_map(["unknown|1,2,3", "bad"]) == {}


def test_arrangement_points_replace_duplicate_landmark_with_last_valid_value():
    points = arrangement_points_from_landmarks(["waist|0,0,900", "waist|0,0,905", "neck|0,0,1150"])
    assert points == ["neck|0,0,1150", "waist|0,0,905"]
