from dataclasses import dataclass
import json

DEFAULT_MEASUREMENTS = {
    "height": 1700.0,
    "chest": 900.0,
    "waist": 760.0,
    "hip": 960.0,
    "shoulder": 420.0,
}


@dataclass(frozen=True)
class AvatarParameters:
    measurements: dict
    skin_offset: float = 0.0
    pose: str = "standing"

    def __post_init__(self):
        values = dict(DEFAULT_MEASUREMENTS)
        values.update({str(k): float(v) for k, v in self.measurements.items()})
        object.__setattr__(self, "measurements", values)
        self.validate()

    def validate(self):
        for name in DEFAULT_MEASUREMENTS:
            if float(self.measurements[name]) <= 0:
                raise ValueError("%s measurement must be positive" % name)
        if self.measurements["waist"] >= self.measurements["chest"]:
            raise ValueError("waist must be smaller than chest")
        if float(self.skin_offset) < 0:
            raise ValueError("skin offset must not be negative")
        if self.pose not in ("standing", "sewing", "sitting"):
            raise ValueError("unsupported avatar pose: %s" % self.pose)

    def measurement(self, name):
        if name not in self.measurements:
            raise KeyError(name)
        return float(self.measurements[name])

    def to_json(self):
        return json.dumps({
            "schema_version": 1,
            "units": "mm",
            "measurements": dict(sorted(self.measurements.items())),
            "skin_offset": float(self.skin_offset),
            "pose": self.pose,
        }, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload):
        data = json.loads(str(payload))
        if int(data.get("schema_version", 1)) != 1:
            raise ValueError("unsupported avatar schema version")
        return cls(data.get("measurements", {}), float(data.get("skin_offset", 0.0)),
                   str(data.get("pose", "standing")))
