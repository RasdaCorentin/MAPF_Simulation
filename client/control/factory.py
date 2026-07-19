import random

from core import Agent, Grid, Position, Simulation, StaticDispatcher, WorldEntity
from algo import PIBTCoordinator, RandomWalkCoordinator, RandomAllocator
from mrta import (
    CompositeTaskSource, FleetManager, QueueTaskSource, RandomTaskSource,
)

from .config import ScenarioConfig
from .controller import SimulationController

COORDINATORS = {
    "pibt":   PIBTCoordinator,
    "random": RandomWalkCoordinator,
}


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
        fleet = FleetManager(
            source=source,
            allocator=RandomAllocator(),
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

    return SimulationController(sim, fleet=fleet, queue=queue)
