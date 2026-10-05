"""Validate canonical simulation and visual evidence manifests."""

from __future__ import annotations

# ruff: isort: skip_file

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path("artifacts/simulation-ladder")
CHECKPOINTS = [0, 1, 5, 15, 45, 90]


def read(path: Path) -> dict:
    if not path.is_file() or not path.stat().st_size:
        raise SystemExit(f"missing manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_simulation() -> None:
    specs = (
        ("cube", ROOT / "cube-ladder-manifest.json", 5, 3.0, "simulation-collision-ladder"),
        ("avatar", ROOT / "avatar-ladder-manifest.json", 5, 8.0, "simulation-avatar-ladder"),
    )
    for name, path, count, max_penetration, purpose in specs:
        data = read(path)
        if data.get("schema") != 1 or data.get("purpose") != purpose:
            raise SystemExit(f"{name}: invalid manifest header")
        if data.get("release_gate_effect") != "gate":
            raise SystemExit(f"{name}: not a release gate")
        if len(data.get("cases", ())) != count:
            raise SystemExit(f"{name}: unexpected case count")
        for case in data["cases"]:
            if not case.get("finite"):
                raise SystemExit(f"{name}: non-finite case")
            if case.get("solver", {}).get("backend") != "pbd":
                raise SystemExit(f"{name}: wrong backend")
            if len(case.get("checkpoints", ())) != 6:
                raise SystemExit(f"{name}: unexpected checkpoint count")
            if case.get("max_penetration_mm", 0) > max_penetration + 1e-6:
                raise SystemExit(f"{name}: penetration too large")
            for image in case.get("images", ()):
                if not (ROOT / image).is_file():
                    raise SystemExit(f"{name}: missing image {image}")
        if data.get("structural_validation", {}).get("first_failing_rung") is not None:
            raise SystemExit(f"{name}: structural rung failed")
        print(f"{name}-collision-ladder=passed")


def validate_turntables() -> None:
    root = Path("docs/images/generated")
    directories = (
        "cloth-avatar-turntable-frames",
        "cloth-simulation-arranged-turntable-frames",
        "cloth-simulation-draped-turntable-frames",
    )
    for directory in directories:
        frames = sorted((root / directory).glob("frame-*.png"))
        if len(frames) != 73:
            raise SystemExit(f"{directory}: expected 73 frames, got {len(frames)}")
        hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in frames}
        if len(hashes) != 73:
            raise SystemExit(f"{directory}: duplicate frame hashes")
        checkpoints = []
        for frame in (0, 18, 36, 54):
            path = root / directory / f"frame-{frame:03d}.png"
            if not path.is_file():
                raise SystemExit(f"{directory}: missing checkpoint {frame}")
            checkpoints.append(hashlib.sha256(path.read_bytes()).hexdigest())
        if len(set(checkpoints)) != 4:
            raise SystemExit(f"{directory}: camera checkpoints are not distinct")

    log = root / "simulation-turntable-progress.log"
    text = log.read_text(encoding="utf-8")
    for marker in (
        "stage=scene-build-pass",
        "stage=arranged-render-pass",
        "stage=simulation-pass",
        "stage=validation-pass",
        "stage=draped-render-pass",
        "stage=total-pass",
        "blanket-turntable-pass",
        "mesh-quality=passed",
    ):
        if marker not in text:
            raise SystemExit(f"turntable: missing marker {marker}")
    displacement = re.findall(
        r"blanket-motion-diagnostic max_centroid_displacement_mm=([+-]?[0-9.]+)",
        text,
    )
    if not displacement or float(displacement[-1]) < 40.0:
        raise SystemExit("turntable: insufficient blanket displacement")
    penetration = re.findall(
        r"collision-penetration=passed max_penetration_mm=([+-]?[0-9.]+)",
        text,
    )
    if not penetration or float(penetration[-1]) > 3.0:
        raise SystemExit("turntable: collision penetration gate failed")
    print("turntables=passed")


def validate_tunic() -> None:
    generated = Path("docs/images/generated")
    progress = generated / "gui-progress.log"
    metrics = Path("artifacts/freecad-realtime/metrics.json")
    if not progress.is_file() or not metrics.is_file():
        raise SystemExit("tunic: required evidence is missing")
    data = json.loads(metrics.read_text(encoding="utf-8"))
    if not data["finite"] or data["mean_frame_ms"] > data["frame_budget_ms"] or data["p95_frame_ms"] > 50.0:
        raise SystemExit(f"tunic: realtime performance gate failed: {data}")
    text = progress.read_text(encoding="utf-8")
    markers = (
        "scenario-pass",
        "realtime-preview=passed backend=position-based-dynamics",
        "drape-metrics=",
        "diagnostic-map=passed metric=stress",
        "diagnostic-stale-guard=passed",
    )
    if any(marker not in text for marker in markers):
        raise SystemExit("tunic: progress contract failed")
    for path in (
        generated / "cloth-simulation-draped.png",
        generated / "cloth-simulation-draped-front.png",
        generated / "cloth-simulation-draped-rear.png",
        generated / "cloth-simulation-draped-left.png",
        generated / "cloth-simulation-draped-right.png",
        generated / "cloth-simulation-draped-top.png",
        generated / "cloth-simulation-draped-bottom.png",
        generated / "cloth-simulation-draped-diagnostics.png",
        generated / "cloth-pattern-design.png",
        generated / "cloth-sewing.png",
    ):
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"tunic: missing image {path}")
    if len(list((generated / "cloth-tunic-mannequin-motion-frames").glob("motion-*.png"))) != 10:
        raise SystemExit("tunic: wrong mannequin motion frame count")
    e2e = Path("artifacts/garment-e2e.log").read_text(encoding="utf-8")
    for marker in (
        "staged-selection=passed",
        "sewing-mn=passed sides=2,2 segments=2",
        "sewing-mn-physical=passed curved-edge=true proportional=true",
        "seam-markers=passed 3d-and-2d=true",
        "arrangement=passed pieces=4",
        "garment-hierarchy=passed groups=Patterns,Sewing,Fabric,Avatar,Simulation",
        "material-presentation=passed native=true",
        "drape-target=passed type=Mannequin",
        "diagnostics=passed metric=stress",
        "save-reload=passed pieces=4 seam=1to1 network=2segment",
        "invalidation=passed seam=",
        "invalidation-restore=passed seam=Valid",
        "stale-export=blocked",
        "diagnostics-after-invalidation=passed metric=stress",
        "determinism-signature=passed",
        "pattern-export=passed formats=SVG,DXF",
        "canonical garment end-to-end acceptance passed",
    ):
        if marker not in e2e:
            raise SystemExit(f"tunic: missing E2E marker {marker}")
    print("tunic-visual=passed")


def validate_blanket() -> None:
    root = Path("docs/images/generated/blanket-example")
    log = root / "blanket-visual.log"
    if not log.is_file():
        raise SystemExit("blanket: missing log")
    text = log.read_text(encoding="utf-8")
    for marker in (
        "blanket-visual-acceptance=passed",
        "mesh=passed",
        "movement=passed",
        "material-presentation=passed viewport=true",
    ):
        if marker not in text:
            raise SystemExit(f"blanket: missing marker {marker}")
    if len(list(root.glob("checkpoint-*.png"))) != 5:
        raise SystemExit("blanket: expected 5 checkpoints")
    if len(list(root.glob("motion-*.png"))) != 16:
        raise SystemExit("blanket: expected 16 motion frames")
    print("blanket-visual=passed")


def validate_diagnostic() -> None:
    root = Path("artifacts/pbd-contact-diagnostics")
    for name, purpose, rung in (
        ("cube-ladder-manifest.json", "simulation-collision-ladder", range(1, 6)),
        ("avatar-ladder-manifest.json", "simulation-avatar-ladder", range(6, 11)),
    ):
        data = read(root / name)
        if data.get("schema") != 1 or data.get("purpose") != purpose:
            raise SystemExit(f"diagnostic {name}: invalid header")
        if data.get("release_gate_effect") != "gate":
            raise SystemExit(f"diagnostic {name}: wrong gate effect")
        if len(data.get("cases", ())) != 5:
            raise SystemExit(f"diagnostic {name}: wrong case count")
        for record, expected_rung in zip(data["cases"], rung, strict=True):
            if record.get("case", {}).get("rung") != expected_rung:
                raise SystemExit(f"diagnostic {name}: unexpected rung")
            if record.get("solver", {}).get("backend") != "pbd":
                raise SystemExit(f"diagnostic {name}: wrong backend")
            if record.get("solver", {}).get("substeps") != 1:
                raise SystemExit(f"diagnostic {name}: wrong substeps")
            if len(record.get("checkpoints", ())) != 6:
                raise SystemExit(f"diagnostic {name}: wrong checkpoints")
            for image in record.get("images", ()):
                candidate = root / ("cube-ladder" if "rung-" in image and "cube" in image else "")
                if not (root / image).is_file() and not candidate.is_file():
                    raise SystemExit(f"diagnostic {name}: missing image {image}")
    data = read(root / "manifest.json")
    if data.get("schema") != 1 or data.get("release_gate_effect") != "none":
        raise SystemExit("diagnostic contact manifest header failed")
    print("diagnostic-contact=passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "kind",
        choices=("simulation", "turntables", "tunic", "blanket", "diagnostic"),
    )
    args = parser.parse_args()
    {
        "simulation": validate_simulation,
        "turntables": validate_turntables,
        "tunic": validate_tunic,
        "blanket": validate_blanket,
        "diagnostic": validate_diagnostic,
    }[args.kind]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
