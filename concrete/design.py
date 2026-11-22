"""Beam member sizing and one-layer rebar selection, ACI 318-19 teaching subset."""
from dataclasses import dataclass
from math import ceil
from .aci318 import (REBAR, Materials, effective_depth, clear_bar_spacing,
                     required_horizontal_clear_spacing)
from .flexure import Section, analyze, FlexureResult


@dataclass(frozen=True)
class Candidate:
    designation: str
    n: int
    as_t: float
    d: float
    clear: float
    result: FlexureResult

    @property
    def label(self):
        return f"{self.n}-{self.designation}"


def candidates_for_section(mu_kft: float, b: float, h: float, mat: Materials,
                           cover: float, stirrup_db: float, aggregate: float = 0.75,
                           as_c: float = 0.0, dp: float = 2.375,
                           min_n: int = 2, max_n: int = 12):
    """Return acceptable one-layer bar combinations sorted by installed As.

    Limited to rectangular beams; both strength and tension-control are mandatory.
    Compression reinforcement, when specified, is fixed and must compress.
    Other ACI requirements are intentionally not checked here.
    """
    if mu_kft <= 0 or b <= 0 or h <= 0 or cover <= 0 or stirrup_db <= 0 or aggregate <= 0:
        raise ValueError("Use positive moment, dimensions, cover, stirrup and aggregate size.")
    good = []
    for size, (db, area) in REBAR.items():
        if size == "#3":
            continue  # exclude small bars as primary beam longitudinal steel
        d = effective_depth(h, cover, stirrup_db, db)
        for n in range(min_n, max_n + 1):
            clear = clear_bar_spacing(b, n, db, cover, stirrup_db)
            if clear < required_horizontal_clear_spacing(db, aggregate):
                continue
            s = Section(b=b, h=h, d=d, as_t=n*area, as_c=as_c, dp=dp)
            result = analyze(s, mat)
            if as_c and result.strain_c_steel <= 0:
                continue  # specified upper steel must actually be in compression
            if (result.control == "Tension-controlled" and
                result.phi_mn_kft + 1e-8 >= mu_kft and
                s.as_t + 1e-8 >= result.as_min):
                good.append(Candidate(size, n, n*area, d, clear, result))
    return sorted(good, key=lambda c: (c.as_t, c.result.phi_mn_kft - mu_kft, c.n))


@dataclass(frozen=True)
class Preliminary:
    rho_trial: float
    d_trial: float
    b_trial: float
    h_selected: float
    b_selected: float
    candidate: Candidate | None
    iterations: int


def preliminary_size(mu_kft: float, mat: Materials, alpha: float = 0.6,
                     strain_target: float = 0.0075, cover: float = 1.5,
                     stirrup_db: float = 0.375, aggregate: float = 0.75):
    """Wight-style initial tension-controlled sizing from a chosen strain target.
    b ≈ alpha*d, d is solved using Mu ≈ phi*R*b*d^2. Then discrete detailing.
    """
    if mu_kft <= 0 or not (0.35 <= alpha <= 1.0):
        raise ValueError("Mu must be positive; choose 0.35 <= b/d <= 1.0.")
    if strain_target < mat.yield_strain + 0.003:
        raise ValueError("Initial strain target must be tension-controlled under ACI 318-19.")
    # c/d from strain compatibility, steel yielding for this strain target.
    k = 0.003 / (0.003 + strain_target)
    rho = 0.85 * mat.fc * mat.beta1 * k / mat.fy
    a_over_d = mat.beta1 * k
    coeff = 0.90 * rho * mat.fy * (1.0 - 0.5 * a_over_d) * alpha
    d_trial = (mu_kft*12.0 / coeff)**(1.0/3.0)
    b_trial = alpha*d_trial
    # Construction convenience for approximate trial, always run exact checking.
    b_start = max(8.0, 2.0 * ceil(b_trial / 2.0))
    h_start = max(12.0, ceil(d_trial + cover + stirrup_db + 0.5))
    for iteration in range(0, 37):
        b_try = b_start
        h_try = h_start + iteration
        good = candidates_for_section(mu_kft, b_try, h_try, mat,
                                      cover, stirrup_db, aggregate)
        if good:
            # Favor conventional 3–5-bar, moderate-size layouts where available;
            # the absolutely smallest As may select two very large bars.
            preferred = [c for c in good if 3 <= c.n <= 5 and
                         c.designation in ("#6", "#7", "#8", "#9")]
            chosen = min(preferred, key=lambda c: (c.as_t, c.n)) if preferred else good[0]
            return Preliminary(rho, d_trial, b_trial, h_try, b_try, chosen, iteration)
    return Preliminary(rho, d_trial, b_trial, h_start+36, b_start, None, 36)
