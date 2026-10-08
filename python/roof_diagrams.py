# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only SVG observation of cell and indexed roof incidence."""

from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "addon"))


def svg(decomposition, composition):
    """Debug drawing only: does not alter graph positions or incidence."""
    points = decomposition.vertices
    g = composition.graph
    lo = [min(p[k] for p in points) for k in (0, 1)]
    hi = [max(p[k] for p in points) for k in (0, 1)]
    scale = 370 / max(hi[k] - lo[k] for k in (0, 1))

    def point(p, panel):
        return (40 + panel * 480 + (p[0] - lo[0]) * scale, 455 - (p[1] - lo[1]) * scale)

    def chain(ids, nodes, panel):
        return " ".join(
            f"{point(nodes[i],panel)[0]:.3f},{point(nodes[i],panel)[1]:.3f}"
            for i in ids
        )

    text = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="525" viewBox="0 0 960 525">',
        '<rect width="960" height="525" fill="white"/>',
        '<g font-family="sans-serif" font-size="14" fill="#18212b">',
        '<text x="40" y="30">Cells / artificial boundary</text>',
        '<text x="520" y="30">2D RoofGraph before geometry solve</text>',
    ]
    palette = ("#e0eefb", "#f9e5d7")
    for cell in decomposition.cells:
        text.append(
            f'<polygon points="{chain(cell.boundary,points,0)}" fill="{palette[cell.id%2]}" stroke="#586779" stroke-width="2"/>'
        )
        centre = tuple(sum(points[i][k] for i in cell.corners) / 4 for k in (0, 1))
        x, y = point(centre, 0)
        text.append(f'<text x="{x:.3f}" y="{y:.3f}">cell {cell.id}</text>')
    for adjacency in decomposition.adjacency:
        text.append(
            f'<polyline points="{chain(adjacency.interval,points,0)}" fill="none" stroke="#222" stroke-width="3" stroke-dasharray="7,5"/>'
        )
    colors = {
        "ridge": "#d63143",
        "valley": "#1767cf",
        "hip": "#dc8818",
        "eave": "#586779",
        "gable_end": "#586779",
    }
    nodes = tuple(v.seed for v in g.vertices)
    for edge in g.edges:
        text.append(
            f'<polyline points="{chain(edge.vertices,nodes,1)}" fill="none" stroke="{colors[edge.kind]}" stroke-width="3"><title>{escape(edge.kind)}: {edge.vertices}, faces {edge.faces}</title></polyline>'
        )
    for i, vertex in enumerate(g.vertices):
        x, y = point(vertex.seed, 1)
        text.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4" fill="#18212b"/><text x="{x+7:.3f}" y="{y-7:.3f}">{i}</text>'
        )
    text.append(
        '<text x="40" y="505">Red: ridge; blue: valley; orange: hip. XY is an initializer, not solved roof geometry.</text></g></svg>'
    )
    return "\n".join(text) + "\n"
