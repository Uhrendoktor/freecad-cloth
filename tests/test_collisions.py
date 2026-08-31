from XPBD import CapsuleCollider, SphereCollider, XPBDClothSolver


def test_primitive_collision_types_validate_as_data_only():
    sphere = SphereCollider((0.0, 0.0, 0.0), 10.0)
    capsule = CapsuleCollider((0.0, 0.0, -10.0), (0.0, 0.0, 10.0), 5.0)
    sphere.validate()
    capsule.validate()


def test_solver_does_not_fallback_to_python_collision_projection():
    sphere = SphereCollider((0.0, 0.0, 0.0), 10.0)
    try:
        XPBDClothSolver(colliders=[sphere])
    except NotImplementedError:
        pass
    else:
        raise AssertionError("primitive collision must be implemented by the PBD collision scene, not Python projection")


if __name__ == "__main__":
    test_primitive_collision_types_validate_as_data_only()
    test_solver_does_not_fallback_to_python_collision_projection()
    print("collision boundary tests passed")
