#!/usr/bin/env python3
"""Build the manuscript figures.

Palette is Okabe-Ito, restricted to subsets that pass the six-check validator
(lightness band, chroma floor, CVD separation, normal-vision floor, contrast)
against a light surface. Typography matches the manuscript body face.
"""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, VERM, GREEN = "#0072B2", "#D55E00", "#009E73"
PURPLE = "#CC79A7"          # Okabe-Ito reddish purple, for the human arm
INK, INK2, MUTED = "#1a1a1a", "#444444", "#8c8c8c"
GRID, SURFACE = "#e3e3e0", "#ffffff"
# Very light tints of the same hues, for row banding and panel wash. Tints are
# background only and never carry data, so they are exempt from the
# categorical separation checks.
BAND, WASH = "#f4f6f8", "#fbfcfd"

mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 10,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.linewidth": 0.8,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "text.color": INK,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "legend.frameon": False,
    "legend.fontsize": 9.5,
})


MAX_PX = 1200          # house rule: draft JPG no larger than 1200 x 1200


WANT_PNG = "--png" in sys.argv     # submission upload; the default is JPG only


def save_fig(fig, stem, dpi=400, **kw):
    """Write the draft JPG, and the full-resolution PNG when asked.

    The manuscript embeds the JPG, capped at MAX_PX on the longer side; its
    dpi is derived from the figure's own size so the long side lands on the
    cap rather than being resampled afterwards. The house rules call for PNG
    at submission, so `make_figures.py --png` writes those alongside.
    """
    w_in, h_in = fig.get_size_inches()
    fig.savefig(OUT / f"{stem}.jpg", dpi=MAX_PX / max(w_in, h_in),
                pil_kwargs={"quality": 92}, **kw)
    if WANT_PNG:
        fig.savefig(OUT / f"{stem}.png", dpi=dpi, **kw)


def band_rows(ax, ys, height=0.9):
    """Alternating row wash, so a long label tracks to the right mark."""
    for k, y in enumerate(ys):
        if k % 2 == 0:
            ax.axhspan(y - height / 2, y + height / 2, color=BAND,
                       lw=0, zorder=0)


def recessive(ax, xgrid=True, ygrid=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    if xgrid:
        ax.xaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.7)


# ---------------------------------------------------------------- Figure 1
def figure1():
    """Study flow. Boxes carry the count; side notes carry the exclusions."""
    fig, ax = plt.subplots(figsize=(6.5, 5.3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0.6, 12.4)
    ax.axis("off")

    main = [
        (11.5, "Search hits returned by 16 frozen seed queries", "4,000"),
        (9.6, "Unique videos after deduplication by video id", "2,641"),
        (7.7, "Passed deterministic metadata gates", "1,887"),
        (5.8, "Passed the vision-language model eligibility classifier", "1,769"),
        (3.9, "Frames extracted", "1,767"),
        (2.0, "Coding-ready corpus, dual-coded by both models", "1,635"),
    ]
    side = [
        (10.55, "1,359 duplicate records removed"),
        (8.65, "754 excluded: duration outside 2-60 min, non-public,\nage-restricted, live, or no audio track"),
        (6.75, "118 excluded: not a guided session (music or\nsoundscape only, or a lecture about meditation)"),
        (4.85, "2 excluded: frame extraction failed"),
        (2.95, "132 excluded: no transcript obtainable"),
    ]

    for y, label, n in main:
        box = FancyBboxPatch((0.35, y - 0.56), 5.3, 1.12,
                             boxstyle="round,pad=0.02,rounding_size=0.08",
                             linewidth=0.9, edgecolor=MUTED, facecolor="#f7f7f5",
                             zorder=2)
        ax.add_patch(box)
        ax.text(0.60, y + 0.21, label, va="center", ha="left", fontsize=9.0, color=INK)
        ax.text(0.60, y - 0.26, f"n = {n}", va="center", ha="left",
                fontsize=10.2, color=BLUE, fontweight="bold")

    for i in range(len(main) - 1):
        y0 = main[i][0] - 0.56
        y1 = main[i + 1][0] + 0.56
        ax.add_patch(FancyArrowPatch((1.6, y0), (1.6, y1), arrowstyle="-|>",
                                     mutation_scale=11, linewidth=0.9,
                                     color=INK2, zorder=1))

    for y, text in side:
        ax.plot([1.6, 2.75], [y, y], color=MUTED, lw=0.8, zorder=1)
        ax.add_patch(FancyArrowPatch((2.75, y), (3.00, y), arrowstyle="-|>",
                                     mutation_scale=9, linewidth=0.8,
                                     color=MUTED, zorder=1))
        ax.text(3.12, y, text, va="center", ha="left", fontsize=8.0, color=INK2)

    ax.text(0.35, 1.0, "Dual coding yielded 3,270 coded observations per variable. Reliability "
                       "side-arms\nre-coded 396 videos (test-retest) and 408 videos (prompt sensitivity).",
            va="center", ha="left", fontsize=8.0, color=MUTED)

    fig.tight_layout()
    save_fig(fig, "figure1_flow", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 2
def figure2():
    """Per-variable reliability across the three arms, against the 0.60 gate."""
    rel = json.loads((ROOT / "data_main/05_reliability/reliability_report.json").read_text())
    arms = [("inter_model", "Inter-model", BLUE, "o"),
            ("test_retest", "Test-retest", VERM, "s"),
            ("prompt_sensitivity", "Prompt sensitivity", GREEN, "^")]
    # The human arm appears only once the registered subsample is coded.
    ha = rel.get("human_agreement") or {}
    if any(isinstance(v, (int, float)) for v in ha.values()):
        arms.append(("human_agreement", "VLM vs human", PURPLE, "D"))
    labels = {
        "nature_imagery_present": "Nature imagery present",
        "technique": "Technique",
        "posture_or_mudra_shown": "Posture or mudra shown",
        "setting_imagery": "Setting imagery",
        "visual_breathing_guide": "Visual breathing guide",
        "presenter_visibility": "Presenter visibility",
        "visual_verbal_congruence": "Visual-verbal congruence",
        "onscreen_text_overlay": "On-screen text overlay",
        "background_sound_type": "Background sound type",
    }
    order = sorted(labels, key=lambda k: rel["inter_model"][k], reverse=True)

    fig, ax = plt.subplots(figsize=(6.5, 4.1))
    recessive(ax, xgrid=True)
    ys = list(range(len(order)))[::-1]

    ax.axvspan(0, 0.60, color="#f2f2ef", zorder=0)
    ax.axvline(0.60, color=INK2, lw=1.0, ls=(0, (4, 2)), zorder=1)
    ax.text(0.575, 0.15, "inclusion gate, 0.60",
            ha="right", va="bottom", fontsize=8.5, color=INK2, rotation=90)

    def val(key, k):
        v = rel.get(key, {}).get(k)
        return v if isinstance(v, (int, float)) else None

    for key, name, col, mk in arms:
        pts = [(val(key, k), y) for k, y in zip(order, ys)]
        pts = [(x, y) for x, y in pts if x is not None]
        ax.scatter([x for x, _ in pts], [y for _, y in pts], s=42,
                   facecolor=col, edgecolor=SURFACE,
                   linewidth=1.2, marker=mk, label=name, zorder=3)

    for y, k in zip(ys, order):
        got = [val(a, k) for a, _, _, _ in arms]
        got = [x for x in got if x is not None]
        lo, hi = min(got), max(got)
        ax.plot([lo, hi], [y, y], color=GRID, lw=1.6, zorder=2)
        ax.text(rel["inter_model"][k] - 0.022, y, f"{rel['inter_model'][k]:.2f}",
                ha="right", va="center", fontsize=8.8, color=INK2)

    ax.set_yticks(ys)
    ax.set_yticklabels([labels[k] for k in order], fontsize=9.5)
    ax.set_xlim(0, 1.04)
    ax.set_ylim(-0.7, len(order) - 0.1)
    ax.set_xlabel("Krippendorff $\\alpha$")
    for y, k in zip(ys, order):
        if rel["inter_model"][k] < 0.60:
            ax.get_yticklabels()[ys.index(y)].set_color(VERM)
    ax.legend(loc="upper left", ncol=1, handletextpad=0.4, borderaxespad=0.8)

    fig.tight_layout()
    save_fig(fig, "figure2_reliability", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- Figure 3
# Rows are techniques, columns are presentation features: the cross-tab the
# title promises and the only place RQ1 is visible at a glance. A sequential
# single hue carries magnitude, and every cell is also printed, so the figure
# does not depend on colour being seen.
TECHNIQUE_LABEL = {
    "visualization_imagery": "Visualization and imagery",
    "focused_attention_breath": "Focused attention on the breath",
    "body_scan": "Body scan",
    "loving_kindness": "Loving-kindness",
    "yoga_nidra_body_relaxation": "Yoga nidra and body relaxation",
    "open_monitoring_mindfulness": "Open-monitoring mindfulness",
    "movement_walking": "Movement or walking",
    "other": "Other",
}
GROUPS = [
    ("Feature present", [("Breathing guide", "visual_breathing_guide", True),
                         ("Posture or mudra", "posture_or_mudra_shown", True),
                         ("Nature imagery", "nature_imagery_present", True)]),
    ("Presenter", [("On-screen", "presenter_visibility", "on_screen_presenter"),
                   ("Voiceover only", "presenter_visibility", "visuals_only_voiceover"),
                   ("Mixed", "presenter_visibility", "mixed")]),
    ("Setting", [("Nature", "setting_imagery", "nature"),
                 ("Abstract or animated", "setting_imagery", "abstract_animated"),
                 ("Studio", "setting_imagery", "studio"),
                 ("Text only", "setting_imagery", "text_only"),
                 ("Other", "setting_imagery", "other")]),
]


def figure3():
    """Technique by presentation feature, as percentages within technique.

    Read from the published rq1 descriptives, not from the analytic frame:
    rebuilding the frame needs the run configuration, which carries
    credentials and is not distributable, and a figure nobody else can
    regenerate is not a reproducible figure.
    """
    from matplotlib.colors import LinearSegmentedColormap
    rq1 = json.loads(
        (ROOT / "data_main/06_results/rq1_descriptives.json").read_text())
    xt = rq1["technique_by_feature"]
    techs = sorted(xt, key=lambda t: -xt[t]["n"])
    cols = [(lab, var, val) for _, g in GROUPS for lab, var, val in g]

    def count(t, var, val):
        cell = xt[t][var]
        return cell if val is True else int(cell.get(str(val), 0))

    M = [[100 * count(t, var, val) / xt[t]["n"] for _, var, val in cols]
         for t in techs]

    cmap = LinearSegmentedColormap.from_list("seq", ["#ffffff", "#0072B2"])
    fig, (axn, ax) = plt.subplots(
        1, 2, figsize=(6.5, 4.25),
        gridspec_kw={"width_ratios": [0.9, 7.1], "wspace": 0.03})

    ys = list(range(len(techs)))
    axn.barh(ys, [xt[t]["n"] for t in techs],
             height=0.62, color="#9ab7cc", edgecolor=SURFACE, linewidth=0.8)
    for y, t in zip(ys, techs):
        axn.text(0.985, y, f"{xt[t]['n']:,}", ha="right", va="center",
                 fontsize=8.4, color=INK2,
                 transform=axn.get_yaxis_transform())
    axn.set_xlim(0, max(xt[t]["n"] for t in techs) * 1.30)
    axn.invert_xaxis()
    axn.set_yticks(ys)
    axn.set_yticklabels([TECHNIQUE_LABEL[t] for t in techs], fontsize=9.2)
    axn.tick_params(left=False, bottom=False, labelbottom=False)
    for sp in axn.spines.values():
        sp.set_visible(False)
    axn.set_ylim(len(techs) - 0.5, -0.5)
    axn.set_title("Videos, n", fontsize=8.6, color=INK2, pad=7)

    ax.imshow(M, cmap=cmap, aspect="auto", vmin=0, vmax=100)
    for i in range(len(techs)):
        for j in range(len(cols)):
            v = M[i][j]
            # A present-but-rare cell must not print as 0: one pacer among
            # 337 visualization videos is 0.3%, and rounding it to zero would
            # say the feature is absent from a technique where it occurs.
            txt = "<1" if 0 < v < 0.5 else f"{v:.0f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8.0,
                    color=SURFACE if v > 55 else INK2)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c[0] for c in cols], fontsize=8.3, rotation=45,
                       ha="left", rotation_mode="anchor")
    ax.tick_params(axis="x", length=0, pad=4)
    ax.set_yticks([])
    ax.xaxis.set_ticks_position("top")
    for sp in ax.spines.values():
        sp.set_visible(False)
    # hairline gaps between cells, so adjacent fills do not merge
    ax.set_xticks([x - 0.5 for x in range(1, len(cols))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(techs))], minor=True)
    ax.grid(which="minor", color=SURFACE, lw=1.4)
    ax.tick_params(which="minor", length=0)

    # group spans above the column labels
    start = 0
    for name, members in GROUPS:
        end = start + len(members) - 1
        ax.annotate("", xy=(start - 0.42, -2.75), xytext=(end + 0.42, -2.75),
                    xycoords=("data", "data"), annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
        ax.text((start + end) / 2, -2.95, name, ha="center", va="bottom",
                fontsize=9.2, color=INK, fontweight="bold", clip_on=False)
        start = end + 1

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 100))
    cb = fig.colorbar(sm, ax=ax, fraction=0.022, pad=0.015)
    cb.set_label("% of videos within technique", fontsize=8.2, color=INK2)
    cb.ax.tick_params(labelsize=7.8, length=2.5, width=0.6)
    cb.outline.set_visible(False)

    fig.subplots_adjust(left=0.292, right=0.930, top=0.705, bottom=0.030)
    save_fig(fig, "figure3_landscape")
    plt.close(fig)


def figure4():
    """Forest plot of the adjusted associations, one panel per outcome.

    Panels are small multiples with independent horizontal scales, because the
    composite index is a linear outcome on a 0-32 scale while the two rates are
    logit coefficients: a shared axis would misrepresent both. The figure is
    rendered close to its printed width so the type stays legible after Word
    scales it into the column.
    """
    d = pd.read_csv(ROOT / "data_main/06_results/rq2_associations.csv")
    pretty = {
        "C(visual_breathing_guide)[T.True]": "Visual breathing guide",
        "C(posture_or_mudra_shown)[T.True]": "Posture or mudra shown",
        "C(nature_imagery_present)[T.True]": "Nature imagery present",
        "C(presenter_visibility)[T.on_screen_presenter]": "Presenter: on-screen",
        "C(presenter_visibility)[T.visuals_only_voiceover]": "Presenter: voiceover only",
        "C(setting_imagery)[T.nature]": "Setting: nature",
        "C(setting_imagery)[T.studio]": "Setting: studio",
        "C(setting_imagery)[T.text_only]": "Setting: text only",
        "C(setting_imagery)[T.other]": "Setting: other",
        "silence_to_voice_ratio_z": "Silence-to-voice ratio",
        "voice_pacing_wpm_z": "Voice pacing",
        "session_length_min_z": "Session length",
        "log_subscribers_z": "Channel subscribers, log",
        "recency_days_z": "Video age",
    }
    order = list(pretty)
    panels = [("like_rate", "Like rate", "fractional logit", BLUE),
              ("comment_rate", "Comment rate", "fractional logit", GREEN),
              ("video_power_index", "Video power index", "linear", VERM)]

    fig, axes = plt.subplots(1, 3, figsize=(6.5, 5.45),
                             gridspec_kw={"wspace": 0.12})
    ys = list(range(len(order)))[::-1]

    for ax, (oc, title, fam, accent) in zip(axes, panels):
        sub = d[d.outcome == oc].set_index("term")
        ax.set_facecolor(WASH)
        band_rows(ax, ys)
        recessive(ax, xgrid=True)
        ax.axvline(0, color=INK2, lw=1.0, zorder=2)

        for y, term in zip(ys, order):
            if term not in sub.index:
                continue
            r = sub.loc[term]
            # Covariates carry no adjusted P value: they sit outside the
            # preregistered correction family. Drawing them in the "does not
            # survive" style would say the opposite of what holds, so they
            # get their own open-marker treatment.
            in_family = pd.notna(r.p_fdr)
            sig = bool(in_family) and r.p_fdr < 0.05
            col = VERM if (sig and r.beta < 0) else (BLUE if sig else MUTED)
            ax.plot([r.ci_low, r.ci_high], [y, y], color=col,
                    lw=2.6 if sig else 1.4, solid_capstyle="round", zorder=3)
            ax.scatter([r.beta], [y], s=62 if sig else 30,
                       facecolor=SURFACE if not in_family else col,
                       edgecolor=col if not in_family else SURFACE,
                       linewidth=1.6, zorder=4)

        ax.set_yticks(ys)
        ax.set_ylim(-0.75, len(order) - 0.25)
        ax.tick_params(axis="x", labelsize=9)
        ax.set_xlabel("")        # one shared label, set on the figure below
        if ax is axes[0]:
            ax.set_yticklabels([pretty[t] for t in order], fontsize=10)
        else:
            ax.set_yticklabels([])
        # accent bar above each panel, carrying the panel's identity
        ax.annotate("", xy=(0.0, 1.045), xytext=(1.0, 1.045),
                    xycoords="axes fraction",
                    arrowprops=dict(arrowstyle="-", lw=3.0, color=accent))
        # Title and family stack rather than sharing a line: side by side
        # they collide once the panel is narrow enough to place at the
        # printed width.
        ax.text(0.0, 1.155, title, transform=ax.transAxes, fontsize=10.5,
                color=INK, ha="left", va="bottom", fontweight="bold")
        ax.text(0.0, 1.072, fam, transform=ax.transAxes, fontsize=8.6,
                color=MUTED, ha="left", va="bottom", style="italic")

    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], color=BLUE, lw=2.6, marker="o", markersize=7,
               markeredgecolor=SURFACE, label="Positive, survives FDR"),
        Line2D([], [], color=VERM, lw=2.6, marker="o", markersize=7,
               markeredgecolor=SURFACE, label="Negative, survives FDR"),
        Line2D([], [], color=MUTED, lw=1.4, marker="o", markersize=5,
               markeredgecolor=SURFACE, label="Does not survive FDR"),
        Line2D([], [], color=MUTED, lw=1.4, marker="o", markersize=5,
               markerfacecolor=SURFACE, markeredgecolor=MUTED,
               label="Covariate, outside the family"),
    ]
    # Explicit layout. tight_layout plus a figure-level legend plus a tight
    # bbox on save repeatedly pushed the legend onto the axis labels, so the
    # margins are reserved directly instead.
    fig.subplots_adjust(left=0.272, right=0.995, top=0.845, bottom=0.225)
    # Three panels carried the same axis label three times, which collided
    # once the figure was drawn at its printed width; one label says it.
    fig.text(0.635, 0.145, "Adjusted coefficient (95% CI)", ha="center",
             fontsize=9.8, color=INK)
    fig.legend(handles=handles, loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, 0.008), columnspacing=1.8, frameon=False)
    save_fig(fig, "figure4_forest")
    plt.close(fig)


if __name__ == "__main__":
    figure1()
    figure2()
    figure3()
    figure4()
    from PIL import Image
    for f in sorted(OUT.glob("*")):
        if f.suffix.lower() not in (".png", ".jpg"):
            continue
        w, h = Image.open(f).size
        flag = "  OVER 1200" if f.suffix == ".jpg" and max(w, h) > 1200 else ""
        print(f"{f.name:30} {w:>5}x{h:<5} {f.stat().st_size/1024:>6.0f} KB{flag}")
