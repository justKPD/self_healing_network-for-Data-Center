"""
Configuration -- real THD Deggendorf specifications from planning PDF.
"""

from dataclasses import dataclass


@dataclass
class Config:
    # Room geometry (from PDF: Lehrrechenzentrum_Planentwurf+Mengen_20251002)
    num_rooms: int = 3
    room_areas: dict = None
    room_heights: dict = None

    # Per-room hardware
    racks_per_room: int = 4
    servers_per_rack: int = 8
    leaves_per_room: int = 2
    spines_per_room: int = 1

    # Power (W)
    server_power: dict = None          # per-room
    leaf_power: float = 150.0
    spine_power: float = 200.0

    # Cable lengths to Main Distribution (metres, from PDF)
    cable_lengths: dict = None

    # Failure rates (daily)
    cable_failure_rate: float = 0.001
    switch_failure_rate: float = 0.003
    server_failure_rate: float = 0.0005

    # Costs
    power_cost_kwh: float = 0.30       # EUR (German commercial 2024)
    cable_cost_per_m: float = 15.0     # EUR (Sachsenkabel)
    cable_replacement: float = 740.0   # EUR per failed cable

    # Repair
    repair_time_days: int = 7

    # Simulation
    simulation_days: int = 365

    def __post_init__(self):
        if self.room_areas is None:
            self.room_areas = {1: 57.15, 2: 67.94, 3: 111.97}
        if self.room_heights is None:
            self.room_heights = {1: 4.98, 2: 7.53, 3: 9.38}
        if self.server_power is None:
            self.server_power = {1: 250, 2: 400, 3: 400}
        if self.cable_lengths is None:
            self.cable_lengths = {1: 44, 2: 32, 3: 34}
