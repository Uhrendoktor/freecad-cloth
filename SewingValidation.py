"""Headless validation and inspection helpers for the Sewing workbench."""


def _pattern_pieces(doc):
    return [o for o in getattr(doc, "Objects", ()) if getattr(o, "PatternType", "") == "PatternPiece"]


def _seams(doc):
    return [o for o in getattr(doc, "Objects", ()) if getattr(o, "SeamId", "")]


def _networks(doc):
    return [o for o in getattr(doc, "Objects", ()) if getattr(o, "SewingType", "") == "SewingNetwork"]


def seam_diagnostic(seam, piece_map=None):
    """Return a stable diagnostic dictionary for one persisted seam."""
    status = str(getattr(seam, "Status", "Valid")) or "Valid"
    seam_id = str(getattr(seam, "SeamId", "")) or getattr(seam, "Name", "<unnamed>")
    result = {
        "id": seam_id,
        "status": status,
        "reversed": bool(getattr(seam, "ReversedB", False)),
        "piece_a": str(getattr(seam, "PieceA", "")),
        "piece_b": str(getattr(seam, "PieceB", "")),
        "edge_a": str(getattr(seam, "EdgeAId", getattr(seam, "EdgeA", ""))),
        "edge_b": str(getattr(seam, "EdgeBId", getattr(seam, "EdgeB", ""))),
        "length_a": 0.0,
        "length_b": 0.0,
        "difference": 0.0,
        "message": status,
    }
    if piece_map:
        try:
            from SewingObjects import _seam_length
            a = piece_map[result["piece_a"]]
            b = piece_map[result["piece_b"]]
            result["length_a"] = _seam_length(a, seam, "A")
            result["length_b"] = _seam_length(b, seam, "B")
            result["difference"] = abs(result["length_a"] - result["length_b"])
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            result["status"] = "Invalid"
            result["message"] = "Unable to resolve seam geometry: %s" % exc
            return result
    if status == "Valid":
        result["message"] = "valid%s" % ("; B direction reversed" if result["reversed"] else "")
    elif status == "Changed reference":
        result["message"] = "edge geometry changed; repair or recreate this seam"
    elif status == "Missing reference":
        result["message"] = "referenced edge is missing; repair or recreate this seam"
    elif status == "Length mismatch":
        result["message"] = "seam lengths differ by %.3f mm" % result["difference"]
    return result


def validate_sewing_graph(doc, tolerance=0.5):
    """Validate all sewing relationships and report graph completeness.

    Every pattern piece is a graph node. Canonical seams and M:N network
    members are graph edges. Isolated pattern pieces make the graph
    ``Incomplete``; broken references make it ``Invalid``. Length mismatches
    are reported without being silently accepted.
    """
    pieces = _pattern_pieces(doc)
    piece_map = {str(getattr(p, "PieceId", "")): p for p in pieces}
    seams = _seams(doc)
    networks = _networks(doc)
    diagnostics = [seam_diagnostic(seam, piece_map) for seam in seams]
    invalid = []
    connected = set()
    for item in diagnostics:
        if item["piece_a"] in piece_map and item["piece_b"] in piece_map and item["status"] == "Valid":
            connected.update((item["piece_a"], item["piece_b"]))
        if item["status"] != "Valid":
            invalid.append(item)
    network_diagnostics = []
    for network in networks:
        status = str(getattr(network, "Status", "Incomplete"))
        members = tuple(getattr(network, "Seams", ()) or ())
        network_diagnostics.append({
            "id": str(getattr(network, "RelationshipId", "")) or getattr(network, "Name", "<unnamed>"),
            "status": status,
            "segments": len(members),
            "difference": float(getattr(network, "LengthDifference", 0.0)),
        })
        for member in members:
            a = str(getattr(member, "PieceA", "")); b = str(getattr(member, "PieceB", ""))
            if a in piece_map and b in piece_map and str(getattr(member, "Status", "Valid")) == "Valid":
                connected.update((a, b))
        if status not in {"Valid"}:
            invalid.append({"id": network_diagnostics[-1]["id"], "status": status, "message": str(getattr(network, "InvalidReason", ""))})
    isolated = sorted(pid for pid in piece_map if pid not in connected)
    mismatch = [item for item in diagnostics if item["status"] == "Length mismatch"]
    if invalid:
        status = "Invalid"
        message = "Invalid sewing graph: " + "; ".join("%s (%s)" % (x["id"], x["status"]) for x in invalid)
    elif mismatch:
        status = "Length mismatch"
        message = "Length mismatch in: " + ", ".join(x["id"] for x in mismatch)
    elif isolated:
        status = "Incomplete"
        message = "Unsewn pattern pieces: " + ", ".join(isolated)
    elif not pieces:
        status = "Incomplete"
        message = "No pattern pieces in the document"
    else:
        status = "Valid"
        message = "Complete sewing graph"
    return {
        "status": status,
        "message": message,
        "piece_count": len(pieces),
        "seam_count": len(seams),
        "network_count": len(networks),
        "isolated": tuple(isolated),
        "seams": tuple(diagnostics),
        "networks": tuple(network_diagnostics),
        "tolerance": float(tolerance),
    }
