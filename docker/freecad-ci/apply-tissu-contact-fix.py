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
    solver_header = ROOT / "core/include/physics/Solver.hpp"
    solver_cpp = ROOT / "core/src/physics/Solver.cpp"
    stitch_header = ROOT / "core/include/physics/StitchConstraint.hpp"
    stitch_cpp = ROOT / "core/src/physics/StitchConstraint.cpp"
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

    replace_once(
        header,
        """    void resolve(std::vector<Particle>& particles, double dt,
                 double thickness) override;""",
        """    void resolve(std::vector<Particle>& particles, double dt,
                 double thickness) override;

    bool firstSegmentHit(const Eigen::Vector3d& start,
                         const Eigen::Vector3d& end,
                         double& hitT, Eigen::Vector3d& hitNormal,
                         int& hitTriangle, bool& hitEntering) const;""",
        "MeshCollider firstSegmentHit declaration",
    )

    replace_once(
        cpp_path,
        """#include <utility>

namespace Tissu {""",
        """#include <utility>
#include <limits>

namespace Tissu {""",
        "MeshCollider numeric limits include",
    )
    replace_once(
        cpp_path,
        """return {true, signedVolume > 0.0 ? 1.0 : -1.0};
}

} // namespace

MeshCollider::MeshCollider""",
        """return {true, signedVolume > 0.0 ? 1.0 : -1.0};
}

bool segmentTriangleHit(
    const Eigen::Vector3d& start,
    const Eigen::Vector3d& end,
    const Eigen::Vector3d& a,
    const Eigen::Vector3d& b,
    const Eigen::Vector3d& c,
    double& hitT, Eigen::Vector3d& hitNormal) {
    constexpr double kEpsilon = 1.0e-10;
    const Eigen::Vector3d direction = end - start;
    const Eigen::Vector3d edge1 = b - a;
    const Eigen::Vector3d edge2 = c - a;
    const Eigen::Vector3d pvec = direction.cross(edge2);
    const double det = edge1.dot(pvec);
    // Coplanar/tangent segments do not cross the surface.
    if (std::abs(det) <= kEpsilon)
        return false;

    const double invDet = 1.0 / det;
    const Eigen::Vector3d tvec = start - a;
    const double u = tvec.dot(pvec) * invDet;
    if (u < -kEpsilon || u > 1.0 + kEpsilon)
        return false;

    const Eigen::Vector3d qvec = tvec.cross(edge1);
    const double v = direction.dot(qvec) * invDet;
    if (v < -kEpsilon || u + v > 1.0 + kEpsilon)
        return false;

    const double t = edge2.dot(qvec) * invDet;
    if (t <= kEpsilon || t >= 1.0 - kEpsilon)
        return false;

    Eigen::Vector3d rawNormal = edge1.cross(edge2);
    const double normalLength = rawNormal.norm();
    if (normalLength <= kEpsilon)
        return false;
    rawNormal /= normalLength;

    hitT = t;
    hitNormal = rawNormal;
    return true;
}

} // namespace

MeshCollider::MeshCollider""",
        "MeshCollider segment intersection helper",
    )
    replace_once(
        cpp_path,
        """void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {""",
        """bool MeshCollider::firstSegmentHit(
    const Eigen::Vector3d& start,
    const Eigen::Vector3d& end,
    double& hitT, Eigen::Vector3d& hitNormal,
    int& hitTriangle, bool& hitEntering) const {
    const Eigen::Vector3d segment = end - start;
    const double length = segment.norm();
    if (length <= 1.0e-12)
        return false;

    std::vector<int> candidates;
    const Eigen::Vector3d midpoint = 0.5 * (start + end);
    m_bvh.query(midpoint, 0.5 * length + 1.0e-9, candidates);
    std::sort(candidates.begin(), candidates.end());
    candidates.erase(
        std::unique(candidates.begin(), candidates.end()), candidates.end());

    // Only an entering crossing through a closed manifold is a stitch barrier.
    // Exit and tangent motion stay unclipped; open meshes have no inside test.
    double bestT = std::numeric_limits<double>::infinity();
    int bestTriangle = -1;
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();

    for (const int triIdx : candidates) {
        const Triangle& tri = m_bvh.getTriangle(triIdx);
        double candidateT = 0.0;
        Eigen::Vector3d candidateNormal = Eigen::Vector3d::Zero();
        if (!segmentTriangleHit(
                start,
                end,
                m_worldVertices[tri.a],
                m_worldVertices[tri.b],
                m_worldVertices[tri.c],
                candidateT,
                candidateNormal)) {
            continue;
        }

        if (!m_closedManifold)
            continue;

        candidateNormal *= m_outwardNormalSign;
        if ((end - start).dot(candidateNormal) >= -1.0e-10)
            continue;

        if (candidateT < bestT - 1.0e-12 ||
            (std::abs(candidateT - bestT) <= 1.0e-12 &&
             (bestTriangle == -1 || triIdx < bestTriangle))) {
            bestT = candidateT;
            bestTriangle = triIdx;
            bestNormal = candidateNormal;
        }
    }

    if (bestTriangle == -1)
        return false;

    hitT = bestT;
    hitNormal = bestNormal;
    hitTriangle = bestTriangle;
    hitEntering = true;
    return true;
}
void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {"""

    )

    replace_once(
        stitch_header,
        """namespace Tissu {

class StitchConstraint""",
        """namespace Tissu {

class MeshCollider;

class StitchConstraint""",
        "StitchConstraint MeshCollider forward declaration",
    )
    replace_once(
        stitch_header,
        """    void solve(std::vector<Particle>& particles, double dt) override;""",
        """    void solve(std::vector<Particle>& particles, double dt) override;

    void solveSwept(
        std::vector<Particle>& particles,
        double dt,
        const std::vector<const MeshCollider*>& meshColliders,
        double thickness);""",
        "StitchConstraint solveSwept declaration",
    )
    replace_once(
        stitch_cpp,
        """#include "physics/StitchConstraint.hpp"

namespace Tissu {""",
        """#include "physics/StitchConstraint.hpp"

#include <algorithm>
#include <cmath>

#include "physics/MeshCollider.hpp"

namespace Tissu {""",
        "StitchConstraint includes",
    )
    replace_once(
        stitch_cpp,
        """
} // namespace Tissu
""",
        r"""
void StitchConstraint::solveSwept(
    std::vector<Particle>& particles,
    double dt,
    const std::vector<const MeshCollider*>& meshColliders,
    double thickness) {
    Particle& pA = particles[m_idA];
    Particle& pB = particles[m_idB];

    const Eigen::Vector3d startA = pA.getPosition();
    const Eigen::Vector3d startB = pB.getPosition();
    const Eigen::Vector3d delta = startA - startB;
    const double currentLength = delta.norm();
    if (currentLength < 1e-6)
        return;

    const double wA = pA.getInverseMass();
    const double wB = pB.getInverseMass();
    const double wSum = wA + wB;
    if (wSum == 0.0)
        return;

    const Eigen::Vector3d norm = delta / currentLength;
    const double C = currentLength;
    const double alphaHat = m_compliance / (dt * dt);
    const double deltaLambda =
        (-C - alphaHat * m_lambda) / (wSum + alphaHat);

    const Eigen::Vector3d correctionA = wA * norm * deltaLambda;
    const Eigen::Vector3d correctionB = -wB * norm * deltaLambda;
    const double safeThickness = std::max(0.0, thickness);

    struct ClipResult {
        Eigen::Vector3d position;
        double appliedFraction = 1.0;
    };

    const auto clipEnteringCorrection =
        [&](const Eigen::Vector3d& start,
            const Eigen::Vector3d& correction) -> ClipResult {
        if (correction.squaredNorm() <= 1.0e-24)
            return {start + correction, 1.0};

        const Eigen::Vector3d end = start + correction;
        double bestT = 1.0;
        int bestColliderIndex = -1;
        int bestTriangle = -1;
        Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();

        for (int colliderIndex = 0;
             colliderIndex < static_cast<int>(meshColliders.size());
             ++colliderIndex) {
            const MeshCollider* collider = meshColliders[colliderIndex];
            if (collider == nullptr)
                continue;

            double hitT = 0.0;
            int hitTriangle = -1;
            bool hitEntering = false;
            Eigen::Vector3d hitNormal = Eigen::Vector3d::Zero();
            if (!collider->firstSegmentHit(
                    start,
                    end,
                    hitT,
                    hitNormal,
                    hitTriangle,
                    hitEntering) ||
                !hitEntering) {
                continue;
            }

            if (hitT < bestT - 1.0e-12 ||
                (std::abs(hitT - bestT) <= 1.0e-12 &&
                 (bestColliderIndex < 0 ||
                  colliderIndex < bestColliderIndex ||
                  (colliderIndex == bestColliderIndex &&
                   hitTriangle < bestTriangle)))) {
                bestT = hitT;
                bestColliderIndex = colliderIndex;
                bestTriangle = hitTriangle;
                bestNormal = hitNormal;
            }
        }

        if (bestColliderIndex < 0)
            return {end, 1.0};

        const Eigen::Vector3d hitPoint = start + correction * bestT;
        const Eigen::Vector3d clipped =
            hitPoint + bestNormal * safeThickness;
        const double correctionSquared = correction.squaredNorm();
        const double appliedFraction = std::clamp(
            (clipped - start).dot(correction) / correctionSquared,
            0.0,
            1.0);
        return {clipped, appliedFraction};
    };

    const ClipResult resultA =
        clipEnteringCorrection(startA, correctionA);
    const ClipResult resultB =
        clipEnteringCorrection(startB, correctionB);

    // XPBD lambda tracks the generalized correction actually applied. Clipping
    // only reduces delta-lambda by the mass-weighted applied correction ratio.
    const double lambdaScale =
        (wA * resultA.appliedFraction +
         wB * resultB.appliedFraction) / wSum;
    m_lambda += deltaLambda * lambdaScale;

    pA.setPosition(resultA.position);
    pB.setPosition(resultB.position);
}

} // namespace Tissu
""",

    )
    replace_once(
        solver_header,
        """    void solveConstraints(double dt);""",
        """    void solveConstraints(World& world, double dt);""",
        "Solver solveConstraints declaration",
    )
    replace_once(
        solver_cpp,
        """#include "physics/StitchConstraint.hpp"
#include "physics/VolumeConstraint.hpp""",
        """#include "physics/StitchConstraint.hpp"
#include "physics/VolumeConstraint.hpp"
#include "physics/MeshCollider.hpp""",
        "Solver MeshCollider include",
    )
    replace_once(
        solver_cpp,
        """        solveConstraints(dt);""",
        """        solveConstraints(world, dt);""",
        "Solver solveConstraints call",
    )
    replace_once(
        solver_cpp,
        """void Solver::solveConstraints(double dt) {""",
        """void Solver::solveConstraints(World& world, double dt) {
    std::vector<const MeshCollider*> meshColliders;
    for (const auto& collider : world.getColliders()) {
        if (const auto* mesh = dynamic_cast<const MeshCollider*>(collider.get()))
            meshColliders.push_back(mesh);
    }""",
        "Solver solveConstraints definition",
    )
    replace_once(
        solver_cpp,
        """            const int batchSize = static_cast<int>(batch.size());
#pragma omp parallel for
            for (int i = 0; i < batchSize; ++i) {
                const int idx = batch[i];
                m_constraints[idx]->solve(m_particles, dt);
            }""",
        """            const int batchSize = static_cast<int>(batch.size());
#pragma omp parallel for
            for (int i = 0; i < batchSize; ++i) {
                const int idx = batch[i];
                if (!meshColliders.empty()) {
                    if (auto* stitch =
                            dynamic_cast<StitchConstraint*>(m_constraints[idx].get())) {
                        stitch->solveSwept(
                            m_particles, dt, meshColliders, world.getThickness());
                        continue;
                    }
                }
                m_constraints[idx]->solve(m_particles, dt);
            }""",
        "Solver batched stitch dispatch",
    )
    replace_once(
        solver_cpp,
        """    if (m_batches.empty()) {
        for (const auto& constraint : m_constraints)
            constraint->solve(m_particles, dt);
    }""",
        """    if (m_batches.empty()) {
        for (const auto& constraint : m_constraints) {
            if (!meshColliders.empty()) {
                if (auto* stitch =
                        dynamic_cast<StitchConstraint*>(constraint.get())) {
                    stitch->solveSwept(
                        m_particles, dt, meshColliders, world.getThickness());
                    continue;
                }
            }
            constraint->solve(m_particles, dt);
        }
    }""",
        "Solver unbatched stitch dispatch",
    )

    stitch_test = ROOT / "tests/physics/test_stitch_constraint.cpp"
    let_stitch_test = stitch_test.read_text(encoding="utf-8");
    replace_once(
        stitch_test,
        """#include <vector>

#include "Eigen/Dense"
#include "physics/Particle.hpp"
#include "physics/Solver.hpp"
#include "physics/StitchConstraint.hpp""",
        """#include <array>
#include <memory>
#include <vector>

#include "Eigen/Dense"
#include "engine/World.hpp"
#include "physics/MeshCollider.hpp"
#include "physics/Particle.hpp"
#include "physics/Solver.hpp"
#include "physics/StitchConstraint.hpp""",
        "StitchConstraint test includes",
    )
    replace_once(
        stitch_test,
        """using namespace Tissu;

TEST(StitchConstraint, ParticleShareSamePosition) {""",
        """using namespace Tissu;

static std::shared_ptr<MeshCollider> makeTetrahedronCollider() {
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
    return std::make_shared<MeshCollider>(vertices, triangles, 0.0);
}

static bool tetrahedronContains(const Eigen::Vector3d& point) {
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
    for (const auto& tri : triangles) {
        const Eigen::Vector3d& a = vertices[tri[0]];
        const Eigen::Vector3d& b = vertices[tri[1]];
        const Eigen::Vector3d& c = vertices[tri[2]];
        Eigen::Vector3d normal = (b - a).cross(c - a).normalized();
        if ((center - a).dot(normal) > 0.0)
            normal = -normal;
        if ((point - a).dot(normal) > 1e-9)
            return false;
    }
    return true;
}

TEST(StitchConstraint, ParticleShareSamePosition) {""",
        "StitchConstraint test helper",
    )
    let_stitch_test += r"""

TEST(StitchConstraint, EnteringCrossingIsClassifiedAndExitIsIgnored) {
    auto collider = makeTetrahedronCollider();
    double hitT = 0.0;
    int hitTriangle = -1;
    bool hitEntering = false;
    Eigen::Vector3d hitNormal = Eigen::Vector3d::Zero();

    EXPECT_TRUE(collider->firstSegmentHit(
        Eigen::Vector3d(1.0, 2.5, 1.0),
        Eigen::Vector3d(1.0, 0.5, 1.0),
        hitT,
        hitNormal,
        hitTriangle,
        hitEntering));
    EXPECT_TRUE(hitEntering);
    EXPECT_GT(hitT, 0.0);
    EXPECT_LT(hitT, 1.0);
    EXPECT_GT(hitNormal.norm(), 0.9);

    hitEntering = false;
    EXPECT_FALSE(collider->firstSegmentHit(
        Eigen::Vector3d(1.0, 0.5, 1.0),
        Eigen::Vector3d(1.0, 2.5, 1.0),
        hitT,
        hitNormal,
        hitTriangle,
        hitEntering));
    EXPECT_FALSE(hitEntering);
}

TEST(StitchConstraint, SolverScalesLambdaToActuallyAppliedEnteringCorrection) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.01);
    world.addCollider(makeTetrahedronCollider());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int a = solver.addParticle(Eigen::Vector3d(1.0, 2.5, 1.0));
    const int b = solver.addParticle(Eigen::Vector3d(1.0, 0.5, 1.0));
    solver.setParticleInverseMass(b, 0.0);
    solver.addStitch(a, b, 0.0);

    const Eigen::Vector3d startA = solver.getParticles()[a].getPosition();
    const Eigen::Vector3d startB = solver.getParticles()[b].getPosition();
    const Eigen::Vector3d norm = (startA - startB).normalized();

    solver.update(world, 0.016);

    const double appliedLambda =
        (solver.getParticles()[a].getPosition() - startA).dot(norm);
    const double lambda = solver.getConstraints()[0]->getLambda();

    EXPECT_NEAR(lambda, appliedLambda, 1.0e-9);
    EXPECT_LT(std::abs(lambda), (startA - startB).norm());
    EXPECT_FALSE(tetrahedronContains(solver.getParticles()[a].getPosition()));
}

TEST(StitchConstraint, SolverPreservesFullNoCrossingCorrection) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.01);
    world.addCollider(makeTetrahedronCollider());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int a = solver.addParticle(Eigen::Vector3d(4.0, 3.0, 4.0));
    const int b = solver.addParticle(Eigen::Vector3d(4.0, 2.0, 4.0));
    solver.addStitch(a, b, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(solver.getParticles()[a].getPosition().y(), 2.5, 1e-9);
    EXPECT_NEAR(solver.getParticles()[b].getPosition().y(), 2.5, 1e-9);
}

TEST(StitchConstraint, SolverDoesNotClipExitMotion) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.01);
    world.addCollider(makeTetrahedronCollider());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int a = solver.addParticle(Eigen::Vector3d(1.0, 0.5, 1.0));
    const int b = solver.addParticle(Eigen::Vector3d(1.0, 4.0, 1.0));
    solver.addStitch(a, b, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(solver.getParticles()[a].getPosition().y(), 2.25, 1e-9);
    EXPECT_NEAR(solver.getParticles()[b].getPosition().y(), 2.25, 1e-9);
}
"""

    stitch_test.write_text(let_stitch_test, encoding="utf-8")

    let_mesh_test = test.read_text(encoding="utf-8");
    let_mesh_test += r"""

TEST(MeshCollider, SegmentHitRejectsCoplanarTangentAndFindsCrossing) {
    const std::vector<Eigen::Vector3d> vertices = {
        {-2.0, 0.0, -2.0},
        {2.0, 0.0, -2.0},
        {0.0, 0.0, 2.0},
    };
    const std::vector<std::array<int, 3>> triangles = {{0, 1, 2}};
    MeshCollider mesh(vertices, triangles, 0.0);

    double hitT = 0.0;
    Eigen::Vector3d hitNormal = Eigen::Vector3d::Zero();
    int hitTriangle = -1;
    bool hitEntering = false;
    EXPECT_FALSE(mesh.firstSegmentHit(
        Eigen::Vector3d(-1.0, 0.0, 0.0),
        Eigen::Vector3d(1.0, 0.0, 0.0),
        hitT,
        hitNormal,
        hitTriangle,
        hitEntering));
    EXPECT_FALSE(mesh.firstSegmentHit(
        Eigen::Vector3d(0.0, -1.0, 0.0),
        Eigen::Vector3d(0.0, 1.0, 0.0),
        hitT,
        hitNormal,
        hitTriangle,
        hitEntering));
}
"""
    test.write_text(let_mesh_test, encoding="utf-8")

    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "tests/physics/test_mesh_collider.cpp",
        "core/include/physics/Solver.hpp",
        "core/src/physics/Solver.cpp",
        "core/include/physics/StitchConstraint.hpp",
        "core/src/physics/StitchConstraint.cpp",
        "tests/physics/test_stitch_constraint.cpp",
    }
    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "tests/physics/test_mesh_collider.cpp",
        "core/include/physics/Solver.hpp",
        "core/src/physics/Solver.cpp",
        "core/include/physics/StitchConstraint.hpp",
        "core/src/physics/StitchConstraint.cpp",
        "tests/physics/test_stitch_constraint.cpp",
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
