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
    std::vector<std::vector<int>> m_vertexTriangles;
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
#include <unordered_set>
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

    struct EdgeInfo {
        int count = 0;
        int direction = 0;
        int firstTriangle = -1;
        int secondTriangle = -1;
    };

    std::unordered_map<std::uint64_t, EdgeInfo> edges;
    std::unordered_map<int, std::vector<int>> vertexTriangles;
    edges.reserve(triangles.size() * 3);
    vertexTriangles.reserve(vertices.size());

    double signedVolume = 0.0;
    for (size_t triangleIndex = 0; triangleIndex < triangles.size();
         ++triangleIndex) {
        const auto& tri = triangles[triangleIndex];
        const int ids[3] = {tri.a, tri.b, tri.c};
        signedVolume +=
            ids[0] < static_cast<int>(vertices.size()) &&
                    ids[1] < static_cast<int>(vertices.size()) &&
                    ids[2] < static_cast<int>(vertices.size())
                ? vertices[ids[0]].dot(
                      vertices[ids[1]].cross(vertices[ids[2]])) /
                      6.0
                : 0.0;

        for (const int vertex : ids) {
            if (vertex < 0 ||
                vertex >= static_cast<int>(vertices.size())) {
                return {};
            }
            vertexTriangles[vertex].push_back(
                static_cast<int>(triangleIndex));
        }

        for (int edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {
            const int from = ids[edgeIndex];
            const int to = ids[(edgeIndex + 1) % 3];
            const auto key = edgeKey(from, to);
            auto& edge = edges[key];
            ++edge.count;
            edge.direction +=
                from == std::min(from, to) ? 1 : -1;
            if (edge.firstTriangle == -1)
                edge.firstTriangle = static_cast<int>(triangleIndex);
            else if (edge.secondTriangle == -1)
                edge.secondTriangle = static_cast<int>(triangleIndex);
        }
    }

    for (const auto& [key, edge] : edges) {
        (void)key;
        if (edge.count != 2 || edge.direction != 0 ||
            edge.firstTriangle < 0 || edge.secondTriangle < 0)
            return {};
    }

    // A vertex fan must be connected through shared edges. Two closed shells
    // that merely touch at one vertex are not a single manifold surface.
    for (const auto& [vertex, incident] : vertexTriangles) {
        (void)vertex;
        if (incident.empty())
            return {};
        std::unordered_set<int> incidentSet(incident.begin(), incident.end());
        std::unordered_set<int> connected;
        std::vector<int> pending{incident.front()};
        connected.insert(incident.front());

        while (!pending.empty()) {
            const int triangleIndex = pending.back();
            pending.pop_back();
            const auto& tri = triangles[triangleIndex];
            const int ids[3] = {tri.a, tri.b, tri.c};
            for (int edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {
                const int from = ids[edgeIndex];
                const int to = ids[(edgeIndex + 1) % 3];
                if (from != vertex && to != vertex)
                    continue;
                const auto& edge = edges.at(edgeKey(from, to));
                const int otherTriangle =
                    edge.firstTriangle == triangleIndex
                        ? edge.secondTriangle
                        : edge.firstTriangle;
                if (otherTriangle >= 0 &&
                    incidentSet.count(otherTriangle) > 0 &&
                    connected.insert(otherTriangle).second) {
                    pending.push_back(otherTriangle);
                }
            }
        }

        if (connected.size() != incidentSet.size())
            return {};
    }

    if (std::abs(signedVolume) <= 1.0e-12)
        return {};

    return {true, signedVolume < 0.0 ? 1.0 : -1.0};
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

    m_vertexTriangles.assign(m_worldVertices.size(), {});
    for (size_t triangleIndex = 0; triangleIndex < m_triangles.size();
         ++triangleIndex) {
        const Triangle& triangle = m_triangles[triangleIndex];
        if (triangle.a < 0 ||
            triangle.b < 0 ||
            triangle.c < 0 ||
            triangle.a >= static_cast<int>(m_vertexTriangles.size()) ||
            triangle.b >= static_cast<int>(m_vertexTriangles.size()) ||
            triangle.c >= static_cast<int>(m_vertexTriangles.size()))
            throw std::runtime_error("MeshCollider triangle index out of range");
        m_vertexTriangles[triangle.a].push_back(static_cast<int>(triangleIndex));
        m_vertexTriangles[triangle.b].push_back(static_cast<int>(triangleIndex));
        m_vertexTriangles[triangle.c].push_back(static_cast<int>(triangleIndex));
    }

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

    m_vertexTriangles.assign(m_worldVertices.size(), {});
    for (size_t triangleIndex = 0; triangleIndex < m_triangles.size();
         ++triangleIndex) {
        const Triangle& triangle = m_triangles[triangleIndex];
        if (triangle.a < 0 ||
            triangle.b < 0 ||
            triangle.c < 0 ||
            triangle.a >= static_cast<int>(m_vertexTriangles.size()) ||
            triangle.b >= static_cast<int>(m_vertexTriangles.size()) ||
            triangle.c >= static_cast<int>(m_vertexTriangles.size()))
            throw std::runtime_error("MeshCollider triangle index out of range");
        m_vertexTriangles[triangle.a].push_back(static_cast<int>(triangleIndex));
        m_vertexTriangles[triangle.b].push_back(static_cast<int>(triangleIndex));
        m_vertexTriangles[triangle.c].push_back(static_cast<int>(triangleIndex));
    }

    m_bvh.build(m_worldVertices, m_triangles);""",
            "MeshCollider.cpp vector constructor",
        ),
        ( 
            """void MeshCollider::resolve(std::vector<Particle>& particles, double dt,
                           double thickness) {
    Eigen::Vector3d linearVel = getLinearVelocity(dt);
    Eigen::Vector3d omega = getAngularVelocity(dt);

    constexpr int kMaxClosedContactIterations = 8;
    constexpr double kContactEpsilon = 1e-12;

    for (auto& particle : particles) {
        Eigen::Vector3d resolvedPosition = particle.getPosition();
        Eigen::Vector3d finalNormal = Eigen::Vector3d::Zero();
        bool touched = false;

        const int maxIterations =
            m_closedManifold ? kMaxClosedContactIterations : 1;

        for (int iteration = 0; iteration < maxIterations; ++iteration) {
            const int triIdx =
                m_bvh.closestTriangle(resolvedPosition, m_worldVertices);
            if (triIdx == -1)
                break;

            const Triangle& tri = m_bvh.getTriangle(triIdx);
            const Eigen::Vector3d& a = m_worldVertices[tri.a];
            const Eigen::Vector3d& b = m_worldVertices[tri.b];
            const Eigen::Vector3d& c = m_worldVertices[tri.c];

            const Eigen::Vector3d cp =
                closestPointOnTriangle(resolvedPosition, a, b, c);
            const Eigen::Vector3d toParticle = resolvedPosition - cp;
            const double distance = toParticle.norm();

            const Eigen::Vector3d faceNormalRaw = (b - a).cross(c - a);
            const double faceNormalLength = faceNormalRaw.norm();
            if (faceNormalLength <= kContactEpsilon)
                break;

            const Eigen::Vector3d outwardNormal =
                (faceNormalRaw / faceNormalLength) * m_outwardNormalSign;

            bool insideClosedMesh = false;
            if (m_closedManifold) {
                std::vector<int> candidateTriangles;
                candidateTriangles.reserve(
                    m_vertexTriangles[tri.a].size() +
                    m_vertexTriangles[tri.b].size() +
                    m_vertexTriangles[tri.c].size());
                candidateTriangles.insert(
                    candidateTriangles.end(),
                    m_vertexTriangles[tri.a].begin(),
                    m_vertexTriangles[tri.a].end());
                candidateTriangles.insert(
                    candidateTriangles.end(),
                    m_vertexTriangles[tri.b].begin(),
                    m_vertexTriangles[tri.b].end());
                candidateTriangles.insert(
                    candidateTriangles.end(),
                    m_vertexTriangles[tri.c].begin(),
                    m_vertexTriangles[tri.c].end());
                std::sort(candidateTriangles.begin(), candidateTriangles.end());
                candidateTriangles.erase(
                    std::unique(candidateTriangles.begin(),
                                candidateTriangles.end()),
                    candidateTriangles.end());

                const double tieTolerance =
                    1e-7 * std::max(1.0, distance);
                bool allCandidatesInterior = true;
                bool hasCandidate = false;
                for (const int candidateIndex : candidateTriangles) {
                    const Triangle& candidate =
                        m_bvh.getTriangle(candidateIndex);
                    const Eigen::Vector3d& ca =
                        m_worldVertices[candidate.a];
                    const Eigen::Vector3d& cb =
                        m_worldVertices[candidate.b];
                    const Eigen::Vector3d& cc =
                        m_worldVertices[candidate.c];
                    const Eigen::Vector3d candidatePoint =
                        closestPointOnTriangle(
                            resolvedPosition, ca, cb, cc);
                    const double candidateDistance =
                        (resolvedPosition - candidatePoint).norm();
                    if (std::abs(candidateDistance - distance) >
                        tieTolerance)
                        continue;

                    hasCandidate = true;
                    const Eigen::Vector3d candidateNormalRaw =
                        (cb - ca).cross(cc - ca);
                    const double candidateNormalLength =
                        candidateNormalRaw.norm();
                    if (candidateNormalLength <= kContactEpsilon) {
                        allCandidatesInterior = false;
                        break;
                    }

                    const Eigen::Vector3d candidateOutward =
                        (candidateNormalRaw / candidateNormalLength) *
                        m_outwardNormalSign;
                    const double candidateSignedDistance =
                        (resolvedPosition - candidatePoint).dot(
                            candidateOutward);
                    if (candidateSignedDistance >= -tieTolerance) {
                        allCandidatesInterior = false;
                        break;
                    }
                }
                insideClosedMesh = hasCandidate && allCandidatesInterior;
            }

            if (distance > thickness && !insideClosedMesh)
                break;

            Eigen::Vector3d normal;
            if (m_closedManifold && insideClosedMesh) {
                normal = outwardNormal;
            } else if (distance > 1e-6) {
                // Preserve the pinned legacy outside-contact response exactly.
                normal = toParticle / distance;
            } else {
                normal = (faceNormalRaw / faceNormalLength) *
                         (m_closedManifold ? m_outwardNormalSign : 1.0);
            }

            const Eigen::Vector3d newPosition =
                cp + normal * thickness;
            if ((newPosition - resolvedPosition).norm() <= kContactEpsilon)
                break;

            resolvedPosition = newPosition;
            finalNormal = normal;
            touched = true;

            if (!m_closedManifold || !insideClosedMesh)
                break;
        }

        if (!touched)
            continue;

        particle.setPosition(resolvedPosition);

        Eigen::Vector3d colliderVelocity =
            linearVel + omega.cross(resolvedPosition - m_position);
        Eigen::Vector3d colliderDisplacement = colliderVelocity * dt;
        Eigen::Vector3d particleDisplacement =
            resolvedPosition - particle.getOldPosition();
        Eigen::Vector3d relDisplacement =
            particleDisplacement - colliderDisplacement;

        double normalVelMag = relDisplacement.dot(finalNormal);
        Eigen::Vector3d normalVel = finalNormal * normalVelMag;
        Eigen::Vector3d tangentVel = relDisplacement - normalVel;

        Eigen::Vector3d newVelocity =
            normalVel + tangentVel * (1.0 - m_friction);

        particle.setOldPosition(resolvedPosition - newVelocity);
    }
}""",
            "MeshCollider.cpp contact response",
        )
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

TEST(MeshCollider, VertexTouchingClosedShellsDoNotEnableDeepContact) {
    const std::vector<Eigen::Vector3d> vertices = {
        {0.0, 0.0, 0.0},
        {2.0, 0.0, 0.0},
        {1.0, 0.0, 2.0},
        {1.0, 2.0, 1.0},
        {0.0, 2.0, 3.0},
        {-1.0, 2.0, 2.0},
        {-1.0, 4.0, 2.0},
    };
    const std::vector<std::array<int, 3>> triangles = {
        {0, 2, 1}, {0, 1, 3}, {1, 2, 3}, {0, 3, 2},
        {0, 4, 5}, {0, 5, 6}, {4, 6, 5}, {0, 6, 4},
    };
    MeshCollider mesh(vertices, triangles, 0.0);

    Eigen::Vector3d initialPos(-0.5, 2.0, 1.75);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.01);

    EXPECT_NEAR(
        (particles[0].getPosition() - initialPos).norm(),
        0.0, 1e-9);
}

TEST(MeshCollider, ClosedMeshSharedVertexOutsideTieDoesNotMove) {
    MeshCollider mesh = makeTetrahedron(0.0);
    Eigen::Vector3d initialPos(-0.1, -0.1, 0.0);
    std::vector<Particle> particles;
    particles.emplace_back(initialPos);

    mesh.resolve(particles, 0.016, 0.01);

    EXPECT_NEAR(
        (particles[0].getPosition() - initialPos).norm(),
        0.0, 1e-9);
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
