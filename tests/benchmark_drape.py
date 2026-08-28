"""Deterministic reference-backend benchmark artifact for CI."""
import json
from pathlib import Path
from ClothSolver import ClothSystem
from DrapeQuality import benchmark

result = benchmark(lambda: ClothSystem.grid(30, 15, nx=4, ny=3), steps=30, iterations=8, repeats=2, gravity=(0, 0, -98.1))
out = Path("artifacts/drape-benchmark.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(out)
