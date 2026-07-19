"""Sidebar: selection readout, task tallies and transport controls.

Pure presentation — it is handed a snapshot and a selection and draws
them. Deciding what a click *means* stays in PygameFrontend, which owns
the interaction state; the sidebar only reports where its buttons are.
"""

import pygame

from client.view import StepSnapshot

WIDTH = 190

BG        = (245, 246, 250)
SEP       = (205, 208, 220)
TEXT      = (30, 30, 30)
MUTED     = (110, 112, 130)
BTN       = (225, 228, 240)
BTN_HOVER = (208, 213, 232)

STATE_COLORS = {
    "pending":  (150, 150, 160),
    "assigned": (40, 130, 200),
    "done":     (60, 160, 90),
    "failed":   (200, 60, 60),
}


class Sidebar:
    """Draws the right-hand panel and exposes its button rectangles."""

    def __init__(self, height: int) -> None:
        """Input: the window height.
        Output: None. Button rects are laid out once, bottom-anchored.
        """
        self.height = height
        self.buttons: dict[str, pygame.Rect] = {}
        y = height - 4 * 34 - 12
        for key in ("select_all", "clear", "play", "step"):
            self.buttons[key] = pygame.Rect(12, y, WIDTH - 24, 28)
            y += 34

    def draw(
        self,
        screen,
        origin_x: int,
        snap: StepSnapshot,
        selection: set[int],
        playing: bool,
        replaying: bool,
        fonts: dict,
    ) -> None:
        """Input: the surface, the sidebar's left edge, the snapshot to
        report, the current selection, transport state, and the fonts.
        Output: None.
        """
        panel = pygame.Rect(origin_x, 0, WIDTH, self.height)
        pygame.draw.rect(screen, BG, panel)
        pygame.draw.line(screen, SEP, (origin_x, 0), (origin_x, self.height))

        y = 14
        y = self._section(screen, origin_x, y, "SELECTION", fonts)
        if selection:
            ids = ", ".join(str(i) for i in sorted(selection))
            for line in self._wrap(ids, 22):
                screen.blit(fonts["sm"].render(line, True, TEXT), (origin_x + 12, y))
                y += 15
        else:
            screen.blit(fonts["sm"].render("click or drag agents", True, MUTED),
                        (origin_x + 12, y))
            y += 15
        y += 10

        y = self._section(screen, origin_x, y, "TASKS", fonts)
        for name, value in snap.counts().items():
            pygame.draw.circle(screen, STATE_COLORS[name], (origin_x + 18, y + 6), 5)
            screen.blit(fonts["sm"].render(f"{name:<9}{value}", True, TEXT),
                        (origin_x + 30, y))
            y += 17
        y += 12

        y = self._section(screen, origin_x, y, "STEP", fonts)
        state = "replay" if replaying else ("playing" if playing else "paused")
        screen.blit(fonts["sm"].render(f"{snap.step}  ({state})", True, TEXT),
                    (origin_x + 12, y))

        labels = {
            "select_all": "Select all  [A]",
            "clear":      "Clear       [C]",
            "play":       ("Pause    [Space]" if playing else "Play     [Space]"),
            "step":       "Step          [>]",
        }
        mouse = pygame.mouse.get_pos()
        for key, rect in self.buttons.items():
            shifted = rect.move(origin_x, 0)
            hovered = shifted.collidepoint(mouse)
            pygame.draw.rect(screen, BTN_HOVER if hovered else BTN, shifted, border_radius=4)
            label = fonts["sm"].render(labels[key], True, TEXT)
            screen.blit(label, label.get_rect(center=shifted.center))

    def hit(self, position: tuple[int, int], origin_x: int) -> str | None:
        """Input: a mouse position and the sidebar's left edge.
        Output: the key of the button under it, or None.
        """
        for key, rect in self.buttons.items():
            if rect.move(origin_x, 0).collidepoint(position):
                return key
        return None

    def _section(self, screen, origin_x: int, y: int, title: str, fonts) -> int:
        """Input: surface, left edge, current y, section title, fonts.
        Output: the y below the drawn heading.
        """
        screen.blit(fonts["hdr"].render(title, True, MUTED), (origin_x + 12, y))
        return y + 20

    @staticmethod
    def _wrap(text: str, width: int) -> list[str]:
        """Input: a string and a character width.
        Output: the string split into lines of at most that width.
        """
        return [text[i:i + width] for i in range(0, len(text), width)] or [""]
