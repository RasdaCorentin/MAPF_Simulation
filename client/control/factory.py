import random

from core import Agent, Grid, Position, Simulation, StaticDispatcher, WorldEntity, Zone
from algo import (
    PIBTCoordinator, RandomWalkCoordinator, PIBTPlusCoordinator, LaCAMCoordinator,
    EasiestAllocator, RandomAllocator,
)
from mrta import (
    CompositeTaskSource, FleetManager, QueueTaskSource, RandomTaskSource,
)

from .config import ScenarioConfig
from .controller import SimulationController

COORDINATORS = {
    "pibt":   PIBTCoordinator,
    "random": RandomWalkCoordinator,
    "pibt+":  PIBTPlusCoordinator,
    "lacam":  LaCAMCoordinator,
}


def _rect(x0: int, y0: int, w: int, h: int, width: int, height: int) -> list:
    """Input: a rectangle (top-left corner, then size) and the grid's size.
    Output: the cells it covers, clipped to the grid.

    Clipped rather than rejected: the layout below is written in
    fractions of the grid, so a very small board would otherwise turn a
    rounding artefact into a crash at start-up.
    """
    return [
        Position(x, y)
        for x in range(max(0, x0), min(width, x0 + w))
        for y in range(max(0, y0), min(height, y0 + h))
    ]


def default_zones(width: int, height: int) -> tuple:
    """Input: the grid dimensions.
    Output: the three operational zones, as rectangular blocks.

    The vocabulary is the warehouse's, not the map's: a *rack* is the
    crate a robot carries, so the regions are named after what sits in
    them — the loading station, the working space, and the area where
    empty racks are parked.

    A zone marks a *place of work*, not a third of the map: the blocks
    below leave most of the floor as plain aisle, so "send them to the
    loading station" names a dock and not a whole column. They are still
    derived from the grid rather than hard-coded, so ``--width 40``
    scales them instead of leaving three slivers against one wall.

    **The table below is the knob.** Each entry is ``(x, y, w, h)`` in
    cells, top-left corner first; nothing outside this function knows
    the geometry, so moving or resizing a zone here is enough — the
    sidebar button, the tint on the board and "send the batch there"
    all follow the cells.
    """
    dock_w, dock_h = max(2, width // 4), max(1, height // 6)
    work_w, work_h = max(1, width // 2), max(1, height // 2)
    park_w, park_h = max(2, width // 4), max(1, height // 5)

    blocks = {
        # A narrow dock centred against the top wall.
        "loading station": ((width - dock_w) // 2, 0, dock_w, dock_h),
        # The shop floor: centred, clear of both the dock and the park.
        "working space":   ((width - work_w) // 2, (height - work_h) // 2,
                            work_w, work_h),
        # Empty racks parked out of the way, in the bottom-left corner.
        "empty-rack area": (0, height - park_h, park_w, park_h),
    }
    zones = []
    for i, (name, (x0, y0, w, h)) in enumerate(blocks.items()):
        cells = _rect(x0, y0, w, h, width, height)
        if cells:
            zones.append(Zone(i, name, cells))
    return tuple(zones)


def build(config: ScenarioConfig) -> SimulationController:
    """Input: a scenario description.
    Output: a ready-to-drive SimulationController.

    This is the composition root: the one place allowed to know both
    ``algo`` and ``mrta`` concretely. Everything downstream — the
    frontends — sees only the controller and its snapshots, which is
    what lets a new algorithm or allocator be swapped in here without
    touching a line of presentation code.
    """
    rng = random.Random(config.seed)
    grid = Grid(config.width, config.height)

    cells = [Position(x, y) for x in range(config.width) for y in range(config.height)]
    drawn = rng.sample(cells, config.agents + config.obstacles)
    agent_cells, obstacle_cells = drawn[:config.agents], drawn[config.agents:]

    coordinator = COORDINATORS[config.algo]()

    fleet = queue = None
    if config.mode == "mrta":
        # The interactive queue is always present so send_batch_to() works;
        # a background generator is composed alongside it when asked for.
        queue = QueueTaskSource()
        source = queue
        if config.tasks == "random":
            source = CompositeTaskSource(
                queue,
                RandomTaskSource(grid, every=config.task_every,
                                 count=config.task_count, seed=config.seed),
            )
        # The baseline allocator is seeded from the scenario, so "same
        # --seed, same run" holds for it too and not only for the layout.
        allocator = (
            EasiestAllocator() if config.allocator == "easiest"
            else RandomAllocator(seed=config.seed)
        )
        fleet = FleetManager(
            source=source,
            allocator=allocator,
            patience=config.patience,
            max_attempts=config.max_attempts,
        )
        dispatcher = fleet
    else:
        # Static mode: fixed goals drawn once, no allocation at all.
        goal_cells = rng.sample(cells, config.agents)
        dispatcher = StaticDispatcher(
            goals={i: goal_cells[i] for i in range(config.agents)}
        )

    sim = Simulation(grid, coordinator=coordinator, dispatcher=dispatcher)
    for i, cell in enumerate(agent_cells):
        sim.add_agent(Agent(i, cell))
    for n, cell in enumerate(obstacle_cells):
        sim.add_object(WorldEntity(n, cell, blocks_movement=True))
    # Zones label ground and block nothing, so they can be laid over the
    # agents and obstacles already drawn without contending for cells.
    for zone in config.zones:
        sim.add_object(zone)

    return SimulationController(sim, fleet=fleet, queue=queue)
