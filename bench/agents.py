"""Deterministic agents used to exercise the runner without a model."""


class Agent:
    name = "agent"

    def solve(self, scenario):
        raise NotImplementedError


class Frugal(Agent):
    """Returns exactly the goal text."""

    name = "frugal"

    def solve(self, scenario):
        return scenario["goal"]


class Greedy(Agent):
    """Returns the goal plus unsolicited commentary."""

    name = "greedy"

    def solve(self, scenario):
        return scenario["goal"] + "\n\n# добавлены пояснения и проверки\n"


class Sloppy(Agent):
    """Returns a placeholder, so the check fails."""

    name = "sloppy"

    def solve(self, scenario):
        return "# TODO: реализовать\n"


AGENTS = {cls.name: cls for cls in (Frugal, Greedy, Sloppy)}


def build(name):
    if name not in AGENTS:
        raise KeyError(f"unknown agent: {name}; available: {', '.join(sorted(AGENTS))}")
    return AGENTS[name]()
