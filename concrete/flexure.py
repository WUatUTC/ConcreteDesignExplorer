"""Strain-compatible nominal flexural analysis with Whitney stress block.

Uses a normalized bisection equilibrium solver, no code black box.
All lengths in inches, stresses in ksi, forces in kips and moments in kip-in.
"""
from dataclasses import dataclass
from .aci318 import Materials, strength_reduction_factor, minimum_beam_steel


@dataclass(frozen=True)
class Section:
    b: float = 12.0  # rectangular width OR T-beam web width, inches
    h: float = 24.0
    d: float = 21.625
    as_t: float = 2.37
    kind: str = "Rectangular"  # or "T-beam (+M)"
    bf: float = 0.0
    hf: float = 0.0
    as_c: float = 0.0
    dp: float = 2.375

    def __post_init__(self):
        if self.b <= 0 or self.h <= 0 or self.as_t <= 0:
            raise ValueError("Width, height and tension steel area must be positive.")
        if not (0 < self.d < self.h):
            raise ValueError("Effective depth must satisfy 0 < d < h.")
        if self.as_c < 0 or self.dp <= 0:
            raise ValueError("Compression steel area must be nonnegative; d' > 0.")
        if self.as_c and not (self.dp < self.d):
            raise ValueError("Compression reinforcement must be above tension steel (d' < d).")
        if self.kind not in ("Rectangular", "T-beam (+M)"):
            raise ValueError("Section type not supported.")
        if self.kind == "T-beam (+M)" and not (self.b <= self.bf and 0 < self.hf < self.h):
            raise ValueError("T-beam needs bf >= bw and 0 < hf < h.")


@dataclass(frozen=True)
class FlexureResult:
    c: float
    a: float
    strain_t: float
    strain_c_steel: float
    stress_t: float
    stress_c_steel: float
    cc: float
    cs_net: float
    tension: float
    mn: float
    phi: float
    phi_mn: float
    control: str
    as_min: float
    case: str
    equilibrium_error: float

    @property
    def mn_kft(self):
        return self.mn / 12.0

    @property
    def phi_mn_kft(self):
        return self.phi_mn / 12.0


def _stress_block(s: Section, m: Materials, a: float):
    """Compression force and first moment about compression face.
    For T sections, the width beyond hf is the web width; bf effective preverified by user.
    """
    base = 0.85 * m.fc
    if s.kind == "Rectangular":
        cc = base * s.b * a
        return cc, cc * a / 2.0
    # Formulate as full web plus flange overhang up to flange thickness.
    web_force = base * s.b * a
    extra_height = min(a, s.hf)
    overhang_force = base * (s.bf - s.b) * extra_height
    return (web_force + overhang_force,
            web_force * a / 2.0 + overhang_force * extra_height / 2.0)


def _quantities(c: float, s: Section, m: Materials):
    a = m.beta1 * c
    cc, cc_first_moment = _stress_block(s, m, a)
    et = 0.003 * (s.d - c) / c
    fst = max(-m.fy, min(m.fy, m.es * et))
    eps_cp = 0.003 * (c - s.dp) / c if s.as_c else 0.0
    fcp = max(-m.fy, min(m.fy, m.es * eps_cp)) if s.as_c else 0.0
    # Avoid counting concrete and reinforcing steel over the same area
    # when the upper reinforcement is located inside equivalent stress block.
    cs_net = s.as_c * (fcp - (0.85 * m.fc if s.dp <= a else 0.0))
    t = s.as_t * fst
    return a, cc, cc_first_moment, et, fst, eps_cp, fcp, cs_net, t


def analyze(s: Section, m: Materials) -> FlexureResult:
    # Bisection in (0,d), because positive bending presumes the specified
    # bottom reinforcement is in the tension zone at ultimate.
    low, high = s.d * 1e-8, s.d * (1 - 1e-10)

    def balance(c):
        _, cc, _, _, _, _, _, cs_net, t = _quantities(c, s, m)
        return cc + cs_net - t

    fl, fh = balance(low), balance(high)
    if not (fl < 0 < fh):
        raise ValueError("Cannot bracket a positive-bending equilibrium state with tension steel in tension.")
    for _ in range(110):
        mid = (low + high) / 2.0
        if balance(mid) > 0:
            high = mid
        else:
            low = mid
    c = (low + high) / 2.0
    a, cc, cc_first, et, fst, eps_cp, fcp, cs_net, t = _quantities(c, s, m)
    # Internal couple about tension steel centroid; concrete first moment
    # is already relative to top face, and net compression steel at d'.
    mn = cc * s.d - cc_first + cs_net * (s.d - s.dp)
    phi, control = strength_reduction_factor(et, m)
    if s.kind == "Rectangular":
        case = "Rectangular Whitney compression block"
    elif a <= s.hf + 1e-9:
        case = "T-beam Case 1: compression block entirely within flange"
    else:
        case = "T-beam Case 2: compression block extends into web"
    return FlexureResult(
        c=c, a=a, strain_t=et, strain_c_steel=eps_cp,
        stress_t=fst, stress_c_steel=fcp, cc=cc, cs_net=cs_net,
        tension=t, mn=mn, phi=phi, phi_mn=phi*mn,
        control=control, as_min=minimum_beam_steel(s.b, s.d, m),
        case=case, equilibrium_error=abs(balance(c)),
    )
