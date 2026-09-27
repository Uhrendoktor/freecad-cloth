#!/usr/bin/env python3
"""Apply the pinned Tissu contact-response fix with explicit topology metadata hints."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys


ROOT = Path("/tmp/Tissu")
EXPECTED_COMMIT = "c28a3c7504ddc782bef844ab5bd4cd0bde14b628"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def main() -> int:
    if run("git", "rev-parse", "HEAD") != EXPECTED_COMMIT:
        raise RuntimeError("Tissu source commit does not match the pinned revision")

    header = ROOT / "core/include/physics/MeshCollider.hpp"
    cpp_path = ROOT / "core/src/physics/MeshCollider.cpp"
    bindings = [
        ROOT / "python/src/bindings.cpp",
        ROOT / "python/src/bindings_headless.cpp",
    ]
    engine_py = ROOT / "python/tissu/engine.py"
    stub_py = ROOT / "python/tissu/_cloth_sdk_core.pyi"
    test = ROOT / "tests/physics/test_mesh_collider.cpp"

    replace_once(
        header,
        """#include <array>
#include <vector>""",
        """#include <array>
#include <vector>

#include <Eigen/Geometry>""",
        "MeshCollider.hpp Eigen geometry include",
    )

    replace_once(
        header,
        """    std::vector<Eigen::Vector3d> m_localVertices;
    std::vector<Eigen::Vector3d> m_worldVertices;
    std::vector<Triangle> m_triangles;
    BVH m_bvh;""",
        """    std::vector<Eigen::Vector3d> m_localVertices;
    std::vector<Eigen::Vector3d> m_worldVertices;
    std::vector<Triangle> m_triangles;
    bool m_closedManifold = false;
    double m_outwardNormalSign = 1.0;
    bool m_containmentBootstrapped = false;
    Eigen::AlignedBox3d m_worldBounds;
    BVH m_bvh;

    bool pointInsideClosedMesh(const Eigen::Vector3d& point) const;""",
        "MeshCollider.hpp member layout",
    )
    header_text = header.read_text(encoding="utf-8")
    old_signature = """    MeshCollider(const std::vector<Eigen::Vector3d>& vertices,
                 const std::vector<std::array<int, 3>>& triangles,
                 double friction);"""
    new_signature = """    MeshCollider(const std::vector<Eigen::Vector3d>& vertices,
                 const std::vector<std::array<int, 3>>& triangles,
                 double friction, bool closedManifold = false,
                 double outwardNormalSign = 1.0);"""
    if header_text.count(old_signature) != 1:
        raise RuntimeError("MeshCollider.hpp constructor anchor mismatch")
    header.write_text(header_text.replace(old_signature, new_signature, 1), encoding="utf-8")

    cpp = cpp_path.read_text(encoding="utf-8")
    include_old = """#include "physics/Particle.hpp"

namespace Tissu {"""
    include_new = """#include "physics/Particle.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace Tissu {"""
    if cpp.count(include_old) != 1:
        raise RuntimeError("MeshCollider.cpp include anchor mismatch")
    cpp = cpp.replace(include_old, include_new, 1)

    transform_old = """void MeshCollider::transform(const Eigen::Vector3d& position,
                             const Eigen::Quaterniond& rotation) {
    Collider::transform(position, rotation);

    for (size_t i = 0; i < m_localVertices.size(); ++i)
        m_worldVertices[i] = rotation * m_localVertices[i] + position;

    m_bvh.build(m_worldVertices, m_triangles);
}"""
    transform_new = """void MeshCollider::transform(const Eigen::Vector3d& position,
                             const Eigen::Quaterniond& rotation) {
    Collider::transform(position, rotation);

    for (size_t i = 0; i < m_localVertices.size(); ++i)
        m_worldVertices[i] = rotation * m_localVertices[i] + position;

    m_worldBounds.setEmpty();
    for (const auto& vertex : m_worldVertices)
        m_worldBounds.extend(vertex);
    m_containmentBootstrapped = false;

    m_bvh.build(m_worldVertices, m_triangles);
}"""
    if cpp.count(transform_old) != 1:
        raise RuntimeError("MeshCollider.cpp transform anchor mismatch")
    cpp = cpp.replace(transform_old, transform_new, 1)

    ctor_old = """MeshCollider::MeshCollider(const std::vector<Eigen::Vector3d>& vertices,
                           const std::vector<std::array<int, 3>>& triangles,
                           double friction)
    : m_localVertices(vertices), m_worldVertices(vertices) {
    m_friction = friction;

    m_triangles.reserve(triangles.size());
    for (const auto& tri : triangles) {
        m_triangles.emplace_back(tri[0], tri[1], tri[2]);
    }

    m_bvh.build(m_worldVertices, m_triangles);
}"""
    ctor_new = """MeshCollider::MeshCollider(const std::vector<Eigen::Vector3d>& vertices,
                           const std::vector<std::array<int, 3>>& triangles,
                           double friction, bool closedManifold,
                           double outwardNormalSign)
    : m_localVertices(vertices), m_worldVertices(vertices) {
    if (!std::isfinite(outwardNormalSign) ||
        std::abs(std::abs(outwardNormalSign) - 1.0) > 1.0e-12) {
        throw std::invalid_argument(
            "MeshCollider outwardNormalSign must be +1 or -1");
    }

    m_friction = friction;
    m_closedManifold = closedManifold;
    m_outwardNormalSign = outwardNormalSign;
    m_worldBounds.setEmpty();
    for (const auto& vertex : m_worldVertices)
        m_worldBounds.extend(vertex);

    m_triangles.reserve(triangles.size());
    for (const auto& tri : triangles) {
        m_triangles.emplace_back(tri[0], tri[1], tri[2]);
    }

    m_bvh.build(m_worldVertices, m_triangles);
}"""
    if cpp.count(ctor_old) != 1:
        raise RuntimeError("MeshCollider.cpp array-constructor anchor mismatch")
    cpp = cpp.replace(ctor_old, ctor_new, 1)

    resolve_old = """void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {"""
    resolve_new = """bool MeshCollider::pointInsideClosedMesh(
    const Eigen::Vector3d& point) const {
    if (!m_closedManifold || m_worldBounds.isEmpty() ||
        !m_worldBounds.contains(point))
        return false;

    const Eigen::Vector3d direction =
        Eigen::Vector3d(1.0, 0.3713906763541037, 0.6123724356957945)
            .normalized();
    const double scale = std::max(1.0, point.norm());
    const Eigen::Vector3d jitter =
        direction.cross(Eigen::Vector3d::UnitX()) * (1e-9 * scale);
    const Eigen::Vector3d origin = point + jitter;

    int intersections = 0;
    constexpr double epsilon = 1e-10;
    for (const auto& tri : m_triangles) {
        const Eigen::Vector3d& a = m_worldVertices[tri.a];
        const Eigen::Vector3d& b = m_worldVertices[tri.b];
        const Eigen::Vector3d& c = m_worldVertices[tri.c];
        const Eigen::Vector3d edge1 = b - a;
        const Eigen::Vector3d edge2 = c - a;
        const Eigen::Vector3d pvec = direction.cross(edge2);
        const double determinant = edge1.dot(pvec);
        if (std::abs(determinant) <= epsilon)
            continue;
        const double inverseDeterminant = 1.0 / determinant;
        const Eigen::Vector3d tvec = origin - a;
        const double u = tvec.dot(pvec) * inverseDeterminant;
        if (u < -epsilon || u > 1.0 + epsilon)
            continue;
        const Eigen::Vector3d qvec = tvec.cross(edge1);
        const double v = direction.dot(qvec) * inverseDeterminant;
        if (v < -epsilon || u + v > 1.0 + epsilon)
            continue;
        const double rayDistance = edge2.dot(qvec) * inverseDeterminant;
        if (rayDistance > epsilon)
            ++intersections;
    }
    return (intersections % 2) == 1;
}

void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {"""

    cpp = cpp.replace(resolve_old, resolve_new, 1)

    contact_old = """        if (distance <= thickness) {
            Eigen::Vector3d normal = (distance > 1e-6)
                                         ? toParticle.normalized()
                                         : ((b - a).cross(c - a)).normalized();

            Eigen::Vector3d newPosition = cp + normal * thickness;"""
    contact_new = """        if (distance <= thickness) {
            Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;

            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;
            Eigen::Vector3d outwardNormal = faceNormal * m_outwardNormalSign;
            Eigen::Vector3d normal = outwardNormal;

            if (distance > 1e-6) {
                normal = toParticle / distance;
                if (m_closedManifold && normal.dot(outwardNormal) < 0.0)
                    normal = -normal;
            }

            Eigen::Vector3d newPosition = cp + normal * thickness;"""
    if cpp.count(contact_old) != 1:
        raise RuntimeError("MeshCollider.cpp contact-response anchor mismatch")
    cpp_path.write_text(cpp.replace(contact_old, contact_new, 1), encoding="utf-8")

    binding_old = """        .def(py::init<const std::vector<Eigen::Vector3d>&,
                      const std::vector<std::array<int, 3>>&, double>(),
             py::arg("vertices"), py::arg("triangles"), py::arg("friction"))"""
    binding_new = """        .def(py::init<const std::vector<Eigen::Vector3d>&,
                      const std::vector<std::array<int, 3>>&, double, bool, double>(),
             py::arg("vertices"), py::arg("triangles"), py::arg("friction"),
             py::arg("closed_manifold") = false,
             py::arg("outward_normal_sign") = 1.0)"""
    for binding_path in bindings:
        binding_text = binding_path.read_text(encoding="utf-8")
        if binding_text.count(binding_old) != 1:
            raise RuntimeError(f"{binding_path}: MeshCollider binding anchor mismatch")
        binding_path.write_text(
            binding_text.replace(binding_old, binding_new, 1), encoding="utf-8"
        )

    engine_text = engine_py.read_text(encoding="utf-8")
    engine_old = """    def add_mesh_from_arrays(
        self,
        name: str,
        vertices: np.ndarray,
        triangles: np.ndarray,
        friction: float = 0.5,
    ):
        collider = sdk.MeshCollider(vertices, triangles, float(friction))"""
    engine_new = """    def add_mesh_from_arrays(
        self,
        name: str,
        vertices: np.ndarray,
        triangles: np.ndarray,
        friction: float = 0.5,
        closed_manifold: bool = False,
        outward_normal_sign: float = 1.0,
    ):
        collider = sdk.MeshCollider(
            vertices,
            triangles,
            float(friction),
            bool(closed_manifold),
            float(outward_normal_sign),
        )"""
    if engine_text.count(engine_old) != 1:
        raise RuntimeError("python/tissu/engine.py add_mesh_from_arrays anchor mismatch")
    engine_py.write_text(engine_text.replace(engine_old, engine_new, 1), encoding="utf-8")

    stub_text = stub_py.read_text(encoding="utf-8")
    stub_old = """    @overload
    def __init__(self, vertices: list[numpy.ndarray[numpy.float64[3, 1]]], triangles, friction: float) -> None: ..."""
    stub_new = """    @overload
    def __init__(self, vertices: list[numpy.ndarray[numpy.float64[3, 1]]], triangles, friction: float) -> None: ...
    @overload
    def __init__(
        self,
        vertices: list[numpy.ndarray[numpy.float64[3, 1]]],
        triangles,
        friction: float,
        closed_manifold: bool,
        outward_normal_sign: float,
    ) -> None: ..."""
    if stub_text.count(stub_old) != 1:
        raise RuntimeError("MeshCollider stub anchor mismatch")
    stub_py.write_text(stub_text.replace(stub_old, stub_new, 1), encoding="utf-8")

    test_cpp = test.read_text(encoding="utf-8")
    if "#include <array>" not in test_cpp:
        test_cpp = test_cpp.replace("#include <vector>\n", "#include <array>\n#include <vector>\n", 1)

    tetra_ctor = "    return MeshCollider(vertices, triangles, friction);"
    if test_cpp.count(tetra_ctor) != 1:
        raise RuntimeError("MeshCollider test tetrahedron constructor anchor mismatch")
    test_cpp = test_cpp.replace(
        tetra_ctor,
        "    return MeshCollider(vertices, triangles, friction, true, -1.0);",
        1,
    )

    helper = """static bool tetrahedronContains(const Eigen::Vector3d& point) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
        {1.0, 2.0, 1.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 2, 1},
        {0, 1, 3},
        {1, 2, 3},
        {0, 3, 2},
    };
    const Eigen::Vector3d center =
        (vertices[0] + vertices[1] + vertices[2] + vertices[3]) / 4.0;
    constexpr double epsilon = 1e-9;

    for (const auto& tri : triangles) {
        const Eigen::Vector3d& a = vertices[tri[0]];
        const Eigen::Vector3d& b = vertices[tri[1]];
        const Eigen::Vector3d& c = vertices[tri[2]];
        Eigen::Vector3d normal = (b - a).cross(c - a).normalized();
        if ((center - a).dot(normal) > 0.0)
            normal = -normal;
        if ((point - a).dot(normal) > epsilon)
            return false;
    }
    return true;
}

"""
    if "static bool tetrahedronContains" not in test_cpp:
        anchor = "TEST(MeshCollider, ParticleInsideMeshMovesOutside) {"
        if test_cpp.count(anchor) != 1:
            raise RuntimeError("MeshCollider test first regression anchor missing")
        test_cpp = test_cpp.replace(anchor, helper + anchor, 1)

    first_old = """    double distanceMoved = (particles[0].getPosition() - initialPos).norm();
    EXPECT_GT(distanceMoved, 0.0);
}"""
    first_new = """    double distanceMoved = (particles[0].getPosition() - initialPos).norm();
    EXPECT_GT(distanceMoved, 0.0);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}"""
    if test_cpp.count(first_old) != 1:
        raise RuntimeError("MeshCollider first regression body anchor mismatch")
    test_cpp = test_cpp.replace(first_old, first_new, 1)

    closed_test = """TEST(MeshCollider, ClosedMeshKeepsOutsideContactOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    Eigen::Vector3d initialPos(1.0, -0.01, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

"""
    if "TEST(MeshCollider, ClosedMeshKeepsOutsideContactOutside)" not in test_cpp:
        anchor = "TEST(MeshCollider, ParticleOutsideMeshDoesNotChangePosition) {"
        if test_cpp.count(anchor) != 1:
            raise RuntimeError("MeshCollider closed-mesh regression insertion anchor missing")
        test_cpp = test_cpp.replace(anchor, closed_test + anchor, 1)

    open_test = """TEST(MeshCollider, OpenMeshRetainsLegacyContactDirection) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {0.0, 0.0, 2.0},
    };
    const std::vector<std::array<int, 3>> triangles = {{0, 1, 2}};
    MeshCollider mesh(vertices, triangles, 0.0);

    Eigen::Vector3d initialPos(0.5, 0.05, 0.5);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_GT(particles[0].getPosition().y(), initialPos.y());
}

"""
    if "TEST(MeshCollider, OpenMeshRetainsLegacyContactDirection)" not in test_cpp:
        anchor = "TEST(MeshCollider, ParticleOutsideMeshDoesNotChangePosition) {"
        if test_cpp.count(anchor) != 1:
            raise RuntimeError("MeshCollider open-mesh regression insertion anchor missing")
        test_cpp = test_cpp.replace(anchor, open_test + anchor, 1)

    nonwatertight_test = """TEST(MeshCollider, NonWatertightMeshHonorsExplicitClosedHint) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
    };
    const std::vector<std::array<int, 3>> triangles = {{0, 2, 1}};
    MeshCollider mesh(vertices, triangles, 0.0, true, 1.0);

    const Eigen::Vector3d initialPos(1.0, -0.05, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_GT(particles[0].getPosition().y(), 0.0);
}

"""
    if "TEST(MeshCollider, NonWatertightMeshHonorsExplicitClosedHint)" not in test_cpp:
        anchor = "TEST(MeshCollider, ParticleOutsideMeshDoesNotChangePosition) {"
        if test_cpp.count(anchor) != 1:
            raise RuntimeError("MeshCollider non-watertight regression insertion anchor missing")
        test_cpp = test_cpp.replace(anchor, nonwatertight_test + anchor, 1)

    test.write_text(test_cpp, encoding="utf-8")

    diff = run("git", "diff", "--name-only")
    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "python/src/bindings.cpp",
        "python/src/bindings_headless.cpp",
        "python/tissu/engine.py",
        "python/tissu/_cloth_sdk_core.pyi",
        "tests/physics/test_mesh_collider.cpp",
    }
    if set(diff.splitlines()) != expected:
        raise RuntimeError(f"unexpected patched files: {diff!r}")

    full_diff = run("git", "diff")
    if "inferMeshOrientation" in full_diff or "std::unordered_map" in full_diff:
        raise RuntimeError("MeshCollider patch must not infer closure from solver geometry")

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")

    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"Tissu source commit: {EXPECTED_COMMIT}")
    print(f"Tissu contact fix script sha256: {script_sha}")
    print("Tissu contact fix: applied and self-checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
