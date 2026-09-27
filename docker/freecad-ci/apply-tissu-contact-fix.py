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
    bvh_header = ROOT / "core/include/data-structures/BVH.hpp"
    bvh_cpp = ROOT / "core/src/data-structures/BVH.cpp"
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
    double m_outwardNormalSign = 1.0;
    BVH m_bvh;""",
        "MeshCollider.hpp member layout",
    )

    bvh_header_text = bvh_header.read_text(encoding="utf-8")
    bvh_header_text = bvh_header_text.replace(
        """    int closestTriangle(const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices) const;""",
        """    int closestTriangle(const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices) const;
    int rayIntersectionCount(
        const Eigen::Vector3d& origin, const Eigen::Vector3d& direction,
        const std::vector<Eigen::Vector3d>& vertices,
        bool& ambiguous) const;""",
        1,
    )
    if "rayIntersectionCount(" not in bvh_header_text:
        raise RuntimeError("BVH.hpp ray-count declaration missing")
    bvh_header_text = bvh_header_text.replace(
        """    int closestRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices,
                         double& bestDistSq) const;""",
        """    int closestRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices,
                         double& bestDistSq) const;
    int rayIntersectionRecursive(
        int nodeIdx, const Eigen::Vector3d& origin,
        const Eigen::Vector3d& direction,
        const std::vector<Eigen::Vector3d>& vertices,
        bool& ambiguous) const;""",
        1,
    )
    if "rayIntersectionRecursive(" not in bvh_header_text:
        raise RuntimeError("BVH.hpp private ray-count declaration missing")
    bvh_header.write_text(bvh_header_text, encoding="utf-8")

    bvh_cpp_text = bvh_cpp.read_text(encoding="utf-8")
    bvh_include_anchor = '#include "data-structures/BVH.hpp"\n\nnamespace Tissu {'
    bvh_include_replacement = """#include "data-structures/BVH.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace {

constexpr double kRayEpsilon = 1.0e-10;
constexpr double kRayEdgeEpsilon = 1.0e-9;

bool rayAabbHit(
    const Eigen::Vector3d& origin, const Eigen::Vector3d& direction,
    const Eigen::AlignedBox3d& box) {
    double tMin = 0.0;
    double tMax = std::numeric_limits<double>::infinity();
    for (int axis = 0; axis < 3; ++axis) {
        const double d = direction[axis];
        const double minValue = box.min()[axis];
        const double maxValue = box.max()[axis];
        if (std::abs(d) <= kRayEpsilon) {
            if (origin[axis] < minValue || origin[axis] > maxValue)
                return false;
            continue;
        }
        double t0 = (minValue - origin[axis]) / d;
        double t1 = (maxValue - origin[axis]) / d;
        if (t0 > t1)
            std::swap(t0, t1);
        tMin = std::max(tMin, t0);
        tMax = std::min(tMax, t1);
        if (tMax < tMin)
            return false;
    }
    return tMax > kRayEpsilon;
}

bool rayTriangleHit(
    const Eigen::Vector3d& origin, const Eigen::Vector3d& direction,
    const Eigen::Vector3d& a, const Eigen::Vector3d& b,
    const Eigen::Vector3d& c, double& t, bool& ambiguous) {
    const Eigen::Vector3d e1 = b - a;
    const Eigen::Vector3d e2 = c - a;
    const Eigen::Vector3d p = direction.cross(e2);
    const double det = e1.dot(p);
    if (std::abs(det) <= kRayEpsilon)
        return false;

    const double invDet = 1.0 / det;
    const Eigen::Vector3d tv = origin - a;
    const double u = tv.dot(p) * invDet;
    if (u < -kRayEdgeEpsilon || u > 1.0 + kRayEdgeEpsilon)
        return false;

    const Eigen::Vector3d q = tv.cross(e1);
    const double v = direction.dot(q) * invDet;
    if (v < -kRayEdgeEpsilon || u + v > 1.0 + kRayEdgeEpsilon)
        return false;

    t = e2.dot(q) * invDet;
    if (t <= kRayEpsilon)
        return false;

    const double w = 1.0 - u - v;
    if (std::abs(u) <= kRayEdgeEpsilon ||
        std::abs(v) <= kRayEdgeEpsilon ||
        std::abs(w) <= kRayEdgeEpsilon) {
        ambiguous = true;
        return false;
    }
    return true;
}

} // namespace

namespace Tissu {"""
    if bvh_cpp_text.count(bvh_include_anchor) != 1:
        raise RuntimeError("BVH.cpp include anchor mismatch")
    bvh_cpp_text = bvh_cpp_text.replace(bvh_include_anchor,bvh_include_replacement,1)
    bvh_cpp_text = bvh_cpp_text.replace(
        """int BVH::closestTriangle(const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices) const {""",
        """int BVH::rayIntersectionCount(
    const Eigen::Vector3d& origin, const Eigen::Vector3d& direction,
    const std::vector<Eigen::Vector3d>& vertices,
    bool& ambiguous) const {
    ambiguous = false;
    if (m_rootIndex == -1 || m_nodes.empty())
        return 0;
    return rayIntersectionRecursive(
        m_rootIndex, origin, direction, vertices, ambiguous);
}

int BVH::rayIntersectionRecursive(
    int nodeIdx, const Eigen::Vector3d& origin,
    const Eigen::Vector3d& direction,
    const std::vector<Eigen::Vector3d>& vertices,
    bool& ambiguous) const {
    const BVHNode& node = m_nodes[nodeIdx];
    if (!rayAabbHit(origin, direction, node.bbox))
        return 0;

    if (node.isLeaf()) {
        int count = 0;
        for (int i = 0; i < node.primitiveCount; ++i) {
            const int triIdx = node.triangleIndex + i;
            const Triangle& tri = m_triangles[triIdx];
            double t = 0.0;
            if (rayTriangleHit(
                    origin, direction,
                    vertices[tri.a], vertices[tri.b], vertices[tri.c],
                    t, ambiguous)) {
                ++count;
            }
        }
        return count;
    }

    return rayIntersectionRecursive(
               node.left, origin, direction, vertices, ambiguous) +
           rayIntersectionRecursive(
               node.right, origin, direction, vertices, ambiguous);
}

int BVH::closestTriangle(const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices) const {""",
        1,
    )
    if "rayIntersectionCount(" not in bvh_cpp_text:
        raise RuntimeError("BVH.cpp ray-count implementation missing")
    bvh_cpp.write_text(bvh_cpp_text, encoding="utf-8")

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

enum class ContainmentState {
    Outside,
    Inside,
    Ambiguous,
};

ContainmentState classifyClosedMeshPoint(
    const BVH& bvh,
    const Eigen::Vector3d& point,
    const std::vector<Eigen::Vector3d>& vertices) {
    static const std::array<Eigen::Vector3d, 3> directions = {
        Eigen::Vector3d(1.0, 0.3713906764, 0.1591549431).normalized(),
        Eigen::Vector3d(-0.2113248654, 1.0, 0.5773502692).normalized(),
        Eigen::Vector3d(0.4472135955, -0.8017837257, 1.0).normalized(),
    };
    int insideVotes = 0;
    int outsideVotes = 0;
    for (const auto& direction : directions) {
        bool ambiguous = false;
        const Eigen::Vector3d origin = point + direction * 1.0e-8;
        const int intersections =
            bvh.rayIntersectionCount(origin, direction, vertices, ambiguous);
        if (ambiguous)
            continue;
        if (intersections & 1)
            ++insideVotes;
        else
            ++outsideVotes;
        if (insideVotes >= 2)
            return ContainmentState::Inside;
        if (outsideVotes >= 2)
            return ContainmentState::Outside;
    }
    return ContainmentState::Ambiguous;
}

struct MeshOrientation {
    bool closedManifold = false;
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
    if (triangles.empty())
        return {};

    std::unordered_map<std::uint64_t, std::pair<int, int>> edges;
    edges.reserve(triangles.size() * 3);

    double signedVolume = 0.0;
    for (const auto& tri : triangles) {
        const int ids[3] = {tri.a, tri.b, tri.c};
        signedVolume +=
            ids[0] < static_cast<int>(vertices.size()) &&
                    ids[1] < static_cast<int>(vertices.size()) &&
                    ids[2] < static_cast<int>(vertices.size())
                ? vertices[ids[0]].dot(
                      vertices[ids[1]].cross(vertices[ids[2]])) /
                      6.0
                : 0.0;

        for (int edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {
            const int from = ids[edgeIndex];
            const int to = ids[(edgeIndex + 1) % 3];
            if (from < 0 || to < 0 ||
                from >= static_cast<int>(vertices.size()) ||
                to >= static_cast<int>(vertices.size())) {
                return {};
            }
            const auto key = edgeKey(from, to);
            auto& edge = edges[key];
            ++edge.first;
            edge.second +=
                from == std::min(from, to) ? 1 : -1;
        }
    }

    for (const auto& [key, edge] : edges) {
        (void)key;
        if (edge.first != 2 || edge.second != 0)
            return {};
    }
    if (std::abs(signedVolume) <= 1.0e-12)
        return {};

    return {true, signedVolume > 0.0 ? 1.0 : -1.0};
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
            """        const bool deepInterior =
            m_closedManifold && distance > thickness &&
            classifyClosedMeshPoint(
                m_bvh, particle.getPosition(), m_worldVertices) ==
                ContainmentState::Inside;

        if (distance <= thickness || deepInterior) {
            Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;
            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;

            Eigen::Vector3d normal = faceNormal;
            if (deepInterior) {
                normal = faceNormal * m_outwardNormalSign;
            } else if (distance > 1e-6) {
                normal = toParticle / distance;
                if (m_closedManifold) {
                    const Eigen::Vector3d outwardNormal =
                        faceNormal * m_outwardNormalSign;
                    // A particle on the interior side of a closed, consistently
                    // oriented surface must be resolved along the outward
                    // normal; outside contact preserves the existing vector.
                    if (normal.dot(outwardNormal) < 0.0)
                        normal = -normal;
                }
            } else if (m_closedManifold) {
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
    deep_tests = r'''
TEST(MeshCollider, DeepInteriorClosedMeshProjectsOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    constexpr double thickness = 0.05;
    const Eigen::Vector3d initialPos(1.0, 0.5, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);
    mesh.resolve(particles, 0.016, thickness);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
    EXPECT_GT((particles[0].getPosition() - initialPos).norm(), thickness);
}

TEST(MeshCollider, DeepInteriorClosedMeshHandlesReversedWinding) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
        {1.0, 2.0, 1.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 1, 2},
        {0, 3, 1},
        {1, 3, 2},
        {0, 2, 3},
    };
    MeshCollider mesh(vertices, triangles, 0.0);
    const Eigen::Vector3d initialPos(1.0, 0.5, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);
    mesh.resolve(particles, 0.016, 0.05);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

'''
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

    deep_test = r'''
TEST(MeshCollider, DeepInteriorClosedMeshProjectsOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    constexpr double thickness = 0.05;
    const Eigen::Vector3d initialPos(1.0, 0.5, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);
    mesh.resolve(particles, 0.016, thickness);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
    EXPECT_GT((particles[0].getPosition() - initialPos).norm(), thickness);
}

TEST(MeshCollider, DeepInteriorClosedMeshHandlesReversedWinding) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
        {1.0, 2.0, 1.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 1, 2},
        {0, 3, 1},
        {1, 3, 2},
        {0, 2, 3},
    };
    MeshCollider mesh(vertices, triangles, 0.0);
    const Eigen::Vector3d initialPos(1.0, 0.5, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);
    mesh.resolve(particles, 0.016, 0.05);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

'''
    test_anchor = "TEST(MeshCollider, ParticleOutsideMeshDoesNotChangePosition) {"
    if test_cpp.count(test_anchor) != 1:
        raise RuntimeError("deep-interior regression insertion anchor mismatch")
    test_cpp = test_cpp.replace(test_anchor, deep_test + test_anchor, 1)

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/data-structures/BVH.hpp",
        "core/include/physics/MeshCollider.hpp",
        "core/src/data-structures/BVH.cpp",
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
