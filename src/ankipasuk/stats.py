"""Corpus-level statistics over a fetched range of verses.

This module has no tkinter dependency, so it can be unit tested (and used
from a script or notebook) without a display.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict

from .cloze import split_segment, tree_depth, tree_leaf_count
from .text_processing import disj_count, group_into_units, tokenize_pasuk


def _label_sort_key(label: str):
    """Sort verse labels like '3:16' numerically by chapter then verse."""
    try:
        ch, vs = label.split(":")
        return (int(ch), int(vs))
    except (ValueError, AttributeError):
        return (0, 0)


def analyze_verse_for_stats(pointed: str, max_leaf_disj: int) -> dict:
    tokens = tokenize_pasuk(pointed)
    units = group_into_units(tokens)
    tree = split_segment(units, max_leaf_disj=max_leaf_disj)

    d_count = disj_count(units)
    trope_names = [
        t["trope_name"] for t in tokens
        if t["trope_name"] and 1 <= t["level"] <= 4
    ]

    return {
        "word_count": len(tokens),
        "disj_count": d_count,
        "conj_count": len(tokens) - d_count,
        "legarmeh_count": sum(1 for t in tokens if t["is_legarmeh"]),
        "trope_names": trope_names,
        "tree_depth": tree_depth(tree),
        "clause_count": tree_leaf_count(tree),
    }


def compute_corpus_stats(verse_data, max_leaf_disj: int):
    """Aggregate per-verse statistics over the currently loaded verse range.

    Alongside each Counter distribution, a parallel ``*_bins`` dict maps
    every bin key to the list of verse labels that fall in it, and
    ``verse_lookup`` maps each label to its actual text -- together these
    let a UI let the user click a bar/point/row and see exactly which
    verses (and their text) are behind it.
    """
    per_verse = []

    word_count_dist = Counter()
    word_count_bins = defaultdict(list)

    disj_count_dist = Counter()
    disj_count_bins = defaultdict(list)

    clause_count_dist = Counter()
    clause_count_bins = defaultdict(list)

    depth_dist = Counter()
    depth_bins = defaultdict(list)

    ratio_dist = Counter()          # words per disjunctive group, rounded to nearest 0.5
    ratio_bins = defaultdict(list)

    trope_freq = Counter()          # total occurrences across all verses
    trope_bins = defaultdict(list)  # trope name -> verses containing it (deduped per verse)

    chapter_word_totals = defaultdict(int)
    chapter_disj_totals = defaultdict(int)
    chapter_verse_counts = defaultdict(int)
    chapter_bins = defaultdict(list)

    scatter_points = defaultdict(list)  # (word_count, tree_depth) -> [labels]
    verse_lookup = {}  # label -> {"ch", "vs", "pointed", "plain"}

    total_words = 0
    total_disj = 0
    total_conj = 0
    total_legarmeh = 0
    longest = None   # (word_count, label)
    shortest = None  # (word_count, label)

    for item in verse_data:
        pointed = item["pointed"].strip()
        if not pointed:
            continue

        s = analyze_verse_for_stats(pointed, max_leaf_disj)
        label = f"{item['ch']}:{item['vs']}"
        verse_lookup[label] = {
            "ch": item["ch"],
            "vs": item["vs"],
            "pointed": pointed,
            "plain": item.get("plain", ""),
        }

        word_count_dist[s["word_count"]] += 1
        word_count_bins[s["word_count"]].append(label)

        disj_count_dist[s["disj_count"]] += 1
        disj_count_bins[s["disj_count"]].append(label)

        clause_count_dist[s["clause_count"]] += 1
        clause_count_bins[s["clause_count"]].append(label)

        depth_dist[s["tree_depth"]] += 1
        depth_bins[s["tree_depth"]].append(label)

        ratio = (s["word_count"] / s["disj_count"]) if s["disj_count"] else 0.0
        ratio_key = round(ratio * 2) / 2  # bin to nearest 0.5
        ratio_dist[ratio_key] += 1
        ratio_bins[ratio_key].append(label)

        for name in set(s["trope_names"]):
            trope_bins[name].append(label)
        trope_freq.update(s["trope_names"])

        chapter_word_totals[item["ch"]] += s["word_count"]
        chapter_disj_totals[item["ch"]] += s["disj_count"]
        chapter_verse_counts[item["ch"]] += 1
        chapter_bins[item["ch"]].append(label)

        scatter_points[(s["word_count"], s["tree_depth"])].append(label)

        total_words += s["word_count"]
        total_disj += s["disj_count"]
        total_conj += s["conj_count"]
        total_legarmeh += s["legarmeh_count"]

        if longest is None or s["word_count"] > longest[0]:
            longest = (s["word_count"], label)
        if shortest is None or s["word_count"] < shortest[0]:
            shortest = (s["word_count"], label)

        per_verse.append((label, s))

    n = len(per_verse)
    if n == 0:
        return None

    chapters = sorted(chapter_verse_counts.keys())
    chapter_avg_words = {ch: chapter_word_totals[ch] / chapter_verse_counts[ch] for ch in chapters}
    chapter_avg_disj = {ch: chapter_disj_totals[ch] / chapter_verse_counts[ch] for ch in chapters}

    for bins in (word_count_bins, disj_count_bins, clause_count_bins, depth_bins,
                 ratio_bins, trope_bins, chapter_bins):
        for key in bins:
            bins[key].sort(key=_label_sort_key)

    return {
        "n_verses": n,
        "word_count_dist": word_count_dist, "word_count_bins": word_count_bins,
        "disj_count_dist": disj_count_dist, "disj_count_bins": disj_count_bins,
        "clause_count_dist": clause_count_dist, "clause_count_bins": clause_count_bins,
        "depth_dist": depth_dist, "depth_bins": depth_bins,
        "ratio_dist": ratio_dist, "ratio_bins": ratio_bins,
        "trope_freq": trope_freq, "trope_bins": trope_bins,
        "chapters": chapters,
        "chapter_avg_words": chapter_avg_words,
        "chapter_avg_disj": chapter_avg_disj,
        "chapter_bins": chapter_bins,
        "scatter_points": scatter_points,
        "verse_lookup": verse_lookup,
        "total_words": total_words,
        "total_disj": total_disj,
        "total_conj": total_conj,
        "total_legarmeh": total_legarmeh,
        "avg_words": total_words / n,
        "avg_disj": total_disj / n,
        "avg_words_per_disj": (total_words / total_disj) if total_disj else 0.0,
        "longest": longest,
        "shortest": shortest,
        "per_verse": per_verse,
    }


def _weighted_avg(dist: Counter, n: int) -> float:
    if n == 0:
        return 0.0
    return sum(k * v for k, v in dist.items()) / n


def format_stats_summary(stats, max_leaf_disj: int) -> str:
    if stats is None:
        return "No verses to analyze."

    lines = [
        f"Verses analyzed: {stats['n_verses']}",
        f"Total words: {stats['total_words']}",
        f"Average words / verse: {stats['avg_words']:.2f}",
        f"Longest verse: {stats['longest'][1]}  ({stats['longest'][0]} words)",
        f"Shortest verse: {stats['shortest'][1]}  ({stats['shortest'][0]} words)",
        "",
        f"Total minimum disjunctive groups: {stats['total_disj']}",
        f"Average disjunctive groups / verse: {stats['avg_disj']:.2f}",
        f"Average words / disjunctive group: {stats['avg_words_per_disj']:.2f}",
        f"Total conjunctive (non-disjunctive) words: {stats['total_conj']}",
        f"Total Munach Legarmeh occurrences: {stats['total_legarmeh']}",
        "",
        f"With max {max_leaf_disj} disjunctive group(s) per cloze leaf:",
        f"  Average clauses / verse after splitting: "
        f"{_weighted_avg(stats['clause_count_dist'], stats['n_verses']):.2f}",
        f"  Average split-tree depth: "
        f"{_weighted_avg(stats['depth_dist'], stats['n_verses']):.2f}",
        "",
        "Disjunctive trope frequency (across all verses):",
    ]
    for name, cnt in stats["trope_freq"].most_common():
        lines.append(f"  {name}: {cnt}")

    return "\n".join(lines)


def write_stats_csv(path, stats, max_leaf_disj: int) -> None:
    """Write one row per verse with its per-verse stats. Pure I/O, no GUI."""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Verse", "Words", "Disjunctive groups", "Conjunctive words",
            "Munach legarmeh", f"Clauses (max {max_leaf_disj}/leaf)", "Split-tree depth",
        ])
        for label, s in stats["per_verse"]:
            writer.writerow([
                label, s["word_count"], s["disj_count"], s["conj_count"],
                s["legarmeh_count"], s["clause_count"], s["tree_depth"],
            ])
