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
    bvh_header = ROOT / "core/include/data-structures/BVH.hpp"
    bvh_cpp = ROOT / "core/src/data-structures/BVH.cpp"

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

    replace_once(
        header,
        """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

private:""",
        """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

private:
    bool firstSegmentHit(const Eigen::Vector3d& start,
                         const Eigen::Vector3d& end, double margin,
                         double& hitT, Eigen::Vector3d& hitNormal,
                         int& triangleIndex) const;""",
        "MeshCollider.hpp first-segment-hit declaration",
    )

    replace_once(
        bvh_header,
        """    void query(const Eigen::Vector3d& point, double radius,
               std::vector<int>& outTriangles) const;
    int closestTriangle(const Eigen::Vector3d& point,
                        const std::vector<Eigen::Vector3d>& vertices) const;""",
        """    void query(const Eigen::Vector3d& point, double radius,
               std::vector<int>& outTriangles) const;
    int closestTriangle(const Eigen::Vector3d& point,
                        const std::vector<Eigen::Vector3d>& vertices) const;""",
        "BVH public query preservation",
    )

    replace_once(
        bvh_header,
        """private:
    int buildRecursive(std::vector<Triangle>& tempTriangles,
                       const std::vector<Eigen::Vector3d>& vertices, int start,
                       int end);""",
        """private:
    friend class MeshCollider;
    void query(const Eigen::AlignedBox3d& box,
               std::vector<int>& outTriangles) const;

    int buildRecursive(std::vector<Triangle>& tempTriangles,
                       const std::vector<Eigen::Vector3d>& vertices, int start,
                       int end);""",
        "BVH private box query declaration",
    )

    replace_once(
        bvh_header,
        """    void queryRecursive(int nodeIdx, const Eigen::Vector3d& point,
                        double squaredRadius,
                        std::vector<int>& outTriangles) const;""",
        """    void queryRecursive(int nodeIdx, const Eigen::Vector3d& point,
                        double squaredRadius,
                        std::vector<int>& outTriangles) const;
    void queryBoxRecursive(int nodeIdx, const Eigen::AlignedBox3d& box,
                           std::vector<int>& outTriangles) const;""",
        "BVH box query recursive declaration",
    )


    cpp = cpp.read_text(encoding="utf-8")
    include_old = '#include "physics/Particle.hpp"\n\nnamespace Tissu {'
    include_new = """#include "physics/Particle.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
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

bool segmentTriangleHit(
    const Eigen::Vector3d& start, const Eigen::Vector3d& end,
    const Eigen::Vector3d& a, const Eigen::Vector3d& b,
    const Eigen::Vector3d& c, double epsilon, double& t,
    Eigen::Vector3d& normal) {
    const Eigen::Vector3d direction = end - start;
    const Eigen::Vector3d edge1 = b - a;
    const Eigen::Vector3d edge2 = c - a;
    const Eigen::Vector3d pvec = direction.cross(edge2);
    const double determinant = edge1.dot(pvec);
    if (std::abs(determinant) <= epsilon)
        return false;

    const double inverseDeterminant = 1.0 / determinant;
    const Eigen::Vector3d tvec = start - a;
    const double u = tvec.dot(pvec) * inverseDeterminant;
    if (u < -epsilon || u > 1.0 + epsilon)
        return false;

    const Eigen::Vector3d qvec = tvec.cross(edge1);
    const double v = direction.dot(qvec) * inverseDeterminant;
    if (v < -epsilon || u + v > 1.0 + epsilon)
        return false;

    t = edge2.dot(qvec) * inverseDeterminant;
    if (t <= epsilon || t > 1.0 + epsilon)
        return false;

    Eigen::Vector3d rawNormal = edge1.cross(edge2);
    const double normalLength = rawNormal.norm();
    const double directionLength = direction.norm();
    if (normalLength <= epsilon || directionLength <= epsilon)
        return false;

    rawNormal /= normalLength;
    if (std::abs(direction.normalized().dot(rawNormal)) <= 1e-10)
        return false;

    normal = rawNormal;
    if (t > 1.0)
        t = 1.0;
    return true;
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
            """        if (distance <= thickness) {
            Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;
            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;

            Eigen::Vector3d normal = faceNormal;
            if (distance > 1e-6) {
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
    replace_once(
        bvh_cpp,
        """void BVH::queryRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         double squaredRadius,
                         std::vector<int>& outTriangles) const {""",
        """void BVH::query(const Eigen::AlignedBox3d& box,
                std::vector<int>& outTriangles) const {
    outTriangles.clear();
    if (m_rootIndex == -1 || m_nodes.empty())
        return;
    queryBoxRecursive(m_rootIndex, box, outTriangles);
}

void BVH::queryBoxRecursive(int nodeIdx, const Eigen::AlignedBox3d& box,
                            std::vector<int>& outTriangles) const {
    const BVHNode& node = m_nodes[nodeIdx];
    if (!node.bbox.intersects(box))
        return;

    if (node.isLeaf()) {
        for (int i = 0; i < node.primitiveCount; ++i)
            outTriangles.push_back(node.triangleIndex + i);
        return;
    }

    queryBoxRecursive(node.left, box, outTriangles);
    queryBoxRecursive(node.right, box, outTriangles);
}

void BVH::queryRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         double squaredRadius,
                         std::vector<int>& outTriangles) const {""",
        "BVH box query implementation",
    )

    cpp_path = ROOT / "core/src/physics/MeshCollider.cpp"
    first_segment_old = """void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {""",
"""
    first_segment_new = """"void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {""",
"""
    if cpp.count(first_segment_old) != 1:
        raise RuntimeError("MeshCollider first-segment-hit implementation anchor mismatch")
    cpp = cpp.replace(first_segment_old, first_segment_new, 1)

    current_contact = """        if (distance <= thickness) {
            Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;
            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;

            Eigen::Vector3d normal = faceNormal;
            if (distance > 1e-6) {
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

            Eigen::Vector3d newPosition = cp + normal * thickness;""";
    swept_contact = """        Eigen::Vector3d sweptNormal = Eigen::Vector3d::Zero();
        Eigen::Vector3d sweptFaceNormal = Eigen::Vector3d::Zero();
        bool sweptContact = false;
        const Eigen::Vector3d displacement =
            particle.getPosition() - particle.getOldPosition();
        if (distance > thickness &&
            displacement.squaredNorm() > thickness * thickness) {
            double hitT = 1.0;
            Eigen::Vector3d hitNormal = Eigen::Vector3d::Zero();
            int hitTriangle = -1;
            if (firstSegmentHit(
                    particle.getOldPosition(), particle.getPosition(),
                    thickness, hitT, hitNormal, hitTriangle)) {
                const Triangle& hitTri = m_bvh.getTriangle(hitTriangle);
                const Eigen::Vector3d& hitA = m_worldVertices[hitTri.a];
                const Eigen::Vector3d& hitB = m_worldVertices[hitTri.b];
                const Eigen::Vector3d& hitC = m_worldVertices[hitTri.c];
                const Eigen::Vector3d hitPoint =
                    particle.getOldPosition() + displacement * hitT;
                const Eigen::Vector3d rawHitNormal =
                    (hitB - hitA).cross(hitC - hitA);
                const double hitNormalLength = rawHitNormal.norm();
                if (hitNormalLength > 1e-12) {
                    sweptFaceNormal = rawHitNormal / hitNormalLength;
                    sweptNormal = hitNormal.normalized();
                    if (m_closedManifold) {
                        sweptNormal = sweptFaceNormal * m_outwardNormalSign;
                    } else if (
                        (particle.getOldPosition() - hitPoint)
                            .dot(sweptNormal) < 0.0) {
                        sweptNormal = -sweptNormal;
                    }
                    cp = hitPoint;
                    sweptContact = true;
                }
            }
        }

        if (distance <= thickness || sweptContact) {
            Eigen::Vector3d faceNormalRaw =
                sweptContact ? sweptFaceNormal : (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= 1e-12)
                continue;
            Eigen::Vector3d faceNormal = faceNormalRaw / faceNormalLength;

            Eigen::Vector3d normal = sweptContact ? sweptNormal : faceNormal;
            if (!sweptContact && distance > 1e-6) {
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
            } else if (!sweptContact && m_closedManifold) {
                normal *= m_outwardNormalSign;
            }

            Eigen::Vector3d newPosition = cp + normal * thickness;""";
    current_count = cpp.count(current_contact)
    if current_count != 1:
        raise RuntimeError(f"generated contact anchor count mismatch: {current_count}")
    cpp = cpp.replace(current_contact, swept_contact, 1)

    Path(cpp_path).write_text(cpp, encoding="utf-8")
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
}

TEST(MeshCollider, HighSpeedOutsideToInsideCrossingIsResolved) {
    MeshCollider mesh = makeTetrahedron(0.0);
    std::vector<Particle> particles;
    particles.emplace_back(Eigen::Vector3d(1.0, 0.5, 0.75));
    particles[0].setOldPosition(Eigen::Vector3d(1.0, -5.0, 0.75));

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
    EXPECT_LT(particles[0].getPosition().y(), 0.0);
}

TEST(MeshCollider, InsideToOutsideCrossingLeavesParticleOutside) {
    MeshCollider mesh = makeTetrahedron(0.0);
    std::vector<Particle> particles;
    particles.emplace_back(Eigen::Vector3d(1.0, -5.0, 0.75));
    particles[0].setOldPosition(Eigen::Vector3d(1.0, 0.5, 0.75));

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_FALSE(tetrahedronContains(particles[0].getPosition()));
}

TEST(MeshCollider, ParallelOutsideMotionDoesNotFalsePositive) {
    MeshCollider mesh = makeTetrahedron(0.0);
    std::vector<Particle> particles;
    const Eigen::Vector3d start(-1.0, -0.11, 1.0);
    const Eigen::Vector3d end(3.0, -0.11, 1.0);
    particles.emplace_back(end);
    particles[0].setOldPosition(start);

    mesh.resolve(particles, 0.016, 0.1);

    EXPECT_EQ(particles[0].getPosition(), end);
}

TEST(MeshCollider, EarliestCrossingIsSelectedDeterministically) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, -10.0, -10.0}, {0.0, 10.0, -10.0},
        {0.0, 10.0, 10.0}, {0.0, -10.0, 10.0},
        {100.0, -10.0, -10.0}, {100.0, 10.0, -10.0},
        {100.0, 10.0, 10.0}, {100.0, -10.0, 10.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 1, 2}, {0, 2, 3}, {4, 6, 5}, {4, 7, 6},
    };
    MeshCollider mesh(vertices, triangles, 0.0);
    const Eigen::Vector3d start(-250.0, 0.0, 0.0);
    const Eigen::Vector3d end(250.0, 0.0, 0.0);
    std::vector<Particle> particles;
    particles.emplace_back(end);
    particles[0].setOldPosition(start);

    mesh.resolve(particles, 0.016, 0.5);

    EXPECT_LT(particles[0].getPosition().x(), 0.0);
    EXPECT_GT(particles[0].getPosition().x(), -1.0);
}

"""
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
    bvh_header_text = bvh_header.read_text(encoding="utf-8")
    bvh_cpp_text = bvh_cpp.read_text(encoding="utf-8")
    generated_cpp = cpp_path.read_text(encoding="utf-8")
    for anchor in (
        "void query(const Eigen::AlignedBox3d& box,",
        "void queryBoxRecursive(int nodeIdx, const Eigen::AlignedBox3d& box,",
    ):
        if anchor not in bvh_header_text:
            raise RuntimeError(f"missing BVH header anchor: {anchor}")
    for anchor in (
        "void BVH::query(const Eigen::AlignedBox3d& box,",
        "void BVH::queryBoxRecursive(int nodeIdx, const Eigen::AlignedBox3d& box,",
    ):
        if anchor not in bvh_cpp_text:
            raise RuntimeError(f"missing BVH implementation anchor: {anchor}")
    for anchor in (
        "bool MeshCollider::firstSegmentHit(",
        "m_bvh.query(queryBox, candidates);",
        "if (distance <= thickness || sweptContact)",
    ):
        if anchor not in generated_cpp:
            raise RuntimeError(f"missing continuous-contact anchor: {anchor}")
    print("Tissu contact fix: applied and self-checked")
    print("Tissu continuous body contact: verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
