#!/usr/bin/env python3
"""Generate the submission-ready PDC project report from measured project data."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from PIL import Image as PILImage
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "benchmarks.csv"
PLOTS = ROOT / "results" / "plots"
OUTPUT = ROOT / "docs" / "PDC_Heat_Diffusion_Project_Report.pdf"

NAVY = colors.black
BLUE = colors.black
LIGHT_BLUE = colors.HexColor("#E6E6E6")
LIGHT_GRAY = colors.HexColor("#F2F2F2")
MID_GRAY = colors.HexColor("#666666")
DARK = colors.black
GREEN = colors.HexColor("#505050")


def register_fonts():
    candidates = [
        ("ReportSans", Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/ariali.ttf")),
        ("ReportSans", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf")),
    ]
    for family, regular, bold, italic in candidates:
        if regular.exists() and bold.exists() and italic.exists():
            pdfmetrics.registerFont(TTFont(family, str(regular)))
            pdfmetrics.registerFont(TTFont(f"{family}-Bold", str(bold)))
            pdfmetrics.registerFont(TTFont(f"{family}-Italic", str(italic)))
            pdfmetrics.registerFontFamily(family, normal=family, bold=f"{family}-Bold", italic=f"{family}-Italic")
            return family
    return "Helvetica"


FONT = register_fonts()
FONT_BOLD = f"{FONT}-Bold" if FONT != "Helvetica" else "Helvetica-Bold"
FONT_ITALIC = f"{FONT}-Italic" if FONT != "Helvetica" else "Helvetica-Oblique"


class ReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        body = Frame(2.1 * cm, 1.9 * cm, A4[0] - 4.2 * cm, A4[1] - 3.8 * cm, id="body")
        title = Frame(2.2 * cm, 2.0 * cm, A4[0] - 4.4 * cm, A4[1] - 4.0 * cm, id="title")
        self.addPageTemplates([
            PageTemplate(id="Title", frames=title, onPage=self.draw_title_page),
            PageTemplate(id="Body", frames=body, onPage=self.draw_body_page),
        ])

    def draw_title_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 1.1 * cm, A4[0], 1.1 * cm, fill=1, stroke=0)
        canvas.setFillColor(BLUE)
        canvas.rect(0, 0, A4[0], 0.55 * cm, fill=1, stroke=0)
        canvas.restoreState()

    def draw_body_page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D0D0D0"))
        canvas.line(2.1 * cm, A4[1] - 1.35 * cm, A4[0] - 2.1 * cm, A4[1] - 1.35 * cm)
        canvas.setFont(FONT, 8)
        canvas.setFillColor(MID_GRAY)
        canvas.drawString(2.1 * cm, A4[1] - 1.05 * cm, "Parallel 2D Heat Diffusion using Hybrid MPI and OpenMP")
        canvas.drawRightString(A4[0] - 2.1 * cm, A4[1] - 1.05 * cm, "PDC Project Report")
        canvas.line(2.1 * cm, 1.45 * cm, A4[0] - 2.1 * cm, 1.45 * cm)
        canvas.drawString(2.1 * cm, 1.05 * cm, "Sajjad Ahmed | Wali Uddin | Saad Zaidi")
        canvas.drawRightString(A4[0] - 2.1 * cm, 1.05 * cm, f"Page {doc.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            if style == "H1":
                text = flowable.getPlainText()
                key = f"h1-{self.seq.nextf('h1')}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=0, closed=False)
                self.notify("TOCEntry", (0, text, self.page, key))
            elif style == "H2":
                text = flowable.getPlainText()
                key = f"h2-{self.seq.nextf('h2')}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=1, closed=False)
                self.notify("TOCEntry", (1, text, self.page, key))


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleBig", fontName=FONT_BOLD, fontSize=23, leading=29, textColor=NAVY, alignment=TA_CENTER, spaceAfter=14))
styles.add(ParagraphStyle(name="TitleSub", fontName=FONT, fontSize=13, leading=18, textColor=BLUE, alignment=TA_CENTER))
styles.add(ParagraphStyle(name="Meta", fontName=FONT, fontSize=10.5, leading=17, alignment=TA_CENTER, textColor=DARK))
styles.add(ParagraphStyle(name="H1", fontName=FONT_BOLD, fontSize=16, leading=20, textColor=NAVY, spaceBefore=10, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle(name="H2", fontName=FONT_BOLD, fontSize=12.2, leading=16, textColor=BLUE, spaceBefore=9, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="BodyJ", fontName=FONT, fontSize=9.5, leading=14, alignment=TA_JUSTIFY, textColor=DARK, spaceAfter=7))
styles.add(ParagraphStyle(name="Body", fontName=FONT, fontSize=9.5, leading=14, alignment=TA_LEFT, textColor=DARK, spaceAfter=7))
styles.add(ParagraphStyle(name="Small", fontName=FONT, fontSize=8, leading=11, textColor=DARK))
styles.add(ParagraphStyle(name="TableHeader", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=colors.white))
styles.add(ParagraphStyle(name="MetaLabel", fontName=FONT_BOLD, fontSize=8, leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="Caption", fontName=FONT_ITALIC, fontSize=8.2, leading=11, alignment=TA_CENTER, textColor=MID_GRAY, spaceBefore=3, spaceAfter=8))
styles.add(ParagraphStyle(name="Equation", fontName=FONT, fontSize=10.5, leading=16, alignment=TA_CENTER, textColor=DARK, backColor=LIGHT_GRAY, borderPadding=7, spaceBefore=4, spaceAfter=8))
styles.add(ParagraphStyle(name="ReportCode", fontName="Courier", fontSize=7.6, leading=10.5, leftIndent=8, rightIndent=8, textColor=colors.black, backColor=colors.HexColor("#F8F8F8"), borderColor=colors.HexColor("#D0D0D0"), borderWidth=0.5, borderPadding=7, spaceAfter=8))
styles.add(ParagraphStyle(name="Callout", fontName=FONT, fontSize=9, leading=13, textColor=DARK, backColor=LIGHT_BLUE, borderColor=BLUE, borderWidth=0.6, borderPadding=8, spaceBefore=4, spaceAfter=8))
styles.add(ParagraphStyle(name="BulletReport", parent=styles["BodyJ"], leftIndent=14, firstLineIndent=-8, bulletIndent=3, spaceAfter=4))
styles.add(ParagraphStyle(name="Ref", fontName=FONT, fontSize=8.5, leading=12, leftIndent=16, firstLineIndent=-16, textColor=DARK, spaceAfter=5))


def P(text, style="BodyJ"):
    return Paragraph(text, styles[style])


def heading(text, level=1):
    return P(text, "H1" if level == 1 else "H2")


def bullet(text):
    return Paragraph(f"&#8226; {text}", styles["BulletReport"])


def table(data, widths, header=True, font_size=8.2, alignments=None):
    normalized = []
    for row_index, row in enumerate(data):
        cell_style = "TableHeader" if header and row_index == 0 else "Small"
        normalized.append([cell if hasattr(cell, "wrap") else P(escape(str(cell)), cell_style) for cell in row])
    t = Table(normalized, colWidths=widths, repeatRows=1 if header else 0, hAlign="CENTER")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8B8B8")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD)]
    if alignments:
        for col, alignment in enumerate(alignments):
            commands.append(("ALIGN", (col, 1 if header else 0), (col, -1), alignment))
    t.setStyle(TableStyle(commands))
    return t


def figure(filename, caption, width=15.8 * cm):
    path = PLOTS / filename
    if not path.exists():
        return P(f"Figure unavailable: {escape(filename)}", "Callout")
    grayscale = BytesIO()
    PILImage.open(path).convert("L").save(grayscale, format="PNG")
    grayscale.seek(0)
    image = Image(grayscale)
    image._report_buffer = grayscale
    image._restrictSize(width, 10.2 * cm)
    return KeepTogether([image, P(caption, "Caption")])


def strip_diagram():
    width, height = 445, 150
    d = Drawing(width, height)
    d.add(String(5, 136, "Horizontal strip decomposition with one halo row per neighbor", fontName=FONT_BOLD, fontSize=10, fillColor=NAVY))
    rows = [("Rank 0", 103, colors.HexColor("#D8D8D8")), ("Rank 1", 64, colors.HexColor("#E5E5E5")), ("Rank 2", 25, colors.HexColor("#C8C8C8"))]
    for name, y, fill in rows:
        d.add(String(5, y + 10, name, fontName=FONT_BOLD, fontSize=8, fillColor=DARK))
        d.add(Rect(55, y, 45, 28, fillColor=LIGHT_GRAY, strokeColor=MID_GRAY))
        d.add(Rect(100, y, 285, 28, fillColor=fill, strokeColor=NAVY))
        d.add(Rect(385, y, 45, 28, fillColor=LIGHT_GRAY, strokeColor=MID_GRAY))
        d.add(String(62, y + 10, "top halo", fontName=FONT, fontSize=6.5, fillColor=MID_GRAY))
        d.add(String(210, y + 10, "owned rows", fontName=FONT_BOLD, fontSize=8, fillColor=DARK))
        d.add(String(391, y + 10, "bottom", fontName=FONT, fontSize=6.5, fillColor=MID_GRAY))
    for y1, y2 in [(103, 64), (64, 25)]:
        d.add(Line(365, y1, 405, y2 + 28, strokeColor=BLUE, strokeWidth=1.5))
        d.add(Line(120, y1, 80, y2 + 28, strokeColor=GREEN, strokeWidth=1.5))
    d.add(String(135, 4, "Only adjacent ranks exchange complete boundary rows every time step.", fontName=FONT_ITALIC, fontSize=7.5, fillColor=MID_GRAY))
    return KeepTogether([d, P("Figure 1. One-dimensional decomposition of the 2D grid along its row dimension.", "Caption")])


def overlap_diagram():
    d = Drawing(445, 112)
    d.add(String(5, 96, "Overlapped iteration timeline", fontName=FONT_BOLD, fontSize=10, fillColor=NAVY))
    x0, y, h = 10, 44, 30
    blocks = [
        ("Post Irecv/Isend", 82, LIGHT_BLUE),
        ("Compute interior rows", 184, colors.HexColor("#E5E5E5")),
        ("Waitall", 66, colors.HexColor("#D6D6D6")),
        ("Compute edge rows", 91, colors.HexColor("#C8C8C8")),
    ]
    x = x0
    for label, w, fill in blocks:
        d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=NAVY))
        d.add(String(x + 5, y + 11, label, fontName=FONT, fontSize=7.2, fillColor=DARK))
        x += w
    d.add(Line(94, 36, 278, 36, strokeColor=BLUE, strokeWidth=2))
    d.add(String(128, 22, "halo communication may progress", fontName=FONT_ITALIC, fontSize=7.5, fillColor=BLUE))
    d.add(String(10, 6, "MPI calls remain on the main thread; OpenMP computes rows using static scheduling.", fontName=FONT, fontSize=7.5, fillColor=MID_GRAY))
    return KeepTogether([d, P("Figure 2. Communication/computation overlap used in hybrid_overlap mode.", "Caption")])


def measured_summary(df):
    med = df.groupby(["size", "steps", "mode", "ranks", "threads", "tile"], as_index=False)["total_s"].median()
    med["cores"] = med.ranks * med.threads
    rows = []
    for n in sorted(med["size"].unique()):
        g = med[med["size"] == n]
        baseline_row = g[g["mode"] == "seq_tiled"].sort_values("total_s").iloc[0]
        eligible = g[(g["cores"] >= 2) & g["mode"].isin(["mpi", "omp", "hybrid", "hybrid_overlap"])]
        best = eligible.sort_values("total_s").iloc[0]
        label = {"mpi": "MPI", "omp": "OpenMP", "hybrid": "Hybrid", "hybrid_overlap": "Hybrid overlap"}[best["mode"]]
        rows.append([
            f"{n} x {n}", int(baseline_row["steps"]), int(baseline_row["tile"]),
            f"{baseline_row['total_s']:.6f}", f"{label} {int(best['ranks'])}x{int(best['threads'])}",
            f"{best['total_s']:.6f}", f"{baseline_row['total_s']/best['total_s']:.2f}x",
        ])
    return rows


def build_report():
    if not RESULTS.exists():
        raise SystemExit(f"Missing benchmark data: {RESULTS}")
    df = pd.read_csv(RESULTS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = ReportDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=2.1 * cm, rightMargin=2.1 * cm,
        topMargin=1.9 * cm, bottomMargin=1.9 * cm,
        title="Parallel 2D Heat Diffusion using Hybrid MPI and OpenMP",
        author="Sajjad Ahmed, Wali Uddin, Saad Zaidi",
        subject="Parallel and Distributed Computing Project Report",
    )
    story = []

    # Title page
    story += [Spacer(1, 2.0 * cm), P("PARALLEL AND DISTRIBUTED COMPUTING", "TitleSub"), Spacer(1, 0.7 * cm)]
    story += [P("Parallel 2D Heat Diffusion<br/>using Hybrid MPI and OpenMP", "TitleBig")]
    story += [Spacer(1, 0.5 * cm), P("Complete Project Report", "TitleSub"), Spacer(1, 1.5 * cm)]
    meta = [
        [P("Course", "MetaLabel"), P("Parallel and Distributed Computing (PDC)", "Small")],
        [P("Instructor", "MetaLabel"), P("Minhal Raza", "Small")],
        [P("Group Members", "MetaLabel"), P("Sajjad Ahmed (23K-0754)<br/>Wali Uddin (23K-0719)<br/>Saad Zaidi (23K-0874)", "Small")],
        [P("Project", "MetaLabel"), P("University Course Project", "Small")],
        [P("Submission Date", "MetaLabel"), P("November 2026", "Small")],
    ]
    mt = Table(meta, colWidths=[4.1 * cm, 9.1 * cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), NAVY), ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8B8B8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("BACKGROUND", (1, 0), (1, -1), colors.white),
    ]))
    story += [mt, Spacer(1, 1.5 * cm), P("A reproducible study of shared-memory, distributed-memory, and hybrid parallelization for an explicit finite-difference heat equation solver.", "Meta")]

    story += [NextPageTemplate("Body"), PageBreak()]
    story += [heading("Abstract")]
    story += [P(
        "This project implements and evaluates a two-dimensional heat diffusion solver using sequential, OpenMP, MPI, and hybrid MPI/OpenMP execution. The governing heat equation is discretized with an explicit five-point finite-difference stencil and stable time step. Six execution modes are provided: naive sequential, cache-tiled sequential, OpenMP-only, MPI-only, hybrid with blocking halo exchange, and hybrid with nonblocking overlapped communication. The distributed design partitions the domain into uneven horizontal strips, uses halo rows for nearest-neighbor dependencies, and supports deterministic global or rank-local initialization. Correctness is established by comparison with an independent sequential reference, a discrete sine eigenmode with known decay, non-divisible domain sizes, and sampled stencil recomputation. All automated regression cases passed within a relative tolerance of 10<super>-10</super>. The benchmark data contains 381 measured runs on an AMD Ryzen 5 3600 system. On a 2048 x 2048 grid, four MPI ranks achieved 0.609 s for 100 steps compared with a tuned tiled baseline of 0.723 s, a 1.19x speedup. Small problems were dominated by startup and synchronization overhead, while short 8192 x 8192 runs were dominated by initialization and final gathering. The results demonstrate correct hybrid parallelization and show how memory bandwidth, communication overhead, workload size, and process/thread selection determine observed scalability."
    )]
    story += [P("<b>Keywords:</b> heat equation, finite differences, MPI, OpenMP, hybrid parallelism, halo exchange, domain decomposition, high-performance computing", "Small")]

    story += [heading("Table of Contents")]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(name="TOC1", fontName=FONT_BOLD, fontSize=9.5, leading=15, leftIndent=0, firstLineIndent=0, textColor=NAVY),
        ParagraphStyle(name="TOC2", fontName=FONT, fontSize=8.5, leading=13, leftIndent=15, firstLineIndent=0, textColor=DARK),
    ]
    story += [toc, PageBreak()]

    story += [heading("1. Introduction")]
    story += [heading("1.1 Background", 2)]
    story += [P(
        "Heat diffusion is a standard model for studying numerical simulation and parallel computing. Each time step updates every interior grid point using only its four immediate neighbors. This local dependency structure makes the stencil naturally parallel, but practical speedup is limited by memory traffic, synchronization, halo communication, and the amount of computation assigned to each worker. The problem therefore provides a useful comparison of shared-memory OpenMP, distributed-memory MPI, and hybrid programming."
    )]
    story += [heading("1.2 Problem Statement", 2)]
    story += [P(
        "The objective is to solve transient heat diffusion on a square two-dimensional domain while preserving numerical correctness across different parallel decompositions. The implementation must handle grids that are not evenly divisible by the number of MPI processes, retain fixed boundary values, use reproducible initial conditions, and expose timing data that separates computation from communication."
    )]
    story += [heading("1.3 Objectives", 2)]
    for item in [
        "Implement a stable, double-precision five-point finite-difference solver with fixed Dirichlet boundaries.",
        "Develop six comparable execution modes covering sequential, OpenMP, MPI, and hybrid designs.",
        "Overlap halo communication with useful computation using nonblocking MPI operations.",
        "Verify every mode against a trusted sequential solution and an analytic discrete eigenmode.",
        "Measure execution time, speedup, efficiency, updates per second, and computation/communication cost.",
        "Provide reproducible build, test, benchmark, and plotting workflows.",
    ]:
        story.append(bullet(item))
    story += [heading("1.4 Scope", 2)]
    story += [P(
        "The implemented scope is the two-dimensional equation on square grids. Large runs are guarded by an available-memory check and MPI count limits. The project targets Linux with OpenMPI or MPICH, while the recorded measurements were produced on the available Windows development machine with Microsoft MPI. A three-dimensional extension was treated as optional and was not included because it would increase validation and memory risk without improving the core 2D comparison."
    )]

    story += [heading("2. Mathematical Model")]
    story += [heading("2.1 Governing Equation", 2)]
    story += [P("For a homogeneous material with constant thermal diffusivity <i>alpha</i>, the two-dimensional heat equation is:")]
    story += [P("du/dt = alpha (d<super>2</super>u/dx<super>2</super> + d<super>2</super>u/dy<super>2</super>)", "Equation")]
    story += [P("Here, <i>u(x,y,t)</i> is temperature, <i>alpha</i> is thermal diffusivity, and <i>t</i> is time.")]
    story += [heading("2.2 Explicit Five-Point Discretization", 2)]
    story += [P(
        "Using equal spacing <i>dx</i> in both directions and forward Euler integration in time gives the following update for every interior grid point:"
    )]
    story += [P("u<super>n+1</super><sub>i,j</sub> = u<super>n</super><sub>i,j</sub> + r (u<super>n</super><sub>i-1,j</sub> + u<super>n</super><sub>i+1,j</sub> + u<super>n</super><sub>i,j-1</sub> + u<super>n</super><sub>i,j+1</sub> - 4u<super>n</super><sub>i,j</sub>)", "Equation")]
    story += [P("where r = alpha dt / dx<super>2</super>. Two buffers are used so that all values at step <i>n+1</i> depend only on step <i>n</i>. The buffer handles are swapped after each iteration, avoiding a full-grid copy.")]
    story += [heading("2.3 Stability and Boundary Conditions", 2)]
    story += [P("The explicit two-dimensional stencil is stable when:")]
    story += [P("dt <= dx<super>2</super> / (4 alpha)", "Equation")]
    story += [P(
        "The default time step is 90% of this bound. A user-supplied unstable value is rejected. All outer grid cells use fixed Dirichlet values and are never modified during time stepping. The default boundary temperature is zero."
    )]
    story += [heading("2.4 Initial Conditions", 2)]
    init_data = [
        ["Condition", "Purpose", "Definition"],
        ["Hot spots", "Demonstration and visualization", "Two deterministic Gaussian temperature peaks"],
        ["Random", "Reproducible stress testing", "Coordinate-hashed field controlled by a 64-bit seed"],
        ["Sine", "Analytic verification", "sin(pi y/(N-1)) sin(pi x/(N-1))"],
    ]
    story += [table(init_data, [2.7 * cm, 5.0 * cm, 8.0 * cm])]

    story += [heading("3. System Design")]
    story += [heading("3.1 Execution Modes", 2)]
    modes = [
        ["Mode", "Processes", "Threads", "Main technique"],
        ["seq_naive", "1", "1", "Plain row-major nested stencil loops"],
        ["seq_tiled", "1", "1", "Cache tiles with configurable block size"],
        ["omp", "1", "T", "Static OpenMP work sharing and SIMD"],
        ["mpi", "P", "1", "Horizontal strips and blocking halo exchange"],
        ["hybrid", "P", "T", "MPI halo exchange followed by OpenMP update"],
        ["hybrid_overlap", "P", "T", "Nonblocking exchange overlapped with interior rows"],
    ]
    story += [table(modes, [3.1 * cm, 2.2 * cm, 2.2 * cm, 8.2 * cm])]
    story += [heading("3.2 Domain Decomposition", 2), strip_diagram()]
    story += [P(
        "The global N x N domain is divided into contiguous horizontal strips. If N is not divisible by the process count, the first N mod P ranks receive one additional row. Counts and displacements are computed on every rank, allowing MPI_Scatterv and MPI_Gatherv to distribute and collect uneven strips. Each rank allocates its owned rows plus one halo above and one halo below. MPI_PROC_NULL represents the missing neighbor at the physical top and bottom boundaries."
    )]
    story += [heading("3.3 Halo Exchange", 2)]
    story += [P(
        "Each time step requires the last owned row from the upper neighbor and the first owned row from the lower neighbor. MPI-only and non-overlapped hybrid modes use two MPI_Sendrecv calls. This avoids deadlock while keeping the logic explicit. The overlapped mode posts two receives and two sends, computes rows 2 through local_rows-1, waits for communication, and then computes the first and last owned rows."
    ), overlap_diagram()]
    story += [heading("3.4 Threading and Memory Layout", 2)]
    for item in [
        "MPI is initialized with MPI_THREAD_FUNNELED; only the main thread makes MPI calls.",
        "Grid storage is a contiguous one-dimensional row-major allocation for predictable access and MPI transfers.",
        "OpenMP static scheduling assigns stable row ranges to threads; the innermost column loop remains unit stride.",
        "SIMD directives encourage compiler vectorization, and tile loops use collapse(2) where appropriate.",
        "First-touch initialization is parallelized so pages can be placed near the threads that later use them on NUMA systems.",
        "The release build enables -O3 and -march=native for the tested compiler.",
    ]:
        story.append(bullet(item))

    story += [heading("4. Implementation")]
    story += [heading("4.1 Software Structure", 2)]
    files = [
        ["Component", "Responsibility"],
        ["src/main.cpp", "CLI parsing, initialization, stencil kernels, MPI distribution, verification, timing, output"],
        ["CMakeLists.txt / Makefile", "C++17 build, MPI/OpenMP discovery, release flags, CTest integration"],
        ["scripts/verify.py", "Cross-mode regression tests and discrete sine-mode validation"],
        ["scripts/benchmark.py", "Warmups, repetitions, core/split/tile sweeps, measured CSV output"],
        ["scripts/plot_results.py", "Time, speedup, efficiency, split, overlap, breakdown, and tile plots"],
        ["scripts/plot_heatmaps.py", "Temperature-field visualization at selected time steps"],
    ]
    story += [table(files, [4.5 * cm, 11.2 * cm])]
    story += [heading("4.2 Command-Line Interface", 2)]
    cli = [
        ["Option", "Meaning"],
        ["--size N / --steps S", "Square grid dimension and number of time steps"],
        ["--alpha / --dx / --dt", "Physical and numerical parameters; dt is automatic by default"],
        ["--mode", "Select one of the six execution modes"],
        ["--threads T / --tile B", "OpenMP thread count and tile dimension"],
        ["--init / --seed", "Hot spots, random, or sine initialization and reproducible seed"],
        ["--local-init", "Generate each strip independently instead of scattering the initial grid"],
        ["--verify", "Compare the gathered field with an independent sequential reference"],
        ["--dump FILE", "Write a full or downsampled final field as CSV"],
        ["--output", "Emit JSON or a compact CSV line"],
    ]
    story += [table(cli, [4.2 * cm, 11.5 * cm])]
    story += [heading("4.3 Timing and Metrics", 2)]
    story += [P(
        "Timing uses MPI_Wtime on every rank. Initialization, communication, computation, and total duration are accumulated separately and reduced with MPI_MAX because parallel completion is limited by the slowest rank. Communication includes recurring halo exchange and the final gather. Throughput is reported as grid updates per second and as GFLOPS using the project convention of five floating-point operations per interior update. The JSON output also includes total heat, mean, extrema, center temperature, and correctness errors."
    )]
    story += [P("GFLOPS = 5 (N-2)<super>2</super> steps / (total_seconds x 10<super>9</super>)", "Equation")]
    story += [heading("4.4 Safety and Portability", 2)]
    story += [P(
        "The application validates all numeric inputs, rejects unstable time steps, checks the supplied MPI threading level, prevents more ranks than rows, and estimates memory before allocation. It also rejects grids exceeding the signed 32-bit count/displacement range used by traditional MPI_Scatterv and MPI_Gatherv. MPI_Finalize is reached on normal completion; fatal distributed errors call MPI_Abort to prevent ranks from hanging."
    )]

    story += [heading("5. Verification and Testing")]
    story += [heading("5.1 Reference Comparison", 2)]
    story += [P(
        "For --verify, rank 0 reconstructs the same initial field and evolves it with a separate plain sequential reference routine. Each parallel result is compared point by point using max |parallel-reference|/(1+|reference|). The acceptance threshold is 10<super>-10</super>, avoiding inappropriate exact floating-point equality."
    )]
    tests = [
        ["Coverage", "Cases"],
        ["All execution modes", "seq_naive, seq_tiled, omp, mpi, hybrid, hybrid_overlap"],
        ["Initial conditions", "Fixed hot spots, seeded random, analytic sine mode"],
        ["Uneven decomposition", "131 x 131 and 129 x 129 grids across 3 or 4 ranks"],
        ["Process/thread splits", "1x4, 2x2, and 4x1 for hybrid overlap"],
        ["Larger regression", "1024 x 1024, 2 ranks x 2 threads"],
        ["Local initialization", "Seeded random fields generated from global coordinates"],
    ]
    story += [table(tests, [4.5 * cm, 11.2 * cm])]
    story += [heading("5.2 Analytic Discrete Sine Mode", 2)]
    story += [P(
        "The sine initialization is an eigenvector of the discrete Laplacian. For theta = pi/(N-1), its amplitude after one time step is multiplied by 1 + 4r(cos(theta)-1). After S steps, the exact discrete amplitude is this factor raised to S. The test checks both pointwise error and the corresponding total-heat decay. This validates time integration independently of the general sequential reference."
    )]
    story += [heading("5.3 Sample and Conservation Diagnostics", 2)]
    story += [P(
        "During the final iteration, three globally selected points are recomputed directly from the old buffer before swapping. Their reduced values are compared with the gathered final grid. The reported sum and mean provide a second diagnostic: with zero-temperature boundaries, heat should diffuse outward smoothly, and all execution modes for the same configuration should report the same aggregate values."
    )]
    story += [P("<b>Observed test outcome:</b> CTest and the complete Python regression suite passed. Every reported reference, analytic, and sampled error was zero at the printed precision.", "Callout")]

    story += [heading("6. Experimental Methodology")]
    story += [heading("6.1 Test Platform", 2)]
    platform = [
        ["Item", "Measured environment"],
        ["CPU", "AMD Ryzen 5 3600, 6 physical cores / 12 logical processors"],
        ["Memory", "7.93 GiB RAM"],
        ["Operating system", "Microsoft Windows 11 Pro"],
        ["C++ compiler", "GCC 16.2.0, MSYS2 UCRT64"],
        ["MPI", "Microsoft MPI 10.1.12498.52"],
        ["Build system", "CMake 4.4.4 with Ninja"],
        ["Analysis", "Python, pandas, Matplotlib"],
    ]
    story += [table(platform, [4.4 * cm, 11.3 * cm])]
    story += [heading("6.2 Benchmark Procedure", 2)]
    for item in [
        "One unrecorded warmup precedes each configuration.",
        "The benchmark records only completed measured runs; no values are fabricated or extrapolated.",
        "Total core counts of 1, 2, 4, and 8 are tested where possible, with multiple MPI/OpenMP splits.",
        "Sequential tile sizes 32, 64, 128, and 256 are swept on large grids.",
        "The tuned sequential tiled run is the speedup baseline for each grid size.",
        "Shorter step counts are used for large grids because the available machine has 8 GiB RAM and limited benchmark time.",
    ]:
        story.append(bullet(item))
    repetitions = [
        ["Grid", "Steps", "Recorded repetitions", "Reason"],
        ["128 x 128", "10", "5", "Quick pipeline and overhead behavior"],
        ["256 x 256", "10", "5", "Quick pipeline and overhead behavior"],
        ["2048 x 2048", "100", "2", "Main scalability comparison"],
        ["4096 x 4096", "20", "1", "Memory and runtime constraint"],
        ["8192 x 8192", "5", "1", "Memory guard and short feasibility run"],
    ]
    story += [table(repetitions, [3.4 * cm, 2.0 * cm, 3.6 * cm, 6.7 * cm])]

    story += [heading("7. Results and Discussion")]
    story += [heading("7.1 Overall Measured Performance", 2)]
    summary = [["Grid", "Steps", "Tile", "Baseline (s)", "Best >=2 cores", "Time (s)", "Speedup"]] + measured_summary(df)
    story += [table(summary, [2.7 * cm, 1.3 * cm, 1.2 * cm, 2.3 * cm, 3.8 * cm, 2.2 * cm, 1.8 * cm], font_size=7.5)]
    story += [P(
        "The smallest grids show slowdown under parallel execution because their useful work is too short to amortize process launch, synchronization, and data movement. The 2048 x 2048 grid is the clearest positive result: four MPI ranks reduce total time from 0.723 s to 0.609 s. The 4096 x 4096 run shows a smaller gain because it uses only 20 steps, so initialization and gathering represent a larger portion of total time. The five-step 8192 x 8192 experiment is primarily a memory-feasibility and pipeline test rather than a steady-state scalability measurement."
    )]
    story += [figure("2048_total_s.png", "Figure 3. Total execution time versus total cores for the 2048 x 2048 grid.")]
    story += [figure("2048_speedup.png", "Figure 4. Speedup relative to the best measured single-thread tiled baseline.")]
    story += [heading("7.2 MPI, OpenMP, and Hybrid Splits", 2)]
    story += [figure("2048_splits.png", "Figure 5. Process/thread split comparison at 2048 x 2048.")]
    story += [P(
        "The fastest 2048 x 2048 configuration uses four MPI processes and one thread each. On this single-socket desktop, additional OpenMP layers do not consistently improve total time. MPI-only strips have simple scheduling and may benefit from independent address spaces, whereas hybrid runs incur both MPI and OpenMP overhead. Eight logical processors also exceed the six physical cores, so simultaneous multithreading does not guarantee additional memory bandwidth."
    )]
    story += [heading("7.3 Overlapped versus Non-overlapped Communication", 2)]
    story += [figure("2048_overlap.png", "Figure 6. Blocking hybrid and overlapped hybrid execution time.")]
    story += [P(
        "At the representative 2-rank x 2-thread split, non-overlapped hybrid took approximately 0.707 s and overlapped hybrid took 0.773 s. The nonblocking algorithm is correct, but overlap introduces request management, additional kernel launches, and a barrier between interior and edge work. On one physical machine, shared-memory MPI transfers are already fast, leaving little communication latency to hide. Overlap is more likely to help across networked nodes or for larger computation-to-synchronization ratios."
    )]
    story += [heading("7.4 Computation and Communication Breakdown", 2)]
    story += [figure("2048_breakdown.png", "Figure 7. Measured computation and communication components at 2048 x 2048.")]
    story += [P(
        "As process count increases, each rank owns fewer rows while still exchanging two full-width halo rows per step. This increases the communication-to-computation ratio. The rank-max reporting method also exposes load imbalance: when strips differ by one row, total completion follows the rank with the largest local duration. The imbalance is small for large grids but is deliberately covered by correctness tests."
    )]
    story += [heading("7.5 Tile-Size Behavior", 2)]
    story += [figure("2048_tiles.png", "Figure 8. Sequential tile-size sweep for the 2048 x 2048 grid.")]
    story += [P(
        "A tile size of 256 was the fastest measured choice for the large sequential runs, while 64 performed best on the smallest quick cases. Tile performance depends on loop overhead, cache hierarchy, compiler vectorization, and memory prefetching. The result supports making tile size configurable rather than embedding one universal value."
    )]
    story += [heading("7.6 Temperature Evolution", 2)]
    story += [figure("heatmaps.png", "Figure 9. Deterministic hot-spot field at 0, 50, and 200 time steps.", width=16.2 * cm)]
    story += [P(
        "The temperature peaks spread outward and decrease in magnitude while the zero boundary remains fixed. This qualitative behavior is consistent with diffusion: sharp gradients are smoothed, no new extrema are introduced by the stable explicit update, and heat gradually exits through the cold boundary."
    )]
    story += [heading("7.7 Correctness of Aggregate Results", 2)]
    sums = df.groupby(["size", "steps"])["sum"].agg(["min", "max"]).reset_index()
    sum_rows = [["Grid", "Steps", "Minimum sum", "Maximum sum", "Difference"]]
    for r in sums.itertuples():
        sum_rows.append([f"{r.size} x {r.size}", r.steps, f"{r.min:.6g}", f"{r.max:.6g}", f"{r.max-r.min:.3g}"])
    story += [table(sum_rows, [3.2 * cm, 2.0 * cm, 3.5 * cm, 3.5 * cm, 3.0 * cm])]
    story += [P(
        "For every grid/step group, all recorded execution modes produced the same total heat to the stored CSV precision. Together with pointwise verification, the analytic mode, and sampled final-step checks, this provides strong evidence that decomposition and halo exchange preserve the numerical result."
    )]

    story += [heading("8. Limitations and Threats to Validity")]
    for item in [
        "The benchmark host is Windows with Microsoft MPI, while the intended deployment environment is Linux with OpenMPI or MPICH. Correctness is portable through standard MPI/OpenMP APIs, but exact timings will differ.",
        "The 4096 and 8192 grids have one measured repetition. Their results show feasibility but have limited statistical confidence.",
        "The 8192 grid uses five time steps, so setup and gather costs dominate. It should not be used to claim steady-state scalability.",
        "The 16384 x 16384 case and 1000-step large-grid sweeps were not run because the host has only 7.93 GiB RAM.",
        "All ranks ran on one physical computer. Inter-node network latency and bandwidth were not measured, so the benefit of nonblocking overlap on a cluster remains open.",
        "The GFLOPS convention follows the project requirement of five operations per update; alternate operation-count conventions would change the reported rate, though not elapsed time.",
        "The MPI Scatterv/Gatherv implementation uses signed int counts and displacements and therefore rejects grids exceeding that API range.",
    ]:
        story.append(bullet(item))

    story += [heading("9. Conclusion")]
    story += [P(
        "The project successfully implements a correct and configurable 2D heat diffusion solver using sequential, OpenMP, MPI, and hybrid parallelism. The code handles uneven strip decomposition, reproducible initialization, fixed boundaries, blocking and nonblocking halo exchange, tiled/vector-friendly computation, rank-max timing, automated verification, and reproducible analysis. Every regression and analytic test passed. The measured data shows that parallelism becomes useful only after the problem contains enough work to amortize its overhead: four MPI ranks achieved the best 2048 x 2048 result, while small and very short runs did not benefit. On the tested single-node platform, communication overlap added overhead rather than reducing time, which is a valid result and highlights the importance of matching an optimization to the hardware and workload."
    )]
    story += [heading("9.1 Future Work", 2)]
    for item in [
        "Repeat the large-grid experiments for 1000 steps on a Linux cluster with substantially more RAM.",
        "Measure inter-node communication and determine the crossover point where overlap becomes beneficial.",
        "Use MPI large-count interfaces or chunked collectives for global arrays beyond signed-int displacement limits.",
        "Add checkpoint output and parallel MPI-IO for long simulations.",
        "Evaluate a two-dimensional Cartesian decomposition for improved surface-to-volume ratio at high process counts.",
        "Implement the optional 3D seven-point stencil after establishing an adequate memory and validation environment.",
    ]:
        story.append(bullet(item))

    story += [heading("10. Reproducibility Guide")]
    story += [heading("10.1 Linux Build and Test", 2)]
    story += [P("cmake -S . -B build -DCMAKE_BUILD_TYPE=Release<br/>cmake --build build -j<br/>ctest --test-dir build --output-on-failure<br/>python3 scripts/verify.py --binary build/heat", "ReportCode")]
    story += [heading("10.2 Example Runs", 2)]
    story += [P("./build/heat --mode seq_tiled --size 2048 --steps 1000 --tile 256 --verify<br/>OMP_PROC_BIND=close OMP_PLACES=cores mpirun -np 4 ./build/heat --mode hybrid --threads 2 --size 2048 --steps 1000 --verify<br/>OMP_PROC_BIND=close OMP_PLACES=cores mpirun -np 4 ./build/heat --mode hybrid_overlap --threads 2 --size 2048 --steps 1000 --verify", "ReportCode")]
    story += [heading("10.3 Benchmark and Plot Regeneration", 2)]
    story += [P("python3 scripts/benchmark.py --binary build/heat --quick --repeats 2<br/>python3 scripts/benchmark.py --binary build/heat --repeats 5<br/>python3 scripts/plot_results.py results/benchmarks.csv<br/>python3 scripts/plot_heatmaps.py --binary build/heat<br/>python3 scripts/generate_report.py", "ReportCode")]

    story += [heading("References")]
    refs = [
        "[1] Message Passing Interface Forum, <i>MPI: A Message-Passing Interface Standard, Version 4.1</i>, 2023.",
        "[2] OpenMP Architecture Review Board, <i>OpenMP Application Programming Interface, Version 5.2</i>, 2021.",
        "[3] W. Gropp, E. Lusk, and A. Skjellum, <i>Using MPI: Portable Parallel Programming with the Message-Passing Interface</i>, 3rd ed., MIT Press, 2014.",
        "[4] T. Rauber and G. Ruenger, <i>Parallel Programming: For Multicore and Cluster Systems</i>, 3rd ed., Springer, 2023.",
        "[5] R. J. LeVeque, <i>Finite Difference Methods for Ordinary and Partial Differential Equations</i>, SIAM, 2007.",
        "[6] G. H. Golub and J. M. Ortega, <i>Scientific Computing and Differential Equations: An Introduction to Numerical Methods</i>, Academic Press, 1992.",
    ]
    for ref in refs:
        story.append(P(ref, "Ref"))

    story += [PageBreak(), heading("Appendix A: Deliverables")]
    story += [P(
        "The repository preserves the raw sweep CSV files as well as the combined benchmark table. All figures in this report are generated from the committed measurements, except the temperature heat map, which is generated from deterministic small-grid solver output."
    )]
    deliverables = [
        ["Deliverable", "Location"],
        ["C++17 solver", "src/main.cpp"],
        ["Build configuration", "CMakeLists.txt and Makefile"],
        ["Automated tests", "scripts/verify.py and CTest"],
        ["Benchmark automation", "scripts/benchmark.py"],
        ["Measured data", "results/benchmarks.csv"],
        ["Generated plots", "results/plots/"],
        ["Project documentation", "README.md"],
        ["Project report", "docs/PDC_Heat_Diffusion_Project_Report.pdf"],
    ]
    story += [table(deliverables, [5.0 * cm, 10.7 * cm])]

    doc.multiBuild(story)
    print(f"Generated {OUTPUT}")


if __name__ == "__main__":
    build_report()
