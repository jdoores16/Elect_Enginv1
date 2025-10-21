
from pathlib import Path
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt

def dxf_to_pdf(dxf_path: Path, pdf_path: Path, project: str | None = None, sheet_title: str | None = None) -> Path:
    """
    Render a DXF to a single-page PDF using ezdxf's Matplotlib backend.
    """
    dxf_path = Path(dxf_path)
    pdf_path = Path(pdf_path)
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])  # full-bleed
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)
    _annotate_title(ax, project, sheet_title)
    fig.savefig(pdf_path, format="pdf")
    plt.close(fig)
    return pdf_path


def _annotate_title(ax, project: str | None, sheet_title: str | None):
    # simple border
    ax.figure.canvas.draw()
    w, h = ax.figure.get_size_inches()
    # Margin in figure fraction
    ax.add_patch(plt.Rectangle((0.01,0.01), 0.98, 0.98, fill=False, transform=ax.figure.transFigure, linewidth=1.2))
    footer = (sheet_title or "Sheet") + (" — " + project if project else "")
    import datetime as _dt
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ax.text(0.02, 0.015, f\"{footer}\", transform=ax.figure.transFigure, fontsize=8)
    ax.text(0.88, 0.015, f\"Generated: {ts}\", transform=ax.figure.transFigure, fontsize=8)

# Monkey-patch the call site: after drawing layout, add title
# (We re-open the function and add the call without breaking existing users)
