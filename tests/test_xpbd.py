import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_cloth.pattern.PatternGeometry import rectangle
from freecad_cloth.pattern.PatternMesh import triangulate
from freecad_cloth.simulation.XPBD import CapsuleCollider, DistanceConstraint, XPBDClothSolver, ShearConstraint, BendingConstraint, structural_constraints, shear_constraints, bending_constraints
from freecad_cloth.simulation.SimulationBackend import ClothState

def test_structural_constraints_are_unique():
    mesh=triangulate(rectangle(100.,50.));constraints=structural_constraints(mesh);assert len(constraints)==5;assert len({(c.a,c.b) for c in constraints})==5

def test_shear_and_bending_constraints_are_explicit():
    mesh=triangulate(rectangle(100.,50.));shear=shear_constraints(mesh);bending=bending_constraints(mesh)
    assert shear and bending
    assert all(isinstance(c, ShearConstraint) for c in shear)
    assert all(isinstance(c, BendingConstraint) for c in bending)

def test_xpbd_pin_and_gravity():
    state=ClothState([(0.,0.,0.),(100.,0.,0.)]);state.inverse_masses=[0.,1.];state.velocities=[(0.,0.,0.),(0.,0.,0.)];XPBDClothSolver([DistanceConstraint(0,1,100.)],iterations=4,pinned=[0]).step(state,.001);assert state.positions[0]==(0.,0.,0.);assert state.positions[1][2]<0.

def test_capsule_pushes_particle_to_surface():
    state=ClothState([(0.,0.,0.)]);state.inverse_masses=[1.];state.velocities=[(0.,0.,0.)];capsule=CapsuleCollider((0.,0.,-10.),(0.,0.,10.),5.);XPBDClothSolver(gravity=(0.,0.,0.),iterations=2,colliders=[capsule]).step(state,.1);assert state.positions[0]==(5.,0.,0.)

def test_capsule_collision_is_deterministic():
    capsule=CapsuleCollider((-2.,0.,-5.),(-2.,0.,5.),3.,.5);results=[]
    for _ in range(2):
        state=ClothState([(-2.,2.,0.)]);state.inverse_masses=[1.];state.velocities=[(0.,0.,0.)];XPBDClothSolver(gravity=(0.,0.,0.),iterations=4,colliders=[capsule]).step(state,.1);results.append(tuple(state.positions[0]))
    assert results[0]==results[1];assert abs(results[0][1]-3.5)<1e-12

def test_self_collision_separates_overlapping_particles():
    state=ClothState([(0.,0.,0.),(0.5,0.,0.)]);state.inverse_masses=[1.,1.];state.velocities=[(0.,0.,0.),(0.,0.,0.)]
    XPBDClothSolver(gravity=(0.,0.,0.),iterations=2,self_collision_radius=1.0).step(state,.01)
    assert abs(state.positions[1][0]-state.positions[0][0]) >= 2.0 - 1e-12

def test_capsule_validation_rejects_degenerate_segment():
    try:CapsuleCollider((0.,0.,0.),(0.,0.,0.),1.).validate()
    except ValueError:return
    raise AssertionError("degenerate capsule must be rejected")
if __name__=="__main__":
    for name,fn in globals().copy().items():
        if name.startswith("test_"):fn()
    print("xpbd tests passed")
