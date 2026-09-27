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
    stitch_header = ROOT / "core/include/physics/StitchConstraint.hpp"
    stitch_cpp = ROOT / "core/src/physics/StitchConstraint.cpp"
    solver_header = ROOT / "core/include/physics/Solver.hpp"
    solver_cpp = ROOT / "core/src/physics/Solver.cpp"
    stitch_test = ROOT / "tests/physics/test_stitch_constraint.cpp"

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


    bvh_header_text = bvh_header.read_text(encoding="utf-8")
    replace_once(
        bvh_header,
        """    void query(const Eigen::Vector3d& point, double radius,
               std::vector<int>& outTriangles) const;
    int closestTriangle(const Eigen::Vector3d& point,
                        const std::vector<Eigen::Vector3d>& vertices) const;""",
        """    void query(const Eigen::Vector3d& point, double radius,
               std::vector<int>& outTriangles) const;
    void query(const Eigen::AlignedBox3d& box,
               std::vector<int>& outTriangles) const;
    int closestTriangle(const Eigen::Vector3d& point,
                        const std::vector<Eigen::Vector3d>& vertices) const;""",
        "BVH box query declaration",
    )

    replace_once(
        bvh_header,
        """    void queryRecursive(int nodeIdx, const Eigen::Vector3d& point,
                        double squaredRadius,
                        std::vector<int>& outTriangles) const;
    int closestRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices,
                         double& bestDistSq) const;""",
        """    void queryRecursive(int nodeIdx, const Eigen::Vector3d& point,
                        double squaredRadius,
                        std::vector<int>& outTriangles) const;
    void queryBoxRecursive(int nodeIdx, const Eigen::AlignedBox3d& box,
                           std::vector<int>& outTriangles) const;
    int closestRecursive(int nodeIdx, const Eigen::Vector3d& point,
                         const std::vector<Eigen::Vector3d>& vertices,
                         double& bestDistSq) const;""",
        "BVH box helper declaration",
    )

    bvh_cpp_text = bvh_cpp.read_text(encoding="utf-8")
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

    replace_once(
        ROOT / "core/include/physics/MeshCollider.hpp",
        """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

private:""",
        """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

    // Returns the earliest proper segment/triangle crossing in [start, end].
    bool firstSegmentHit(const Eigen::Vector3d& start,
                         const Eigen::Vector3d& end, double margin,
                         double& hitT, Eigen::Vector3d& hitNormal,
                         int& triangleIndex) const;

private:""",
        "MeshCollider first-segment-hit declaration",
    )

    replace_once(
        ROOT / "core/src/physics/MeshCollider.cpp",
        """#include "physics/MeshCollider.hpp"

#include "io/OBJLoader.hpp""",
        """#include "physics/MeshCollider.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

#include "io/OBJLoader.hpp""",
        "MeshCollider first-segment-hit includes",
    )

    replace_once(
        ROOT / "core/src/physics/MeshCollider.cpp",
        """namespace Tissu {

MeshCollider::MeshCollider(const std::string& meshPath, double friction)
    : m_meshPath(meshPath) {""",
        """namespace Tissu {

namespace {

bool segmentTriangleHit(const Eigen::Vector3d& start,
                        const Eigen::Vector3d& end,
                        const Eigen::Vector3d& a,
                        const Eigen::Vector3d& b,
                        const Eigen::Vector3d& c, double epsilon,
                        double& t, Eigen::Vector3d& normal) {
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
    // Reject grazing/tangent contact: a stitch correction must actually cross
    // the triangle plane rather than merely touch or run along it.
    if (std::abs(direction.normalized().dot(rawNormal)) <= 1e-10)
        return false;

    normal = rawNormal;
    if (t > 1.0)
        t = 1.0;
    return true;
}

} // namespace

MeshCollider::MeshCollider(const std::string& meshPath, double friction) {""",
        "MeshCollider first-segment-hit helper",
    )

    replace_once(
        ROOT / "core/src/physics/MeshCollider.cpp",
        """void MeshCollider::resolve(std::vector<Particle>& particles, double dt,""",
        """bool MeshCollider::firstSegmentHit(const Eigen::Vector3d& start,
                                   const Eigen::Vector3d& end, double margin,
                                   double& hitT, Eigen::Vector3d& hitNormal,
                                   int& triangleIndex) const {
    const double safeMargin = std::max(0.0, margin);
    const Eigen::Vector3d segmentMin =
        start.cwiseMin(end) - Eigen::Vector3d::Constant(safeMargin);
    const Eigen::Vector3d segmentMax =
        start.cwiseMax(end) + Eigen::Vector3d::Constant(safeMargin);
    const Eigen::AlignedBox3d queryBox(segmentMin, segmentMax);

    std::vector<int> candidates;
    m_bvh.query(queryBox, candidates);
    std::sort(candidates.begin(), candidates.end());
    candidates.erase(std::unique(candidates.begin(), candidates.end()),
                     candidates.end());

    constexpr double epsilon = 1e-12;
    double bestT = std::numeric_limits<double>::infinity();
    int bestTriangle = -1;
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();

    for (const int candidateIndex : candidates) {
        const Triangle& tri = m_bvh.getTriangle(candidateIndex);
        double candidateT = 0.0;
        Eigen::Vector3d candidateNormal = Eigen::Vector3d::Zero();
        if (!segmentTriangleHit(start, end, m_worldVertices[tri.a],
                                m_worldVertices[tri.b], m_worldVertices[tri.c],
                                epsilon, candidateT, candidateNormal))
            continue;

        if (candidateT < bestT - epsilon ||
            (std::abs(candidateT - bestT) <= epsilon &&
             (bestTriangle < 0 || candidateIndex < bestTriangle))) {
            bestT = candidateT;
            bestTriangle = candidateIndex;
            bestNormal = candidateNormal;
        }
    }

    if (bestTriangle < 0)
        return false;

    hitT = bestT;
    hitNormal = bestNormal;
    triangleIndex = bestTriangle;
    return true;
}

void MeshCollider::resolve(std::vector<Particle>& particles, double dt,""",
        "MeshCollider first-segment-hit method",
    )

    replace_once(
        ROOT / "core/include/physics/StitchConstraint.hpp",
        """#pragma once
#include "physics/Constraint.hpp""",
        """#pragma once
#include <memory>
#include "physics/Constraint.hpp""",
        "StitchConstraint memory include",
    )
    replace_once(
        ROOT / "core/include/physics/StitchConstraint.hpp",
        """namespace Tissu {

class StitchConstraint""",
        """namespace Tissu {

class Collider;

class StitchConstraint""",
        "StitchConstraint collider forward declaration",
    )
    replace_once(
        ROOT / "core/include/physics/StitchConstraint.hpp",
        """    void solve(std::vector<Particle>& particles, double dt) override;
    std::vector<int>""",
        """    void solve(std::vector<Particle>& particles, double dt) override;
    std::vector<int>""",
        "StitchConstraint public API declaration",
    )
    replace_once(
        ROOT / "core/include/physics/StitchConstraint.hpp",
        """private:
    int m_idA;""",
        """private:
    friend class Solver;
    void solveWithColliders(
        std::vector<Particle>& particles, double dt,
        const std::vector<std::shared_ptr<Collider>>& colliders,
        double thickness);
    void solveInternal(
        std::vector<Particle>& particles, double dt,
        const std::vector<std::shared_ptr<Collider>>* colliders,
        double thickness);

    int m_idA;""",
        "StitchConstraint private collision-aware solve declaration",
    )

    replace_once(
        ROOT / "core/src/physics/StitchConstraint.cpp",
        """#include "physics/StitchConstraint.hpp"

namespace Tissu {""",
        """#include "physics/StitchConstraint.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

#include "physics/Collider.hpp"
#include "physics/MeshCollider.hpp"

namespace Tissu {""",
        "StitchConstraint collision-aware includes",
    )

    stitch_cpp_text = (ROOT / "core/src/physics/StitchConstraint.cpp").read_text(encoding="utf-8")
    replace_once(
        ROOT / "core/src/physics/StitchConstraint.cpp",
        """void StitchConstraint::solve(std::vector<Particle>& particles, double dt) {
    Particle& pA = particles[m_idA];
    Particle& pB = particles[m_idB];

    Eigen::Vector3d delta = pA.getPosition() - pB.getPosition();
    double currentLength = delta.norm();
    if (currentLength < 1e-6)
        return;

    double wA = pA.getInverseMass();
    double wB = pB.getInverseMass();
    double wSum = wA + wB;
    if (wSum == 0.0)
        return;

    Eigen::Vector3d norm = delta / currentLength;
    double C = currentLength;
    double alphaHat = m_compliance / (dt * dt);
    double deltaLambda = (-C - alphaHat * m_lambda) / (wSum + alphaHat);
    m_lambda += deltaLambda;

    pA.setPosition(pA.getPosition() + wA * norm * deltaLambda);
    pB.setPosition(pB.getPosition() - wB * norm * deltaLambda);
}""",
        """namespace {

struct ClippedCorrection {
    Eigen::Vector3d position;
    double scale;
};

ClippedCorrection clipCorrectionAtFirstMeshHit(
    const Eigen::Vector3d& start, const Eigen::Vector3d& correction,
    const std::vector<std::shared_ptr<Collider>>& colliders, double thickness) {
    if (correction.squaredNorm() <= 1e-18)
        return {start + correction, 1.0};

    const Eigen::Vector3d end = start + correction;
    double bestT = 1.0;
    int bestCollider = -1;
    int bestTriangle = -1;
    Eigen::Vector3d bestPoint = end;
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();

    for (int colliderIndex = 0;
         colliderIndex < static_cast<int>(colliders.size()); ++colliderIndex) {
        const auto& collider = colliders[colliderIndex];
        const auto* mesh = dynamic_cast<const MeshCollider*>(collider.get());
        if (mesh == nullptr)
            continue;

        double hitT = 0.0;
        Eigen::Vector3d hitNormal = Eigen::Vector3d::Zero();
        int hitTriangle = -1;
        if (!mesh->firstSegmentHit(start, end, thickness, hitT, hitNormal,
                                   hitTriangle))
            continue;

        if (hitT < bestT - 1e-12 ||
            (std::abs(hitT - bestT) <= 1e-12 &&
             (bestCollider < 0 || colliderIndex < bestCollider ||
              (colliderIndex == bestCollider && hitTriangle < bestTriangle)))) {
            bestT = hitT;
            bestCollider = colliderIndex;
            bestTriangle = hitTriangle;
            bestPoint = start + correction * hitT;
            bestNormal = hitNormal;
        }
    }

    if (bestCollider < 0)
        return {end, 1.0};

    if ((start - bestPoint).dot(bestNormal) < 0.0)
        bestNormal = -bestNormal;

    return {
        bestPoint + bestNormal * std::max(0.0, thickness),
        bestT,
    };
}

} // namespace

void StitchConstraint::solve(std::vector<Particle>& particles, double dt) {
    solveInternal(particles, dt, nullptr, 0.0);
}

void StitchConstraint::solveWithColliders(
    std::vector<Particle>& particles, double dt,
    const std::vector<std::shared_ptr<Collider>>& colliders, double thickness) {
    solveInternal(particles, dt, &colliders, thickness);
}

void StitchConstraint::solveInternal(
    std::vector<Particle>& particles, double dt,
    const std::vector<std::shared_ptr<Collider>>* colliders, double thickness) {
    Particle& pA = particles[m_idA];
    Particle& pB = particles[m_idB];

    Eigen::Vector3d delta = pA.getPosition() - pB.getPosition();
    double currentLength = delta.norm();
    if (currentLength < 1e-6)
        return;

    double wA = pA.getInverseMass();
    double wB = pB.getInverseMass();
    double wSum = wA + wB;
    if (wSum == 0.0)
        return;

    Eigen::Vector3d norm = delta / currentLength;
    double C = currentLength;
    double alphaHat = m_compliance / (dt * dt);
    double deltaLambda = (-C - alphaHat * m_lambda) / (wSum + alphaHat);
    const Eigen::Vector3d correctionA = wA * norm * deltaLambda;
    const Eigen::Vector3d correctionB = -wB * norm * deltaLambda;

    if (colliders != nullptr && !colliders->empty()) {
        const ClippedCorrection clippedA = clipCorrectionAtFirstMeshHit(
            pA.getPosition(), correctionA, *colliders, thickness);
        const ClippedCorrection clippedB = clipCorrectionAtFirstMeshHit(
            pB.getPosition(), correctionB, *colliders, thickness);

        // Lambda tracks the stitch-normal component actually applied before
        // collision-thickness offsets, so repeated iterations remain coherent
        // even when the two endpoints hit different barriers.
        const double appliedScale =
            (wA * clippedA.scale + wB * clippedB.scale) / wSum;
        m_lambda += deltaLambda * appliedScale;
        pA.setPosition(clippedA.position);
        pB.setPosition(clippedB.position);
        return;
    }

    m_lambda += deltaLambda;
    pA.setPosition(pA.getPosition() + correctionA);
    pB.setPosition(pB.getPosition() + correctionB);
}""",
        "StitchConstraint collision-aware solve implementation",
    )

    replace_once(
        ROOT / "core/include/physics/Solver.hpp",
        """    void solveConstraints(double dt);""",
        """    void solveConstraints(World& world, double dt);""",
        "Solver solveConstraints declaration",
    )
    replace_once(
        ROOT / "core/src/physics/Solver.cpp",
        """        solveConstraints(dt);""",
        """        solveConstraints(world, dt);""",
        "Solver step collision-aware call",
    )
    replace_once(
        ROOT / "core/src/physics/Solver.cpp",
        """void Solver::solveConstraints(double dt) {""",
        """void Solver::solveConstraints(World& world, double dt) {""",
        "Solver solveConstraints definition",
    )
    replace_once(
        ROOT / "core/src/physics/Solver.cpp",
        """    if (m_batches.empty()) {
        for (const auto& constraint : m_constraints)
            constraint->solve(m_particles, dt);
    } else {
        for (const auto& batch : m_batches) {
            const int batchSize = static_cast<int>(batch.size());
#pragma omp parallel for
            for (int i = 0; i < batchSize; ++i) {
                const int idx = batch[i];
                m_constraints[idx]->solve(m_particles, dt);
            }
        }
    }""",
        """    auto solveConstraint = [&](Constraint& constraint) {
        if (auto* stitch = dynamic_cast<StitchConstraint*>(&constraint)) {
            stitch->solveWithColliders(m_particles, dt, world.getColliders(),
                                       world.getThickness());
        } else {
            constraint.solve(m_particles, dt);
        }
    };

    if (m_batches.empty()) {
        for (const auto& constraint : m_constraints)
            solveConstraint(*constraint);
    } else {
        for (const auto& batch : m_batches) {
            const int batchSize = static_cast<int>(batch.size());
#pragma omp parallel for
            for (int i = 0; i < batchSize; ++i) {
                const int idx = batch[i];
                solveConstraint(*m_constraints[idx]);
            }
        }
    }""",
        "Solver stitch dispatch",
    )

    stitch_test_text = stitch_test.read_text(encoding="utf-8")
    replace_once(
        stitch_test,
        """#include <vector>

#include "Eigen/Dense"
#include "physics/Particle.hpp" """.rstrip(),
        """#include <array>
#include <memory>
#include <vector>

#include "Eigen/Dense"
#include "engine/World.hpp"
#include "physics/MeshCollider.hpp"
#include "physics/Particle.hpp" """.rstrip(),
        "Stitch test includes",
    )
    replace_once(
        stitch_test,
        """using namespace Tissu;

TEST(StitchConstraint, ParticleShareSamePosition) {""",
        """using namespace Tissu;

static std::shared_ptr<MeshCollider> makeWall(double x, double extent = 600.0) {
    std::vector<Eigen::Vector3d> vertices = {
        {x, -extent, -extent},
        {x, extent, -extent},
        {x, extent, extent},
        {x, -extent, extent},
    };
    std::vector<std::array<int, 3>> triangles = {
        {0, 1, 2},
        {0, 2, 3},
    };
    return std::make_shared<MeshCollider>(vertices, triangles, 0.0);
}

TEST(StitchConstraint, ParticleShareSamePosition) {""",
        "Stitch test wall helper",
    )
    stitch_test_text = stitch_test.read_text(encoding="utf-8")
    stitch_test.write_text(
        stitch_test_text
        + """
        
TEST(StitchConstraint, SolverClipsLargeCorrectionAtFirstMeshCrossing) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.5);
    world.addCollider(makeWall(0.0));

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving =
        solver.addParticle(Particle(Eigen::Vector3d(-250.0, 0.0, 0.0)));
    const int anchor =
        solver.addParticle(Particle(Eigen::Vector3d(250.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_LT(solver.getParticles()[moving].getPosition().x(), -0.49);
    EXPECT_GT(solver.getParticles()[moving].getPosition().x(), -1.01);
}

TEST(StitchConstraint, SolverPreservesLongFreeSpaceCorrection) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.5);

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving =
        solver.addParticle(Particle(Eigen::Vector3d(-250.0, 0.0, 0.0)));
    const int anchor =
        solver.addParticle(Particle(Eigen::Vector3d(250.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(solver.getParticles()[moving].getPosition().x(), 250.0, 1e-9);
}

TEST(StitchConstraint, SolverDoesNotClipTangentCorrection) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.0);
    world.addCollider(makeWall(0.0));

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving =
        solver.addParticle(Particle(Eigen::Vector3d(0.0, -250.0, 0.0)));
    const int anchor =
        solver.addParticle(Particle(Eigen::Vector3d(0.0, 250.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(solver.getParticles()[moving].getPosition().x(), 0.0, 1e-9);
    EXPECT_NEAR(solver.getParticles()[moving].getPosition().y(), 250.0, 1e-9);
}

TEST(StitchConstraint, SolverMultipleIterationsKeepSweptEndpointBounded) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.5);
    world.addCollider(makeWall(0.0));

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(3);
    const int moving =
        solver.addParticle(Particle(Eigen::Vector3d(-250.0, 0.0, 0.0)));
    const int anchor =
        solver.addParticle(Particle(Eigen::Vector3d(250.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    const double x = solver.getParticles()[moving].getPosition().x();
    EXPECT_LT(x, -0.49);
    EXPECT_GT(x, -1.01);
}

TEST(StitchConstraint, SolverChoosesEarliestCrossingAcrossMultipleMeshes) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.5);
    world.addCollider(makeWall(0.0));
    world.addCollider(makeWall(100.0));

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving =
        solver.addParticle(Particle(Eigen::Vector3d(-250.0, 0.0, 0.0)));
    const int anchor =
        solver.addParticle(Particle(Eigen::Vector3d(250.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_LT(solver.getParticles()[moving].getPosition().x(), -0.49);
    EXPECT_GT(solver.getParticles()[moving].getPosition().x(), -1.01);
}
""",
        encoding="utf-8",
    )

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/data-structures/BVH.hpp",
        "core/src/data-structures/BVH.cpp",
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "core/include/physics/StitchConstraint.hpp",
        "core/src/physics/StitchConstraint.cpp",
        "core/include/physics/Solver.hpp",
        "core/src/physics/Solver.cpp",
        "tests/physics/test_mesh_collider.cpp",
        "tests/physics/test_stitch_constraint.cpp",
    }
    if set(changed.splitlines()) != expected:
        raise RuntimeError(f"unexpected patched files: {changed!r}")

    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"Tissu source commit: {EXPECTED_COMMIT}")
    print(f"Tissu contact fix script sha256: {script_sha}")
    print("Tissu contact fix: applied and self-checked")
    solver_cpp_text = solver_cpp.read_text(encoding="utf-8")
    for anchor in (
        "for (const auto& pin : m_transientPins)",
        "for (const auto& attach : m_attachments)",
        "solveWithColliders(m_particles, dt, world.getColliders(),",
        "void Solver::solveConstraints(World& world, double dt)",
    ):
        if anchor not in solver_cpp_text:
            raise RuntimeError(f"missing solver integration anchor: {anchor}")
    print("Tissu stitch sweep integration anchors: verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
