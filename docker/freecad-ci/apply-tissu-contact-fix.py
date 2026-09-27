#!/usr/bin/env python3
"""Apply the pinned Tissu contact-response fix with fail-closed source anchors."""
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
    cpp = ROOT / "core/src/physics/MeshCollider.cpp"
    test = ROOT / "tests/physics/test_mesh_collider.cpp"

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
    bool m_orientationKnown = false;
    double m_outwardNormalSign = 1.0;
    BVH m_bvh;""",
        "MeshCollider.hpp member layout",
    )

    cpp = cpp.read_text(encoding="utf-8")
    include_old = '#include "physics/Particle.hpp"\n\nnamespace Tissu {'
    include_new = """#include "physics/Particle.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <utility>

namespace Tissu {

namespace {

struct MeshOrientation {
    bool closedManifold = false;
    bool orientationKnown = false;
    double outwardNormalSign = 1.0;
};

std::uint64_t edgeKey(int a, int b) {
    const auto low = static_cast<std::uint32_t>(std::min(a, b));
    const auto high = static_cast<std::uint32_t>(std::max(a, b));
    return (static_cast<std::uint64_t>(low) << 32) |
           static_cast<std::uint64_t>(high);
}

MeshOrientation inferMeshOrientation(
    const std::vector<Eigen::Vector3d>& vertices,
    const std::vector<Triangle>& triangles) {
    if (triangles.empty() || vertices.empty())
        return {};

    std::unordered_map<std::uint64_t, std::pair<int, int>> edges;
    edges.reserve(triangles.size() * 3);

    Eigen::Vector3d center = Eigen::Vector3d::Zero();
    for (const auto& vertex : vertices)
        center += vertex;
    center /= static_cast<double>(vertices.size());

    double signedVolume = 0.0;
    double absoluteVolume = 0.0;
    double signedRadialArea = 0.0;
    double absoluteRadialArea = 0.0;

    for (const auto& tri : triangles) {
        const int ids[3] = {tri.a, tri.b, tri.c};
        if (ids[0] < 0 || ids[1] < 0 || ids[2] < 0 ||
            ids[0] >= static_cast<int>(vertices.size()) ||
            ids[1] >= static_cast<int>(vertices.size()) ||
            ids[2] >= static_cast<int>(vertices.size())) {
            return {};
        }

        const Eigen::Vector3d& a = vertices[ids[0]];
        const Eigen::Vector3d& b = vertices[ids[1]];
        const Eigen::Vector3d& c = vertices[ids[2]];
        const Eigen::Vector3d faceRaw = (b - a).cross(c - a);
        const double faceLength = faceRaw.norm();
        if (faceLength <= 1.0e-12)
            return {};
        const Eigen::Vector3d normal = faceRaw / faceLength;
        const Eigen::Vector3d triCenter = (a + b + c) / 3.0;
        const double area = 0.5 * faceLength;
        const double radial = normal.dot(triCenter - center);

        const Eigen::Vector3d localA = a - center;
        const Eigen::Vector3d localB = b - center;
        const Eigen::Vector3d localC = c - center;
        const double volume = localA.dot(localB.cross(localC)) / 6.0;
        signedVolume += volume;
        absoluteVolume += std::abs(volume);
        signedRadialArea += radial * area;
        absoluteRadialArea += std::abs(radial) * area;

        for (int edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {
            const int from = ids[edgeIndex];
            const int to = ids[(edgeIndex + 1) % 3];
            const auto key = edgeKey(from, to);
            auto& edge = edges[key];
            ++edge.first;
            edge.second += from == std::min(from, to) ? 1 : -1;
        }
    }

    const bool closed =
        !edges.empty() &&
        std::all_of(
            edges.begin(), edges.end(),
            [](const auto& item) {
                const auto& edge = item.second;
                return edge.first == 2 && edge.second == 0;
            });

    const double volumeDominance =
        absoluteVolume > 1.0e-12 ? std::abs(signedVolume) / absoluteVolume : 0.0;
    const double radialDominance =
        absoluteRadialArea > 1.0e-9
            ? std::abs(signedRadialArea) / absoluteRadialArea
            : 0.0;
    const bool volumeKnown = volumeDominance >= 0.20;
    const bool radialKnown = radialDominance >= 0.85;
    const double volumeSign = signedVolume >= 0.0 ? 1.0 : -1.0;
    const double radialSign = signedRadialArea >= 0.0 ? 1.0 : -1.0;
    const bool signAgreement = volumeSign == radialSign;

    if (closed && volumeKnown)
        return {true, true, signedVolume > 0.0 ? 1.0 : -1.0};

    if (volumeKnown && radialKnown && signAgreement)
        // Negative radial sign means authored normals are outward; positive
        // means authored normals are inward.
        return {false, true, -radialSign};

    return {false, false, 1.0};
}

} // namespace
"""
    if cpp.count(include_old) != 1:
        raise RuntimeError("MeshCollider.cpp include anchor mismatch")
    cpp = cpp.replace(include_old, include_new, 1)

    replace_cpp = [
        (
            """    m_triangles.reserve(indices.size() / 3);
    for (size_t i = 0; i + 2 < indices.size(); i += 3)
        m_triangles.emplace_back(indices[i], indices[i + 1], indices[i + 2]);

    m_bvh.build(m_worldVertices, m_triangles);""",
            """    m_triangles.reserve(indices.size() / 3);
    for (size_t i = 0; i + 2 < indices.size(); i += 3)
        m_triangles.emplace_back(indices[i], indices[i + 1], indices[i + 2]);

    const MeshOrientation orientation =
        inferMeshOrientation(m_worldVertices, m_triangles);
    m_closedManifold = orientation.closedManifold;
    m_orientationKnown = orientation.orientationKnown;
    m_outwardNormalSign = orientation.outwardNormalSign;

    m_bvh.build(m_worldVertices, m_triangles);""",
            "MeshCollider.cpp file constructor",
        ),
        (
            """    m_triangles.reserve(triangles.size());
    for (const auto& tri : triangles) {
        m_triangles.emplace_back(tri[0], tri[1], tri[2]);
    }

    m_bvh.build(m_worldVertices, m_triangles);""",
            """    m_triangles.reserve(triangles.size());
    for (const auto& tri : triangles) {
        m_triangles.emplace_back(tri[0], tri[1], tri[2]);
    }

    const MeshOrientation orientation =
        inferMeshOrientation(m_worldVertices, m_triangles);
    m_closedManifold = orientation.closedManifold;
    m_orientationKnown = orientation.orientationKnown;
    m_outwardNormalSign = orientation.outwardNormalSign;

    m_bvh.build(m_worldVertices, m_triangles);""",
            "MeshCollider.cpp vector constructor",
        ),
        (
            """        if (distance <= thickness) {
            Eigen::Vector3d normal = (distance > 1e-6)
                                         ? toParticle.normalized()
                                         : ((b - a).cross(c - a)).normalized();

            Eigen::Vector3d newPosition = cp + normal * thickness;""",
            """        if (distance <= thickness) {
            Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;
            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;

            Eigen::Vector3d normal = faceNormal;
            if (distance > 1e-6) {
                normal = toParticle / distance;
                if (m_orientationKnown) {
                    const Eigen::Vector3d outwardNormal =
                        faceNormal * m_outwardNormalSign;
                    // A particle on the interior side of a closed, consistently
                    // oriented surface must be resolved along the outward
                    // normal; outside contact preserves the existing vector.
                    if (normal.dot(outwardNormal) < 0.0)
                        normal = -normal;
                }
            } else if (m_orientationKnown) {
                normal *= m_outwardNormalSign;
            }

            Eigen::Vector3d newPosition = cp + normal * thickness;""",
            "MeshCollider.cpp contact response",
        ),
    ]
    for old, new, label in replace_cpp:
        count = cpp.count(old)
        if count != 1:
            raise RuntimeError(f"{label}: expected one source anchor, found {count}")
        cpp = cpp.replace(old, new, 1)
    Path(cpp_path := ROOT / "core/src/physics/MeshCollider.cpp").write_text(cpp, encoding="utf-8")

    test_cpp = test.read_text(encoding="utf-8")
    test_cpp = test_cpp.replace("#include <vector>\n", "#include <array>\n#include <vector>\n", 1)
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
    if test_cpp.count("TEST(MeshCollider, ParticleInsideMeshMovesOutside)") != 1:
        raise RuntimeError("MeshCollider test anchor missing")
    test_cpp = test_cpp.replace(
        "TEST(MeshCollider, ParticleInsideMeshMovesOutside) {",
        helper + "TEST(MeshCollider, ParticleInsideMeshMovesOutside) {",
        1,
    )
    old = """    double distanceMoved = (particles[0].getPosition() - initialPos).norm();
    EXPECT_GT(distanceMoved, 0.0);
}"""
    new = """    double distanceMoved = (particles[0].getPosition() - initialPos).norm();
    EXPECT_GT(distanceMoved, 0.0);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

TEST(MeshCollider, ClosedMeshKeepsOutsideContactOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    Eigen::Vector3d initialPos(1.0, -0.01, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

TEST(MeshCollider, OpenConsistentlyWoundSurfaceMovesInteriorParticleOutside) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
        {1.0, 2.0, 1.0},
    };
    // This is the closed tetrahedron with the outward-facing base omitted;
    // the remaining three authored faces retain the source exterior winding.
    const std::vector<std::array<int, 3>> triangles = {
        {0, 1, 3},
        {1, 2, 3},
        {0, 3, 2},
    };
    MeshCollider mesh(vertices, triangles, 0.0);

    const Eigen::Vector3d faceA = vertices[0];
    const Eigen::Vector3d faceB = vertices[1];
    const Eigen::Vector3d faceC = vertices[3];
    Eigen::Vector3d authoredOutwardNormal =
        (faceB - faceA).cross(faceC - faceA).normalized();
    const Eigen::Vector3d faceCenter = (faceA + faceB + faceC) / 3.0;
    const Eigen::Vector3d tetraCenter =
        (vertices[0] + vertices[1] + vertices[2] + vertices[3]) / 4.0;
    const Eigen::Vector3d geometricOutward = faceCenter - tetraCenter;
    ASSERT_GT(geometricOutward.dot(authoredOutwardNormal), 0.0);
    const Eigen::Vector3d initialPos =
        faceCenter - authoredOutwardNormal * 0.05;
    const double initialSignedDistance =
        (initialPos - faceA).dot(authoredOutwardNormal);
    ASSERT_NEAR(initialSignedDistance, -0.05, 1e-9);

    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    const double finalSignedDistance =
        (particles[0].getPosition() - faceA).dot(authoredOutwardNormal);
    EXPECT_GT(finalSignedDistance, 0.0);
    EXPECT_GT(finalSignedDistance, initialSignedDistance);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

TEST(MeshCollider, OpenMeshRetainsLegacyContactDirection) {
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
}"""
    if test_cpp.count(old) != 1:
        raise RuntimeError("MeshCollider regression test body anchor mismatch")
    test_cpp = test_cpp.replace(old, new, 1)
    test.write_text(test_cpp, encoding="utf-8")

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "tests/physics/test_mesh_collider.cpp",
    }
    if set(changed.splitlines()) != expected:
        raise RuntimeError(f"unexpected patched files: {changed!r}")

    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"Tissu source commit: {EXPECTED_COMMIT}")
    print(f"Tissu contact fix script sha256: {script_sha}")
    print("Tissu contact fix: applied and self-checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
