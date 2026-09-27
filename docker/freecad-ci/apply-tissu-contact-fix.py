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

    solver_text = solver_cpp.read_text(encoding="utf-8")
    solver_old = """    const auto& colliders = world.getColliders();
    for (auto& collider : colliders)
        collider->resolve(m_particles, dt, world.getThickness());

    solveSelfCollisions(dt, world.getThickness());"""
    # The second collider pass is the isolated fixed-point discriminator.
    solver_new = """    const auto& colliders = world.getColliders();
    for (auto& collider : colliders)
        collider->resolve(m_particles, dt, world.getThickness());

    // Re-enforce the existing constraints once after collision projection,
    // then re-project collisions so the two operations reach a bounded
    // fixed point without changing the configured solver iteration count.
    solveConstraints(dt);

    for (auto& collider : colliders)
        collider->resolve(m_particles, dt, world.getThickness());

    solveSelfCollisions(dt, world.getThickness());"""
    if solver_text.count(solver_old) != 1:
        raise RuntimeError("Solver.cpp collision-order anchor mismatch")
    solver_cpp.write_text(solver_text.replace(solver_old, solver_new, 1), encoding="utf-8")

    cloth_test_cpp = cloth_test.read_text(encoding="utf-8")
    cloth_test_cpp = cloth_test_cpp.replace(
        '#include "physics/Solver.hpp"\n',
        '#include "physics/Collider.hpp"\n#include "physics/Solver.hpp"\n#include "engine/World.hpp"\n',
        1,
    )
    cloth_test_cpp = cloth_test_cpp.replace("#include <gtest/gtest.h>\n", "#include <gtest/gtest.h>\n#include <memory>\n", 1)
    order_test = """class OneShotDisplacingCollider final : public Collider {
public:
    int calls = 0;
    double first_gap = -1.0;
    double second_gap = -1.0;

    void resolve(std::vector<Particle>& particles, double, double) override {
        ++calls;
        if (particles.size() < 2)
            return;
        if (calls == 1) {
            particles[0].setPosition(Eigen::Vector3d(-0.5, 0.0, 0.0));
            particles[1].setPosition(Eigen::Vector3d(0.5, 0.0, 0.0));
            first_gap = (particles[0].getPosition() - particles[1].getPosition()).norm();
        } else if (calls == 2) {
            second_gap = (particles[0].getPosition() - particles[1].getPosition()).norm();
        }
    }
};

TEST(Solver, ReenforcesStitchesThenReprojectsCollider) {
    Solver solver;
    solver.setIterations(1);
    solver.setSubsteps(1);
    const int a = solver.addParticle(Particle(Eigen::Vector3d::Zero()));
    const int b = solver.addParticle(Particle(Eigen::Vector3d::Zero()));
    solver.addStitch(a, b, 0.0);

    World world;
    world.setGravity(Eigen::Vector3d::Zero());
    world.setThickness(0.01);
    auto collider = std::make_shared<OneShotDisplacingCollider>();
    world.addCollider(collider);

    solver.update(world, 1.0 / 60.0);

    ASSERT_EQ(collider->calls, 2);
    EXPECT_GT(collider->first_gap, 0.9);
    EXPECT_NEAR(collider->second_gap, 0.0, 1e-9);
    const auto& particles = solver.getParticles();
    EXPECT_NEAR((particles[a].getPosition() - particles[b].getPosition()).norm(), 0.0, 1e-9);
}

"""
    if cloth_test_cpp.count("TEST(Cloth, ClearFabric)") != 1:
        raise RuntimeError("Cloth test anchor missing")
    cloth_test_cpp = cloth_test_cpp.replace("TEST(Cloth, ClearFabric) {", order_test + "TEST(Cloth, ClearFabric) {", 1)
    cloth_test.write_text(cloth_test_cpp, encoding="utf-8")


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
        "core/src/physics/MeshCollider.cpp",
        "core/src/physics/Solver.cpp",
        "tests/physics/test_mesh_collider.cpp",
        "tests/physics/test_cloth.cpp",
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
