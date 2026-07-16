from core import Grid, Agent, WorldEntity, Simulation
from core.position import Position
from algo import RandomWalkCoordinator
from client import Renderer

if __name__ == "__main__":
    grid = Grid(10, 10)
    sim = Simulation(grid, coordinator=RandomWalkCoordinator())

    for i in range(5):
        sim.add_agent(Agent(i, Position(i, i)))

    sim.add_object(WorldEntity(0, Position(3, 6), blocks_movement=True))
    sim.add_object(WorldEntity(1, Position(7, 7), blocks_movement=True))

    renderer = Renderer(sim)
    renderer.run(steps=20, pause=0.5)
