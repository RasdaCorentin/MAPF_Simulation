"""PygameFrontend — the interactive window.

Controls:
    left click on an agent   toggle its selection
    left drag                rubber-band selection
    left click on a cell     send the selected batch there
    Space                    play / pause
    Right arrow              one step (while paused)
    Left arrow               replay backwards through history
    A / C                    select all / clear selection
    Q / Esc                  quit
"""

import pygame

from core import Position
from client.view import StepSnapshot

from .frontend import Frontend
from . import sidebar as sidebar_mod
from .sidebar import Sidebar

# Window budget for the grid area; CELL is derived from it so a 15x15
# board fits as comfortably as a 5x5 one. Hard-coding CELL is what made
# the old renderers unusable past a handful of cells.
MAX_GRID_PX = 720
MIN_CELL    = 14
MAX_CELL    = 60
HEADER      = 34

# A tick costing more than tick_duration must never let the accumulator
# outrun the frame: without this clamp the backlog grows without bound
# and the window freezes (the classic spiral of death). Clamping degrades
# to slow motion instead, which stays interactive.
MAX_STEPS_PER_FRAME = 4

BG_A     = (240, 244, 255)
BG_B     = (255, 255, 255)
GRID_C   = (214, 217, 228)
WHITE    = (255, 255, 255)
DARK     = (30, 30, 30)
HDR_BG   = (230, 234, 250)
SELECT   = (250, 190, 40)
BAND     = (90, 140, 220)
OBSTACLE = (180, 30, 30)

AGENT_COLORS = [
    (31, 119, 180), (255, 127, 14), (44, 160, 44),  (214, 39, 40),
    (148, 103, 189), (140, 86, 75), (227, 119, 194), (127, 127, 127),
    (188, 189, 34),  (23, 190, 207),
]


class PygameFrontend(Frontend):
    """Interactive pygame frontend with batch dispatch and replay."""

    def __init__(self, controller, tick_ms: int = 350) -> None:
        """Input: the controller to drive, and the wall-clock duration of
        one simulation step in milliseconds.
        Output: None.
        """
        super().__init__(controller)
        self.tick_ms = tick_ms
        self.cell = self._cell_size()
        self.selection: set[int] = set()
        self.history: list[StepSnapshot] = []
        self.cursor = 0                      # index into history being shown
        self.playing = False
        self._drag_from: tuple[int, int] | None = None
        self._drag_to: tuple[int, int] | None = None

    # ── Geometry ─────────────────────────────────────────────────────────────

    def _cell_size(self) -> int:
        """Input: none.
        Output: the pixel size of a cell, fitted to the grid so the board
        stays inside the window budget.
        """
        grid = self.controller.sim.grid
        fitted = MAX_GRID_PX // max(grid.width, grid.height)
        return max(MIN_CELL, min(MAX_CELL, fitted))

    def _cell_at(self, px: int, py: int) -> Position | None:
        """Input: a pixel position.
        Output: the grid cell under it, or None if outside the board.
        """
        grid = self.controller.sim.grid
        x, y = px // self.cell, (py - HEADER) // self.cell
        if py < HEADER or not (0 <= x < grid.width and 0 <= y < grid.height):
            return None
        return Position(x, y)

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self, steps: int = 0) -> None:
        """Input: an optional step budget (0 = run until quit).
        Output: None. Opens the interactive window and blocks.
        """
        grid = self.controller.sim.grid
        grid_w, grid_h = grid.width * self.cell, grid.height * self.cell
        width  = grid_w + sidebar_mod.WIDTH
        height = max(grid_h + HEADER, 380)

        pygame.init()
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("MAPF — fleet control")
        fonts = {
            "lg":  pygame.font.SysFont("monospace", max(10, self.cell // 3), bold=True),
            "sm":  pygame.font.SysFont("monospace", 12),
            "hdr": pygame.font.SysFont("monospace", 12, bold=True),
        }
        panel = Sidebar(height)
        clock = pygame.time.Clock()

        self.history = [self.controller.snapshot()]
        self.cursor = 0
        accumulator = 0.0

        while True:
            dt = clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                if self._handle(event, grid_w, panel) is False:
                    pygame.quit()
                    return

            # Fixed-step accumulator: the frontend owns the clock, step()
            # stays a pure "advance by one". Only advance while the user
            # is looking at the present — replaying the past must not
            # silently mutate the future.
            if self.playing and self._at_present():
                accumulator += dt
                taken = 0
                while accumulator >= self.tick_ms and taken < MAX_STEPS_PER_FRAME:
                    if steps and self.controller.sim.current_step >= steps:
                        self.playing = False
                        break
                    self._advance()
                    accumulator -= self.tick_ms
                    taken += 1
                if taken == MAX_STEPS_PER_FRAME:
                    accumulator = 0.0   # drop the backlog rather than chase it
            else:
                accumulator = 0.0

            self._draw(screen, panel, grid_w, fonts)
            pygame.display.flip()

    # ── Interaction ──────────────────────────────────────────────────────────

    def _handle(self, event, grid_w: int, panel: Sidebar):
        """Input: a pygame event, the board width and the sidebar.
        Output: False to quit, None otherwise.
        """
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_q, pygame.K_ESCAPE):
                return False
            if event.key == pygame.K_SPACE:
                self._toggle_play()
            elif event.key == pygame.K_RIGHT:
                self._forward()
            elif event.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif event.key == pygame.K_a:
                self.selection = {a.agent_id for a in self.controller.sim.agents}
            elif event.key == pygame.K_c:
                self.selection.clear()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if event.pos[0] >= grid_w:
                self._button(panel.hit(event.pos, grid_w))
            else:
                self._drag_from = self._drag_to = event.pos

        elif event.type == pygame.MOUSEMOTION and self._drag_from:
            self._drag_to = event.pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._drag_from:
            self._release(self._drag_from, event.pos)
            self._drag_from = self._drag_to = None
        return None

    def _release(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """Input: the drag's start and end pixel positions.
        Output: None. A drag selects agents in the band; a plain click
        toggles an agent, or — on an empty cell — dispatches the batch.
        """
        if max(abs(start[0] - end[0]), abs(start[1] - end[1])) > 4:
            self.selection = self._agents_in_band(start, end)
            return

        cell = self._cell_at(*end)
        if cell is None:
            return

        agent = self.controller.sim.grid.get_agent_at(cell)
        if agent is not None:
            self.selection ^= {agent.agent_id}
        elif self.selection and self.controller.queue is not None:
            self.controller.send_batch_to(cell, agent_ids=self.selection)

    def _agents_in_band(self, start, end) -> set[int]:
        """Input: two pixel corners.
        Output: the ids of the agents whose cell falls inside the band.
        """
        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))
        found = set()
        for agent in self.controller.sim.agents:
            cx = agent.position.x * self.cell + self.cell // 2
            cy = HEADER + agent.position.y * self.cell + self.cell // 2
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                found.add(agent.agent_id)
        return found

    def _button(self, key: str | None) -> None:
        """Input: a sidebar button key (or None).
        Output: None. Applies the button's action.
        """
        if key == "select_all":
            self.selection = {a.agent_id for a in self.controller.sim.agents}
        elif key == "clear":
            self.selection.clear()
        elif key == "play":
            self._toggle_play()
        elif key == "step":
            self._forward()

    def _toggle_play(self) -> None:
        """Input: none. Output: None. Playing always resumes from the
        present, so leaving replay mode cannot fork the timeline."""
        self.cursor = len(self.history) - 1
        self.playing = not self.playing

    def _forward(self) -> None:
        """Input: none.
        Output: None. Moves one step forward — through history while
        replaying, otherwise by advancing the engine.
        """
        if self._at_present():
            self._advance()
        else:
            self.cursor += 1

    def _advance(self) -> None:
        """Input: none. Output: None. Runs one simulation step."""
        self.history.append(self.controller.step())
        self.cursor = len(self.history) - 1

    def _at_present(self) -> bool:
        """Input: none. Output: True if the cursor shows the latest step.

        Backward navigation is *replay only*: Grid and PriorityManager
        are destructive, so the engine has no undo and the past cannot be
        resumed from. Frozen snapshots make looking back safe; they do
        not make rewinding possible.
        """
        return self.cursor >= len(self.history) - 1

    # ── Drawing ──────────────────────────────────────────────────────────────

    def _draw(self, screen, panel: Sidebar, grid_w: int, fonts) -> None:
        """Input: the surface, sidebar, board width and fonts.
        Output: None. Renders one frame from the snapshot at the cursor.
        """
        snap = self.history[self.cursor]
        screen.fill(WHITE)
        self._draw_header(screen, snap, grid_w, fonts)
        self._draw_board(screen, snap, fonts)
        panel.draw(screen, grid_w, snap, self.selection,
                   self.playing, not self._at_present(), fonts)

        if self._drag_from and self._drag_to:
            x0, x1 = sorted((self._drag_from[0], self._drag_to[0]))
            y0, y1 = sorted((self._drag_from[1], self._drag_to[1]))
            pygame.draw.rect(screen, BAND, (x0, y0, x1 - x0, y1 - y0), 1)

    def _draw_header(self, screen, snap: StepSnapshot, grid_w: int, fonts) -> None:
        """Input: surface, snapshot, board width, fonts.
        Output: None. Draws the top bar."""
        pygame.draw.rect(screen, HDR_BG, (0, 0, grid_w, HEADER))
        hint = "select agents, then click a cell to send them"
        if not self._at_present():
            hint = f"replaying step {snap.step} — Space returns to live"
        label = fonts["sm"].render(hint, True, DARK)
        screen.blit(label, (10, (HEADER - label.get_height()) // 2))

    def _draw_board(self, screen, snap: StepSnapshot, fonts) -> None:
        """Input: surface, snapshot, fonts.
        Output: None. Draws cells, tasks, obstacles and agents.

        One routine for the whole board — the three legacy renderers each
        carried their own near-identical copy of this.
        """
        grid = self.controller.sim.grid
        cell = self.cell

        for x in range(grid.width):
            for y in range(grid.height):
                shade = BG_A if (x + y) % 2 == 0 else BG_B
                pygame.draw.rect(screen, shade,
                                 (x * cell, HEADER + y * cell, cell, cell))
        for x in range(grid.width + 1):
            pygame.draw.line(screen, GRID_C, (x * cell, HEADER),
                             (x * cell, HEADER + grid.height * cell))
        for y in range(grid.height + 1):
            pygame.draw.line(screen, GRID_C, (0, HEADER + y * cell),
                             (grid.width * cell, HEADER + y * cell))

        for task in snap.tasks:
            colour = (
                AGENT_COLORS[task.assignee_id % len(AGENT_COLORS)]
                if task.assignee_id is not None
                else sidebar_mod.STATE_COLORS[task.state.value]
            )
            rect = (task.target.x * cell + 3, HEADER + task.target.y * cell + 3,
                    cell - 6, cell - 6)
            pygame.draw.rect(screen, colour, rect, 2)

        for pos, _kind in snap.objects:
            inset = max(3, cell // 6)
            pygame.draw.rect(screen, OBSTACLE,
                             (pos.x * cell + inset, HEADER + pos.y * cell + inset,
                              cell - 2 * inset, cell - 2 * inset))

        radius = max(4, cell // 2 - 5)
        for aid, pos in snap.result.positions.items():
            cx = pos.x * cell + cell // 2
            cy = HEADER + pos.y * cell + cell // 2
            if aid in self.selection:
                pygame.draw.circle(screen, SELECT, (cx, cy), radius + 3)
            pygame.draw.circle(screen, AGENT_COLORS[aid % len(AGENT_COLORS)], (cx, cy), radius)
            if cell >= 26:
                label = fonts["lg"].render(str(aid), True, WHITE)
                screen.blit(label, label.get_rect(center=(cx, cy)))
