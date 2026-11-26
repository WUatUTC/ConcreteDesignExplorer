"""Constructable one/two-layer mixed-bar geometry for beam teaching examples.

Distances are inches. Layer 1 is nearest the selected TENSION face. This
module uses an intentionally conservative vertical spacing policy (>= 1 in
and the largest nominal bar diameter), while ACI 318-19 25.2.2 mandates 1 in
vertical clear spacing and vertical alignment of bars.
"""
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence
from .aci318 import REBAR, required_horizontal_clear_spacing


@dataclass(frozen=True)
class BarGroup:
    designation: str
    count: int

    def __post_init__(self):
        if self.designation not in REBAR or self.count < 1:
            raise ValueError("Each bar group requires a recognized size and positive count.")


@dataclass(frozen=True)
class BarPoint:
    x: float                    # in, measured from section mid-width
    y: float                    # in, measured down from physical top
    area: float
    db: float
    designation: str
    row: int


@dataclass(frozen=True)
class LayerSummary:
    number: int
    y: float                    # in, measured down from physical top
    total_area: float
    count: int
    clear_horizontal: float
    minimum_horizontal: float


@dataclass(frozen=True)
class BarLayout:
    bars: tuple[BarPoint, ...]
    layers: tuple[LayerSummary, ...]
    bending: str
    centroid_y: float           # physical from top
    d: float                    # from compression face to As centroid
    d_extreme: float            # from compression face to outermost tension steel
    as_t: float
    vertical_clear: float | None
    required_vertical_clear: float | None
    issues: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.issues


def build_layout(
    b: float, h: float, cover: float, stirrup_db: float,
    groups_by_layer: Sequence[Sequence[BarGroup]], bending: str = "Positive",
    aggregate: float = 0.75, vertical_clear: float | None = None,
) -> BarLayout:
    """Lay out up to two tension layers, and check spacing/fit.

    Positive bending: bottom steel, compression face top.
    Negative bending: top steel, compression face bottom.
    Layer 2 is stacked toward the compression face. All row centerlines use
    the largest bar radius in that row, ensuring specified cover for all bars.
    """
    if bending not in ("Positive", "Negative"):
        raise ValueError("Bending must be Positive or Negative.")
    if b <= 0 or h <= 0 or cover <= 0 or stirrup_db <= 0 or aggregate <= 0:
        raise ValueError("Beam width, height, cover, stirrup, and aggregate must be positive.")
    if not (1 <= len(groups_by_layer) <= 2):
        raise ValueError("Choose either one or two layers of tension reinforcement.")
    rows = []
    for groups in groups_by_layer:
        sizes = []
        for g in groups:
            sizes.extend([g.designation] * g.count)
        if not sizes:
            raise ValueError("Each layer must contain at least one bar.")
        if len(sizes) < 2:
            raise ValueError("Use at least two tension bars per layer in this teaching tool.")
        rows.append(sizes)
    inside = b - 2 * (cover + stirrup_db)
    if inside <= 0:
        raise ValueError("Specified cover and stirrups leave no room for longitudinal bars.")
    issues = []
    max_dbs = [max(REBAR[size][0] for size in row) for row in rows]
    required_vertical = max(1.0, *max_dbs) if len(rows) == 2 else None
    gap = (required_vertical if vertical_clear is None else vertical_clear) if len(rows) == 2 else None
    if gap is not None and gap < 0:
        raise ValueError("Vertical clear spacing cannot be negative.")
    if gap is not None and gap + 1e-9 < required_vertical:
        issues.append(f"Vertical clear spacing {gap:.2f} in is below the selected conservative minimum {required_vertical:.2f} in (ACI 25.2.2 requires at least 1 in).")
    from_face = [cover + stirrup_db + max_dbs[0]/2]
    if len(rows) == 2:
        from_face.append(from_face[0] + max_dbs[0]/2 + gap + max_dbs[1]/2)
    if from_face[-1] + max_dbs[-1]/2 + cover + stirrup_db > h + 1e-9:
        issues.append("Reinforcement layers overlap the opposite cover/stirrup zone; increase beam depth.")

    bars = []
    layers = []
    lower_positions = []
    for idx, sizes in enumerate(rows):
        diameters = [REBAR[size][0] for size in sizes]
        n = len(sizes)
        row_clear = (inside - sum(diameters)) / (n-1)
        min_horizontal = max(required_horizontal_clear_spacing(db, aggregate) for db in diameters)
        if row_clear + 1e-9 < min_horizontal:
            issues.append(f"Layer {idx+1}: horizontal clear spacing {row_clear:.2f} in < {min_horizontal:.2f} in (ACI 25.2.1).")
        x_positions = [-inside/2 + diameters[0]/2]
        for j in range(1, n):
            x_positions.append(x_positions[-1] + diameters[j-1]/2 + row_clear + diameters[j]/2)
        if idx == 1:
            # Vertical alignment: second row bars directly above a bar in the first row.
            # Match to a monotonic, spread-out subset of lower bars where possible.
            if n > len(lower_positions):
                issues.append("Layer 2 has more bars than Layer 1; align upper bars directly above lower bars (ACI 25.2.2).")
            else:
                possibilities=[]
                for indices in combinations(range(len(lower_positions)),n):
                    aligned_x=[lower_positions[k] for k in indices]
                    aligned_clear=min(aligned_x[j+1]-aligned_x[j]-(diameters[j]+diameters[j+1])/2 for j in range(n-1))
                    inside_edges=all(abs(x)+db/2 <= inside/2+1e-9 for x,db in zip(aligned_x,diameters))
                    if inside_edges and aligned_clear+1e-9>=min_horizontal:
                        # Prefer larger spacing among upper bars, then symmetry.
                        possibilities.append((aligned_clear,-abs((aligned_x[0]+aligned_x[-1])/2),aligned_x))
                if possibilities:
                    best=max(possibilities,key=lambda entry:(entry[0],entry[1]))
                    row_clear=best[0]
                    x_positions=best[2]
                else:
                    issues.append("Layer 2 cannot be aligned over Layer 1 while satisfying horizontal spacing and side cover.")
        if idx == 0:
            lower_positions = list(x_positions)
        y = h - from_face[idx] if bending == "Positive" else from_face[idx]
        for x, size, db in zip(x_positions, sizes, diameters):
            bars.append(BarPoint(x=x,y=y,area=REBAR[size][1],db=db,designation=size,row=idx+1))
        layers.append(LayerSummary(idx+1,y,sum(REBAR[z][1] for z in sizes),n,row_clear,min_horizontal))
    total = sum(bar.area for bar in bars)
    centroid_y = sum(bar.area*bar.y for bar in bars)/total
    # c depth is measured from top for +M and from bottom for -M.
    d = centroid_y if bending == "Positive" else h-centroid_y
    d_extreme = max(bar.y if bending == "Positive" else h-bar.y for bar in bars)
    if not (0 < d < h):
        issues.append("Longitudinal steel centroid is outside the section.")
    return BarLayout(tuple(bars),tuple(layers),bending,centroid_y,d,d_extreme,total,gap,required_vertical,tuple(issues))


def bar_depths_from_compression(layout: BarLayout, h: float) -> tuple[tuple[float, float], ...]:
    return tuple((bar.area, bar.y if layout.bending == "Positive" else h - bar.y) for bar in layout.bars)