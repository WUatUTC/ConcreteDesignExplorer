"""Original instructional illustrations; no textbook images embedded."""
import numpy as np
import plotly.graph_objects as go
from .flexure import Section, analyze
from .aci318 import Materials

BLUE = "#246E9E"
RED = "#C36A52"
TEAL = "#358A78"
INK = "#283846"


def section_figure(section: Section, r=None, layout=None):
    """Schematic (not detailing drawing): compression zone, concrete, and bars."""
    if r is None:
        r = analyze(section, Materials())
    s = section
    xmax = s.bf if s.kind == "T-beam (+M)" else s.b
    fig = go.Figure()
    rect_fill = "rgba(165,177,186,0.28)"
    if s.kind == "Rectangular":
        fig.add_shape(type="rect", x0=-s.b/2, x1=s.b/2, y0=0, y1=s.h,
                      fillcolor=rect_fill, line=dict(color=INK, width=2))
    else:
        fig.add_shape(type="rect", x0=-s.b/2, x1=s.b/2, y0=0, y1=s.h,
                      fillcolor=rect_fill, line=dict(color=INK, width=2))
        fig.add_shape(type="rect", x0=-s.bf/2, x1=s.bf/2, y0=0, y1=s.hf,
                      fillcolor=rect_fill, line=dict(color=INK, width=2))
    # Physical y=0 is TOP. Negative bending compresses the BOTTOM face.
    compress_bottom = s.bending == "Negative"
    def cy(value):
        return s.h-value if compress_bottom else value
    def compression_rect(x0,x1,from_face,to_face):
        lo,hi = sorted((cy(from_face),cy(to_face)))
        fig.add_shape(type="rect",x0=x0,x1=x1,y0=lo,y1=hi,
                      fillcolor="rgba(36,110,158,.26)",line=dict(width=0))

    if s.kind == "Rectangular":
        compression_rect(-s.b/2,s.b/2,0,r.a)
    elif r.a <= s.hf:
        compression_rect(-s.bf/2,s.bf/2,0,r.a)
    else:
        compression_rect(-s.bf/2,s.bf/2,0,s.hf)
        compression_rect(-s.b/2,s.b/2,s.hf,r.a)
    fig.add_hline(y=cy(r.c),line=dict(color=TEAL,width=2,dash="dash"),
                  annotation_text="Neutral axis",annotation_position="bottom right")
    if layout is not None:
        xx = [bar.x for bar in layout.bars]
        yy = [bar.y for bar in layout.bars]
        labels = [f"Layer {bar.row} · {bar.designation}" for bar in layout.bars]
        diameters = [bar.db for bar in layout.bars]
        fig.add_trace(go.Scatter(x=xx,y=yy,mode="markers",name="Tension bars",
              customdata=labels,
              marker=dict(size=[max(10,15*db) for db in diameters],color=INK,line=dict(width=1,color="white")),
              hovertemplate="%{customdata}<br>Physical depth from top: %{y:.2f} in<extra></extra>"))
        fig.add_hline(y=layout.centroid_y,line=dict(color=RED,width=1,dash="dot"),
                      annotation_text="As centroid",annotation_position="top right")
    else:
        n_sym=4 if s.as_t>=2.5 else 3
        xx=np.linspace(-s.b*.30,s.b*.30,n_sym)
        fig.add_trace(go.Scatter(x=xx,y=[cy(s.d)]*n_sym,mode="markers",name="Tension steel (schematic)",
                 marker=dict(size=13,color=INK,line=dict(width=1,color="white"))))
    if s.as_c:
        xx2=np.linspace(-s.b*.25,s.b*.25,2)
        fig.add_trace(go.Scatter(x=xx2,y=[cy(s.dp)]*2,mode="markers",name="Compression-face steel",
                                 marker=dict(size=11,color=RED,line=dict(width=1,color="white"))))
    fig.update_layout(
        height=410, margin=dict(l=20,r=40,t=26,b=30), showlegend=False,
        plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[-xmax*.85,xmax*.85],visible=False,scaleanchor="y",scaleratio=1),
        yaxis=dict(range=[s.h*1.10,-s.h*.08], title="Physical depth from TOP (in)", zeroline=False,
                   gridcolor="rgba(150,150,150,0.10)")
    )
    return fig


def interaction_charts(section: Section, mat: Materials, current=None):
    base = current or analyze(section, mat)
    as_axis = np.linspace(max(.12, section.as_t*.12), max(section.as_t*2.5, section.as_t+3), 80)
    strengths, strains, phis, mn_values = [], [], [], []
    for As in as_axis:
        updated={**section.__dict__,"as_t":float(As)}
        if section.tension_bars:
            updated["tension_bars"]=tuple((area*float(As)/section.as_t,depth) for area,depth in section.tension_bars)
        r = analyze(Section(**updated), mat)
        strengths.append(r.phi_mn_kft)
        mn_values.append(r.mn_kft)
        strains.append(r.strain_t)
        phis.append(r.phi)
    strength = go.Figure()
    strength.add_trace(go.Scatter(x=as_axis,y=mn_values,mode="lines",name="Nominal Mn",line=dict(color="#8AA6B7",dash="dot")))
    strength.add_trace(go.Scatter(x=as_axis,y=strengths,mode="lines",name="Design strength φMn",line=dict(color=BLUE,width=3)))
    strength.add_trace(go.Scatter(x=[section.as_t],y=[base.phi_mn_kft],mode="markers",name="Current section",marker=dict(size=11,color=RED)))
    strength.update_layout(height=320,margin=dict(l=15,r=15,t=18,b=30),
                           xaxis_title="Tension steel area As (in²)",yaxis_title="Moment (kip-ft)",
                           legend=dict(orientation="h",y=-.35),hovermode="x unified")
    strain_chart = go.Figure()
    strain_chart.add_trace(go.Scatter(x=as_axis,y=np.array(strains)*1000,mode="lines",name="Tension strain",line=dict(color=TEAL,width=3)))
    strain_chart.add_hline(y=mat.yield_strain*1000,annotation_text="εty",line=dict(color=RED,dash="dash"))
    strain_chart.add_hline(y=(mat.yield_strain+.003)*1000,
                           annotation_text="εty + .003 (tension control)",line=dict(color=BLUE,dash="dash"))
    strain_chart.add_trace(go.Scatter(x=[section.as_t],y=[base.strain_t*1000],mode="markers",
                                      name="Current section",marker=dict(size=11,color=RED)))
    strain_chart.update_layout(height=320,margin=dict(l=15,r=15,t=18,b=30),
                               xaxis_title="Tension steel area As (in²)",yaxis_title="Extreme tension strain εt (× 10⁻³)",
                               showlegend=False,hovermode="x unified")
    return strength, strain_chart