# Hakka ASR Post-Correction

Phonetic matching module for Taiwanese Hakka ASR post-correction.

## Overview

Rule-based phonetic correction pipeline for low-resource, multi-dialect Taiwanese Hakka ASR output.

Inspired by:
- CB-RAG (arXiv:2509.19567, EMNLP 2025) — semantic retrieval for ASR context
- RASTAR (arXiv:2602.12287) — phonetic-level named entity correction

## Dialects Supported

| Code | Dialect |
|------|---------|
| sixian | 四縣腔 |
| hailu | 海陸腔 |
| dapu | 大埔腔 |
| raoping | 饒平腔 |
| zhaoan | 詔安腔 |
| nansixian | 南四縣腔 |

## Dictionary Source

Dictionaries built from [g0v/moedict-data-hakka](https://github.com/g0v/moedict-data-hakka)
(教育部臺灣客家語常用詞辭典, CC BY-ND 3.0 TW)

~14k–15k entries per dialect.

## Usage

```python
from phonetic_matcher import PhoneticMatcher

matcher = PhoneticMatcher(dialect="sixian", dict_dir="./dictionaries")

# Find phonetically similar candidates
candidates = matcher.find_candidates_by_text("不是", top_k=5)
for entry, sim in candidates:
    print(f"{entry['text']} ({entry['pinyin']}) sim={sim:.3f}")
# → 不時 (bud²sii¹¹) sim=0.857

# Correct ASR output segment
suggestions = matcher.correct_segment("台湾不是由铁通")
```

## Quick Start

```bash
# Clone dictionary source
cd dictionaries
git clone --depth 1 https://github.com/g0v/moedict-data-hakka.git moedict-hakka

# Build dialect dictionaries
python3 build_dicts.py

# Run demo
python3 phonetic_matcher.py
```

## Project Status

Work in progress — part of ongoing research on tool-augmented ASR post-correction for low-resource Hakka.
