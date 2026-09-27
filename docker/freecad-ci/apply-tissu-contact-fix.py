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
    stitch_header = ROOT / "core/include/physics/StitchConstraint.hpp"
    stitch_cpp = ROOT / "core/src/physics/StitchConstraint.cpp"
    solver_header = ROOT / "core/include/physics/Solver.hpp"
    solver_cpp = ROOT / "core/src/physics/Solver.cpp"
    test = ROOT / "tests/physics/test_mesh_collider.cpp"
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
    BVH m_bvh;

    friend class StitchConstraint;

    bool firstEnteringSegmentHit(
        const Eigen::Vector3d& start,
        const Eigen::Vector3d& end,
        double& hitT,
        Eigen::Vector3d& hitNormal) const;""",
        "MeshCollider.hpp member layout",
    )

    cpp = cpp.read_text(encoding="utf-8")
    include_old = '#include "physics/Particle.hpp"\n\nnamespace Tissu {'
    include_new = """#include "physics/Particle.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <limits>
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
    entering_helper = """bool MeshCollider::firstEnteringSegmentHit(
    const Eigen::Vector3d& start,
    const Eigen::Vector3d& end,
    double& hitT,
    Eigen::Vector3d& hitNormal) const {
    if (!m_closedManifold)
        return false;

    const Eigen::Vector3d direction = end - start;
    if (direction.squaredNorm() <= 1e-18)
        return false;

    constexpr double epsilon = 1e-10;
    double bestT = std::numeric_limits<double>::infinity();
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();

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
        const Eigen::Vector3d tvec = start - a;
        const double u = tvec.dot(pvec) * inverseDeterminant;
        if (u < -epsilon || u > 1.0 + epsilon)
            continue;
        const Eigen::Vector3d qvec = tvec.cross(edge1);
        const double v = direction.dot(qvec) * inverseDeterminant;
        if (v < -epsilon || u + v > 1.0 + epsilon)
            continue;
        const double candidateT = edge2.dot(qvec) * inverseDeterminant;
        if (candidateT <= epsilon || candidateT >= 1.0 - epsilon)
            continue;

        Eigen::Vector3d faceNormal = edge1.cross(edge2);
        const double normalLength = faceNormal.norm();
        if (normalLength <= epsilon)
            continue;
        faceNormal /= normalLength;
        const Eigen::Vector3d outwardNormal =
            faceNormal * m_outwardNormalSign;

        // Entering means travel against the authoritative outward normal.
        // Exit and tangent events are deliberately left to the collider pass.
        if (direction.dot(outwardNormal) >= -epsilon)
            continue;

        if (candidateT < bestT) {
            bestT = candidateT;
            bestNormal = outwardNormal;
        }
    }

    if (!std::isfinite(bestT))
        return false;

    hitT = bestT;
    hitNormal = bestNormal;
    return true;
}

""";
    for old, new, label in replace_cpp:
        count = cpp.count(old)
        if count != 1:
            raise RuntimeError(f"{label}: expected one source anchor, found {count}")
        cpp = cpp.replace(old, new, 1)
    Path(cpp_path := ROOT / "core/src/physics/MeshCollider.cpp").write_text(cpp, encoding="utf-8")

    resolve_anchor = "void MeshCollider::resolve(std::vector<Particle>& particles, double dt,"
    if cpp.count(resolve_anchor) != 1:
        raise RuntimeError("MeshCollider resolve anchor mismatch")
    cpp = cpp.replace(resolve_anchor, entering_helper + resolve_anchor, 1)
    Path(cpp_path := ROOT / "core/src/physics/MeshCollider.cpp").write_text(cpp, encoding="utf-8")

    replace_once(
        stitch_header,
        """#pragma once
#include "physics/Constraint.hpp"
#include "physics/Particle.hpp""",
        """#pragma once
#include <memory>

#include "physics/Constraint.hpp"
#include "physics/Particle.hpp""",
        "StitchConstraint header includes",
    )
    replace_once(
        stitch_header,
        """namespace Tissu {

class StitchConstraint""",
        """namespace Tissu {

class Collider;
class Solver;

class StitchConstraint""",
        "StitchConstraint forward declarations",
    )

    replace_once(
        stitch_header,
        """private:
    int m_idA;""",
        """private:
    friend class Solver;

    void solveWithColliders(
        std::vector<Particle>& particles,
        double dt,
        const std::vector<std::shared_ptr<Collider>>& colliders,
        double thickness);

    void solveInternal(
        std::vector<Particle>& particles,
        double dt,
        const std::vector<std::shared_ptr<Collider>>* colliders,
        double thickness);

    static double correctionScaleForEnteringHit(
        const Eigen::Vector3d& start,
        const Eigen::Vector3d& correction,
        const std::vector<std::shared_ptr<Collider>>& colliders,
        double thickness);

    int m_idA;""",
        "StitchConstraint private collider helpers",
    )

    replace_once(
        stitch_cpp,
        """#include "physics/StitchConstraint.hpp"

namespace Tissu {""",
        """#include "physics/StitchConstraint.hpp"

#include <algorithm>
#include <cmath>

#include "physics/Collider.hpp"
#include "physics/MeshCollider.hpp"

namespace Tissu {""",
        "StitchConstraint collision includes",
    )

    replace_once(
        stitch_cpp,
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

struct AppliedCorrection {
    Eigen::Vector3d correction = Eigen::Vector3d::Zero();
    double scale = 1.0;
};

AppliedCorrection clipCorrectionAtFirstEnteringMeshHit(
    const Eigen::Vector3d& start,
    const Eigen::Vector3d& correction,
    const std::vector<std::shared_ptr<Collider>>& colliders,
    double thickness) {
    if (correction.squaredNorm() <= 1e-18)
        return {correction, 1.0};

    double bestT = 1.0;
    Eigen::Vector3d bestNormal = Eigen::Vector3d::Zero();
    bool foundHit = false;

    for (const auto& collider : colliders) {
        const auto* mesh = dynamic_cast<const MeshCollider*>(collider.get());
        if (mesh == nullptr)
            continue;

        double hitT = 1.0;
        Eigen::Vector3d outwardNormal = Eigen::Vector3d::Zero();
        if (!mesh->firstEnteringSegmentHit(
                start, start + correction, hitT, outwardNormal))
            continue;

        if (!foundHit || hitT < bestT - 1e-12) {
            bestT = hitT;
            bestNormal = outwardNormal;
            foundHit = true;
        }
    }

    if (!foundHit)
        return {correction, 1.0};

    const Eigen::Vector3d hitPoint = start + correction * bestT;
    const Eigen::Vector3d clippedPosition =
        hitPoint + bestNormal * std::max(0.0, thickness);
    const Eigen::Vector3d appliedCorrection = clippedPosition - start;
    const double correctionNorm2 = correction.squaredNorm();
    double scale =
        appliedCorrection.dot(correction) / correctionNorm2;
    scale = std::max(0.0, std::min(1.0, scale));
    return {appliedCorrection, scale};
}

}

void StitchConstraint::solve(std::vector<Particle>& particles, double dt) {
    solveInternal(particles, dt, nullptr, 0.0);
}

void StitchConstraint::solveWithColliders(
    std::vector<Particle>& particles,
    double dt,
    const std::vector<std::shared_ptr<Collider>>& colliders,
    double thickness) {
    solveInternal(particles, dt, &colliders, thickness);
}

void StitchConstraint::solveInternal(
    std::vector<Particle>& particles,
    double dt,
    const std::vector<std::shared_ptr<Collider>>* colliders,
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
    const double previousLambda = m_lambda;
    const double deltaLambda =
        (-C - alphaHat * previousLambda) / (wSum + alphaHat);

    const Eigen::Vector3d correctionA = wA * norm * deltaLambda;
    const Eigen::Vector3d correctionB = -wB * norm * deltaLambda;

    AppliedCorrection appliedA{correctionA, 1.0};
    AppliedCorrection appliedB{correctionB, 1.0};
    if (colliders != nullptr && !colliders->empty()) {
        appliedA = clipCorrectionAtFirstEnteringMeshHit(
            startA, correctionA, *colliders, thickness);
        appliedB = clipCorrectionAtFirstEnteringMeshHit(
            startB, correctionB, *colliders, thickness);
    }

    const Eigen::Vector3d appliedPositionA = appliedA.correction;
    const Eigen::Vector3d appliedPositionB = appliedB.correction;
    const double proposedMagnitude =
        std::sqrt(correctionA.squaredNorm() + correctionB.squaredNorm());
    const double appliedMagnitude =
        std::sqrt(appliedPositionA.squaredNorm() + appliedPositionB.squaredNorm());
    const double lambdaScale =
        proposedMagnitude > 1e-12
            ? std::max(0.0, std::min(1.0,
                appliedMagnitude / proposedMagnitude))
            : 1.0;

    m_lambda = previousLambda + deltaLambda * lambdaScale;
    pA.setPosition(startA + appliedPositionA);
    pB.setPosition(startB + appliedPositionB);
}""",
        "StitchConstraint collision-clipped solve",
    )

    replace_once(
        solver_header,
        """    void solveConstraints(double dt);""",
        """    void solveConstraints(World& world, double dt);""",
        "Solver collision-aware constraint declaration",
    )

    replace_once(
        solver_cpp,
        """        solveConstraints(dt);""",
        """        solveConstraints(world, dt);""",
        "Solver collision-aware call",
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
    }""",
        """void Solver::solveConstraints(World& world, double dt) {
    ZoneScopedN("Solve Constraints");
    const auto& colliders = world.getColliders();
    auto solveConstraint = [&](Constraint& constraint) {
        if (auto* stitch = dynamic_cast<StitchConstraint*>(&constraint)) {
            stitch->solveWithColliders(
                m_particles, dt, colliders, world.getThickness());
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
    stitch_test_text = stitch_test_text.replace(
        "#include <vector>\n",
        "#include <array>\n#include <memory>\n#include <vector>\n",
        1,
    )
    stitch_test_text = stitch_test_text.replace(
        "#include \"Eigen/Dense\"\n",
        "#include \"Eigen/Dense\"\n#include \"engine/World.hpp\"\n#include \"physics/MeshCollider.hpp\"\n",
        1,
    )
    stitch_test_text += """

static std::shared_ptr<MeshCollider> makeClosedTetrahedron(double offsetX = 0.0) {
    const std::vector<Eigen::Vector3d> vertices = {
        {-1.0 + offsetX, -1.0, -1.0},
        {1.0 + offsetX, -1.0, -1.0},
        {offsetX, 1.0, -1.0},
        {offsetX, 0.0, 1.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 2, 1}, {0, 1, 3}, {1, 2, 3}, {0, 3, 2}};
    return std::make_shared<MeshCollider>(vertices, triangles, 0.0);
}

static bool containsClosedTetrahedron(
    const Eigen::Vector3d& point, double offsetX = 0.0) {
    const std::vector<Eigen::Vector3d> vertices = {
        {-1.0 + offsetX, -1.0, -1.0},
        {1.0 + offsetX, -1.0, -1.0},
        {offsetX, 1.0, -1.0},
        {offsetX, 0.0, 1.0},
    };
    const Eigen::Vector3d center =
        (vertices[0] + vertices[1] + vertices[2] + vertices[3]) / 4.0;
    const int faces[4][3] = {{0, 2, 1}, {0, 1, 3}, {1, 2, 3}, {0, 3, 2}};
    constexpr double epsilon = 1e-9;
    for (const auto& face : faces) {
        const auto& a = vertices[face[0]];
        const auto& b = vertices[face[1]];
        const auto& c = vertices[face[2]];
        Eigen::Vector3d normal = (b - a).cross(c - a).normalized();
        if ((center - a).dot(normal) > 0.0)
            normal = -normal;
        if ((point - a).dot(normal) > epsilon)
            return false;
    }
    return true;
}

TEST(StitchConstraint, SolverClipsEnteringCrossingIntoClosedSurface) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.05);
    world.addCollider(makeClosedTetrahedron());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving = solver.addParticle(
        Particle(Eigen::Vector3d(-2.0, 0.0, 0.0)));
    const int anchor = solver.addParticle(
        Particle(Eigen::Vector3d(2.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    const auto position = solver.getParticles()[moving].getPosition();
    EXPECT_FALSE(containsClosedTetrahedron(position));
    EXPECT_LT(position.x(), -0.05);
    EXPECT_GT(position.x(), -2.0);
}

TEST(StitchConstraint, SolverAllowsExitFromClosedSurface) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.05);
    world.addCollider(makeClosedTetrahedron());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving = solver.addParticle(
        Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
    const int anchor = solver.addParticle(
        Particle(Eigen::Vector3d(2.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(
        solver.getParticles()[moving].getPosition().x(), 2.0, 1e-6);
}

TEST(StitchConstraint, SolverPreservesFreeSpaceStitchConvergence) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving = solver.addParticle(
        Particle(Eigen::Vector3d(-2.0, 0.0, 0.0)));
    const int anchor = solver.addParticle(
        Particle(Eigen::Vector3d(-1.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(
        solver.getParticles()[moving].getPosition().x(), -1.0, 1e-6);
}

TEST(StitchConstraint, SolverChoosesEarliestEnteringCrossingAcrossMeshes) {
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.05);
    world.addCollider(makeClosedTetrahedron(-0.75));
    world.addCollider(makeClosedTetrahedron(2.0));

    Solver solver;
    solver.setSubsteps(1);
    solver.setIterations(1);
    const int moving = solver.addParticle(
        Particle(Eigen::Vector3d(-3.0, 0.0, 0.0)));
    const int anchor = solver.addParticle(
        Particle(Eigen::Vector3d(4.0, 0.0, 0.0)));
    solver.setParticleInverseMass(anchor, 0.0);
    solver.addStitch(moving, anchor, 0.0);

    solver.update(world, 0.016);

    const auto position = solver.getParticles()[moving].getPosition();
    EXPECT_FALSE(containsClosedTetrahedron(position, -0.75));
    EXPECT_GT(position.x(), -3.0);
    EXPECT_LT(position.x(), -0.75);
}

"""
    stitch_test.write_text(stitch_test_text.rstrip(" \t\r\n") + "\n", encoding="utf-8")

    stitch_cpp_text = stitch_cpp.read_text(encoding="utf-8")
    for marker in (
        "const double previousLambda = m_lambda;",
        "m_lambda = previousLambda + deltaLambda * lambdaScale;",
        "clipCorrectionAtFirstEnteringMeshHit(",
    ):
        if marker not in stitch_cpp_text:
            raise RuntimeError(f"missing stitch crossing marker: {marker}")
    if "direction.dot(outwardNormal) >= -epsilon" not in cpp:
        raise RuntimeError("missing entering/exiting discriminator")
    solver_cpp_text = solver_cpp.read_text(encoding="utf-8")
    if "stitch->solveWithColliders(" not in solver_cpp_text:
        raise RuntimeError("missing Solver stitch collider dispatch")
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

    if "firstEnteringSegmentHit" not in entering_helper:
        raise RuntimeError("stitch entering helper self-check marker missing")

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
