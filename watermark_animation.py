from math import log, exp
from typing import List, Dict, Sequence

from manimlib import *


def softmax(logits: Sequence[float]) -> List[float]:
    m = max(logits)
    exps = [exp(x - m) for x in logits]
    s = sum(exps)
    return [x / s for x in exps]


def logits_from_probs(probs: Sequence[float]) -> List[float]:
    eps = 1e-8
    return [log(max(p, eps)) for p in probs]


class HorizontalProbBars(VGroup):
    def __init__(
        self,
        labels: List[str],
        probs: List[float],
        *,
        max_width: float = 5.0,
        bar_height: float = 0.35,
        label_width: float = 2.4,
        base_color = GREY_B,
        value_font_size: int = 28,
        label_font_size: int = 34,
    ):
        super().__init__()
        assert len(labels) == len(probs)
        self.labels = labels
        self.probs = list(probs)
        self.max_width = max_width
        self.bar_height = bar_height
        self.label_width = label_width
        self.base_color = base_color
        self.value_font_size = value_font_size
        self.label_font_size = label_font_size

        self.rows: List[VGroup] = []
        self.bar_rects: List[Rectangle] = []
        self.label_texts: List[Text] = []
        self.value_texts: List[Text] = []

        for lab, p in zip(labels, probs):
            label = Text(lab, font_size=self.label_font_size)
            # Fix label width for alignment
            if label.width > self.label_width:
                label.scale_to_fit_width(self.label_width)
            else:
                # Pad with invisible spacer to keep alignment
                pass

            bar = Rectangle(
                height=self.bar_height,
                width=max(p * self.max_width, 1e-3),
                fill_color=self.base_color,
                fill_opacity=1.0,
                stroke_width=1.0,
                stroke_color=WHITE,
            )
            val = Text(f"{p:.2f}", font_size=self.value_font_size)
            row = VGroup(label, bar, val).arrange(RIGHT, buff=0.35, aligned_edge=DOWN)
            self.rows.append(row)
            self.bar_rects.append(bar)
            self.label_texts.append(label)
            self.value_texts.append(val)

        self.group = VGroup(*self.rows).arrange(DOWN, buff=0.25, aligned_edge=LEFT)
        self.add(self.group)

    def set_probs_immediate(self, new_probs: Sequence[float]):
        self.probs = list(new_probs)
        for p, bar, val in zip(self.probs, self.bar_rects, self.value_texts):
            new_w = max(p * self.max_width, 1e-3)
            bar.stretch_to_fit_width(new_w)
            bar.align_to(self.label_texts[0], LEFT)
            val.set_text(f"{p:.2f}")

    def animate_to_probs(
        self,
        new_probs: Sequence[float],
        *,
        run_time: float = 0.9,
        boosted_indices: Sequence[int] | None = None,
        highlight_color = None,
    ) -> AnimationGroup:
        animations: List[Animation] = []
        for i, (p, bar, val) in enumerate(zip(new_probs, self.bar_rects, self.value_texts)):
            new_w = max(p * self.max_width, 1e-3)
            target = Rectangle(
                height=self.bar_height,
                width=new_w,
                fill_color=(highlight_color if (highlight_color and boosted_indices and i in boosted_indices) else self.base_color),
                fill_opacity=1.0,
                stroke_width=1.0,
                stroke_color=WHITE,
            )
            target.move_to(bar, aligned_edge=LEFT)
            animations.append(Transform(bar, target))
            animations.append(Transform(val, Text(f"{p:.2f}", font_size=self.value_font_size).move_to(val)))

        self.probs = list(new_probs)
        return AnimationGroup(*animations, lag_ratio=0.05, run_time=run_time)

    def colorize_rows(self, indices: Sequence[int], color):
        for i in indices:
            self.bar_rects[i].set_fill(color)

    def reset_colors(self):
        for bar in self.bar_rects:
            bar.set_fill(self.base_color)


class WatermarkSecondToken(Scene):
    def construct(self):
        # Colors
        BOOST_COLOR = "#20948b"  # expectation and predictive bias color as requested

        # Data
        tokens_current = ["cake", "banana", "apples"]
        base_probs_current = [0.7, 0.2, 0.1]

        prev_candidates = ["like", "eat", "buy"]
        prev_probs = [0.5, 0.2, 0.3]

        next_token = "and"
        next_prob = 1.0  # known next token in sentence "... and chocolate"

        green: Dict[str, List[str]] = {
            "like": ["cake"],
            "eat": ["banana", "apples"],
            "buy": ["apples"],
            "cake": [],
            "banana": ["and"],
            "apples": ["and"],
        }

        # Tunable boost magnitudes (logit space)
        EXPECTATION_BOOST = 1.0
        PREDICTIVE_BOOST = 0.8

        # Layout scaffolding
        title = Text("Watermarking the 2nd token", font_size=42)
        subtitle = Text("I ? ? and chocolate.", font_size=32, slant=ITALIC)
        header = VGroup(title, subtitle).arrange(DOWN, buff=0.2).to_edge(UP)
        self.play(FadeIn(header, shift=UP), run_time=0.8)

        # Left: previous token distribution (context candidates)
        prev_title = Text("Context: 1st ?", font_size=30)
        prev_items: List[Text] = []
        for tok, p in zip(prev_candidates, prev_probs):
            prev_items.append(Text(f"{tok}  ({p:.2f})", font_size=30))
        prev_list = VGroup(prev_title, *prev_items).arrange(DOWN, aligned_edge=LEFT, buff=0.25)
        prev_list.to_edge(LEFT).shift(DOWN * 0.5)
        self.play(FadeIn(prev_list, shift=LEFT), run_time=0.8)

        # Right: current distribution as horizontal bars
        dist_title = Text("Current token distribution", font_size=30)
        bars = HorizontalProbBars(tokens_current, base_probs_current, max_width=5.5, bar_height=0.38, label_width=2.6)
        right_group = VGroup(dist_title, bars).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        right_group.to_edge(RIGHT).shift(DOWN * 0.2)
        self.play(FadeIn(dist_title, shift=RIGHT), FadeIn(bars), run_time=0.8)

        # Helper maps
        idx_by_token: Dict[str, int] = {t: i for i, t in enumerate(tokens_current)}

        # Keep logits and staged updates
        logits = logits_from_probs(base_probs_current)

        # Step 1: Expectation boost
        step1_label = Text("Expectation boost", font_size=32, color=BOOST_COLOR)
        step1_label.next_to(right_group, UP, buff=0.4)
        self.play(FadeIn(step1_label), run_time=0.6)

        explanation1 = Text("Add boost × P(context)", font_size=26, color=BOOST_COLOR)
        explanation1.next_to(step1_label, DOWN, aligned_edge=LEFT)
        self.play(FadeIn(explanation1), run_time=0.4)

        # Animate through each previous candidate
        prev_item_mobs: List[Mobject] = prev_items

        for i, (ctx_tok, ctx_p) in enumerate(zip(prev_candidates, prev_probs)):
            # Highlight the context token
            hi_box = SurroundingRectangle(prev_item_mobs[i], color=BOOST_COLOR, buff=0.1, stroke_width=3)
            self.play(Create(hi_box), run_time=0.3)

            # Determine which current tokens get the boost
            boosted = []
            for cand in green.get(ctx_tok, []):
                if cand in idx_by_token:
                    boosted.append(idx_by_token[cand])

            # Stage: add boost in logit space and animate bars
            staged_logits = list(logits)
            for bi in boosted:
                staged_logits[bi] += EXPECTATION_BOOST * ctx_p
            staged_probs = softmax(staged_logits)

            note = Text(
                f"{ctx_tok} ({ctx_p:.2f}) → boost",
                font_size=26,
                color=BOOST_COLOR,
            ).next_to(dist_title, DOWN, buff=0.2, aligned_edge=LEFT)

            self.play(FadeIn(note, shift=RIGHT), run_time=0.2)
            anim = bars.animate_to_probs(
                staged_probs,
                run_time=0.9,
                boosted_indices=boosted,
                highlight_color=BOOST_COLOR,
            )
            self.play(anim)
            self.play(FadeOut(note, shift=RIGHT), run_time=0.2)
            self.play(FadeOut(hi_box), run_time=0.2)

            # Commit logits
            logits = staged_logits
            bars.reset_colors()

        # Step 2: Predictive bias
        step2_label = Text("Predictive bias", font_size=32, color=BOOST_COLOR)
        step2_label.next_to(step1_label, DOWN, aligned_edge=LEFT, buff=0.6)
        self.play(FadeIn(step2_label), run_time=0.6)

        next_note = Text(f"Next token target: '{next_token}'", font_size=26)
        next_note.next_to(step2_label, DOWN, aligned_edge=LEFT)
        self.play(FadeIn(next_note), run_time=0.4)

        # We'll iterate current candidates and boost if `and` is green for them
        # We animate banana then apples since cake has no effect
        current_indices_order = [idx_by_token[t] for t in tokens_current]
        for ci in current_indices_order:
            tok = tokens_current[ci]
            # Visual highlight on the right for the current candidate row
            hi_row = SurroundingRectangle(bars.rows[ci], color=BOOST_COLOR, buff=0.1, stroke_width=3)
            self.play(Create(hi_row), run_time=0.25)

            if next_token in green.get(tok, []):
                staged_logits = list(logits)
                staged_logits[ci] += PREDICTIVE_BOOST * next_prob
                staged_probs = softmax(staged_logits)

                note2 = Text(
                    f"'{tok}' makes '{next_token}' green → +boost",
                    font_size=26,
                    color=BOOST_COLOR,
                ).next_to(next_note, DOWN, aligned_edge=LEFT)

                self.play(FadeIn(note2, shift=RIGHT), run_time=0.2)
                anim = bars.animate_to_probs(
                    staged_probs,
                    run_time=0.9,
                    boosted_indices=[ci],
                    highlight_color=BOOST_COLOR,
                )
                self.play(anim)
                self.play(FadeOut(note2), run_time=0.2)
                logits = staged_logits
                bars.reset_colors()

            self.play(FadeOut(hi_row), run_time=0.2)

        # Final hold
        final_title = Text("Final distribution", font_size=30)
        final_title.next_to(dist_title, DOWN, buff=0.1)
        self.play(FadeIn(final_title), run_time=0.4)
        self.wait(1.0)

