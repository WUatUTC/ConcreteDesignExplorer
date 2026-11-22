"""Selected ACI 318-19 provisions for educational NONPRESTRESSED BEAM flexure.
Units throughout: kip, inch, ksi, kip-in (unless explicitly labeled).
Not a full code-compliance or construction-design library.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Materials:
    fc: float = 4.0  # ksi
    fy: float = 60.0  # ksi
    es: float = 29000.0  # ksi

    def __post_init__(self):
        if not (2.5 <= self.fc <= 12):
            raise ValueError("This instructional model limits f'c to 2.5–12 ksi.")
        if not (40 <= self.fy <= 80):
            raise ValueError("This instructional model limits fy to Grade 40–80 (ksi).")
        if not (27000 <= self.es <= 30000):
            raise ValueError("Enter steel modulus Es between 27,000 and 30,000 ksi.")

    @property
    def yield_strain(self) -> float:
        return self.fy / self.es

    @property
    def beta1(self) -> float:
        """ACI 318-19 Table 22.2.2.4.3, normalweight assumptions."""
        return max(0.65, min(0.85, 0.85 - 0.05 * (self.fc - 4.0)))


def strength_reduction_factor(epsilon_t: float, materials: Materials):
    """ACI 318-19 Table 21.2.2, nonprestressed tied-member strain limits.

    Returns (phi, classification); phi is a diagnostic for analysis of invalid
    beam sections, NOT permission to design compression/transition-controlled beams.
    """
    ey = materials.yield_strain
    if epsilon_t >= ey + 0.003 - 1e-12:
        return 0.90, "Tension-controlled"
    if epsilon_t <= ey + 1e-12:
        return 0.65, "Compression-controlled"
    return 0.65 + 0.25 * (epsilon_t - ey) / 0.003, "Transition"


def minimum_beam_steel(bw: float, d: float, m: Materials) -> float:
    """ACI 318-19 Section 9.6.1.2, US customary; excludes §9.6.1.3 exception.
    fy is capped at 80 ksi by model input. f'c and fy here are in ksi.
    """
    if bw <= 0 or d <= 0:
        raise ValueError("bw and d must be positive.")
    return max(3.0 * math.sqrt(m.fc * 1000) / (m.fy * 1000),
               200.0 / (m.fy * 1000)) * bw * d


# ASTM standard nominal dimensions; values in inch and inch². Tables are
# standard nominal rounded values, not copied from the user's textbook.
REBAR = {
    "#3": (0.375, 0.11),
    "#4": (0.500, 0.20),
    "#5": (0.625, 0.31),
    "#6": (0.750, 0.44),
    "#7": (0.875, 0.60),
    "#8": (1.000, 0.79),
    "#9": (1.128, 1.00),
    "#10": (1.270, 1.27),
    "#11": (1.410, 1.56),
}


def effective_depth(h: float, cover: float, stirrup_db: float, main_bar_db: float) -> float:
    """One row of bars; clear cover is to the stirrup's outside surface."""
    result = h - cover - stirrup_db - 0.5 * main_bar_db
    if result <= 0:
        raise ValueError("Invalid geometry produces nonpositive effective depth.")
    return result


def clear_bar_spacing(b: float, n: int, bar_db: float, cover: float, stirrup_db: float) -> float:
    """One row of tension steel, equal clear spacing among n bars."""
    if n < 2:
        raise ValueError("Bar layout uses at least two tension bars.")
    inside = b - 2 * (cover + stirrup_db)
    return (inside - n * bar_db) / (n - 1)


def required_horizontal_clear_spacing(bar_db: float, aggregate_size: float = 0.75) -> float:
    """ACI 318-19 Sec. 25.2.1 typical parallel bars in one layer."""
    return max(1.0, bar_db, 4.0 * aggregate_size / 3.0)
