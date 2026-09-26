#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_tissu_headless.py <CMakeLists.txt>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

source_block = """    src/io/SceneExporter.cpp
    src/io/AlembicExporter.cpp
    src/io/StateSerializer.cpp"""
source_replacement = """    src/io/SceneExporter.cpp
    src/io/StateSerializer.cpp"""
dependency_block = """if(NOT TARGET Alembic::Alembic)
    find_package(Alembic REQUIRED)
endif()
if(NOT TARGET Imath::Imath)
    find_package(Imath REQUIRED)
endif()

"""
link_block = """target_link_libraries(TissuCore PUBLIC 
    Alembic::Alembic 
    Imath::Imath
)
"""

for label, old, new in (
    ("Alembic source entry", source_block, source_replacement),
    ("Alembic dependency discovery", dependency_block, ""),
    ("Alembic link block", link_block, ""),
):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"headless Tissu patch expected exactly one {label}, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
