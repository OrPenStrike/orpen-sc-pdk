"""Source-defined spline strips with explicit boundary curves and polygon witnesses.

The nominal transverse width is separation along Y, not a constant-normal-width
offset. Default horizontal tangents make the end caps perpendicular to ports.
Sampling defines the GDS representation; it is not a native conformity claim.
"""

import math

import gdsfactory as gf
import numpy as np

from orpen_sc_pdk.tech import LAYER


def _strip_component(
    *,
    samples: np.ndarray,
    width: float,
    die_side: float,
    upper_curve: dict,
    lower_curve: dict,
    source: dict,
    start_tangent: np.ndarray,
    end_tangent: np.ndarray,
) -> gf.Component:
    """Close the two authored boundary curves with their actual end caps."""
    if width <= 0:
        raise ValueError("strip_width_um must be positive")
    upper = samples + (0.0, width / 2)
    lower = samples - (0.0, width / 2)
    c = gf.Component()
    c.add_polygon(np.vstack((upper, lower[::-1])), layer=LAYER.D0_TOP_M1_DRAW)
    substrate = c << gf.components.rectangle(
        size=(die_side, die_side), centered=True, layer=LAYER.D0_SUBSTRATE_AREA
    )
    substrate.name = "SUBSTRATE"
    # A full-face mask explicitly requests no background Ground plane.
    mask = c << gf.components.rectangle(
        size=(die_side, die_side), centered=True, layer=LAYER.D0_TOP_GROUND_MASK
    )
    mask.name = "NO_BACKGROUND_GROUND_MASK"
    for name, center, tangent, reverse in (
        ("o1", samples[0], start_tangent, True),
        ("o2", samples[-1], end_tangent, False),
    ):
        if not np.any(tangent):
            raise ValueError("endpoint tangent must define a port direction")
        orientation = (
            math.degrees(math.atan2(tangent[1], tangent[0])) + (180 if reverse else 0)
        ) % 360
        c.add_port(
            name,
            center=tuple(center),
            width=width,
            orientation=orientation,
            layer=LAYER.D0_TOP_M1_DRAW,
            port_type="electrical",
        )
    selector = tuple(samples[len(samples) // 2])
    c.info["component_semantics"] = {
        "schema_version": 2,
        "conductor_regions": [
            {
                "semantic_id": "TRACE",
                "level": "D0_TOP_M1",
                "gds_layer": tuple(LAYER.D0_TOP_M1_DRAW),
                "geometry": {"geometry_source": "gds_polygon", "selector_point_um": selector},
            }
        ],
        "boundary_curves": [
            {
                "boundary_id": "TRACE_OUTER",
                "entity_id": "TRACE",
                "selector_point_um": selector,
                "role": "outer",
                "curves": [
                    upper_curve,
                    {"kind": "line_segment", "points_um": [upper[-1].tolist(), lower[-1].tolist()]},
                    lower_curve,
                    {"kind": "line_segment", "points_um": [lower[0].tolist(), upper[0].tolist()]},
                ],
            }
        ],
    }
    c.info["spline_source"] = {
        **source,
        "nominal_transverse_width_um": width,
        "width_definition": "boundary Y separation; not constant normal width",
        "boundary_ownership": "TRACE_OUTER contains two spline edges and two closed end caps",
        "sampled_centerline_um": samples.tolist(),
        "endpoint_tangents": [start_tangent.tolist(), end_tangent.tolist()],
        "native_comparison": (
            "UNOBSERVED; source polygon sampling is not native conformity evidence"
        ),
        "nets": "none; final electrical Nets belong to caller",
        "ground": "none",
        "JJ": "none",
    }
    return c


@gf.cell(tags=["simulation", "primitive", "curved_strip", "single_die", "interpolation_spline"])
def interpolation_spline_strip(
    through_points_um: tuple[tuple[float, float], ...] = (
        (-200.0, 0.0),
        (-100.0, 60.0),
        (0.0, -40.0),
        (100.0, 60.0),
        (200.0, 0.0),
    ),
    strip_width_um: float = 10.0,
    die_side_um: float = 1000.0,
    samples_per_span: int = 32,
) -> gf.Component:
    """Interpolate a cubic Hermite Y(X) graph through the supplied source points.

    X must increase strictly. Interior slopes are centered secants; endpoint
    slopes are zero. Each boundary interpolates the same points translated
    by +/-width/2 in Y. SCG's OCC addSpline chooses its own interpolation law;
    equality to this explicit Hermite construction has not been observed.
    """
    points = np.asarray(through_points_um, dtype=float)
    x, y = points.T
    if len(points) < 2 or np.any(np.diff(x) <= 0):
        raise ValueError("Hermite graph needs at least two strictly increasing X points")
    slopes = np.zeros(len(points))
    slopes[1:-1] = (y[2:] - y[:-2]) / (x[2:] - x[:-2])
    samples = []
    for i in range(len(points) - 1):
        t = np.linspace(0, 1, samples_per_span, endpoint=False)
        h = x[i + 1] - x[i]
        yy = (
            (2 * t**3 - 3 * t**2 + 1) * y[i]
            + (t**3 - 2 * t**2 + t) * h * slopes[i]
            + (-2 * t**3 + 3 * t**2) * y[i + 1]
            + (t**3 - t**2) * h * slopes[i + 1]
        )
        samples.extend(np.column_stack((x[i] + t * h, yy)))
    samples = np.vstack((samples, points[-1]))
    upper = points + (0.0, strip_width_um / 2)
    lower = points - (0.0, strip_width_um / 2)
    return _strip_component(
        samples=samples,
        width=strip_width_um,
        die_side=die_side_um,
        upper_curve={"kind": "interpolation_spline", "points_um": upper.tolist()},
        lower_curve={"kind": "interpolation_spline", "points_um": lower[::-1].tolist()},
        start_tangent=np.array((1.0, slopes[0])),
        end_tangent=np.array((1.0, slopes[-1])),
        source={
            "family": "interpolation_spline",
            "through_points_um": points.tolist(),
            "source_law": (
                "piecewise cubic Hermite Y(X); endpoint slopes 0; interior centered secants"
            ),
            "slopes_dy_dx": slopes.tolist(),
            "samples_per_span": samples_per_span,
            "parameter_domain_x_um": [float(x[0]), float(x[-1])],
            "native_interpolation_limit": (
                "OCC addSpline does not accept this source slope law; equivalence UNOBSERVED"
            ),
        },
    )


@gf.cell(tags=["simulation", "primitive", "curved_strip", "single_die", "bspline"])
def bspline_strip(
    control_points_um: tuple[tuple[float, float], ...] = (
        (-200.0, 0.0),
        (-100.0, 0.0),
        (0.0, 150.0),
        (100.0, -30.0),
        (200.0, -30.0),
    ),
    degree: int = 3,
    weights: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0, 1.0),
    knots: tuple[float, ...] = (0.0, 0.5, 1.0),
    multiplicities: tuple[int, ...] = (4, 1, 4),
    strip_width_um: float = 10.0,
    die_side_um: float = 1000.0,
    samples_per_span: int = 64,
) -> gf.Component:
    """Sample the explicit clamped rational B-spline with de Boor evaluation.

    Distinct knots, their multiplicities, degree and weights author both boundary
    curves. Default endpoint control pairs are horizontal; controls are not
    interpolation points. Width is the Y translation between boundary curves.
    """
    points = np.asarray(control_points_um, dtype=float)
    w = np.asarray(weights, dtype=float)
    expanded = np.repeat(knots, multiplicities)
    n = len(points)
    if len(w) != n or len(expanded) != n + degree + 1:
        raise ValueError("weights and expanded knots must match the control count and degree")
    if degree < 1 or multiplicities[0] != degree + 1 or multiplicities[-1] != degree + 1:
        raise ValueError("this source factory requires a clamped B-spline of positive degree")
    homogeneous = np.column_stack((points * w[:, None], w))
    lo, hi = expanded[degree], expanded[n]
    parameters = np.concatenate(
        [
            np.linspace(a, b, samples_per_span, endpoint=False)
            for a, b in zip(knots[:-1], knots[1:], strict=False)
        ]
        + [np.array([hi])]
    )
    samples = []
    for u in parameters:
        span = min(int(np.searchsorted(expanded, u, side="right") - 1), n - 1)
        d = homogeneous[span - degree : span + 1].copy()
        for r in range(1, degree + 1):
            for j in range(degree, r - 1, -1):
                i = span - degree + j
                alpha = (u - expanded[i]) / (expanded[i + degree - r + 1] - expanded[i])
                d[j] = (1 - alpha) * d[j - 1] + alpha * d[j]
        samples.append(d[degree, :2] / d[degree, 2])
    samples = np.asarray(samples)
    upper = points + (0.0, strip_width_um / 2)
    lower = points - (0.0, strip_width_um / 2)
    start_tangent = degree * w[1] / w[0] * (points[1] - points[0]) / (expanded[degree + 1] - lo)
    end_tangent = degree * w[-2] / w[-1] * (points[-1] - points[-2]) / (hi - expanded[n - 1])
    return _strip_component(
        samples=samples,
        width=strip_width_um,
        die_side=die_side_um,
        upper_curve={
            "kind": "bspline",
            "points_um": upper.tolist(),
            "degree": degree,
            "weights": weights,
            "knots": knots,
            "multiplicities": multiplicities,
            "parameter_interval": (float(lo), float(hi)),
        },
        lower_curve={
            "kind": "bspline",
            "points_um": lower[::-1].tolist(),
            "degree": degree,
            "weights": weights[::-1],
            "knots": tuple(lo + hi - k for k in knots[::-1]),
            "multiplicities": multiplicities[::-1],
            "parameter_interval": (float(lo), float(hi)),
        },
        start_tangent=start_tangent,
        end_tangent=end_tangent,
        source={
            "family": "bspline",
            "control_points_um": points.tolist(),
            "degree": degree,
            "weights": weights,
            "distinct_knots": knots,
            "multiplicities": multiplicities,
            "parameter_domain": (float(lo), float(hi)),
            "samples_per_span": samples_per_span,
            "source_law": "rational clamped B-spline; de Boor homogeneous evaluation",
        },
    )
