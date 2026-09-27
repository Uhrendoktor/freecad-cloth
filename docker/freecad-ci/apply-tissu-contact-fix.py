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
#include <limits>
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

    solver_text = solver_header.read_text(encoding="utf-8")
    solver_text = solver_text.replace(
        "    void solveConstraints(double dt);\n",
        "    void solveConstraints(double dt, double stitchCorrectionLimit);\n",
        1,
    )
    if "void solveConstraints(double dt, double stitchCorrectionLimit);" not in solver_text:
        raise RuntimeError("Solver.hpp stitch-bound API anchor mismatch")
    solver_header.write_text(solver_text, encoding="utf-8")

    solver_source = solver_cpp.read_text(encoding="utf-8")
    step_call = """    for (int i = 0; i < m_iterations; i++) {
        solveConstraints(dt);
    }
"""
    step_call_replacement = """    for (int i = 0; i < m_iterations; i++) {
        solveConstraints(dt, world.getThickness());
    }
"""
    if solver_source.count(step_call) != 1:
        raise RuntimeError("Solver.cpp step constraint call anchor mismatch")
    solver_source = solver_source.replace(step_call, step_call_replacement, 1)
    start_marker = "void Solver::solveConstraints(double dt) {"
    end_marker = "\nvoid Solver::buildCollisionColorBatches() {"
    if solver_source.count(start_marker) != 1 or solver_source.count(end_marker) != 1:
        raise RuntimeError("Solver.cpp solveConstraints function-boundary anchors mismatch")
    start_index = solver_source.index(start_marker)
    end_index = solver_source.index(end_marker, start_index)
    new_solver_source = """void Solver::solveConstraints(double dt, double stitchCorrectionLimit) {
    ZoneScopedN("Solve Constraints");
    const auto solveConstraint = [this, dt, stitchCorrectionLimit](
                                     const std::unique_ptr<Constraint>& constraint) {
        if (auto* stitch = dynamic_cast<StitchConstraint*>(constraint.get())) {
            stitch->solveBounded(m_particles, dt, stitchCorrectionLimit);
            return;
        }
        constraint->solve(m_particles, dt);
    };
    if (m_batches.empty()) {
        for (const auto& constraint : m_constraints)
            solveConstraint(constraint);
    } else {
        for (const auto& batch : m_batches) {
            const int batchSize = static_cast<int>(batch.size());
#pragma omp parallel for
            for (int i = 0; i < batchSize; ++i) {
                const int idx = batch[i];
                solveConstraint(m_constraints[idx]);
            }
        }
    }

    for (const auto& pin : m_transientPins) {
        pin->solve(m_particles, dt);
    }
    for (const auto& attach : m_attachments) {
        attach->solve(m_particles, dt);
    }
}
"""
    solver_source = solver_source[:start_index] + new_solver_source + solver_source[end_index:]
    if "void Solver::solveConstraints(double dt, double stitchCorrectionLimit)" not in solver_source:
        raise RuntimeError("Solver.cpp bounded solve replacement failed")
    if "for (const auto& pin : m_transientPins)" not in solver_source:
        raise RuntimeError("Solver.cpp pin solve preservation check failed")
    if "for (const auto& attach : m_attachments)" not in solver_source:
        raise RuntimeError("Solver.cpp attachment solve preservation check failed")
    if "void Solver::solveConstraints(double dt, double stitchCorrectionLimit)" not in solver_source:
        raise RuntimeError("Solver.cpp solveConstraints anchor mismatch")
    if "solveConstraints(dt, world.getThickness());" not in solver_source:
        raise RuntimeError("Solver.cpp step must pass world thickness into bounded stitch solve")
    solver_cpp.write_text(solver_source, encoding="utf-8")

    stitch_text = stitch_header.read_text(encoding="utf-8")
    stitch_text = stitch_text.replace(
        "    void solve(std::vector<Particle>& particles, double dt) override;\n",
        "    void solve(std::vector<Particle>& particles, double dt) override;\n"
        "    void solveBounded(std::vector<Particle>& particles, double dt,\n"
        "                      double maxCorrection);\n",
        1,
    )
    if "void solveBounded" not in stitch_text:
        raise RuntimeError("StitchConstraint.hpp bound method anchor mismatch")
    stitch_header.write_text(stitch_text, encoding="utf-8")

    stitch_source = stitch_cpp.read_text(encoding="utf-8")
    stitch_start_marker = "void StitchConstraint::solve(std::vector<Particle>& particles, double dt) {"
    stitch_end_marker = "\n} // namespace Tissu"
    if stitch_source.count(stitch_start_marker) != 1 or stitch_source.count(stitch_end_marker) != 1:
        raise RuntimeError("StitchConstraint.cpp function-boundary anchors mismatch")
    stitch_start = stitch_source.index(stitch_start_marker)
    stitch_end = stitch_source.index(stitch_end_marker, stitch_start)
    new_stitch = """void StitchConstraint::solve(std::vector<Particle>& particles, double dt) {
    solveBounded(particles, dt, std::numeric_limits<double>::infinity());
}

void StitchConstraint::solveBounded(std::vector<Particle>& particles,
                                    double dt, double maxCorrection) {
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
    if (std::isfinite(maxCorrection)) {
        const double correctionLimit = maxCorrection < 0.0 ? 0.0 : maxCorrection;
        const double relativeCorrection = std::abs(deltaLambda) * wSum;
        if (relativeCorrection > correctionLimit)
            deltaLambda = std::copysign(correctionLimit / wSum, deltaLambda);
    }
    m_lambda += deltaLambda;

    pA.setPosition(pA.getPosition() + wA * norm * deltaLambda);
    pB.setPosition(pB.getPosition() - wB * norm * deltaLambda);
}
"""
    stitch_source = stitch_source[:stitch_start] + new_stitch + stitch_source[stitch_end:]
    if "void StitchConstraint::solveBounded" not in stitch_source:
        raise RuntimeError("StitchConstraint.cpp bounded solve replacement failed")
    if stitch_source.count("void StitchConstraint::solve(std::vector<Particle>& particles, double dt)") != 1:
        raise RuntimeError("StitchConstraint.cpp solve function preservation check failed")
    stitch_cpp.write_text(stitch_source, encoding="utf-8")

    stitch_test_text = stitch_test.read_text(encoding="utf-8")
    if '#include "engine/World.hpp"\n' not in stitch_test_text:
        stitch_test_text = stitch_test_text.replace(
            '#include "Eigen/Dense"\n',
            '#include "Eigen/Dense"\n#include "engine/World.hpp"\n',
            1,
        )
    stitch_test_text += """

TEST(Solver, StitchCorrectionIsBoundedByWorldThickness) {
    Solver solver;
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(1.0);
    solver.setSubsteps(1);
    solver.setIterations(1);

    solver.addParticle(Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
    solver.addParticle(Particle(Eigen::Vector3d(10.0, 0.0, 0.0)));
    solver.addStitch(0, 1, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR((solver.getParticles()[0].getPosition() -
                 Eigen::Vector3d(0.5, 0.0, 0.0)).norm(), 0.0, 1e-9);
    EXPECT_NEAR((solver.getParticles()[1].getPosition() -
                 Eigen::Vector3d(9.5, 0.0, 0.0)).norm(), 0.0, 1e-9);
    EXPECT_NEAR(
        (solver.getParticles()[0].getPosition() -
         solver.getParticles()[1].getPosition()).norm(),
        9.0, 1e-9);
}

TEST(Solver, ZeroOrNegativeWorldThicknessFailsClosed) {
    for (double thickness : {0.0, -1.0}) {
        Solver solver;
        World world;
        world.setGravity(Eigen::Vector3d::Zero());
        world.setThickness(thickness);
        solver.setSubsteps(1);
        solver.setIterations(1);

        solver.addParticle(Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
        solver.addParticle(Particle(Eigen::Vector3d(10.0, 0.0, 0.0)));
        solver.addStitch(0, 1, 0.0);

        solver.update(world, 0.016);

        EXPECT_NEAR(
            (solver.getParticles()[0].getPosition() -
             Eigen::Vector3d(0.0, 0.0, 0.0)).norm(),
            0.0, 1e-9);
        EXPECT_NEAR(
            (solver.getParticles()[1].getPosition() -
             Eigen::Vector3d(10.0, 0.0, 0.0)).norm(),
            0.0, 1e-9);
    }
}

TEST(Solver, ZeroOrNegativeWorldThicknessFailsClosed) {
    for (double thickness : {0.0, -1.0}) {
        Solver solver;
        World world;
        world.setGravity(Eigen::Vector3d::Zero());
        world.setThickness(thickness);
        solver.setSubsteps(1);
        solver.setIterations(1);

        solver.addParticle(Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
        solver.addParticle(Particle(Eigen::Vector3d(10.0, 0.0, 0.0)));
        solver.addStitch(0, 1, 0.0);

        solver.update(world, 0.016);

        EXPECT_NEAR(
            (solver.getParticles()[0].getPosition() -
             Eigen::Vector3d(0.0, 0.0, 0.0)).norm(),
            0.0, 1e-9);
        EXPECT_NEAR(
            (solver.getParticles()[1].getPosition() -
             Eigen::Vector3d(10.0, 0.0, 0.0)).norm(),
            0.0, 1e-9);
    }
}

TEST(Solver, StitchCorrectionWithinThicknessRemainsUnclamped) {
    Solver solver;
    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(1.0);
    solver.setSubsteps(1);
    solver.setIterations(1);

    solver.addParticle(Particle(Eigen::Vector3d(0.0, 0.0, 0.0)));
    solver.addParticle(Particle(Eigen::Vector3d(0.5, 0.0, 0.0)));
    solver.addStitch(0, 1, 0.0);

    solver.update(world, 0.016);

    EXPECT_NEAR(
        (solver.getParticles()[0].getPosition() -
         solver.getParticles()[1].getPosition()).norm(),
        0.0, 1e-9);
}
"""
    stitch_test.write_text(stitch_test_text, encoding="utf-8")

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

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(f"Tissu source commit: {EXPECTED_COMMIT}")
    print(f"Tissu contact fix script sha256: {script_sha}")
    print("Tissu contact fix: applied and self-checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
