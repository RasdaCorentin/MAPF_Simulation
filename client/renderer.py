import pygame
from core import Simulation, Agent

# Shared rendering constants (importable by PIBTRenderer)
AGENT_COLORS = [
    (31, 119, 180), (255, 127, 14), (44, 160, 44),  (214, 39, 40),
    (148, 103, 189), (140, 86, 75), (227, 119, 194), (127, 127, 127),
    (188, 189, 34),  (23, 190, 207),
]
OBJ_COLORS = {
    "obstacle": (180, 30, 30),
}
BG_A   = (240, 244, 255)
BG_B   = (255, 255, 255)
GRID_C = (200, 200, 200)
BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
DARK   = (30,  30,  30)

CELL   = 60
MARGIN = 36


class Renderer:
    """Generic pygame renderer: grid, agents and static entities.

    Reads the Simulation, never mutates it. Subclasses override
    ``_draw`` to add algorithm-specific overlays.
    """

    _caption = "Grid Simulation"
    # Longest possible header text — used to size the window so that
    # no text is clipped on small grids.
    _header_sample = "Step 9999  |  ■ obstacle  |  close to quit"

    def __init__(self, simulation: Simulation) -> None:
        """Input: the simulation to display (read-only access).
        Output: None.
        """
        self.sim = simulation
        # PlanResult of the last executed step (diagnostics for subclasses)
        self._last_result = None

    def run(self, steps: int, pause: float = 1.0) -> None:
        """Input: number of simulation steps and pause between frames (s).
        Output: None. Opens a blocking pygame window.
        """
        pause_ms = int(pause * 1000)
        pygame.init()
        font     = pygame.font.SysFont("monospace", 15, bold=True)
        font_sm  = pygame.font.SysFont("monospace", 11)
        font_hdr = pygame.font.SysFont("monospace", 13)
        grid_w = self.sim.grid.width * CELL
        w = max(grid_w, font_hdr.size(self._header_sample)[0] + 16)
        h = self.sim.grid.height * CELL + MARGIN
        screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption(self._caption)
        clock    = pygame.time.Clock()

        self._draw(screen, font, font_sm, font_hdr, w, h)
        pygame.time.wait(pause_ms)

        for _ in range(steps):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
            self._last_result = self.sim.step()
            self._draw(screen, font, font_sm, font_hdr, w, h)
            pygame.time.wait(pause_ms)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
            clock.tick(30)

    def _draw(self, screen, font, font_sm, font_hdr, w, h) -> None:
        """Input: pygame surface, fonts and window size.
        Output: None. Draws the current simulation state.
        """
        screen.fill(WHITE)

        for x in range(self.sim.grid.width):
            for y in range(self.sim.grid.height):
                bg = BG_A if (x + y) % 2 == 0 else BG_B
                pygame.draw.rect(screen, bg, (x * CELL, MARGIN + y * CELL, CELL, CELL))

        grid_w = self.sim.grid.width * CELL
        for x in range(self.sim.grid.width + 1):
            pygame.draw.line(screen, GRID_C, (x * CELL, MARGIN), (x * CELL, h))
        for y in range(self.sim.grid.height + 1):
            pygame.draw.line(screen, GRID_C, (0, MARGIN + y * CELL), (grid_w, MARGIN + y * CELL))

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

        for agent in self.sim.agents:
            cx = agent.position.x * CELL + CELL // 2
            cy = MARGIN + agent.position.y * CELL + CELL // 2
            color = AGENT_COLORS[agent.agent_id % len(AGENT_COLORS)]
            pygame.draw.circle(screen, color, (cx, cy), CELL // 2 - 16)
            if agent.agent_id == 0:
                pygame.draw.circle(screen, BLACK, (cx, cy), CELL // 2 - 16, 2)
            lbl = font.render(str(agent.agent_id), True, WHITE)
            screen.blit(lbl, lbl.get_rect(center=(cx, cy)))

        step_label = "Initial" if self.sim.current_step == 0 else f"Step {self.sim.current_step}"
        hdr = font_hdr.render(
            f"{step_label}  |  ■ obstacle  |  close to quit",
            True, DARK,
        )
        screen.blit(hdr, (8, 8))
        pygame.display.flip()
