"""
demo_pibt.py — Interactive PIBT demo on a 5x5 grid.

Controls:
    Space     pause / play
    ->        step forward
    <-        step back
    Q / Esc   quit

The footer bar shows the priority order, each agent's move, and any
priority inheritances triggered at every step.

────────────────────────────────────────────────────────────────
To build your own demo:

  1. Pick a Coordinator (PIBTCoordinator, RandomWalkCoordinator, or your own).
  2. Build the simulation: Simulation(grid, coordinator=my_algo).
  3. Add agents and entities via sim.add_agent() / sim.add_object().
  4. Configure goals/priorities on the coordinator via set_goal() /
     set_priority() (PIBTCoordinator and any PriorityBasedCoordinator).
  5. Launch with:
       PIBTInteractiveRenderer(sim).run(steps=25)  # with navigation
       PIBTRenderer(sim).run(steps=30, pause=0.3)  # read-only playback
       Renderer(sim).run(steps=30, pause=0.3)      # no PIBT overlay

To add your own algorithm:
  -> see algo/coordination/random_walk.py for a minimal example.
  -> your class must inherit from Coordinator (or PriorityBasedCoordinator)
     and implement plan().
────────────────────────────────────────────────────────────────
"""

import sys
import os

DEBUG = "-d" in sys.argv
if DEBUG:
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from core import Simulation, Agent, Grid, Position
from algo import PIBTCoordinator
if DEBUG:
    # Direct import — avoids loading pygame through client/__init__.py
    from client.pibt_interactive_renderer import PIBTInteractiveRenderer
else:
    from client import PIBTInteractiveRenderer

# ── 1. Grid ────────────────────────────────────────────────────────────────

grid = Grid(width=5, height=5)

# ── 2. Agents ────────────────────────────────────────────────────────────────

start_positions = [
    Position(0, 0), Position(2, 1), Position(4, 3), Position(4, 0),
    Position(1, 0), Position(4, 4), Position(4, 2), Position(3, 4),
    Position(3, 0), Position(3, 3),
]
agents = [Agent(agent_id=i, position=pos) for i, pos in enumerate(start_positions)]

# ── 3. Coordinator: created empty, then configured via set_goal/set_priority ──

pibt = PIBTCoordinator()
sim = Simulation(grid, coordinator=pibt)

for agent in agents:
    sim.add_agent(agent)

# Target cell for each agent — edit these to change where agents go.
goal_positions = [
    Position(4, 4), Position(4, 1), Position(0, 4), Position(0, 0), Position(3, 4),
    Position(4, 3), Position(2, 2), Position(0, 2), Position(1, 1), Position(4, 2),
]
for agent, goal in zip(agents, goal_positions):
    pibt.set_goal(agent, goal)

# Initial priorities — higher value means served first. Optional: if
# omitted, PIBTCoordinator assigns priorities by insertion order.
# Adjustable here or during simulation via pibt.set_priority(agent, x).
initial_priorities = [20.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0]
for agent, priority in zip(agents, initial_priorities):
    pibt.set_priority(agent, priority)

# ── 4. World entities ──────────────────────────────────────────────────────
#    Obstacles: WorldEntity with blocks_movement=True — no subclass needed.
#
# from core import WorldEntity
# sim.add_object(WorldEntity(entity_id=0, position=Position(2, 2), blocks_movement=True))

# ── 5. Run ─────────────────────────────────────────────────────────────────
#    python demo_pibt.py       -> interactive window (<- -> Space Q)
#    python demo_pibt.py -d    -> debug mode: terminal print, zero pygame

renderer = PIBTInteractiveRenderer(sim)
if DEBUG:
    renderer.run_debug(steps=20)
else:
    renderer.run(steps=30, auto_ms=500)
