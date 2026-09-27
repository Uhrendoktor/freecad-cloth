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

    replace_once(
        header,
        """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

private:
    std::string m_meshPath;
    std::vector<Eigen::Vector3d> m_localVertices;
    std::vector<Eigen::Vector3d> m_worldVertices;
    std::vector<Triangle> m_triangles;
    bool m_closedManifold = false;
    double m_outwardNormalSign = 1.0;
    BVH m_bvh;""",
        """    const std::vector<Triangle>& getTriangles() const { return m_triangles; }

private:
    friend class Solver;

    bool firstSegmentHit(const Eigen::Vector3d& start,
                         const Eigen::Vector3d& end, double margin,
                         double& hitT,
                         Eigen::Vector3d& outwardNormal) const;

    std::string m_meshPath;
    std::vector<Eigen::Vector3d> m_localVertices;
    std::vector<Eigen::Vector3d> m_worldVertices;
    std::vector<Triangle> m_triangles;
    bool m_closedManifold = false;
    double m_outwardNormalSign = 1.0;
    BVH m_bvh;""",
        "MeshCollider private stitch helper",
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
    replace_once(
        cpp_path,
        """void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {""",
        """bool MeshCollider::firstSegmentHit(
    const Eigen::Vector3d& start, const Eigen::Vector3d& end,
    double margin, double& hitT, Eigen::Vector3d& outwardNormal) const {
    if (!m_closedManifold)
        return false;

    constexpr double epsilon = 1e-12;
    const Eigen::Vector3d direction = end - start;
    const double length = direction.norm();
    if (length <= epsilon)
        return false;

    const Eigen::Vector3d midpoint = (start + end) * 0.5;
    const double radius = length * 0.5 + std::max(0.0, margin);
    std::vector<int> candidates;
    m_bvh.query(midpoint, radius, candidates);

    double bestT = std::numeric_limits<double>::infinity();
    int bestTriangle = -1;
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();

    const auto& worldVertices = getWorldVertices();
    const auto& triangles = getTriangles();

    for (const int candidateIndex : candidates) {
        if (candidateIndex < 0 ||
            candidateIndex >= static_cast<int>(triangles.size()))
            continue;

        const Triangle& tri = triangles[candidateIndex];
        const Eigen::Vector3d& a = worldVertices[tri.a];
        const Eigen::Vector3d& b = worldVertices[tri.b];
        const Eigen::Vector3d& c = worldVertices[tri.c];

        const Eigen::Vector3d edge1 = b - a;
        const Eigen::Vector3d edge2 = c - a;
        const Eigen::Vector3d pvec = direction.cross(edge2);
        const double determinant = edge1.dot(pvec);
        if (std::abs(determinant) <= epsilon)
            continue;

        const double inverseDeterminant = 1.0 / determinant;
        const Eigen::Vector3d tvec = start - a;
        const double u = tvec.dot(pvec) * inverseDeterminant;
        if (u < -epsilon || u > 1.0 + epsilon)
            continue;

        const Eigen::Vector3d qvec = tvec.cross(edge1);
        const double v = direction.dot(qvec) * inverseDeterminant;
        if (v < -epsilon || u + v > 1.0 + epsilon)
            continue;

        const double candidateT =
            edge2.dot(qvec) * inverseDeterminant;
        if (candidateT <= epsilon || candidateT > 1.0 + epsilon)
            continue;

        Eigen::Vector3d rawNormal = edge1.cross(edge2);
        const double normalLength = rawNormal.norm();
        if (normalLength <= epsilon)
            continue;
        rawNormal /= normalLength;

        const Eigen::Vector3d candidateOutward =
            rawNormal * m_outwardNormalSign;
        if (direction.dot(candidateOutward) >= -epsilon)
            continue;

        const double clampedT = std::min(1.0, candidateT);
        if (clampedT < bestT - epsilon ||
            (std::abs(clampedT - bestT) <= epsilon &&
             (bestTriangle < 0 || candidateIndex < bestTriangle))) {
            bestT = clampedT;
            bestTriangle = candidateIndex;
            bestNormal = candidateOutward;
        }
    }

    if (bestTriangle < 0)
        return false;

    hitT = bestT;
    outwardNormal = bestNormal;
    return true;
}

void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {""",
        "MeshCollider first entering segment hit",
    )

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
        solver_header,
        """    void predictPositions(double dt);
    void solveConstraints(double dt);
    void addAdjacency(int idA, int idB);""",
        """    void predictPositions(double dt);
    void solveConstraints(World& world, double dt);
    void addAdjacency(int idA, int idB);""",
        "Solver private solve signature",
    )

    replace_once(
        solver_cpp,
        """#include "physics/Force.hpp"
#include "physics/PinConstraint.hpp"
#include "physics/StitchConstraint.hpp"
#include "physics/VolumeConstraint.hpp""",
        """#include "physics/Force.hpp"
#include "physics/MeshCollider.hpp"
#include "physics/PinConstraint.hpp"
#include "physics/StitchConstraint.hpp"
#include "physics/VolumeConstraint.hpp""",
        "Solver MeshCollider include",
    )

    replace_once(
        solver_cpp,
        """    for (int i = 0; i < m_iterations; i++) {
        solveConstraints(dt);
    }""",
        """    for (int i = 0; i < m_iterations; i++) {
        solveConstraints(world, dt);
    }""",
        "Solver iteration call",
    )

    replace_once(
        solver_cpp,
        """void Solver::solveConstraints(double dt) {
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
    for (const auto& attach : m_attachments) {
        attach->solve(m_particles, dt);
    }
}""",
        """void Solver::solveConstraints(World& world, double dt) {
    ZoneScopedN("Solve Constraints");
    const auto& colliders = world.getColliders();
    const double thickness = world.getThickness();

    auto solveOne = [&](Constraint& constraint) {
        auto* stitch = dynamic_cast<StitchConstraint*>(&constraint);
        bool stitchReady = false;
        std::array<int, 2> particleIds{};
        std::array<Eigen::Vector3d, 2> beforePositions{};
        double lambdaBefore = 0.0;

        if (stitch) {
            const std::vector<int> ids = constraint.getParticleIds();
            if (ids.size() == 2 &&
                ids[0] >= 0 && ids[1] >= 0 &&
                ids[0] < static_cast<int>(m_particles.size()) &&
                ids[1] < static_cast<int>(m_particles.size())) {
                particleIds[0] = ids[0];
                particleIds[1] = ids[1];
                beforePositions[0] =
                    m_particles[particleIds[0]].getPosition();
                beforePositions[1] =
                    m_particles[particleIds[1]].getPosition();
                lambdaBefore = constraint.getLambda();
                stitchReady = true;
            }
        }

        constraint.solve(m_particles, dt);

        if (!stitchReady)
            return;

        const double proposedDeltaLambda =
            constraint.getLambda() - lambdaBefore;
        double appliedScale = 1.0;
        bool clipped = false;

        for (int endpoint = 0; endpoint < 2; ++endpoint) {
            const int particleId = particleIds[endpoint];
            const Eigen::Vector3d proposedPosition =
                m_particles[particleId].getPosition();
            const Eigen::Vector3d correction =
                proposedPosition - beforePositions[endpoint];
            const double correctionSquared = correction.squaredNorm();
            if (correctionSquared <= 1e-24)
                continue;

            double bestHitT = std::numeric_limits<double>::infinity();
            Eigen::Vector3d bestOutwardNormal = Eigen::Vector3d::Zero();
            bool foundHit = false;

            for (const auto& collider : colliders) {
                const auto mesh =
                    std::dynamic_pointer_cast<const MeshCollider>(collider);
                if (!mesh)
                    continue;

                double hitT = 0.0;
                Eigen::Vector3d outwardNormal = Eigen::Vector3d::Zero();
                if (!mesh->firstSegmentHit(
                        beforePositions[endpoint], proposedPosition,
                        thickness, hitT, outwardNormal)) {
                    continue;
                }

                if (!foundHit || hitT < bestHitT) {
                    bestHitT = hitT;
                    bestOutwardNormal = outwardNormal;
                    foundHit = true;
                }
            }

            if (!foundHit)
                continue;

            const Eigen::Vector3d hitPoint =
                beforePositions[endpoint] + correction * bestHitT;
            const Eigen::Vector3d clippedPosition =
                hitPoint + bestOutwardNormal * thickness;
            double correctionRatio =
                correction.dot(clippedPosition - beforePositions[endpoint]) /
                correctionSquared;
            correctionRatio = std::clamp(correctionRatio, 0.0, 1.0);

            m_particles[particleId].setPosition(clippedPosition);
            appliedScale = std::min(appliedScale, correctionRatio);
            clipped = true;
        }

        if (clipped) {
            constraint.setLambda(
                lambdaBefore + proposedDeltaLambda * appliedScale);
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
    for (const auto& attach : m_attachments) {
        attach->solve(m_particles, dt);
    }
}""",
        "Solver collision-clipped stitch path",
    )

    replace_once(
        stitch_test,
        """#include <vector>

#include "Eigen/Dense"
#include "physics/Particle.hpp"
#include "physics/Solver.hpp"
#include "physics/StitchConstraint.hpp"
#include "gtest/gtest.h"
""",
        """#include <array>
#include <memory>
#include <vector>

#include "Eigen/Dense"
#include "engine/World.hpp"
#include "physics/MeshCollider.hpp"
#include "physics/Particle.hpp"
#include "physics/Solver.hpp"
#include "physics/StitchConstraint.hpp"
#include "gtest/gtest.h"
""",
        "stitch regression includes",
    )

    stitch_test_text = stitch_test.read_text(encoding="utf-8")
    if "ZeroRestStitchCrossingClosedMeshClipsEnteringMotion" in stitch_test_text:
        raise RuntimeError("stitch regression already present before patch")
    stitch_test.write_text(
        stitch_test_text
        + r'''
namespace {

std::shared_ptr<MeshCollider> makeClosedBox(double halfExtent = 1.0) {
    const std::vector<Eigen::Vector3d> vertices = {
        {-halfExtent, -halfExtent, -halfExtent},
        { halfExtent, -halfExtent, -halfExtent},
        { halfExtent,  halfExtent, -halfExtent},
        {-halfExtent,  halfExtent, -halfExtent},
        {-halfExtent, -halfExtent,  halfExtent},
        { halfExtent, -halfExtent,  halfExtent},
        { halfExtent,  halfExtent,  halfExtent},
        {-halfExtent,  halfExtent,  halfExtent},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 4, 7}, {0, 7, 3},
        {1, 2, 6}, {1, 6, 5},
        {0, 1, 5}, {0, 5, 4},
        {3, 7, 6}, {3, 6, 2},
        {0, 3, 2}, {0, 2, 1},
        {4, 5, 6}, {4, 6, 7},
    };
    return std::make_shared<MeshCollider>(vertices, triangles, 0.0);
}

} // namespace

TEST(Solver, ZeroRestStitchCrossingClosedMeshClipsEnteringMotion) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.1);
    world.addCollider(makeClosedBox());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);

    const int first =
        solver.addParticle(Particle(Eigen::Vector3d(-2.0, 0.0, 0.0)));
    const int second =
        solver.addParticle(Particle(Eigen::Vector3d(2.0, 0.0, 0.0)));
    solver.setParticleInverseMass(first, 1.0);
    solver.setParticleInverseMass(second, 1.0);
    solver.addStitch(first, second, 0.0);

    solver.update(world, 0.016);

    const auto& particles = solver.getParticles();
    EXPECT_LE(particles[first].getPosition().x(), -1.1 + 1e-9);
    EXPECT_GE(particles[second].getPosition().x(), 1.1 - 1e-9);
    EXPECT_NEAR(particles[first].getPosition().y(), 0.0, 1e-9);
    EXPECT_NEAR(particles[second].getPosition().y(), 0.0, 1e-9);
    EXPECT_NEAR(
        solver.getConstraints()[0]->getLambda(), -0.9, 1e-9);
}

TEST(Solver, ZeroRestStitchFreeSpaceConvergenceUnchanged) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.1);

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);

    const int first =
        solver.addParticle(Particle(Eigen::Vector3d(-2.0, 0.0, 0.0)));
    const int second =
        solver.addParticle(Particle(Eigen::Vector3d(2.0, 0.0, 0.0)));
    solver.setParticleInverseMass(first, 1.0);
    solver.setParticleInverseMass(second, 1.0);
    solver.addStitch(first, second, 0.0);

    solver.update(world, 0.016);

    const auto& particles = solver.getParticles();
    EXPECT_NEAR(particles[first].getPosition().x(), 0.0, 1e-9);
    EXPECT_NEAR(particles[second].getPosition().x(), 0.0, 1e-9);
    EXPECT_NEAR(
        solver.getConstraints()[0]->getLambda(), -2.0, 1e-9);
}

TEST(Solver, ZeroRestStitchExitMotionIsNotClipped) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.1);
    world.addCollider(makeClosedBox());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);

    const int moving =
        solver.addParticle(Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
    const int anchor =
        solver.addParticle(Particle(Eigen::Vector3d(2.0, 0.0, 0.0)));
    solver.setParticleInverseMass(moving, 1.0);
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(
        solver.getParticles()[moving].getPosition().x(), 2.0, 1e-9);
}
''',
        encoding="utf-8",
    )

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/src/physics/MeshCollider.cpp",
        "core/include/physics/Solver.hpp",
        "core/src/physics/Solver.cpp",
        "tests/physics/test_mesh_collider.cpp",
        "tests/physics/test_stitch_constraint.cpp",
    }
    if set(changed.splitlines()) != expected:
        raise RuntimeError(f"unexpected patched files: {changed!r}")

    solver_cpp_text = solver_cpp.read_text(encoding="utf-8")
    mesh_cpp_text = mesh_cpp.read_text(encoding="utf-8")
    mesh_header_text = header.read_text(encoding="utf-8")
    for anchor, source in (
        ("dynamic_cast<StitchConstraint*>(&constraint)", solver_cpp_text),
        ("const std::vector<int> ids = constraint.getParticleIds();", solver_cpp_text),
        ("lambdaBefore = constraint.getLambda();", solver_cpp_text),
        ("constraint.solve(m_particles, dt);", solver_cpp_text),
        ("const double proposedDeltaLambda =", solver_cpp_text),
        ("constraint.setLambda(", solver_cpp_text),
        ("std::dynamic_pointer_cast<const MeshCollider>(collider)", solver_cpp_text),
        ("direction.dot(candidateOutward) >= -epsilon", mesh_cpp_text),
        ("getWorldVertices()", mesh_cpp_text),
        ("getTriangles()", mesh_cpp_text),
    ):
        if anchor not in source:
            raise RuntimeError(f"missing collision-clipped stitch anchor: {anchor}")
    if "friend class Solver;" not in mesh_header_text:
        raise RuntimeError("MeshCollider stitch helper is not private")
    if "StitchConstraint" in mesh_header_text:
        raise RuntimeError("MeshCollider.hpp unexpectedly references StitchConstraint ABI")

    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"Tissu source commit: {EXPECTED_COMMIT}")
    print(f"Tissu contact fix script sha256: {script_sha}")
    print("Tissu contact fix: applied and self-checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
