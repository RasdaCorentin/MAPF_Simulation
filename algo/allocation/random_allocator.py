import random

from core import Agent, Grid
from mrta import Task, Allocator


class RandomAllocator(Allocator):
    """Baseline allocator: pairs pending tasks with free agents at random.

    No notion of distance or cost — useful as a reference/baseline when
    comparing smarter allocation strategies.
    """

    def allocate(self, pending: list[Task], free: list[Agent], grid: Grid) -> dict[Task, Agent]:
        """Input: pending tasks, free agents, and the grid (unused).
        Output: a random one-to-one matching, limited by whichever of
        pending/free is shorter; leftover tasks or agents are unmatched.
        """
        tasks = list(pending)
        agents = list(free)
        random.shuffle(tasks)
        random.shuffle(agents)
        return dict(zip(tasks, agents))
