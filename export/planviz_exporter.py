"""
PlanVizExporter — writes a run in the format PlanViz (League of Robot
Runners) reads: a .map file plus a .json plan file.

Informed by reading the Start-Kit's own export code (src/Simulator.cpp,
src/ActionModel.cpp, inc/common.h), not just the Input_Output_Format.md
doc:

- action vocabulary: F (forward), R (rotate clockwise), C (rotate
  counter-clockwise), W (wait) — not a generic "rotate";
- a path segment header is ``(tick, row, col, heading, counter)`` —
  row/col, not core's (x, y). Row = y (core's y already grows South,
  matching row-major), col = x;
- heading is numeric (0=E, 1=S, 2=W, 3=N) in the segment header, but a
  *letter* in the top-level ``start`` array — two different encodings
  for the same field in the same file, not a mistake here;
- ``agentCounter`` (execution ticks per Forward/Rotate action, default
  10 in the real competition) is not reproduced — ``ticks_per_action``
  defaults to 1, one PlanViz tick per WorldEngine tick. Raise it for
  more realistic pacing in PlanViz's own player.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from core import Agent, Coordinates2D, Exporter, Orientation

if TYPE_CHECKING:
    from core import Grid2D, StepOutcome

_ORIENTATION_CODE = {
    Orientation.EAST: 0,
    Orientation.SOUTH: 1,
    Orientation.WEST: 2,
    Orientation.NORTH: 3,
}

_History = dict[int, list[tuple[Coordinates2D, Orientation]]]


class PlanVizExporter(Exporter):
    """Accumulates (position, orientation) per agent per tick; flush()
    run-length-encodes the deltas into PlanViz's action strings and
    writes the .map + .json pair.
    """

    def __init__(
        self,
        map_path: str,
        plan_path: str,
        ticks_per_action: int = 1,
    ) -> None:
        """Input: where to write the map and the plan, and how many
        PlanViz ticks one WorldEngine tick should count as (default 1 —
        does not model the Start-Kit's agentCounter).
        Output: None.
        """
        self._map_path = map_path
        self._plan_path = plan_path
        self._ticks_per_action = ticks_per_action
        self._history: _History = {}
        self._grid: Optional["Grid2D"] = None

    def record(
        self,
        step: int,
        agents: list[Agent],
        grid: "Grid2D",
        outcome: "StepOutcome",
    ) -> None:
        """Input: see Exporter.record().
        Output: None. Appends this tick's (position, orientation) for
        every agent. The first tick an agent is seen also seeds a
        baseline entry from outcome.moves — recovering its pre-tick
        position without needing a call before tick 1, which
        WorldEngine never makes. The baseline's heading is a throwaway
        placeholder: flush() defers the declared start heading to the
        first real tick instead of trusting Agent's default NORTH,
        which is "nobody told me yet", not an observed fact.
        """
        self._grid = grid
        for agent in agents:
            aid = agent.agent_id
            if aid not in self._history:
                from_pos, _ = outcome.moves.get(aid, (agent.position, agent.position))
                self._history[aid] = [(from_pos, agent.orientation)]
            self._history[aid].append((agent.position, agent.orientation))

    def flush(self) -> None:
        """Input: none.
        Output: None. Writes the .map and .json files."""
        self._write_map()
        self._write_plan()

    # ── .map ─────────────────────────────────────────────────────────────

    def _write_map(self) -> None:
        grid = self._grid
        if grid is None:
            raise ValueError("PlanVizExporter.flush() called before any record().")
        rows = []
        for y in range(grid.height):
            row = "".join(
                "@" if self._is_static_obstacle(grid, Coordinates2D(x, y)) else "."
                for x in range(grid.width)
            )
            rows.append(row)
        with open(self._map_path, "w") as f:
            f.write("type octile\n")
            f.write(f"height {grid.height}\n")
            f.write(f"width {grid.width}\n")
            f.write("map\n")
            f.write("\n".join(rows) + "\n")

    @staticmethod
    def _is_static_obstacle(grid: "Grid2D", pos: Coordinates2D) -> bool:
        return any(
            e.blocks_movement and e.is_active
            for e in grid.entities_at(pos)
            if not isinstance(e, Agent)
        )

    # ── .json ────────────────────────────────────────────────────────────

    def _write_plan(self) -> None:
        starts = []
        actual_paths = []
        durations = []
        for ticks in self._history.values():
            start_pos, action_str, duration = self._encode_agent(ticks)
            heading = self._start_heading(ticks)
            starts.append([start_pos.x, start_pos.y, heading.value])
            actual_paths.append(
                f"[(0,{start_pos.y},{start_pos.x},"
                f"{_ORIENTATION_CODE[heading]},0):({action_str})]"
            )
            durations.append(duration)

        plan = {
            "actionModel": "MAPF_T",
            "version": "2026 LoRR",
            "teamSize": len(self._history),
            # PlanViz interpolates one cell's motion over agentMaxCounter
            # ticks (plan_config.py's get_ticks_per_timestep(), default 10
            # when this key is absent) — must match _ticks_per_action or
            # the agent visibly moves only a fraction of a cell per action.
            "agentMaxCounter": self._ticks_per_action,
            # The exported timeline can be longer than WorldEngine's own
            # tick count: a same-tick position+orientation change (see
            # record()) becomes an extra R/C action, one PlanViz tick
            # longer than the single WorldEngine tick that produced it.
            "makespan": max(durations, default=0),
            "start": starts,
            "actualPaths": actual_paths,
            "plannerPaths": actual_paths,
            # PlanViz's own loader (plan_config.py) never sets max_seq_num
            # above -1 when "tasks" is empty, and load_events() asserts
            # max_seq_num > -1 unconditionally — even when "events" is
            # also empty. core has no task/mission concept any more (mrta
            # removed), so there is never a real task to report; this
            # single zero-errand placeholder satisfies the loader without
            # rendering anything (loc_num = len([])//2 = 0).
            "tasks": [[0, 0, []]], "events": [], "errors": [],
        }
        with open(self._plan_path, "w") as f:
            json.dump(plan, f, indent=2)

    @staticmethod
    def _start_heading(ticks: list[tuple[Coordinates2D, Orientation]]) -> Orientation:
        """The declared start heading: the first tick's actual heading,
        not the placeholder baseline's — see record()'s docstring."""
        return ticks[1][1] if len(ticks) > 1 else ticks[0][1]

    def _encode_agent(
        self, ticks: list[tuple[Coordinates2D, Orientation]]
    ) -> tuple[Coordinates2D, str, int]:
        """Input: this agent's (position, orientation) history, baseline
        entry included.
        Output: (start position, run-length-encoded action string, total
        duration in PlanViz ticks — >= len(ticks) - 1 whenever a
        same-tick rotate+move needed splitting into two actions).
        """
        start_pos = ticks[0][0]
        actions: list[str] = []
        prev_pos = start_pos
        prev_heading: Optional[Orientation] = None
        for pos, heading in ticks[1:]:
            if prev_heading is None:
                prev_heading = heading  # deferred: first real heading is the start
            if heading != prev_heading:
                actions.extend(self._rotation_actions(prev_heading, heading))
                prev_heading = heading
            actions.append("F" if pos != prev_pos else "W")
            prev_pos = pos

        duration = len(actions) * self._ticks_per_action
        return start_pos, self._run_length_encode(actions), duration

    @staticmethod
    def _rotation_actions(old: Orientation, new: Orientation) -> list[str]:
        """The Start-Kit's own action model: CR (letter R) turns
        clockwise, CCR (letter C) turns counter-clockwise, each one 90
        degrees. Picks whichever direction is fewer steps."""
        cw = (_ORIENTATION_CODE[new] - _ORIENTATION_CODE[old]) % 4
        ccw = (_ORIENTATION_CODE[old] - _ORIENTATION_CODE[new]) % 4
        return ["R"] * cw if cw <= ccw else ["C"] * ccw

    def _run_length_encode(self, actions: list[str]) -> str:
        encoded: list[list] = []
        for a in actions:
            if encoded and encoded[-1][0] == a:
                encoded[-1][1] += self._ticks_per_action
            else:
                encoded.append([a, self._ticks_per_action])
        return ",".join(f"{a} {n}" for a, n in encoded)
