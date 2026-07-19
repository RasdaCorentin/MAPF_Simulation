from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioConfig:
    """Declarative description of a scenario to build.

    Frozen on purpose: a config is a record of what was asked for, so a
    run stays reproducible from it plus its seed. Building the objects
    is ``factory.build()``'s job, not this class's.
    """

    width:  int = 15
    height: int = 15
    agents: int = 20
    obstacles: int = 0

    algo: str = "pibt"      # "pibt" | "random"
    mode: str = "mrta"      # "mrta" | "static"
    seed: int = 0

    # MRTA watchdog tuning — see FleetManager.
    patience: int = 12
    max_attempts: int = 3

    def __post_init__(self) -> None:
        """Input: none. Output: None. Rejects an unbuildable scenario
        early, where the message can still name the offending field.
        """
        if self.algo not in ("pibt", "random"):
            raise ValueError(f"Unknown algo {self.algo!r} (expected 'pibt' or 'random').")
        if self.mode not in ("mrta", "static"):
            raise ValueError(f"Unknown mode {self.mode!r} (expected 'mrta' or 'static').")
        if self.agents + self.obstacles > self.width * self.height:
            raise ValueError(
                f"{self.agents} agents + {self.obstacles} obstacles do not fit "
                f"in a {self.width}x{self.height} grid."
            )
