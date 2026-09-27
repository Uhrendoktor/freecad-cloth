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

    bvh_header = ROOT / "core/include/data-structures/BVH.hpp"
    bvh_cpp_path = ROOT / "core/src/data-structures/BVH.cpp"
    header = ROOT / "core/include/physics/MeshCollider.hpp"
    cpp = ROOT / "core/src/physics/MeshCollider.cpp"
    test = ROOT / "tests/physics/test_mesh_collider.cpp"

    replace_once(
        bvh_header,
        """    int closestTriangle(const Eigen::Vector3d& point,
                        const std::vector<Eigen::Vector3d>& vertices) const;
    const Triangle& getTriangle(int index) const { return m_triangles[index]; }
""",
        """    int closestTriangle(const Eigen::Vector3d& point,
                        const std::vector<Eigen::Vector3d>& vertices) const;
    int rayIntersectionCount(
        const Eigen::Vector3d& origin,
        const Eigen::Vector3d& direction,
        const std::vector<Eigen::Vector3d>& vertices,
        bool& ambiguous) const;
    const Triangle& getTriangle(int index) const { return m_triangles[index]; }
""",
        "BVH ray query declaration",
    )
    replace_once(
        bvh_header,
        """    int closestRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices,
                         double& bestDistSq) const;
""",
        """    int closestRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices,
                         double& bestDistSq) const;

    int rayIntersectionCountRecursive(
        int nodeIdx,
        const Eigen::Vector3d& origin,
        const Eigen::Vector3d& direction,
        const std::vector<Eigen::Vector3d>& vertices,
        bool& ambiguous) const;
""",
        "BVH ray query recursion declaration",
    )

    bvh_cpp = bvh_cpp_path.read_text(encoding="utf-8")
    bvh_cpp = bvh_cpp.replace(
        '#include "data-structures/BVH.hpp"\n',
        '#include "data-structures/BVH.hpp"\n\n#include <algorithm>\n#include <cmath>\n#include <limits>\n',
        1,
    )
    ray_helpers = """namespace {

constexpr double kRayEpsilon = 1e-10;

bool rayIntersectsAabb(const Eigen::Vector3d& origin,
                       const Eigen::Vector3d& direction,
                       const Eigen::AlignedBox3d& bbox) {
    double tMin = 0.0;
    double tMax = std::numeric_limits<double>::infinity();

    for (int axis = 0; axis < 3; ++axis) {
        const double o = origin[axis];
        const double d = direction[axis];
        const double lo = bbox.min()[axis];
        const double hi = bbox.max()[axis];

        if (std::abs(d) <= kRayEpsilon) {
            if (o < lo || o > hi)
                return false;
            continue;
        }

        double tNear = (lo - o) / d;
        double tFar = (hi - o) / d;
        if (tNear > tFar)
            std::swap(tNear, tFar);

        tMin = std::max(tMin, tNear);
        tMax = std::min(tMax, tFar);
        if (tMin > tMax)
            return false;
    }

    return tMax > kRayEpsilon;
}

int rayIntersectsTriangle(const Eigen::Vector3d& origin,
                          const Eigen::Vector3d& direction,
                          const Eigen::Vector3d& a,
                          const Eigen::Vector3d& b,
                          const Eigen::Vector3d& c,
                          bool& ambiguous) {
    const Eigen::Vector3d edge1 = b - a;
    const Eigen::Vector3d edge2 = c - a;
    const Eigen::Vector3d normal = edge1.cross(edge2);
    const double normalLength = normal.norm();
    if (normalLength <= kRayEpsilon) {
        ambiguous = true;
        return 0;
    }

    const Eigen::Vector3d pvec = direction.cross(edge2);
    const double determinant = edge1.dot(pvec);
    if (std::abs(determinant) <= kRayEpsilon) {
        const double planeDistance =
            std::abs((origin - a).dot(normal)) / normalLength;
        if (planeDistance <= 1.0e-9)
            ambiguous = true;
        return 0;
    }

    const double invDeterminant = 1.0 / determinant;
    const Eigen::Vector3d tvec = origin - a;
    const double u = tvec.dot(pvec) * invDeterminant;
    if (u < -1.0e-9 || u > 1.0 + 1.0e-9)
        return 0;

    const Eigen::Vector3d qvec = tvec.cross(edge1);
    const double v = direction.dot(qvec) * invDeterminant;
    if (v < -1.0e-9 || v > 1.0 + 1.0e-9)
        return 0;

    const double w = 1.0 - u - v;
    if (w < -1.0e-9 || w > 1.0 + 1.0e-9)
        return 0;
    if (std::abs(u) <= 1.0e-9 ||
        std::abs(v) <= 1.0e-9 ||
        std::abs(w) <= 1.0e-9) {
        ambiguous = true;
        return 0;
    }

    const double t = edge2.dot(qvec) * invDeterminant;
    if (t < -kRayEpsilon)
        return 0;
    if (std::abs(t) <= kRayEpsilon) {
        ambiguous = true;
        return 0;
    }
    return 1;
}

} // namespace
"""
    if bvh_cpp.count("namespace Tissu {") != 1:
        raise RuntimeError("BVH namespace anchor mismatch")
    bvh_cpp = bvh_cpp.replace("namespace Tissu {\n", "namespace Tissu {\n\n" + ray_helpers + "\n", 1)
    method_anchor = """int BVH::closestTriangle(const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices) const {
"""
    method_block = """int BVH::rayIntersectionCount(
    const Eigen::Vector3d& origin,
    const Eigen::Vector3d& direction,
    const std::vector<Eigen::Vector3d>& vertices,
    bool& ambiguous) const {
    ambiguous = false;
    if (m_rootIndex == -1 || m_nodes.empty() ||
        direction.squaredNorm() <= kRayEpsilon * kRayEpsilon) {
        ambiguous = true;
        return 0;
    }

    return rayIntersectionCountRecursive(
        m_rootIndex, origin, direction.normalized(), vertices, ambiguous);
}

int BVH::rayIntersectionCountRecursive(
    int nodeIdx,
    const Eigen::Vector3d& origin,
    const Eigen::Vector3d& direction,
    const std::vector<Eigen::Vector3d>& vertices,
    bool& ambiguous) const {
    if (ambiguous)
        return 0;

    const BVHNode& node = m_nodes[nodeIdx];
    if (!rayIntersectsAabb(origin, direction, node.bbox))
        return 0;

    if (node.isLeaf()) {
        int count = 0;
        for (int i = 0; i < node.primitiveCount; ++i) {
            const Triangle& tri = m_triangles[node.triangleIndex + i];
            const int intersection = rayIntersectsTriangle(
                origin, direction,
                vertices[tri.a], vertices[tri.b], vertices[tri.c], ambiguous);
            count += intersection;
            if (ambiguous)
                return 0;
        }
        return count;
    }

    const int leftCount =
        rayIntersectionCountRecursive(
            node.left, origin, direction, vertices, ambiguous);
    if (ambiguous)
        return 0;
    const int rightCount =
        rayIntersectionCountRecursive(
            node.right, origin, direction, vertices, ambiguous);
    if (ambiguous)
        return 0;
    return leftCount + rightCount;
}

"""
    if bvh_cpp.count(method_anchor) != 1:
        raise RuntimeError("BVH method anchor mismatch")
    bvh_cpp = bvh_cpp.replace(method_anchor, method_block + method_anchor, 1)
    bvh_cpp_path.write_text(bvh_cpp, encoding="utf-8")
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

    cpp = cpp.read_text(encoding="utf-8")
    include_old = '#include "physics/Particle.hpp"\n\nnamespace Tissu {'
    include_new = """#include "physics/Particle.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <utility>

namespace Tissu {

namespace {

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

bool isDeepInterior(
    const BVH& bvh,
    const Eigen::Vector3d& point,
    const std::vector<Eigen::Vector3d>& vertices) {
    static const std::array<Eigen::Vector3d, 3> directions = {
        Eigen::Vector3d(1.0, 0.371, 0.593).normalized(),
        Eigen::Vector3d(-0.421, 1.0, 0.337).normalized(),
        Eigen::Vector3d(0.263, -0.547, 1.0).normalized(),
    };

    int referenceParity = -1;
    for (const auto& direction : directions) {
        bool ambiguous = false;
        const int intersections =
            bvh.rayIntersectionCount(point, direction, vertices, ambiguous);
        if (ambiguous)
            return false;

        const int parity = intersections & 1;
        if (referenceParity == -1)
            referenceParity = parity;
        else if (parity != referenceParity)
            return false;
    }

    return referenceParity == 1;
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
            """        bool deepInterior = false;
        if (m_closedManifold && distance > thickness)
            deepInterior = isDeepInterior(m_bvh, particle.getPosition(), m_worldVertices);

        if (distance <= thickness || deepInterior) {
            Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;
            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;

            Eigen::Vector3d normal = faceNormal;
            if (deepInterior) {
                normal *= m_outwardNormalSign;
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
    test_cpp = test_cpp.replace(
        "#include <vector>\n",
        "#include <algorithm>\n#include <array>\n#include <vector>\n",
        1,
    )

    helper = """static std::vector<Eigen::Vector3d> makeTestTetrahedronVertices() {
    return {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
        {1.0, 2.0, 1.0},
    };
}

static std::vector<std::array<int, 3>> makeTestTetrahedronTriangles() {
    return {
        {0, 2, 1},
        {0, 1, 3},
        {1, 2, 3},
        {0, 3, 2},
    };
}

static std::vector<Eigen::Vector3d> makeTestCubeVertices() {
    return {
        {-2.0, -2.0, -2.0}, {2.0, -2.0, -2.0},
        {2.0, 2.0, -2.0}, {-2.0, 2.0, -2.0},
        {-2.0, -2.0, 2.0}, {2.0, -2.0, 2.0},
        {2.0, 2.0, 2.0}, {-2.0, 2.0, 2.0},
    };
}

static std::vector<std::array<int, 3>> makeTestCubeTriangles() {
    return {
        {0, 1, 2}, {0, 2, 3},
        {4, 6, 5}, {4, 7, 6},
        {0, 4, 5}, {0, 5, 1},
        {1, 5, 6}, {1, 6, 2},
        {2, 6, 7}, {2, 7, 3},
        {4, 0, 3}, {4, 3, 7},
    };
}

static std::vector<std::array<int, 3>> orientOutward(
    const std::vector<Eigen::Vector3d>& vertices,
    std::vector<std::array<int, 3>> triangles) {
    Eigen::Vector3d center = Eigen::Vector3d::Zero();
    for (const auto& vertex : vertices)
        center += vertex;
    center /= static_cast<double>(vertices.size());

    for (auto& tri : triangles) {
        const Eigen::Vector3d& a = vertices[tri[0]];
        const Eigen::Vector3d& b = vertices[tri[1]];
        const Eigen::Vector3d& c = vertices[tri[2]];
        const Eigen::Vector3d normal = (b - a).cross(c - a);
        if ((center - a).dot(normal) > 0.0)
            std::swap(tri[1], tri[2]);
    }
    return triangles;
}

static bool closedMeshContains(
    const std::vector<Eigen::Vector3d>& vertices,
    const std::vector<std::array<int, 3>>& triangles,
    const Eigen::Vector3d& point) {
    constexpr double epsilon = 1e-9;
    for (const auto& tri : triangles) {
        const Eigen::Vector3d& a = vertices[tri[0]];
        const Eigen::Vector3d& b = vertices[tri[1]];
        const Eigen::Vector3d& c = vertices[tri[2]];
        const Eigen::Vector3d normal = (b - a).cross(c - a);
        if ((point - a).dot(normal) > epsilon)
            return false;
    }
    return true;
}

static bool tetrahedronContains(const Eigen::Vector3d& point) {
    const auto vertices = makeTestTetrahedronVertices();
    const auto triangles =
        orientOutward(vertices, makeTestTetrahedronTriangles());
    return closedMeshContains(vertices, triangles, point);
}

static void expectMovedOutside(
    MeshCollider& mesh,
    const std::vector<Eigen::Vector3d>& vertices,
    const std::vector<std::array<int, 3>>& triangles,
    const Eigen::Vector3d& initialPos) {
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);
    mesh.resolve(particles, 0.016, 0.1);
    EXPECT_GT((particles[0].getPosition() - initialPos).norm(), 0.0);
    EXPECT_FALSE(
        closedMeshContains(vertices, triangles, particles[0].getPosition()));
}

"""
    if test_cpp.count("TEST(MeshCollider, ParticleInsideMeshMovesOutside)") != 1:
        raise RuntimeError("MeshCollider test anchor missing")
    test_cpp = test_cpp.replace(
        "TEST(MeshCollider, ParticleInsideMeshMovesOutside) {",
        helper + """TEST(MeshCollider, DeepInteriorPointMovesOutsideClosedMesh) {
    const auto vertices = makeTestTetrahedronVertices();
    const auto triangles =
        orientOutward(vertices, makeTestTetrahedronTriangles());
    MeshCollider mesh(vertices, triangles, 0.0);
    const Eigen::Vector3d initialPos =
        (vertices[0] + vertices[1] + vertices[2] + vertices[3]) / 4.0;
    expectMovedOutside(mesh, vertices, triangles, initialPos);
}

TEST(MeshCollider, ParticleInsideMeshMovesOutside) {""",
        1,
    )

    old_body = """    double distanceMoved = (particles[0].getPosition() - initialPos).norm();
    EXPECT_GT(distanceMoved, 0.0);
}"""
    if test_cpp.count(old_body) != 1:
        raise RuntimeError("MeshCollider regression test body anchor mismatch")
    test_cpp = test_cpp.replace(
        old_body,
        """    double distanceMoved = (particles[0].getPosition() - initialPos).norm();
    EXPECT_GT(distanceMoved, 0.0);
    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}""",
        1,
    )

    extra_tests = """TEST(MeshCollider, ClosedMeshKeepsOutsideContactOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    const Eigen::Vector3d initialPos(1.0, -0.01, 0.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

TEST(MeshCollider, FarOutsideParticleRemainsUnchanged) {
    MeshCollider mesh = makeTetrahedron(0.0);
    const Eigen::Vector3d initialPos(100.0, 100.0, 100.0);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_NEAR(
        (particles[0].getPosition() - initialPos).norm(), 0.0, 1e-9);
}

TEST(MeshCollider, MultipleParticlesResolveInsideAndPreserveFarOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    const Eigen::Vector3d insidePos(1.0, 0.5, 0.75);
    const Eigen::Vector3d outsidePos(100.0, 100.0, 100.0);
    std::vector<Particle> particles;
    particles.emplace_back(insidePos);
    particles.emplace_back(outsidePos);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
    EXPECT_NEAR(
        (particles[1].getPosition() - outsidePos).norm(), 0.0, 1e-9);
}

TEST(MeshCollider, ReversedClosedTetrahedronAndCubeRemainClassified) {
    {
        auto vertices = makeTestTetrahedronVertices();
        auto triangles =
            orientOutward(vertices, makeTestTetrahedronTriangles());
        for (auto& tri : triangles)
            std::swap(tri[1], tri[2]);
        MeshCollider mesh(vertices, triangles, 0.0);
        expectMovedOutside(
            mesh,
            vertices,
            triangles,
            (vertices[0] + vertices[1] + vertices[2] + vertices[3]) / 4.0);
    }

    {
        auto vertices = makeTestCubeVertices();
        auto triangles = orientOutward(vertices, makeTestCubeTriangles());
        for (auto& tri : triangles)
            std::swap(tri[1], tri[2]);
        MeshCollider mesh(vertices, triangles, 0.0);
        expectMovedOutside(mesh, vertices, triangles, Eigen::Vector3d::Zero());
    }
}

TEST(MeshCollider, TransformedClosedMeshRemainsClassified) {
    const auto baseVertices = makeTestTetrahedronVertices();
    const auto baseTriangles = makeTestTetrahedronTriangles();
    std::vector<Eigen::Vector3d> vertices;
    vertices.reserve(baseVertices.size());
    for (const auto& vertex : baseVertices)
        vertices.emplace_back(
            -vertex.y() + 10.0, vertex.x() - 7.0, vertex.z() + 4.0);

    const auto triangles = orientOutward(vertices, baseTriangles);
    MeshCollider mesh(vertices, triangles, 0.0);
    const Eigen::Vector3d initialPos(9.5, -6.0, 4.75);
    expectMovedOutside(mesh, vertices, triangles, initialPos);
}

TEST(MeshCollider, AmbiguousSharedCornerRayFailsClosed) {
    const Eigen::Vector3d direction =
        Eigen::Vector3d(1.0, 0.371, 0.593).normalized();
    const Eigen::Vector3d basisA =
        Eigen::Vector3d(-direction.y(), direction.x(), 0.0).normalized();
    const Eigen::Vector3d basisB = direction.cross(basisA).normalized();

    std::vector<Eigen::Vector3d> vertices = {
        direction * 8.0,
        direction * (-8.0 / 3.0) + basisA * 5.0,
        direction * (-8.0 / 3.0) - basisA * 2.5 + basisB * 4.0,
        direction * (-8.0 / 3.0) - basisA * 2.5 - basisB * 4.0,
    };
    const auto triangles =
        orientOutward(vertices, makeTestTetrahedronTriangles());
    MeshCollider mesh(vertices, triangles, 0.0);

    const Eigen::Vector3d initialPos = Eigen::Vector3d::Zero();
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);
    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_NEAR(
        (particles[0].getPosition() - initialPos).norm(), 0.0, 1e-9);
}

TEST(MeshCollider, DeepInteriorParityIsDeterministic) {
    const auto vertices = makeTestTetrahedronVertices();
    const auto triangles =
        orientOutward(vertices, makeTestTetrahedronTriangles());
    const Eigen::Vector3d initialPos(1.0, 0.5, 0.75);

    MeshCollider first(vertices, triangles, 0.0);
    MeshCollider second(vertices, triangles, 0.0);
    std::vector<Particle> firstParticles;
    std::vector<Particle> secondParticles;
    firstParticles.emplace_back(initialPos);
    secondParticles.emplace_back(initialPos);

    first.resolve(firstParticles, 0.016, 0.1);
    second.resolve(secondParticles, 0.016, 0.1);

    EXPECT_NEAR(
        (firstParticles[0].getPosition() -
         secondParticles[0].getPosition()).norm(),
        0.0,
        1e-12);
}

"""
    if "TEST(MeshCollider, OpenMeshRetainsLegacyContactDirection)" in test_cpp:
        raise RuntimeError("open-mesh regression already present in pinned source")
    test_cpp = test_cpp.rstrip() + "\n\n" + extra_tests.strip("\r\n") + "\n"
    test.write_text(test_cpp, encoding="utf-8")

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/data-structures/BVH.hpp",
        "core/src/data-structures/BVH.cpp",
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
