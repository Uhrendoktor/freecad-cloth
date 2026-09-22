from pathlib import Path
"""Deterministic triangle-quality instrumentation for the canonical tunic audit."""

_TRIANGLE_QUALITY_EDGE_ORDINALS = (2, 4, 5, 6)
_TRIANGLE_QUALITY_SCHEMA = "tunic-triangle-quality/v1"


def _q(values, fraction):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise RuntimeError("triangle-quality comparison has no finite reference values")
    position = float(fraction) * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * weight)


def _target_quality(a, b, c):
    from math import acos, isfinite, sqrt
    def distance(p, q):
        return sqrt(sum((float(p[i]) - float(q[i])) ** 2 for i in range(3)))
    ab, bc, ca = distance(a, b), distance(b, c), distance(c, a)
    area = 0.5 * ((float(b[0])-float(a[0]))*(float(c[2])-float(a[2])) - (float(b[2])-float(a[2]))*(float(c[0])-float(a[0])))
    if area <= 1e-12 or not isfinite(area):
        raise RuntimeError("triangle-quality manifest found non-positive or non-finite target area")
    if min(ab, bc, ca) <= 1e-12 or not all(isfinite(v) for v in (ab, bc, ca)):
        raise RuntimeError("triangle-quality manifest found a degenerate target triangle")
    def angle(opposite, side_a, side_b):
        cosine = (side_a*side_a + side_b*side_b - opposite*opposite)/(2.0*side_a*side_b)
        cosine = max(-1.0, min(1.0, cosine))
        return acos(cosine) * 180.0 / 3.141592653589793
    minimum = min(angle(bc, ab, ca), angle(ca, ab, bc), angle(ab, bc, ca))
    aspect = max(ab, bc, ca) ** 2 / (2.0 * area)
    if not all(isfinite(v) for v in (area, minimum, aspect)):
        raise RuntimeError("triangle-quality manifest contains a non-finite metric")
    return {
        "signed_area_mm2": round(float(area), 9),
        "minimum_angle_deg": round(float(minimum), 9),
        "aspect_ratio": round(float(aspect), 9),
    }


def _reference_quality(a, b, c):
    import math
    def distance(p, q):
        return math.sqrt(sum((float(p[i]) - float(q[i])) ** 2 for i in range(3)))
    edges = [distance(p, q) for p, q in ((a, b), (b, c), (c, a))]
    if min(edges) <= 1e-12 or not all(math.isfinite(v) for v in edges):
        raise RuntimeError("triangle-quality manifest found a degenerate reference triangle")
    area = abs(0.5 * ((float(b[0])-float(a[0]))*(float(c[2])-float(a[2])) - (float(b[2])-float(a[2]))*(float(c[0])-float(a[0]))))
    if area <= 1e-12 or not math.isfinite(area):
        raise RuntimeError("triangle-quality manifest found a zero reference area")
    angles = []
    for opposite, side_a, side_b in ((edges[1], edges[0], edges[2]), (edges[2], edges[0], edges[1]), (edges[0], edges[1], edges[2])):
        cosine = max(-1.0, min(1.0, (side_a*side_a + side_b*side_b - opposite*opposite)/(2.0*side_a*side_b)))
        angles.append(math.degrees(math.acos(cosine)))
    return {
        "minimum_angle_deg": round(float(min(angles)), 9),
        "aspect_ratio": round(float(max(edges) ** 2 / (2.0 * area)), 9),
    }


def build_triangle_quality_manifest(pieces, panels, proxy, particle_distance, seam_records):
    from freecad_cloth.common.PatternSimulationAdapter import resolve_piece_ir
    from freecad_cloth.simulation.SimulationMeshQuality import quality_piece_mesh

    panel_results = []
    assessments = []
    for piece, panel in sorted(zip(tuple(pieces), tuple(panels)), key=lambda item: (
        str(getattr(item[0], "PieceId", "")), str(getattr(item[1], "Name", "")))):
        positions, triangles, boundary_edges = quality_piece_mesh(piece, 0.0, float(particle_distance))
        piece_ir = resolve_piece_ir(piece)
        semantic_ids = tuple(str(v) for v in (getattr(getattr(piece, "Sketch", None), "SemanticEdgeIds", ()) or ()))
        if len(semantic_ids) <= max(_TRIANGLE_QUALITY_EDGE_ORDINALS):
            raise RuntimeError("triangle-quality manifest found incomplete semantic edge IDs")
        global_ids = tuple(int(v) for v in proxy.panel_indices[panel.Name])
        boundary_by_id = {
            str(boundary.id): tuple(int(v) for v in chain)
            for boundary, chain in zip(piece_ir.boundaries, boundary_edges)
        }
        if len(global_ids) != len(positions):
            raise RuntimeError("triangle-quality manifest found inconsistent local/global particle indexing")
        vertex_boundary_ids = [set() for _ in positions]
        for edge_id, chain in boundary_by_id.items():
            for vertex in chain:
                if not 0 <= vertex < len(vertex_boundary_ids):
                    raise RuntimeError("triangle-quality manifest found an out-of-range boundary vertex")
                vertex_boundary_ids[vertex].add(edge_id)

        target_ids = {}
        target_segments = {}
        for ordinal in _TRIANGLE_QUALITY_EDGE_ORDINALS:
            edge_id = semantic_ids[ordinal]
            chain = boundary_by_id.get(edge_id)
            if chain is None or len(chain) < 2:
                raise RuntimeError("triangle-quality manifest cannot resolve semantic edge %d (%s)" % (ordinal, edge_id))
            target_ids[ordinal] = edge_id
            target_segments[ordinal] = {frozenset((a, b)) for a, b in zip(chain, chain[1:])}

        touched_by_edge = {ordinal: [] for ordinal in _TRIANGLE_QUALITY_EDGE_ORDINALS}
        target_metrics = {}
        touched = set()
        for index, raw in enumerate(triangles):
            triangle = tuple(int(v) for v in raw)
            if len(set(triangle)) != 3 or any(v < 0 or v >= len(positions) for v in triangle):
                raise RuntimeError("triangle-quality manifest found an invalid triangle index")
            segments = (
                frozenset((triangle[0], triangle[1])),
                frozenset((triangle[1], triangle[2])),
                frozenset((triangle[2], triangle[0])),
            )
            ordinals = tuple(ordinal for ordinal in _TRIANGLE_QUALITY_EDGE_ORDINALS
                             if any(segment in target_segments[ordinal] for segment in segments))
            if not ordinals:
                continue
            target_metrics[index] = _target_quality(*(positions[v] for v in triangle))
            touched.add(index)
            for ordinal in ordinals:
                touched_by_edge[ordinal].append(index)

        rest_metrics = [
            _reference_quality(*(positions[int(v)] for v in raw))
            for index, raw in enumerate(triangles) if index not in touched
        ]
        if not touched or not rest_metrics:
            raise RuntimeError("triangle-quality manifest lacks target or reference triangles")

        rest_angles = [item["minimum_angle_deg"] for item in rest_metrics]
        rest_aspects = [item["aspect_ratio"] for item in rest_metrics]
        target_angles = [target_metrics[i]["minimum_angle_deg"] for i in sorted(touched)]
        target_aspects = [target_metrics[i]["aspect_ratio"] for i in sorted(touched)]
        rest_p05_angle = _q(rest_angles, 0.05)
        rest_p95_aspect = _q(rest_aspects, 0.95)
        target_min_angle = min(target_angles)
        target_max_aspect = max(target_aspects)
        assessment = "pathological" if (
            target_min_angle < rest_p05_angle - 5.0 or
            target_max_aspect > rest_p95_aspect * 1.5
        ) else "ordinary"
        assessments.append(assessment)

        semantic_edges = []
        for ordinal in _TRIANGLE_QUALITY_EDGE_ORDINALS:
            edge_id = target_ids[ordinal]
            seams = []
            for seam, piece_a, piece_b in seam_records:
                seam_id = str(getattr(seam, "SeamId", getattr(seam, "Label", "")))
                pairs = tuple(getattr(proxy, "seam_stitch_pairs", {}).get(seam_id, ()))
                for side, seam_piece, attr in (("A", piece_a, "EdgeAId"), ("B", piece_b, "EdgeBId")):
                    if str(getattr(seam_piece, "PieceId", "")) != str(getattr(piece, "PieceId", "")):
                        continue
                    if str(getattr(seam, attr, "")) != edge_id:
                        continue
                    if not pairs:
                        raise RuntimeError("triangle-quality manifest missing exact solver stitch-pair provenance for %s" % seam_id)
                    seams.append({
                        "seam_id": seam_id,
                        "side": side,
                        "semantic_edge_id": edge_id,
                        "solver_stitch_pair_indices": [[int(a), int(b)] for a, b in sorted(pairs, key=lambda pair: (int(pair[0]), int(pair[1])))],
                    })

            chain = boundary_by_id[edge_id]
            records = []
            for index in touched_by_edge[ordinal]:
                triangle = tuple(int(v) for v in triangles[index])
                adjacent = [{
                    "local_particle_index": int(v),
                    "global_particle_index": int(global_ids[v]),
                    "semantic_boundary_ids": sorted(vertex_boundary_ids[v]),
                } for v in triangle if vertex_boundary_ids[v]]
                if len(adjacent) < 2:
                    raise RuntimeError("triangle-quality manifest target triangle lacks expected boundary vertices")
                records.append({
                    "triangle_local_particle_indices": list(triangle),
                    "triangle_global_particle_indices": [int(global_ids[v]) for v in triangle],
                    **target_metrics[index],
                    "adjacent_boundary_vertices": adjacent,
                })
            semantic_edges.append({
                "semantic_edge_ordinal": int(ordinal),
                "semantic_edge_id": edge_id,
                "boundary_chain_local_particle_indices": list(chain),
                "boundary_chain_global_particle_indices": [int(global_ids[v]) for v in chain],
                "affected_solver_seams": sorted(seams, key=lambda item: (item["seam_id"], item["side"])),
                "triangle_indices": [int(v) for v in touched_by_edge[ordinal]],
                "triangles": records,
            })

        panel_results.append({
            "panel": str(getattr(panel, "Name", "")),
            "piece_id": str(getattr(piece, "PieceId", "")),
            "particle_count": len(positions),
            "triangle_count": len(triangles),
            "target_triangle_count": len(touched),
            "rest_triangle_count": len(rest_metrics),
            "positive_orientation": True,
            "comparison": {
                "assessment": assessment,
                "target_minimum_angle_deg": round(float(target_min_angle), 9),
                "rest_p05_minimum_angle_deg": round(float(rest_p05_angle), 9),
                "target_max_aspect_ratio": round(float(target_max_aspect), 9),
                "rest_p95_aspect_ratio": round(float(rest_p95_aspect), 9),
                "angle_pathology_rule": "target minimum angle < rest-panel p05 by more than 5 degrees",
                "aspect_pathology_rule": "target maximum aspect ratio > 1.5 * rest-panel p95",
            },
            "semantic_edges": semantic_edges,
        })

    return {
        "schema": _TRIANGLE_QUALITY_SCHEMA,
        "target_semantic_edge_ordinals": list(_TRIANGLE_QUALITY_EDGE_ORDINALS),
        "signed_area_convention": "x/z panel-plane signed area in mm^2; target triangles must be positive",
        "minimum_angle_convention": "smallest 3D triangle angle in degrees",
        "aspect_ratio_convention": "longest_edge_squared / (2 * signed_area)",
        "ordering": "panel by piece_id then name; edge by semantic ordinal; triangle by mesh-local index",
        "panel_assessments": assessments,
        "overall_assessment": "pathological" if "pathological" in assessments else "ordinary",
        "panels": panel_results,
    }


def persist_triangle_quality_manifest(manifest, metrics_path, log):
    import json
    path = Path(metrics_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["triangle_quality_manifest"] = manifest
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log("triangle-quality-manifest=passed schema=%s edges=2,4,5,6 panels=%d assessment=%s" % (
        manifest["schema"], len(manifest["panels"]), manifest["overall_assessment"]))
