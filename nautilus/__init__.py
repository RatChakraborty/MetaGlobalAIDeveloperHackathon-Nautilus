
"""
Nautilius: robotic failure forensics.

Day 1 implementation:
    Simplified marine vehicle simulator with
    fault injection and controlled experiments.
"""

from .simulator import (
    Vehicle,
    Faults,
    Controller,
    Mission,
    PlantConfig,
    HIDDEN_PLANT,
    Experiment,
    SimulationResult,
    OBSERVATION_FIELDS,
    wrap_angle,
    dynamics,
    command,
    actuator_step,
    validate,
    simulate,
    metrics,
    save_run,
)

__all__ = [
    "Vehicle",
    "Faults",
    "Controller",
    "Mission",
    "PlantConfig",
    "HIDDEN_PLANT",
    "Experiment",
    "SimulationResult",
    "OBSERVATION_FIELDS",
    "wrap_angle",
    "dynamics",
    "command",
    "actuator_step",
    "validate",
    "simulate",
    "metrics",
    "save_run",
]
