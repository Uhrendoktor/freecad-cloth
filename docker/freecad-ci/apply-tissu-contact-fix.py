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

    def patch_stitch_local_swept() -> None:
        mesh_header = ROOT / "core/include/physics/MeshCollider.hpp"
        mesh_cpp = ROOT / "core/src/physics/MeshCollider.cpp"
        stitch_header = ROOT / "core/include/physics/StitchConstraint.hpp"
        stitch_cpp = ROOT / "core/src/physics/StitchConstraint.cpp"
        solver_header = ROOT / "core/include/physics/Solver.hpp"
        solver_cpp = ROOT / "core/src/physics/Solver.cpp"
        mesh_test = ROOT / "tests/physics/test_mesh_collider.cpp"
        stitch_test = ROOT / "tests/physics/test_stitch_constraint.cpp"

        text = stitch_header.read_text(encoding="utf-8")
        old = """class StitchConstraint : public Constraint {
public:
    StitchConstraint(int idA, int idB, double compliance);

    void solve(std::vector<Particle>& particles, double dt) override;
    std::vector<int> getParticleIds() const override { return {m_idA, m_idB}; }

private:
"""
        new = """class World;
class Solver;

class StitchConstraint : public Constraint {
public:
    StitchConstraint(int idA, int idB, double compliance);

    void solve(std::vector<Particle>& particles, double dt) override;
    std::vector<int> getParticleIds() const override { return {m_idA, m_idB}; }

private:
    friend class Solver;
    void solveWithCollisionBarriers(
        std::vector<Particle>& particles,
        double dt,
        const World& world,
        double thickness);

"""
        if text.count(old) != 1:
            raise RuntimeError("StitchConstraint.hpp anchor mismatch")
        stitch_header.write_text(text.replace(old, new, 1), encoding="utf-8")

        text = mesh_header.read_text(encoding="utf-8")
        old = """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

private:
"""
        new = """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

    bool firstSegmentHit(const Eigen::Vector3d& start,
                         const Eigen::Vector3d& end,
                         double& hitT,
                         Eigen::Vector3d& hitNormal,
                         int& hitTriangle) const;

private:
"""
        if text.count(old) != 1:
            raise RuntimeError("MeshCollider.hpp segment-query anchor mismatch")
        mesh_header.write_text(text.replace(old, new, 1), encoding="utf-8")

        text = mesh_cpp.read_text(encoding="utf-8")
        old = """#include "math/Geometry.hpp"
#include "physics/Particle.hpp"
"""
        new = """#include "math/Geometry.hpp"
#include "physics/Particle.hpp"

#include <algorithm>
#include <cmath>
"""
        if text.count(old) != 1:
            raise RuntimeError("MeshCollider.cpp include anchor mismatch")
        text = text.replace(old, new, 1)

        old = """    return {true, signedVolume > 0.0 ? 1.0 : -1.0};
}

} // namespace
"""
        new = """    return {true, signedVolume > 0.0 ? 1.0 : -1.0};
}

bool segmentTriangleHit(
    const Eigen::Vector3d& start,
    const Eigen::Vector3d& end,
    const Eigen::Vector3d& a,
    const Eigen::Vector3d& b,
    const Eigen::Vector3d& c,
    double& hitT,
    Eigen::Vector3d& hitNormal) {
    const Eigen::Vector3d direction = end - start;
    if (direction.squaredNorm() <= 1.0e-18)
        return false;

    const Eigen::Vector3d edge1 = b - a;
    const Eigen::Vector3d edge2 = c - a;
    const Eigen::Vector3d pvec = direction.cross(edge2);
    const double determinant = edge1.dot(pvec);
    constexpr double epsilon = 1.0e-12;
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

    const double t = edge2.dot(qvec) * inverseDeterminant;
    if (t <= epsilon || t > 1.0 + epsilon)
        return false;

    const Eigen::Vector3d rawNormal = edge1.cross(edge2);
    const double normalLength = rawNormal.norm();
    if (normalLength <= epsilon)
        return false;

    hitT = std::clamp(t, 0.0, 1.0);
    hitNormal = rawNormal / normalLength;
    return true;
}

} // namespace
"""
        if text.count(old) != 1:
            raise RuntimeError("MeshCollider.cpp helper anchor mismatch")
        text = text.replace(old, new, 1)

        old = """void MeshCollider::transform(const Eigen::Vector3d& position,
                             const Eigen::Quaterniond& rotation) {
"""
        new = """bool MeshCollider::firstSegmentHit(
    const Eigen::Vector3d& start,
    const Eigen::Vector3d& end,
    double& hitT,
    Eigen::Vector3d& hitNormal,
    int& hitTriangle) const {
    const Eigen::Vector3d direction = end - start;
    const double length = direction.norm();
    if (length <= 1.0e-9)
        return false;

    const Eigen::Vector3d midpoint = 0.5 * (start + end);
    std::vector<int> candidates;
    m_bvh.query(midpoint, 0.5 * length + 1.0e-9, candidates);
    std::sort(candidates.begin(), candidates.end());
    candidates.erase(
        std::unique(candidates.begin(), candidates.end()), candidates.end());

    bool found = false;
    double bestT = 1.0;
    int bestTriangle = -1;
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();
    constexpr double tieEpsilon = 1.0e-12;

    for (const int candidate : candidates) {
        const Triangle& tri = m_bvh.getTriangle(candidate);
        const Eigen::Vector3d& a = m_worldVertices[tri.a];
        const Eigen::Vector3d& b = m_worldVertices[tri.b];
        const Eigen::Vector3d& c = m_worldVertices[tri.c];

        double candidateT = 1.0;
        Eigen::Vector3d candidateNormal = Eigen::Vector3d::Zero();
        if (!segmentTriangleHit(
                start, end, a, b, c, candidateT, candidateNormal))
            continue;

        if (!found || candidateT < bestT - tieEpsilon ||
            (std::abs(candidateT - bestT) <= tieEpsilon &&
             candidate < bestTriangle)) {
            found = true;
            bestT = candidateT;
            bestTriangle = candidate;
            bestNormal = candidateNormal;
        }
    }

    if (!found)
        return false;

    if (direction.dot(bestNormal) > 0.0)
        bestNormal = -bestNormal;

    hitT = bestT;
    hitNormal = bestNormal;
    hitTriangle = bestTriangle;
    return true;
}

""" + old
        if text.count(old) != 1:
            raise RuntimeError("MeshCollider.cpp method anchor mismatch")
        mesh_cpp.write_text(text.replace(old, new, 1), encoding="utf-8")

        text = stitch_cpp.read_text(encoding="utf-8")
        old = """#include "physics/StitchConstraint.hpp"

namespace Tissu {
"""
        new = """#include "physics/StitchConstraint.hpp"

#include <algorithm>
#include <cmath>
#include <memory>

#include "engine/World.hpp"
#include "physics/MeshCollider.hpp"

namespace Tissu {
"""
        if text.count(old) != 1:
            raise RuntimeError("StitchConstraint.cpp include anchor mismatch")
        text = text.replace(old, new, 1)

        old = """} // namespace Tissu
"""
        new = """void StitchConstraint::solveWithCollisionBarriers(
    std::vector<Particle>& particles,
    double dt,
    const World& world,
    double thickness) {
    Particle& pA = particles[m_idA];
    Particle& pB = particles[m_idB];

    const Eigen::Vector3d delta = pA.getPosition() - pB.getPosition();
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
    m_lambda += deltaLambda;

    const Eigen::Vector3d correctionA = wA * norm * deltaLambda;
    const Eigen::Vector3d correctionB = -wB * norm * deltaLambda;

    const auto& colliders = world.getColliders();
    auto clipEndpoint = [&](const Eigen::Vector3d& start,
                            const Eigen::Vector3d& correction) {
        if (correction.squaredNorm() <= 1.0e-18)
            return start;

        bool found = false;
        double bestT = 1.0;
        size_t bestCollider = 0;
        int bestTriangle = -1;
        Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();
        constexpr double tieEpsilon = 1.0e-12;

        const Eigen::Vector3d end = start + correction;
        for (size_t colliderIndex = 0; colliderIndex < colliders.size();
             ++colliderIndex) {
            const auto& collider = colliders[colliderIndex];
            const auto mesh =
                std::dynamic_pointer_cast<MeshCollider>(collider);
            if (!mesh)
                continue;

            double candidateT = 1.0;
            int candidateTriangle = -1;
            Eigen::Vector3d candidateNormal = Eigen::Vector3d::Zero();
            if (!mesh->firstSegmentHit(
                    start,
                    end,
                    candidateT,
                    candidateNormal,
                    candidateTriangle))
                continue;

            if (!found || candidateT < bestT - tieEpsilon ||
                (std::abs(candidateT - bestT) <= tieEpsilon &&
                 (colliderIndex < bestCollider ||
                  (colliderIndex == bestCollider &&
                   candidateTriangle < bestTriangle)))) {
                found = true;
                bestT = candidateT;
                bestCollider = colliderIndex;
                bestTriangle = candidateTriangle;
                bestNormal = candidateNormal;
            }
        }

        if (!found)
            return end;

        return start + correction * bestT +
               bestNormal * std::max(0.0, thickness);
    };

    pA.setPosition(clipEndpoint(pA.getPosition(), correctionA));
    pB.setPosition(clipEndpoint(pB.getPosition(), correctionB));
}

} // namespace Tissu
"""
        if text.count(old) != 1:
            raise RuntimeError("StitchConstraint.cpp terminator mismatch")
        stitch_cpp.write_text(text.replace(old, new, 1), encoding="utf-8")

        text = solver_header.read_text(encoding="utf-8")
        old = "    void solveConstraints(double dt);\n"
        if text.count(old) != 1:
            raise RuntimeError("Solver.hpp signature anchor mismatch")
        solver_header.write_text(
            text.replace(old, "    void solveConstraints(World& world, double dt);\n", 1),
            encoding="utf-8",
        )

        text = solver_cpp.read_text(encoding="utf-8")
        old = "        solveConstraints(dt);\n"
        if text.count(old) != 1:
            raise RuntimeError("Solver.cpp call anchor mismatch")
        text = text.replace(old, "        solveConstraints(world, dt);\n", 1)
        old = """void Solver::solveConstraints(double dt) {
    ZoneScopedN("Solve Constraints");
    if (m_batches.empty()) {
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
    }

    for (const auto& pin : m_transientPins) {
        pin->solve(m_particles, dt);
    }
"""
        new = """void Solver::solveConstraints(World& world, double dt) {
    ZoneScopedN("Solve Constraints");
    auto solveOne = [this, &world, dt](Constraint& constraint) {
        if (auto* stitch = dynamic_cast<StitchConstraint*>(&constraint)) {
            stitch->solveWithCollisionBarriers(
                m_particles, dt, world, world.getThickness());
        } else {
            constraint.solve(m_particles, dt);
        }
    };

    if (m_batches.empty()) {
        for (const auto& constraint : m_constraints)
            solveOne(*constraint);
    } else {
        for (const auto& batch : m_batches) {
            const int batchSize = static_cast<int>(batch.size());
#pragma omp parallel for
            for (int i = 0; i < batchSize; ++i) {
                const int idx = batch[i];
                solveOne(*m_constraints[idx]);
            }
        }
    }

    for (const auto& pin : m_transientPins) {
        pin->solve(m_particles, dt);
    }
"""
        if text.count(old) != 1:
            raise RuntimeError("Solver.cpp body anchor mismatch")
        solver_cpp.write_text(text.replace(old, new, 1), encoding="utf-8")

        text = mesh_test.read_text(encoding="utf-8")
        old = """TEST(MeshCollider, OpenMeshRetainsLegacyContactDirection) {
"""
        new = """TEST(MeshCollider, FirstSegmentHitIsDeterministicAndFindsEarliestCrossing) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0}, {2.0, 0.0, 0.0}, {0.0, 0.0, 2.0}, {2.0, 0.0, 2.0},
        {0.0, -2.0, 0.0}, {2.0, -2.0, 0.0}, {0.0, -2.0, 2.0}, {2.0, -2.0, 2.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 1, 2}, {2, 1, 3}, {4, 5, 6}, {6, 5, 7},
    };
    MeshCollider mesh(vertices, triangles, 0.0);

    double firstT = 0.0;
    Eigen::Vector3d firstNormal = Eigen::Vector3d::Zero();
    int firstTriangle = -1;
    ASSERT_TRUE(mesh.firstSegmentHit(
        {1.0, 1.0, 1.0}, {1.0, -3.0, 1.0},
        firstT, firstNormal, firstTriangle));

    double secondT = 0.0;
    Eigen::Vector3d secondNormal = Eigen::Vector3d::Zero();
    int secondTriangle = -1;
    ASSERT_TRUE(mesh.firstSegmentHit(
        {1.0, 1.0, 1.0}, {1.0, -3.0, 1.0},
        secondT, secondNormal, secondTriangle));

    EXPECT_NEAR(firstT, 0.25, 1e-12);
    EXPECT_EQ(firstTriangle, secondTriangle);
    EXPECT_NEAR(firstT, secondT, 1e-15);
    EXPECT_GT(firstNormal.dot(Eigen::Vector3d(0.0, 1.0, 0.0)), 0.0);
}

TEST(MeshCollider, FirstSegmentHitRejectsTangentMotion) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0}, {2.0, 0.0, 0.0}, {0.0, 0.0, 2.0},
    };
    const std::vector<std::array<int, 3>> triangles = {{0, 1, 2}};
    MeshCollider mesh(vertices, triangles, 0.0);

    double hitT = 0.0;
    Eigen::Vector3d hitNormal = Eigen::Vector3d::Zero();
    int hitTriangle = -1;
    EXPECT_FALSE(mesh.firstSegmentHit(
        {0.25, 0.0, 0.25}, {1.75, 0.0, 0.25},
        hitT, hitNormal, hitTriangle));
}

TEST(MeshCollider, OpenMeshRetainsLegacyContactDirection) {
"""
        if text.count(old) != 1:
            raise RuntimeError("MeshCollider test insertion anchor mismatch")
        mesh_test.write_text(text.replace(old, new, 1), encoding="utf-8")

        text = stitch_test.read_text(encoding="utf-8")
        old = """#include <vector>

#include "Eigen/Dense"
"""
        new = """#include <array>
#include <memory>
#include <vector>

#include "Eigen/Dense"
#include "engine/World.hpp"
#include "physics/MeshCollider.hpp"
"""
        if text.count(old) != 1:
            raise RuntimeError("Stitch test include anchor mismatch")
        text = text.replace(old, new, 1)
        old = """using namespace Tissu;

TEST(StitchConstraint, ParticleShareSamePosition) {
"""
        new = """using namespace Tissu;

namespace {

std::shared_ptr<MeshCollider> makeTestPlane(double y) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, y, -20.0}, {20.0, y, -20.0},
        {0.0, y, 20.0}, {20.0, y, 20.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 1, 2}, {2, 1, 3},
    };
    return std::make_shared<MeshCollider>(vertices, triangles, 0.0);
}

} // namespace

TEST(StitchConstraint, SolverPreservesExactFreeSpaceCorrection) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.05);

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    solver.addParticle(Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
    solver.addParticle(Particle(Eigen::Vector3d(0.0, 6.0, 0.0)));
    solver.addStitch(0, 1, 0.0);

    solver.update(world, 1.0 / 60.0);

    EXPECT_NEAR(solver.getParticles()[0].getPosition().y(), 3.0, 1e-9);
    EXPECT_NEAR(solver.getParticles()[1].getPosition().y(), 3.0, 1e-9);
}

TEST(StitchConstraint, SolverClipsAtEarliestMeshCrossing) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.05);
    world.addCollider(makeTestPlane(-1.0));
    world.addCollider(makeTestPlane(0.0));

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    solver.addParticle(Particle(Eigen::Vector3d(1.0, 1.0, 0.0)));
    solver.addParticle(Particle(Eigen::Vector3d(1.0, -10.0, 0.0)));
    solver.addStitch(0, 1, 0.0);

    solver.update(world, 1.0 / 60.0);

    const auto& particles = solver.getParticles();
    EXPECT_NEAR(particles[0].getPosition().y(), 0.05, 1e-6);
    EXPECT_NEAR(particles[1].getPosition().y(), -4.5, 1e-9);
}

TEST(StitchConstraint, PublicSolveApiRemainsUnchanged) {
    std::vector<Particle> particles;
    particles.emplace_back(Eigen::Vector3d(0.0, 0.0, 0.0));
    particles.emplace_back(Eigen::Vector3d(0.0, 6.0, 0.0));
    StitchConstraint constraint(0, 1, 0.0);

    constraint.solve(particles, 0.016);

    EXPECT_NEAR(particles[0].getPosition().y(), 3.0, 1e-9);
    EXPECT_NEAR(particles[1].getPosition().y(), 3.0, 1e-9);
}

TEST(StitchConstraint, ParticleShareSamePosition) {
"""
        if text.count(old) != 1:
            raise RuntimeError("Stitch test insertion anchor mismatch")
        stitch_test.write_text(text.replace(old, new, 1), encoding="utf-8")

        solver_text = solver_cpp.read_text(encoding="utf-8")
        if "for (const auto& pin : m_transientPins)" not in solver_text:
            raise RuntimeError("transient pin solve loop missing")
        if "for (const auto& attach : m_attachments)" not in solver_text:
            raise RuntimeError("attachment solve loop missing")

    patch_stitch_local_swept()

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "tests/physics/test_mesh_collider.cpp",
        "core/include/physics/StitchConstraint.hpp",
        "core/src/physics/StitchConstraint.cpp",
        "core/include/physics/Solver.hpp",
        "core/src/physics/Solver.cpp",
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
