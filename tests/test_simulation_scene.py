def test_pin_mode_semantics_preserve_automatic_defaults_and_support_no_pins():
    from types import SimpleNamespace

    from freecad_cloth.simulation.SimulationObjects import resolve_pin_indices

    legacy = SimpleNamespace(PinSelection=[])
    automatic = SimpleNamespace(PinSelection=[], PinMode="Automatic")
    explicit = SimpleNamespace(PinSelection=["2", "5"], PinMode="Explicit")
    explicit_empty = SimpleNamespace(PinSelection=[], PinMode="Explicit")
    none = SimpleNamespace(PinSelection=["2", "5"], PinMode="None")

    assert resolve_pin_indices(legacy, 8, (0, 7)) == (0, 7)
    assert resolve_pin_indices(automatic, 8, (0, 7)) == (0, 7)
    assert resolve_pin_indices(explicit, 8, (0, 7)) == (2, 5)
    assert resolve_pin_indices(explicit_empty, 8, (0, 7)) == ()
    assert resolve_pin_indices(none, 8, (0, 7)) == ()


def test_pin_mode_is_part_of_rebuild_signature_and_none_ignores_pin_selection():
    from types import SimpleNamespace

    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

    source = SimpleNamespace(
        Name="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(
                Angle=0.0,
                Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0),
            ),
        ),
    )
    target = SimpleNamespace(
        SourceObject=source,
        CollisionDeflection=1.0,
        CollisionThickness=0.0,
    )
    base = dict(DrapeTarget=target, StitchSamples=8, Document=SimpleNamespace(Objects=[]))
    automatic = SimpleNamespace(**base, PinMode="Automatic", PinSelection=[])
    explicit = SimpleNamespace(**base, PinMode="Explicit", PinSelection=["1", "2"])
    none_a = SimpleNamespace(**base, PinMode="None", PinSelection=["1", "2"])
    none_b = SimpleNamespace(**base, PinMode="None", PinSelection=["6", "7"])

    assert _simulation_source_signature(automatic, []) != _simulation_source_signature(explicit, [])
    assert _simulation_source_signature(explicit, []) != _simulation_source_signature(none_a, [])
    assert _simulation_source_signature(none_a, []) == _simulation_source_signature(none_b, [])


def test_pin_selection_is_part_of_rebuild_signature():
    from types import SimpleNamespace

    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

    source = SimpleNamespace(
        Name="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
        ),
    )
    target = SimpleNamespace(SourceObject=source, CollisionDeflection=1.0, CollisionThickness=0.0)
    scene_a = SimpleNamespace(
        DrapeTarget=target,
        PinSelection=["1", "2"],
        StitchSamples=8,
        Document=SimpleNamespace(Objects=[]),
    )
    scene_b = SimpleNamespace(
        DrapeTarget=target,
        PinSelection=["3", "4"],
        StitchSamples=8,
        Document=SimpleNamespace(Objects=[]),
    )
    assert _simulation_source_signature(scene_a, []) != _simulation_source_signature(scene_b, [])


def test_seam_pair_records_preserve_exact_solver_stitch_provenance():
    from freecad_cloth.pattern.PatternIR import BoundaryIR, PatternIR, PieceIR, SeamIR
    from freecad_cloth.simulation.SimulationObjects import _seam_pair_records

    pattern = PatternIR(
        (
            PieceIR(
                "piece-a",
                "PieceA",
                (BoundaryIR("piece-a:edge:0", "line", ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0))),),
            ),
            PieceIR(
                "piece-b",
                "PieceB",
                (BoundaryIR("piece-b:edge:0", "line", ((0.0, 100.0, 0.0), (20.0, 100.0, 0.0))),),
            ),
        ),
        (
            SeamIR(
                id="seam-1",
                piece_a="piece-a",
                edge_a="piece-a:edge:0",
                piece_b="piece-b",
                edge_b="piece-b:edge:0",
                reversed_b=True,
            ),
        ),
    )
    panel_data = {
        "piece-a": {
            "boundary_edges": ((0, 1, 2),),
            "positions": (
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
            ),
        },
        "piece-b": {
            "boundary_edges": ((3, 4, 5),),
            "positions": (
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
                (0.0, 100.0, 0.0),
                (10.0, 100.0, 0.0),
                (20.0, 100.0, 0.0),
            ),
        },
    }
    pairs, records = _seam_pair_records(pattern, panel_data, seam_samples=3)
    assert pairs == ((0, 5), (1, 4), (2, 3))
    assert records == (("seam-1", "PieceA", "PieceB", ((0, 5), (1, 4), (2, 3))),)


def test_simulation_proxy_does_not_mix_surface_and_legacy_sphere_collision():
    from types import SimpleNamespace

    from freecad_cloth.simulation.SimulationObjects import (
        SimulationProxy,
        _simulation_source_signature,
    )

    class FakeBackend:
        def __init__(self):
            self.calls = []

        def step(self, dt, iterations, gravity, surface):
            self.calls.append((dt, iterations, gravity, surface))

        def positions(self):
            return ()

        @property
        def time(self):
            return 0.0

        def finite(self):
            return True

    scene = SimpleNamespace(
        ClothPieces=[],
        Document=SimpleNamespace(Objects=[]),
        DrapeTarget=None,
        PinSelection=[],
        StitchSamples=8,
        Steps=1,
        TimeStep=1.0 / 60.0,
        Iterations=8,
        GravityX=0.0,
        GravityY=0.0,
        GravityZ=-9810.0,
        CollisionX=0.0,
        CollisionY=0.0,
        CollisionZ=0.0,
        CollisionRadius=38.0,
        DrapePanels=[],
    )
    proxy = SimulationProxy()
    proxy.backend = FakeBackend()
    proxy.collision_surface = object()
    proxy.source_signature = _simulation_source_signature(scene, [])
    proxy.execute(scene)

    assert proxy.backend.calls == [
        (
            scene.TimeStep,
            scene.Iterations,
            (scene.GravityX, scene.GravityY, scene.GravityZ),
            proxy.collision_surface,
        )
    ]



def test_seam_gap_diagnostics_report_exact_per_seam_statistics():
    import pytest
    from freecad_cloth.simulation.SimulationObjects import seam_gap_diagnostics

    positions = (
        (0.0, 0.0, 0.0),
        (3.0, 4.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 0.0, 2.0),
    )
    report = seam_gap_diagnostics(positions, {"side": ((0, 1), (2, 3))})
    assert report["side"] == {
        "pair_count": 2,
        "first_gap": 5.0,
        "last_gap": 2.0,
        "max_gap": 5.0,
    }
    with pytest.raises(ValueError, match="no stitch pairs"):
        seam_gap_diagnostics(positions, {"empty": ()})
    with pytest.raises(ValueError, match="outside solver positions"):
        seam_gap_diagnostics(positions, {"bad": ((0, 8),)})
    with pytest.raises(ValueError, match="itself"):
        seam_gap_diagnostics(positions, {"self": ((0, 0),)})



def _attachment_test_surface():
    from freecad_cloth.shared.collision import surface_from_triangles

    return surface_from_triangles(
        ((-10.0, -10.0, 10.0), (10.0, -10.0, 10.0), (0.0, 10.0, 10.0), (0.0, 0.0, -10.0)),
        ((0, 2, 1),),
    )


def _install_native_mesh_projection(
    monkeypatch, facet_area=200.0, plane_axis="z", plane_value=10.0, normal=(0.0, 0.0, 1.0)
):
    import sys
    from types import SimpleNamespace

    class Vector:
        def __init__(self, x, y=None, z=None):
            if y is None and z is None:
                x, y, z = x
            self.x, self.y, self.z = float(x), float(y), float(z)

        @property
        def Length(self):
            return (self.x * self.x + self.y * self.y + self.z * self.z) ** 0.5

        def normalize(self):
            length = self.Length
            if length <= 1e-12:
                raise ValueError("cannot normalize zero vector")
            self.x, self.y, self.z = self.x / length, self.y / length, self.z / length

        def dot(self, other):
            return self.x * other.x + self.y * other.y + self.z * other.z

        def __sub__(self, other):
            return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

        def __add__(self, other):
            return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

        def __neg__(self):
            return Vector(-self.x, -self.y, -self.z)

        def __mul__(self, scale):
            return Vector(self.x * scale, self.y * scale, self.z * scale)

    class Facet:
        Area = facet_area

        @property
        def Normal(self):
            return Vector(*normal)

    class NativeMesh:
        def __init__(self):
            self.input_facets = []
            self.rays = []

        def addFacets(self, facets):
            self.input_facets.extend(facets)

        @property
        def Facets(self):
            return tuple(Facet() for _ in self.input_facets)

        def nearestFacetOnRay(self, point, direction):
            self.rays.append((tuple(point), tuple(direction)))
            coordinates = [float(value) for value in point]
            vector = [float(value) for value in direction]
            axis = {"x": 0, "y": 1, "z": 2}[plane_axis]
            if abs(vector[axis]) <= 1e-12:
                return {}
            factor = (float(plane_value) - coordinates[axis]) / vector[axis]
            if factor < 0.0:
                return {}
            hit = [coordinates[index] + vector[index] * factor for index in range(3)]
            hit[axis] = float(plane_value)
            return {0: tuple(hit)}

    native_mesh = NativeMesh()
    monkeypatch.setitem(sys.modules, "FreeCAD", SimpleNamespace(Vector=Vector))
    monkeypatch.setitem(sys.modules, "Mesh", SimpleNamespace(Mesh=lambda: native_mesh))
    return native_mesh


def test_avatar_attachment_projection_delegates_surface_queries_to_freecad_mesh(monkeypatch):
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments

    native_mesh = _install_native_mesh_projection(monkeypatch)
    positions = ((0.0, 0.0, 5.0), (4.0, 0.0, 15.0), (5.0, 0.0, 5.0))
    projected, records = project_avatar_attachments(
        positions,
        (0, 2),
        _attachment_test_surface(),
        offset_mm=3.0,
        target_points={0: positions[0], 2: positions[2]},
        projection_directions={0: (0.0, 0.0, 1.0), 2: (0.0, 0.0, 1.0)},
    )
    assert projected[1] == positions[1]
    assert len(records) == 2
    assert len(native_mesh.input_facets) == 1
    assert len(native_mesh.rays) >= 2
    for record in records:
        assert abs(record.anchor_position[2] - 13.0) < 1e-9
        assert abs(record.anchor_position[2] - record.surface_point[2] - 3.0) < 1e-9
        assert record.triangle_index == 0
        assert abs(record.source_distance_mm - 5.0) < 1e-9
        assert record.outward_normal == (0.0, 0.0, 1.0)


def test_avatar_attachment_projection_uses_semantic_front_back_ray_and_native_normal(monkeypatch):
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments
    from freecad_cloth.shared.collision import surface_from_triangles

    for side in (-1.0, 1.0):
        _install_native_mesh_projection(
            monkeypatch,
            plane_axis="y",
            plane_value=10.0 * side,
            normal=(0.0, 1.0, 0.0),
        )
        surface = surface_from_triangles(
            (
                (-10.0, 10.0 * side, -10.0),
                (10.0, 10.0 * side, -10.0),
                (0.0, 10.0 * side, 10.0),
                (0.0, -10.0 * side, 0.0),
            ),
            ((0, 2, 1),),
        )
        projected, records = project_avatar_attachments(
            ((0.0, 0.0, 0.0),),
            (0,),
            surface,
            offset_mm=3.0,
            target_points={0: (0.0, 0.0, 0.0)},
            projection_directions={0: (0.0, side, 0.0)},
        )
        assert abs(projected[0][1] - 13.0 * side) < 1e-9
        assert records[0].outward_normal == (0.0, side, 0.0)
        assert abs(records[0].source_distance_mm - 10.0) < 1e-9


def test_avatar_attachment_projection_tries_reverse_ray_but_keeps_outward_normal(monkeypatch):
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments

    native_mesh = _install_native_mesh_projection(
        monkeypatch,
        plane_axis="x",
        plane_value=180.0,
        normal=(1.0, 0.0, 0.0),
    )
    source = (220.0, 0.0, 1347.5)
    projected, records = project_avatar_attachments(
        (source,),
        (0,),
        _attachment_test_surface(),
        offset_mm=3.0,
        target_points={0: source},
        projection_directions={0: (1.0, 0.0, 0.0)},
    )

    assert tuple(direction for _point, direction in native_mesh.rays) == (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
    )
    assert records[0].source_distance_mm == 40.0
    assert records[0].surface_point == (180.0, 0.0, 1347.5)
    assert records[0].outward_normal == (1.0, 0.0, 0.0)
    assert projected[0] == (183.0, 0.0, 1347.5)


def test_avatar_attachment_projection_rejects_points_too_far_from_target(monkeypatch):
    import pytest
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments

    _install_native_mesh_projection(monkeypatch)
    with pytest.raises(ValueError, match="too far from the DrapeTarget surface"):
        project_avatar_attachments(
            ((0.0, 0.0, 500.0),),
            (0,),
            _attachment_test_surface(),
            target_points={0: (0.0, 0.0, 500.0)},
        )


def test_avatar_attachment_projection_fails_closed_on_invalid_selection_offset_and_surface(monkeypatch):
    import pytest
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments
    from freecad_cloth.shared.collision import surface_from_triangles

    _install_native_mesh_projection(monkeypatch)
    positions = ((0.0, 0.0, 15.0),)
    surface = _attachment_test_surface()
    with pytest.raises(ValueError, match="at least one"):
        project_avatar_attachments(positions, (), surface)
    with pytest.raises(ValueError, match="outside"):
        project_avatar_attachments(positions, (1,), surface)
    with pytest.raises(ValueError, match="between 0 and 100"):
        project_avatar_attachments(positions, (0,), surface, offset_mm=float("nan"))
    with pytest.raises(ValueError, match="integer indices"):
        project_avatar_attachments(positions, (True,), surface)
    with pytest.raises(ValueError, match="integer indices"):
        project_avatar_attachments(positions, (0.5,), surface)
    with pytest.raises(ValueError, match="integer particle indices"):
        project_avatar_attachments(
            positions, (0,), surface, target_points={0.5: (0.0, 0.0, 10.0)}
        )
    from freecad_cloth.shared.collision import CollisionSurface
    malformed = CollisionSurface(
        surface.vertices,
        ((0.5, 1, 2),),
        region=surface.region,
        thickness=surface.thickness,
    )
    with pytest.raises(ValueError, match="invalid triangle"):
        project_avatar_attachments(positions, (0,), malformed)
    degenerate = surface_from_triangles(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((0, 1, 2),),
    )
    _install_native_mesh_projection(monkeypatch, facet_area=0.0)
    with pytest.raises(ValueError, match="non-degenerate"):
        project_avatar_attachments(positions, (0,), degenerate)


def test_avatar_attachment_selection_is_order_independent_and_fails_closed_on_ambiguity():
    import pytest
    from freecad_cloth.simulation.ClothAttachments import select_attachment_particle_near_anchor

    positions = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    anchor = (19.0, 0.0, 0.0)
    assert select_attachment_particle_near_anchor((0, 1, 2), positions, anchor) == 2
    assert select_attachment_particle_near_anchor((2, 0, 1), positions, anchor) == 2
    with pytest.raises(ValueError, match="empty"):
        select_attachment_particle_near_anchor((), positions, anchor)
    with pytest.raises(ValueError, match="integer indices"):
        select_attachment_particle_near_anchor((0, 1.5), positions, anchor)
    with pytest.raises(ValueError, match="integer indices"):
        select_attachment_particle_near_anchor((True,), positions, anchor)
    with pytest.raises(ValueError, match="near the avatar landmark"):
        select_attachment_particle_near_anchor((0,), positions, anchor, max_distance_mm=1.0)
    with pytest.raises(ValueError, match="ambiguously"):
        select_attachment_particle_near_anchor((0, 2), positions, (10.0, 0.0, 0.0))


def test_avatar_attachment_mode_uses_selected_indices_and_includes_offset_in_signature():
    from types import SimpleNamespace
    from freecad_cloth.simulation.SimulationObjects import resolve_pin_indices, _simulation_source_signature

    assert resolve_pin_indices(
        SimpleNamespace(PinMode="Avatar Attachment", PinSelection=["1", "4"]),
        8,
        (0, 7),
    ) == ()  # Avatar anchors are semantic descriptors, never solver indices
    source = SimpleNamespace(
        Name="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
        ),
    )
    target = SimpleNamespace(SourceObject=source, CollisionDeflection=1.0, CollisionThickness=0.0)
    base = dict(
        DrapeTarget=target, StitchSamples=8, Document=SimpleNamespace(Objects=[]),
        PinMode="Avatar Attachment", PinSelection=[],
        AvatarAttachmentAnchors=["front|edge-right|shoulder_right"],
    )
    near = SimpleNamespace(**base, AttachmentOffset=2.0)
    far = SimpleNamespace(**base, AttachmentOffset=5.0)
    assert _simulation_source_signature(near, []) != _simulation_source_signature(far, [])



def test_semantic_avatar_anchor_descriptors_ignore_boundary_array_order():
    from freecad_cloth.simulation.ClothAttachments import resolve_avatar_attachment_indices

    positions = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (20.0, 0.0, 0.0),
        (30.0, 0.0, 0.0),
        (40.0, 0.0, 0.0),
    )
    panel_data = {
        "front": {
            "boundary_edge_ids": ("neckline", "shoulder-right", "side"),
            "boundary_edges": ((0, 1), (2, 3), (4, 5)),
        }
    }
    landmarks = {"shoulder_right": (10.5, 1.0, 0.0)}
    assert resolve_avatar_attachment_indices(
        ("front|shoulder-right|shoulder_right",), panel_data, positions, landmarks
    ) == (2,)


def test_semantic_avatar_anchor_descriptors_fail_closed_on_bad_references():
    import pytest
    from freecad_cloth.simulation.ClothAttachments import resolve_avatar_attachment_indices

    positions = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    panel_data = {
        "front": {
            "boundary_edge_ids": ("edge-a", "edge-b"),
            "boundary_edges": ((0, 1), (1, 2)),
        }
    }
    landmarks = {"shoulder_right": (10.0, 1.0, 0.0), "shoulder_left": (10.0, 1.0, 0.0)}
    with pytest.raises(ValueError, match="PieceId|SemanticEdgeId|landmark"):
        resolve_avatar_attachment_indices(("malformed",), panel_data, positions, landmarks)
    with pytest.raises(ValueError, match="unknown pattern piece"):
        resolve_avatar_attachment_indices(("back|edge-a|shoulder_right",), panel_data, positions, landmarks)
    with pytest.raises(ValueError, match="missing or ambiguous"):
        resolve_avatar_attachment_indices(("front|edge-missing|shoulder_right",), panel_data, positions, landmarks)
    with pytest.raises(ValueError, match="unknown landmark"):
        resolve_avatar_attachment_indices(("front|edge-a|elbow",), panel_data, positions, landmarks)
    with pytest.raises(ValueError, match="same cloth particle"):
        resolve_avatar_attachment_indices(
            ("front|edge-a|shoulder_right", "front|edge-b|shoulder_left"),
            panel_data,
            positions,
            landmarks,
        )



def test_avatar_attachment_landmark_reader_uses_shared_record_contract(monkeypatch):
    import sys
    from types import SimpleNamespace

    from freecad_cloth.simulation.SimulationObjects import avatar_arrangement_landmarks

    class Vector:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = float(x), float(y), float(z)

    freecad = SimpleNamespace(Vector=Vector)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)

    class Placement:
        def multVec(self, point):
            return Vector(point.x + 100.0, point.y - 20.0, point.z + 5.0)

    source = SimpleNamespace(
        Placement=Placement(),
        ArrangementPoints=[
            "shoulder_right|220,0,1347|front|0|shoulder",
            "shoulder_left|-220,0,1347|front|0|shoulder",
        ],
    )
    scene = SimpleNamespace(DrapeTarget=SimpleNamespace(SourceObject=source))
    assert avatar_arrangement_landmarks(scene) == {
        "shoulder_right": (320.0, -20.0, 1352.0),
        "shoulder_left": (-120.0, -20.0, 1352.0),
    }



def test_avatar_attachments_project_the_named_landmark_not_the_original_particle(monkeypatch):
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments

    _install_native_mesh_projection(monkeypatch)
    positions = ((-5.0, 0.0, 15.0), (8.0, 5.0, 15.0))
    target = (5.0, 0.0, 8.0)
    projected, records = project_avatar_attachments(
        positions,
        (0, 1),
        _attachment_test_surface(),
        offset_mm=3.0,
        target_points={0: target, 1: target},
        projection_directions={0: (0.0, 0.0, 1.0), 1: (0.0, 0.0, 1.0)},
    )
    assert projected[0] == projected[1]
    assert records[0].source_position == target
    assert records[0].particle_position == positions[0]
    assert records[1].particle_position == positions[1]
    assert records[0].surface_point == records[1].surface_point
    assert abs(records[0].anchor_position[2] - 13.0) < 1e-9
    assert abs(records[0].source_distance_mm - 2.0) < 1e-9
    assert records[0].outward_normal == (0.0, 0.0, 1.0)


def test_semantic_avatar_anchor_resolver_returns_authoritative_landmark_targets():
    from freecad_cloth.simulation.ClothAttachments import resolve_avatar_attachment_targets

    positions = (
        (0.0, -1.0, 0.0),
        (10.0, -1.0, 0.0),
        (20.0, -1.0, 0.0),
        (0.0, 1.0, 0.0),
        (10.0, 1.0, 0.0),
        (20.0, 1.0, 0.0),
    )
    data = {
        "front": {
            "boundary_edge_ids": ("left", "right"),
            "boundary_edges": ((0, 1), (1, 2)),
        },
        "back": {
            "boundary_edge_ids": ("left", "right"),
            "boundary_edges": ((3, 4), (4, 5)),
        },
    }
    resolved = resolve_avatar_attachment_targets(
        (
            "front|right|shoulder_right",
            "back|right|shoulder_right",
            "front|left|shoulder_left",
            "back|left|shoulder_left",
        ),
        data,
        positions,
        {
            "shoulder_right": (10.0, 0.0, 0.0),
            "shoulder_left": (0.0, 0.0, 0.0),
        },
    )
    assert tuple(item.particle_index for item in resolved) == (1, 4, 0, 3)
    assert tuple(item.target_position for item in resolved) == (
        (10.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    )
    assert tuple(item.projection_direction for item in resolved) == (
        (1.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
    )



def test_avatar_landmark_changes_invalidate_attachment_simulation_signature():
    from types import SimpleNamespace
    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

    def make_scene(arrangement_points):
        source = SimpleNamespace(
            Name="Body",
            Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
            Placement=SimpleNamespace(
                Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
            ),
            ArrangementPoints=arrangement_points,
        )
        target = SimpleNamespace(
            Name="DrapeTarget",
            SourceObject=source,
            CollisionDeflection=1.0,
            CollisionThickness=0.0,
        )
        return SimpleNamespace(
            DrapeTarget=target,
            StitchSamples=8,
            Document=SimpleNamespace(Objects=[]),
            PinMode="Avatar Attachment",
            AvatarAttachmentAnchors=["front|edge-right|shoulder_right"],
            PinSelection=[],
            AttachmentOffset=3.0,
        )

    before = make_scene(["shoulder_right|10,0,10|front|0|shoulder"])
    after = make_scene(["shoulder_right|11,0,10|front|0|shoulder"])
    assert _simulation_source_signature(before, []) != _simulation_source_signature(after, [])



def test_avatar_projection_rejects_landmarks_too_far_from_the_collision_surface(monkeypatch):
    import pytest
    from freecad_cloth.simulation.ClothAttachments import project_avatar_attachments

    _install_native_mesh_projection(monkeypatch)
    positions = ((0.0, 0.0, 500.0),)
    with pytest.raises(ValueError, match="too far from the DrapeTarget surface"):
        project_avatar_attachments(
            positions,
            (0,),
            _attachment_test_surface(),
            offset_mm=3.0,
            target_points={0: (0.0, 0.0, 200.0)},
            projection_directions={0: (0.0, 0.0, -1.0)},
        )


def test_attachment_cache_signature_changes_with_anchor_descriptor():
    from types import SimpleNamespace
    from freecad_cloth.simulation.SimulationObjects import _simulation_source_signature

    source = SimpleNamespace(
        Name="Body",
        Shape=SimpleNamespace(isNull=lambda: False, hashCode=lambda: 123),
        Placement=SimpleNamespace(
            Base=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            Rotation=SimpleNamespace(Angle=0.0, Axis=SimpleNamespace(x=0.0, y=0.0, z=1.0)),
        ),
        ArrangementPoints=["shoulder_right|10,0,10|front|0|shoulder"],
    )
    target = SimpleNamespace(Name="DrapeTarget", SourceObject=source, CollisionDeflection=1.0, CollisionThickness=0.0)
    common = dict(
        DrapeTarget=target, StitchSamples=8, Document=SimpleNamespace(Objects=[]),
        PinMode="Avatar Attachment", PinSelection=[], AttachmentOffset=3.0,
    )
    first = SimpleNamespace(**common, AvatarAttachmentAnchors=["front|edge-right|shoulder_right"])
    second = SimpleNamespace(**common, AvatarAttachmentAnchors=["front|edge-left|shoulder_left"])
    assert _simulation_source_signature(first, []) != _simulation_source_signature(second, [])
