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
    cloth_test = ROOT / "tests/physics/test_cloth.cpp"

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

    solver_header_text = solver_header.read_text(encoding="utf-8")
    solver_header_old = """class World;

class Solver {"""
    solver_header_new = """class World;
class Collider;

class Solver {"""
    if solver_header_text.count(solver_header_old) != 1:
        raise RuntimeError("Solver.hpp forward-declaration anchor mismatch")
    solver_header_text = solver_header_text.replace(
        solver_header_old, solver_header_new, 1
    )

    solver_member_old = """    std::vector<std::unique_ptr<PinConstraint>> m_transientPins;
    std::vector<std::unique_ptr<AttachmentConstraint>> m_attachments;"""
    solver_member_new = """    // The active world colliders are visible only during solveConstraints().
    // This keeps the public Solver/Constraint ABI unchanged while allowing
    // stitch corrections to be clipped against the authoritative mesh surface.
    const std::vector<std::shared_ptr<Collider>>* m_activeColliders = nullptr;
    double m_activeCollisionThickness = 0.0;

    std::vector<std::unique_ptr<PinConstraint>> m_transientPins;
    std::vector<std::unique_ptr<AttachmentConstraint>> m_attachments;"""
    if solver_header_text.count(solver_member_old) != 1:
        raise RuntimeError("Solver.hpp active-collider member anchor mismatch")
    solver_header_text = solver_header_text.replace(
        solver_member_old, solver_member_new, 1
    )
    solver_header.write_text(solver_header_text, encoding="utf-8")

    solver_text = solver_cpp.read_text(encoding="utf-8")
    solver_include_old = """#include "physics/Collider.hpp"
#include "physics/ContactConstraint.hpp"
"""
    solver_include_new = """#include "physics/Collider.hpp"
#include "physics/MeshCollider.hpp"
#include "physics/ContactConstraint.hpp"
"""
    if solver_include_old not in solver_text:
        raise RuntimeError("Solver.cpp mesh-collider include anchor mismatch")
    solver_text = solver_text.replace(solver_include_old, solver_include_new, 1)

    solver_text = solver_text.replace(
        """#include <Eigen/Dense>
#include <algorithm>
#include <memory>
""",
        """#include <Eigen/Dense>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <unordered_map>
#include <utility>
""",
        1,
    )

    solver_namespace_anchor = """namespace Tissu {
Solver::Solver()"""
    if solver_namespace_anchor not in solver_text:
        raise RuntimeError("Solver.cpp namespace anchor mismatch")
    solver_text = solver_text.replace(
        solver_namespace_anchor,
        "namespace Tissu {\n\nnamespace {\n\nstruct MeshClipTarget {\n    const MeshCollider* mesh = nullptr;\n    double outwardNormalSign = 1.0;\n};\n\nstd::uint64_t clipEdgeKey(int a, int b) {\n    const auto low = static_cast<std::uint32_t>(std::min(a, b));\n    const auto high = static_cast<std::uint32_t>(std::max(a, b));\n    return (static_cast<std::uint64_t>(low) << 32) |\n           static_cast<std::uint64_t>(high);\n}\n\nbool inferClosedMeshOrientation(\n    const std::vector<Eigen::Vector3d>& vertices,\n    const std::vector<Triangle>& triangles,\n    double& outwardNormalSign) {\n    if (triangles.empty())\n        return false;\n\n    std::unordered_map<std::uint64_t, std::pair<int, int>> edges;\n    edges.reserve(triangles.size() * 3);\n\n    double signedVolume = 0.0;\n    for (const auto& tri : triangles) {\n        const int ids[3] = {tri.a, tri.b, tri.c};\n        for (const int id : ids) {\n            if (id < 0 || id >= static_cast<int>(vertices.size()))\n                return false;\n        }\n\n        signedVolume +=\n            vertices[ids[0]].dot(\n                vertices[ids[1]].cross(vertices[ids[2]])) /\n            6.0;\n\n        for (int edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {\n            const int from = ids[edgeIndex];\n            const int to = ids[(edgeIndex + 1) % 3];\n            const auto key = clipEdgeKey(from, to);\n            auto& edge = edges[key];\n            ++edge.first;\n            edge.second += from == std::min(from, to) ? 1 : -1;\n        }\n    }\n\n    for (const auto& [key, edge] : edges) {\n        (void)key;\n        if (edge.first != 2 || edge.second != 0)\n            return false;\n    }\n\n    if (std::abs(signedVolume) <= 1.0e-12)\n        return false;\n\n    outwardNormalSign = signedVolume > 0.0 ? 1.0 : -1.0;\n    return true;\n}\n\nbool segmentTriangleIntersection(\n    const Eigen::Vector3d& start, const Eigen::Vector3d& end,\n    const Eigen::Vector3d& a, const Eigen::Vector3d& b,\n    const Eigen::Vector3d& c, double epsilon, double& t,\n    Eigen::Vector3d& faceNormal) {\n    const Eigen::Vector3d direction = end - start;\n    const Eigen::Vector3d edge1 = b - a;\n    const Eigen::Vector3d edge2 = c - a;\n    const Eigen::Vector3d pvec = direction.cross(edge2);\n    const double determinant = edge1.dot(pvec);\n    if (std::abs(determinant) <= epsilon)\n        return false;\n\n    const double inverseDeterminant = 1.0 / determinant;\n    const Eigen::Vector3d tvec = start - a;\n    const double u = tvec.dot(pvec) * inverseDeterminant;\n    if (u < -epsilon || u > 1.0 + epsilon)\n        return false;\n\n    const Eigen::Vector3d qvec = tvec.cross(edge1);\n    const double v = direction.dot(qvec) * inverseDeterminant;\n    if (v < -epsilon || u + v > 1.0 + epsilon)\n        return false;\n\n    t = edge2.dot(qvec) * inverseDeterminant;\n    if (t <= epsilon || t > 1.0 + epsilon)\n        return false;\n\n    Eigen::Vector3d rawNormal = edge1.cross(edge2);\n    const double normalLength = rawNormal.norm();\n    if (normalLength <= epsilon)\n        return false;\n\n    faceNormal = rawNormal / normalLength;\n    t = std::clamp(t, 0.0, 1.0);\n    return true;\n}\n\nbool firstEnteringMeshCrossing(\n    const MeshClipTarget& target, const Eigen::Vector3d& start,\n    const Eigen::Vector3d& end, double thickness, double& correctionRatio) {\n    if (target.mesh == nullptr)\n        return false;\n\n    const Eigen::Vector3d direction = end - start;\n    if (direction.squaredNorm() <= 1.0e-24)\n        return false;\n\n    const auto& vertices = target.mesh->getWorldVertices();\n    const auto& triangles = target.mesh->getTriangles();\n    constexpr double epsilon = 1.0e-12;\n\n    double bestRatio = 1.0;\n    bool found = false;\n\n    for (const auto& tri : triangles) {\n        if (tri.a < 0 || tri.b < 0 || tri.c < 0 ||\n            tri.a >= static_cast<int>(vertices.size()) ||\n            tri.b >= static_cast<int>(vertices.size()) ||\n            tri.c >= static_cast<int>(vertices.size())) {\n            continue;\n        }\n\n        double hitT = 1.0;\n        Eigen::Vector3d faceNormal = Eigen::Vector3d::Zero();\n        if (!segmentTriangleIntersection(\n                start, end, vertices[tri.a], vertices[tri.b], vertices[tri.c],\n                epsilon, hitT, faceNormal)) {\n            continue;\n        }\n\n        const Eigen::Vector3d outwardNormal =\n            faceNormal * target.outwardNormalSign;\n        const double inwardTravel = -direction.dot(outwardNormal);\n        if (inwardTravel <= epsilon)\n            continue;\n\n        const double safeRatio = std::clamp(\n            hitT - thickness / inwardTravel, 0.0, 1.0);\n        if (!found || safeRatio < bestRatio) {\n            bestRatio = safeRatio;\n            found = true;\n        }\n    }\n\n    if (!found)\n        return false;\n\n    correctionRatio = bestRatio;\n    return correctionRatio < 1.0 - 1.0e-12;\n}\n\n} // namespace\n\nSolver::Solver()",
        1,
    )

    step_old = """    for (int i = 0; i < m_iterations; i++)
        solveConstraints(dt);

    const auto& colliders = world.getColliders();"""
    step_new = """    m_activeColliders = &world.getColliders();
    m_activeCollisionThickness = world.getThickness();
    for (int i = 0; i < m_iterations; i++)
        solveConstraints(dt);
    m_activeColliders = nullptr;
    m_activeCollisionThickness = 0.0;

    const auto& colliders = world.getColliders();"""
    if solver_text.count(step_old) != 1:
        raise RuntimeError("Solver.cpp step collider-context anchor mismatch")
    solver_text = solver_text.replace(step_old, step_new, 1)

    solve_old = """void Solver::solveConstraints(double dt) {
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
}"""
    if solve_old not in solver_text:
        raise RuntimeError("Solver.cpp solveConstraints body anchor mismatch")
    solver_text = solver_text.replace(
        solve_old,
        "void Solver::solveConstraints(double dt) {\n    ZoneScopedN(\"Solve Constraints\");\n\n    std::vector<MeshClipTarget> meshClipTargets;\n    if (m_activeColliders != nullptr) {\n        for (const auto& collider : *m_activeColliders) {\n            const auto* mesh = dynamic_cast<const MeshCollider*>(collider.get());\n            if (mesh == nullptr)\n                continue;\n\n            double outwardNormalSign = 1.0;\n            if (inferClosedMeshOrientation(\n                    mesh->getWorldVertices(), mesh->getTriangles(),\n                    outwardNormalSign)) {\n                meshClipTargets.push_back({mesh, outwardNormalSign});\n            }\n        }\n    }\n\n    auto solveConstraint = [&](Constraint& constraint) {\n        auto* stitch = dynamic_cast<StitchConstraint*>(&constraint);\n        if (stitch == nullptr || meshClipTargets.empty()) {\n            constraint.solve(m_particles, dt);\n            return;\n        }\n\n        const std::vector<int> particleIds = stitch->getParticleIds();\n        if (particleIds.size() != 2 ||\n            particleIds[0] < 0 || particleIds[1] < 0 ||\n            particleIds[0] >= static_cast<int>(m_particles.size()) ||\n            particleIds[1] >= static_cast<int>(m_particles.size())) {\n            constraint.solve(m_particles, dt);\n            return;\n        }\n\n        const int idA = particleIds[0];\n        const int idB = particleIds[1];\n        const Eigen::Vector3d beforeA = m_particles[idA].getPosition();\n        const Eigen::Vector3d beforeB = m_particles[idB].getPosition();\n        const double beforeLambda = stitch->getLambda();\n\n        stitch->solve(m_particles, dt);\n\n        const Eigen::Vector3d afterA = m_particles[idA].getPosition();\n        const Eigen::Vector3d afterB = m_particles[idB].getPosition();\n\n        double correctionRatio = 1.0;\n        for (const auto& target : meshClipTargets) {\n            double endpointRatio = 1.0;\n            if (firstEnteringMeshCrossing(\n                    target, beforeA, afterA, m_activeCollisionThickness,\n                    endpointRatio)) {\n                correctionRatio = std::min(correctionRatio, endpointRatio);\n            }\n            endpointRatio = 1.0;\n            if (firstEnteringMeshCrossing(\n                    target, beforeB, afterB, m_activeCollisionThickness,\n                    endpointRatio)) {\n                correctionRatio = std::min(correctionRatio, endpointRatio);\n            }\n        }\n\n        if (correctionRatio >= 1.0 - 1.0e-12)\n            return;\n\n        const double afterLambda = stitch->getLambda();\n        const double deltaLambda = afterLambda - beforeLambda;\n\n        m_particles[idA].setPosition(\n            beforeA + (afterA - beforeA) * correctionRatio);\n        m_particles[idB].setPosition(\n            beforeB + (afterB - beforeB) * correctionRatio);\n        stitch->setLambda(beforeLambda + deltaLambda * correctionRatio);\n    };\n\n    if (m_batches.empty()) {\n        for (const auto& constraint : m_constraints)\n            solveConstraint(*constraint);\n    } else {\n        for (const auto& batch : m_batches) {\n            const int batchSize = static_cast<int>(batch.size());\n#pragma omp parallel for\n            for (int i = 0; i < batchSize; ++i) {\n                const int idx = batch[i];\n                solveConstraint(*m_constraints[idx]);\n            }\n        }\n    }\n\n    for (const auto& pin : m_transientPins) {\n        pin->solve(m_particles, dt);\n    }\n    for (const auto& attach : m_attachments) {\n        attach->solve(m_particles, dt);\n    }\n}",
        1,
    )
    solver_cpp.write_text(solver_text, encoding="utf-8")

    cloth_test_cpp = cloth_test.read_text(encoding="utf-8")
    cloth_test_cpp = cloth_test_cpp.replace(
        '''#include "physics/Solver.hpp"
#include "utils/Logger.hpp"
''',
        '''#include "engine/World.hpp"
#include "physics/MeshCollider.hpp"
#include "physics/Solver.hpp"
#include "utils/Logger.hpp"
''',
        1,
    )
    cloth_test_cpp = cloth_test_cpp.replace(
        "#include <Eigen/Dense>\n",
        "#include <Eigen/Dense>\n#include <array>\n#include <memory>\n",
        1,
    )
    if cloth_test_cpp.count("TEST(Cloth, ClearFabric)") != 1:
        raise RuntimeError("Cloth test anchor missing")
    cloth_test_cpp = cloth_test_cpp.replace(
        "TEST(Cloth, ClearFabric) {",
        "static const std::vector<Eigen::Vector3d>& clipTetrahedronVertices() {\n    static const std::vector<Eigen::Vector3d> vertices = {\n        {0.0, 0.0, 0.0},\n        {2.0, 0.0, 0.0},\n        {1.0, 0.0, 2.0},\n        {1.0, 2.0, 1.0},\n    };\n    return vertices;\n}\n\nstatic const std::vector<std::array<int, 3>>& clipTetrahedronTriangles() {\n    static const std::vector<std::array<int, 3>> triangles = {\n        {0, 2, 1},\n        {0, 1, 3},\n        {1, 2, 3},\n        {0, 3, 2},\n    };\n    return triangles;\n}\n\nstatic bool clipTetrahedronContains(const Eigen::Vector3d& point) {\n    const auto& vertices = clipTetrahedronVertices();\n    const auto& triangles = clipTetrahedronTriangles();\n    const Eigen::Vector3d center =\n        (vertices[0] + vertices[1] + vertices[2] + vertices[3]) / 4.0;\n\n    constexpr double epsilon = 1.0e-9;\n    for (const auto& tri : triangles) {\n        const Eigen::Vector3d& a = vertices[tri[0]];\n        const Eigen::Vector3d& b = vertices[tri[1]];\n        const Eigen::Vector3d& c = vertices[tri[2]];\n        Eigen::Vector3d normal = (b - a).cross(c - a).normalized();\n        if ((center - a).dot(normal) > 0.0)\n            normal = -normal;\n        if ((point - a).dot(normal) > epsilon)\n            return false;\n    }\n    return true;\n}\n\nTEST(Solver, ClipsZeroRestStitchAtClosedMeshCrossing) {\n    Solver solver;\n    solver.setIterations(1);\n    solver.setSubsteps(1);\n\n    const int particleA =\n        solver.addParticle(Particle(Eigen::Vector3d(1.0, -0.5, 0.75)));\n    const int particleB =\n        solver.addParticle(Particle(Eigen::Vector3d(1.0, 2.5, 0.75)));\n    solver.addStitch(particleA, particleB, 0.0);\n\n    World world;\n    world.setGravity(Eigen::Vector3d::Zero());\n    world.setThickness(0.1);\n    world.addCollider(std::make_shared<MeshCollider>(\n        clipTetrahedronVertices(), clipTetrahedronTriangles(), 0.0));\n\n    solver.update(world, 1.0 / 60.0);\n\n    const auto& particles = solver.getParticles();\n    EXPECT_FALSE(clipTetrahedronContains(particles[particleA].getPosition()));\n    EXPECT_FALSE(clipTetrahedronContains(particles[particleB].getPosition()));\n    EXPECT_LT(particles[particleA].getPosition().y(), 0.0);\n    EXPECT_GT(particles[particleB].getPosition().y(), 2.0);\n}\n\nTEST(Solver, ZeroRestStitchFreeSpaceConvergesNormally) {\n    Solver solver;\n    solver.setIterations(1);\n    solver.setSubsteps(1);\n\n    const int particleA =\n        solver.addParticle(Particle(Eigen::Vector3d(-1.0, 0.0, 0.0)));\n    const int particleB =\n        solver.addParticle(Particle(Eigen::Vector3d(1.0, 0.0, 0.0)));\n    solver.addStitch(particleA, particleB, 0.0);\n\n    World world;\n    world.setGravity(Eigen::Vector3d::Zero());\n\n    solver.update(world, 1.0 / 60.0);\n\n    const auto& particles = solver.getParticles();\n    EXPECT_NEAR(\n        (particles[particleA].getPosition() -\n         particles[particleB].getPosition()).norm(),\n        0.0,\n        1e-9);\n}\n\n" + "TEST(Cloth, ClearFabric) {",
        1,
    )
    cloth_test.write_text(cloth_test_cpp, encoding="utf-8")

    generated_solver_header = solver_header.read_text(encoding="utf-8")
    generated_solver_cpp = solver_cpp.read_text(encoding="utf-8")
    generated_cloth_test = cloth_test.read_text(encoding="utf-8")
    for anchor in (
        "m_activeColliders = &world.getColliders();",
        "m_activeCollisionThickness = world.getThickness();",
        "firstEnteringMeshCrossing(",
        "stitch->getLambda()",
        "stitch->setLambda(",
        "dynamic_cast<const MeshCollider*>",
    ):
        if anchor not in generated_solver_cpp:
            raise RuntimeError(f"missing Solver collision-clipping anchor: {anchor}")
    if "m_activeColliders" not in generated_solver_header or "m_activeCollisionThickness" not in generated_solver_header:
        raise RuntimeError("missing Solver active-collider context")
    for anchor in (
        "TEST(Solver, ClipsZeroRestStitchAtClosedMeshCrossing)",
        "TEST(Solver, ZeroRestStitchFreeSpaceConvergesNormally)",
    ):
        if anchor not in generated_cloth_test:
            raise RuntimeError(f"missing stitch-crossing regression: {anchor}")
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

    if subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=False).returncode != 0:
        raise RuntimeError("patched Tissu tree failed git diff --check")
    changed = run("git", "diff", "--name-only")
    expected = {
        "core/include/physics/MeshCollider.hpp",
        "core/include/physics/Solver.hpp",
        "core/src/physics/MeshCollider.cpp",
        "core/src/physics/Solver.cpp",
        "tests/physics/test_cloth.cpp",
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
