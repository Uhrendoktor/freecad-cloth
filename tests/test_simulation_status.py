from SimulationStatus import INPUT_PROPERTIES, STATUS_NAMES, invalidation_message, status_after_execute, status_message


def test_status_vocabulary_and_terminal_lifecycle():
    assert STATUS_NAMES == ("Ready", "Running", "Complete", "Invalid")
    assert status_after_execute(steps=0, finite=True) == "Ready"
    assert status_after_execute(steps=30, finite=True) == "Complete"
    assert status_after_execute(steps=30, finite=False) == "Invalid"


def test_simulation_inputs_invalidate_cached_result():
    assert {"QualityPreset", "ParticleDistance", "SolverIterations", "FabricThickness", "Steps"} <= INPUT_PROPERTIES
    assert invalidation_message("ParticleDistance") == (
        "Simulation invalidated by ParticleDistance; recompute to update the result."
    )


def test_status_message_is_stable_for_task_panel():
    assert status_message("Complete", steps=30, simulated_time=0.5, particles=120) == (
        "Complete | 0.500 s | 120 particles | 30 steps"
    )
