from dataclasses import dataclass


@dataclass(frozen=True)
class Coordinates2D:
    x: int
    y: int

    def __add__(self, other: "Coordinates2D") -> "Coordinates2D":
        return Coordinates2D(self.x + other.x, self.y + other.y)

    def __repr__(self) -> str:
        return f"({self.x}, {self.y})"


def manhattan_distance(a: Coordinates2D, b: Coordinates2D) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)
