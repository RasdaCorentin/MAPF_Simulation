"""
PIBTRenderer — specialised pygame renderer for the PIBT coordinator.

Extends Renderer by adding:
  - goal cells for each agent (coloured square border)
  - current priority displayed on each agent
  - PIBT legend in the header

Usage:
    from client import PIBTRenderer
    PIBTRenderer(sim, pibt).run(steps=30, pause=0.5)
"""

import pygame
from core import Simulation, Agent
from client.renderer import Renderer, AGENT_COLORS, OBJ_COLORS, BG_A, BG_B, GRID_C, BLACK, WHITE, DARK, CELL, MARGIN


class PIBTRenderer(Renderer):
    _caption = "PIBT Simulation"
    _header_sample = "Step 9999  |  PIBT  |  □ goal   ■ obstacle  |  close to quit"

    def __init__(self, simulation: Simulation, pibt) -> None:
        super().__init__(simulation)
        self.pibt = pibt

    def _draw(self, screen, font, font_sm, font_hdr, w, h) -> None:
        screen.fill(WHITE)

        # Checkerboard background + grid lines
        for x in range(self.sim.grid.width):
            for y in range(self.sim.grid.height):
                bg = BG_A if (x + y) % 2 == 0 else BG_B
                pygame.draw.rect(screen, bg, (x * CELL, MARGIN + y * CELL, CELL, CELL))
        grid_w = self.sim.grid.width * CELL
        for x in range(self.sim.grid.width + 1):
            pygame.draw.line(screen, GRID_C, (x * CELL, MARGIN), (x * CELL, h))
        for y in range(self.sim.grid.height + 1):
            pygame.draw.line(screen, GRID_C, (0, MARGIN + y * CELL), (grid_w, MARGIN + y * CELL))

        # Goal cells (coloured square border)
        for agent in self.sim.agents:
            goal = self.pibt.goals.get(agent)
            if goal is None:
                continue
            gx = goal.x * CELL
            gy = MARGIN + goal.y * CELL
            color = AGENT_COLORS[agent.agent_id % len(AGENT_COLORS)]
            pygame.draw.rect(screen, color, (gx + 4, gy + 4, CELL - 8, CELL - 8), 2)

        # Static entities (obstacles)
        for obj in self.sim.grid.get_all():
            if isinstance(obj, Agent) or not obj.active:
                continue
            ox = obj.position.x * CELL + CELL // 2
            oy = MARGIN + obj.position.y * CELL + CELL // 2
            color = OBJ_COLORS["obstacle"]
            r = CELL // 2 - 10
            pygame.draw.rect(screen, color, (ox - r, oy - r, r * 2, r * 2))
            pygame.draw.rect(screen, DARK, (ox - r, oy - r, r * 2, r * 2), 2)
            lbl = font_sm.render("X", True, DARK)
            screen.blit(lbl, lbl.get_rect(center=(ox, oy)))

        # Agents with priority label
        for agent in self.sim.agents:
            cx = agent.position.x * CELL + CELL // 2
            cy = MARGIN + agent.position.y * CELL + CELL // 2
            color = AGENT_COLORS[agent.agent_id % len(AGENT_COLORS)]
            pygame.draw.circle(screen, color, (cx, cy), CELL // 2 - 16)
            if agent.agent_id == 0:
                pygame.draw.circle(screen, BLACK, (cx, cy), CELL // 2 - 16, 2)
            lbl = font.render(str(agent.agent_id), True, WHITE)
            screen.blit(lbl, lbl.get_rect(center=(cx, cy)))
            prio = self.pibt.priorities.get(agent, 0)
            prio_str = "−∞" if prio == float("-inf") else f"{prio:.0f}"
            p_lbl = font_sm.render(prio_str, True, DARK)
            screen.blit(p_lbl, (agent.position.x * CELL + 2, MARGIN + agent.position.y * CELL + 2))

        # Header
        step_label = "Initial" if self.sim.current_step == 0 else f"Step {self.sim.current_step}"
        hdr = font_hdr.render(
            f"{step_label}  |  PIBT  |  □ goal   ■ obstacle  |  close to quit",
            True, DARK,
        )
        screen.blit(hdr, (8, 8))
        pygame.display.flip()
