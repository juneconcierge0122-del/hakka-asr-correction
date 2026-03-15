"""
Phonetic Matching Module for Taiwanese Hakka ASR Post-Correction
================================================================
Inspired by RASTAR (arXiv:2602.12287) phonetic-level retrieval.

Core idea: Use Hakka pinyin edit distance to find dictionary candidates
that sound similar to ASR output tokens.

Usage:
    from phonetic_matcher import PhoneticMatcher
    matcher = PhoneticMatcher(dialect="sixian")
    candidates = matcher.find_candidates("台湾不是由铁通", top_k=5)
"""

import json
import os
import re
import unicodedata
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


# ============================================================
# Pinyin Normalization
# ============================================================

# Hakka tone marks: superscript digits and combining marks
TONE_PATTERN = re.compile(r'[⁰¹²³⁴⁵⁶⁷⁸⁹ˊˇˋ\u0300-\u036f]+')

# Superscript digit mapping
SUPERSCRIPT_MAP = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789')


def normalize_pinyin(pinyin: str, keep_tone: bool = True) -> str:
    """Normalize Hakka pinyin for comparison.
    
    Args:
        pinyin: Raw pinyin string (e.g., 'aˊ baˊ' or 'a²⁴ ba²⁴')
        keep_tone: If True, keep tone numbers; if False, strip tones entirely
    
    Returns:
        Normalized pinyin string
    """
    if not pinyin:
        return ""
    
    # Convert superscript digits to normal digits
    result = pinyin.translate(SUPERSCRIPT_MAP)
    
    # Normalize unicode
    result = unicodedata.normalize('NFC', result)
    
    if not keep_tone:
        # Remove all tone marks and numbers at syllable boundaries
        result = TONE_PATTERN.sub('', result)
        result = re.sub(r'[0-9]+', '', result)
    
    # Lowercase
    result = result.lower().strip()
    
    # Normalize whitespace
    result = re.sub(r'\s+', ' ', result)
    
    return result


def split_syllables(pinyin: str) -> List[str]:
    """Split a pinyin string into individual syllables.
    
    Handles both space-separated and concatenated forms.
    e.g., 'aˊ baˊ' → ['a', 'ba']  (tones stripped for splitting)
          'am hong' → ['am', 'hong']
    """
    normalized = normalize_pinyin(pinyin, keep_tone=False)
    if not normalized:
        return []
    
    # Split by spaces first
    parts = normalized.split()
    return [p for p in parts if p]


# ============================================================
# Edit Distance (Phonetic)
# ============================================================

def phonetic_edit_distance(s1: str, s2: str) -> int:
    """Compute character-level edit distance between two pinyin strings.
    
    This operates on the tone-stripped, normalized pinyin.
    """
    a = normalize_pinyin(s1, keep_tone=False)
    b = normalize_pinyin(s2, keep_tone=False)
    
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i-1] == b[j-1] else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,      # deletion
                dp[i][j-1] + 1,      # insertion
                dp[i-1][j-1] + cost  # substitution
            )
    
    return dp[m][n]


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Normalized edit distance (0.0 = identical, 1.0 = completely different)."""
    a = normalize_pinyin(s1, keep_tone=False)
    b = normalize_pinyin(s2, keep_tone=False)
    
    if not a and not b:
        return 0.0
    
    dist = phonetic_edit_distance(s1, s2)
    max_len = max(len(a), len(b))
    
    return dist / max_len if max_len > 0 else 0.0


def phonetic_similarity(s1: str, s2: str) -> float:
    """Phonetic similarity score (1.0 = identical, 0.0 = completely different)."""
    return 1.0 - normalized_edit_distance(s1, s2)


# ============================================================
# Syllable-level Edit Distance
# ============================================================

def syllable_edit_distance(syls1: List[str], syls2: List[str]) -> int:
    """Edit distance at the syllable level."""
    m, n = len(syls1), len(syls2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            # Use character-level similarity for substitution cost
            sim = phonetic_similarity(syls1[i-1], syls2[j-1])
            cost = 0 if sim > 0.8 else (0.5 if sim > 0.5 else 1.0)
            dp[i][j] = min(
                dp[i-1][j] + 1,
                dp[i][j-1] + 1,
                dp[i-1][j-1] + cost
            )
    
    return dp[m][n]


# ============================================================
# Dictionary & Matcher
# ============================================================

class HakkaDictionary:
    """Loads and indexes a Hakka dialect dictionary."""
    
    def __init__(self, dialect: str, dict_dir: str = None):
        """
        Args:
            dialect: One of 'sixian', 'hailu', 'dapu', 'raoping', 'zhaoan', 'nansixian'
            dict_dir: Directory containing dict_*.json files
        """
        self.dialect = dialect
        
        if dict_dir is None:
            dict_dir = os.path.join(os.path.dirname(__file__), "dictionaries")
        
        dict_path = os.path.join(dict_dir, f"dict_{dialect}.json")
        if not os.path.exists(dict_path):
            raise FileNotFoundError(f"Dictionary not found: {dict_path}")
        
        with open(dict_path, "r", encoding="utf-8") as f:
            self.entries = json.load(f)
        
        # Build indexes
        self._build_indexes()
    
    def _build_indexes(self):
        """Build lookup indexes for fast retrieval."""
        # text → list of (pinyin, entry)
        self.text_to_entries = defaultdict(list)
        # pinyin (normalized, no tone) → list of entries
        self.pinyin_to_entries = defaultdict(list)
        # Character → list of possible pinyin readings
        self.char_to_pinyin = defaultdict(set)
        
        for entry in self.entries:
            text = entry["text"]
            pinyin = entry["pinyin"]
            
            self.text_to_entries[text].append(entry)
            
            norm_pinyin = normalize_pinyin(pinyin, keep_tone=False)
            self.pinyin_to_entries[norm_pinyin].append(entry)
            
            # Single character entries → build char-level G2P
            if len(text) == 1:
                self.char_to_pinyin[text].add(pinyin)
    
    def lookup(self, text: str) -> List[Dict]:
        """Look up a word by its Chinese characters."""
        return self.text_to_entries.get(text, [])
    
    def get_pinyin(self, text: str) -> Optional[str]:
        """Get the pinyin for a text. Returns first match or None."""
        entries = self.lookup(text)
        if entries:
            return entries[0]["pinyin"]
        return None
    
    def text_to_pinyin_sequence(self, text: str) -> str:
        """Convert a text string to pinyin, character by character.
        
        Falls back to empty string for unknown characters.
        """
        result = []
        i = 0
        while i < len(text):
            # Try longest match first (up to 4 chars)
            matched = False
            for length in range(min(4, len(text) - i), 0, -1):
                substr = text[i:i+length]
                entries = self.lookup(substr)
                if entries:
                    result.append(entries[0]["pinyin"])
                    i += length
                    matched = True
                    break
            
            if not matched:
                # Try single character
                char = text[i]
                if char in self.char_to_pinyin:
                    # Take first reading
                    result.append(next(iter(self.char_to_pinyin[char])))
                else:
                    result.append(f"[{char}]")  # Unknown
                i += 1
        
        return " ".join(result)
    
    @property
    def size(self) -> int:
        return len(self.entries)


class PhoneticMatcher:
    """Finds phonetically similar dictionary candidates for ASR output."""
    
    def __init__(self, dialect: str = "sixian", dict_dir: str = None):
        """
        Args:
            dialect: Target dialect
            dict_dir: Directory containing dict_*.json files
        """
        self.dictionary = HakkaDictionary(dialect, dict_dir)
        self.dialect = dialect
        
        # Pre-compute normalized pinyin for all entries
        self._precompute()
    
    def _precompute(self):
        """Pre-compute normalized pinyin strings for fast matching."""
        self.entry_pinyin_cache = []
        for entry in self.dictionary.entries:
            norm = normalize_pinyin(entry["pinyin"], keep_tone=False)
            self.entry_pinyin_cache.append(norm)
    
    def find_candidates_by_pinyin(
        self, 
        query_pinyin: str, 
        top_k: int = 5,
        max_distance: float = 0.5
    ) -> List[Tuple[Dict, float]]:
        """Find dictionary entries phonetically similar to a pinyin query.
        
        Args:
            query_pinyin: Pinyin string to match against
            top_k: Number of candidates to return
            max_distance: Maximum normalized edit distance threshold
            
        Returns:
            List of (entry, similarity_score) tuples, sorted by similarity
        """
        query_norm = normalize_pinyin(query_pinyin, keep_tone=False)
        
        if not query_norm:
            return []
        
        candidates = []
        query_len = len(query_norm)
        
        for i, entry in enumerate(self.dictionary.entries):
            entry_norm = self.entry_pinyin_cache[i]
            
            if not entry_norm:
                continue
            
            # Quick length filter: skip if lengths differ too much
            len_diff = abs(len(entry_norm) - query_len)
            if len_diff > query_len * max_distance + 2:
                continue
            
            sim = phonetic_similarity(query_norm, entry_norm)
            
            if sim >= (1.0 - max_distance):
                candidates.append((entry, sim))
        
        # Sort by similarity (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[:top_k]
    
    def find_candidates_by_text(
        self,
        text: str,
        top_k: int = 5,
        max_distance: float = 0.5
    ) -> List[Tuple[Dict, float]]:
        """Find dictionary entries phonetically similar to a Chinese text.
        
        First converts text to pinyin using the dictionary, then matches.
        
        Args:
            text: Chinese text (ASR output)
            top_k: Number of candidates to return
            max_distance: Maximum normalized edit distance threshold
            
        Returns:
            List of (entry, similarity_score) tuples
        """
        # Convert text to pinyin
        pinyin = self.dictionary.text_to_pinyin_sequence(text)
        
        return self.find_candidates_by_pinyin(pinyin, top_k, max_distance)
    
    def correct_segment(
        self,
        asr_text: str,
        window_sizes: List[int] = [2, 3, 4],
        top_k: int = 3,
        min_similarity: float = 0.6
    ) -> List[Dict]:
        """Scan ASR output with sliding windows and find corrections.
        
        Args:
            asr_text: ASR output text (Chinese characters)
            window_sizes: Character window sizes to scan
            top_k: Number of candidates per window
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of correction suggestions with position, original, candidates
        """
        suggestions = []
        
        for win_size in window_sizes:
            for start in range(len(asr_text) - win_size + 1):
                segment = asr_text[start:start + win_size]
                
                # Skip if segment is already in dictionary
                if self.dictionary.lookup(segment):
                    continue
                
                # Find phonetic candidates
                candidates = self.find_candidates_by_text(
                    segment, top_k=top_k, max_distance=(1.0 - min_similarity)
                )
                
                if candidates:
                    suggestions.append({
                        "position": (start, start + win_size),
                        "original": segment,
                        "original_pinyin": self.dictionary.text_to_pinyin_sequence(segment),
                        "candidates": [
                            {
                                "text": c["text"],
                                "pinyin": c["pinyin"],
                                "similarity": round(sim, 3),
                                "definitions": c.get("definitions", [])[:1]
                            }
                            for c, sim in candidates
                        ]
                    })
        
        # Deduplicate overlapping suggestions, keep highest similarity
        return self._deduplicate_suggestions(suggestions)
    
    def _deduplicate_suggestions(self, suggestions: List[Dict]) -> List[Dict]:
        """Remove overlapping suggestions, keeping the best ones."""
        if not suggestions:
            return []
        
        # Sort by best candidate similarity (descending)
        suggestions.sort(
            key=lambda s: s["candidates"][0]["similarity"] if s["candidates"] else 0,
            reverse=True
        )
        
        kept = []
        used_positions = set()
        
        for s in suggestions:
            start, end = s["position"]
            positions = set(range(start, end))
            
            # Skip if overlapping with already-kept suggestion
            if positions & used_positions:
                continue
            
            kept.append(s)
            used_positions |= positions
        
        # Sort by position
        kept.sort(key=lambda s: s["position"][0])
        return kept


# ============================================================
# Multi-dialect Matcher
# ============================================================

class MultiDialectMatcher:
    """Phonetic matcher that works across all six Hakka dialects."""
    
    DIALECTS = ["sixian", "hailu", "dapu", "raoping", "zhaoan", "nansixian"]
    DIALECT_NAMES = {
        "sixian": "四縣腔",
        "hailu": "海陸腔", 
        "dapu": "大埔腔",
        "raoping": "饒平腔",
        "zhaoan": "詔安腔",
        "nansixian": "南四縣腔"
    }
    
    def __init__(self, dict_dir: str = None):
        self.matchers = {}
        for d in self.DIALECTS:
            try:
                self.matchers[d] = PhoneticMatcher(d, dict_dir)
                print(f"  ✅ {self.DIALECT_NAMES[d]}: {self.matchers[d].dictionary.size} entries")
            except FileNotFoundError:
                print(f"  ⚠️ {self.DIALECT_NAMES[d]}: not found, skipping")
    
    def find_candidates(
        self,
        text: str,
        dialect: str = None,
        top_k: int = 5,
        max_distance: float = 0.5
    ) -> Dict[str, List]:
        """Find candidates across one or all dialects."""
        if dialect:
            if dialect not in self.matchers:
                return {}
            return {dialect: self.matchers[dialect].find_candidates_by_text(
                text, top_k, max_distance
            )}
        
        results = {}
        for d, matcher in self.matchers.items():
            candidates = matcher.find_candidates_by_text(text, top_k, max_distance)
            if candidates:
                results[d] = candidates
        return results
    
    def correct_segment(
        self,
        asr_text: str,
        dialect: str = "sixian",
        **kwargs
    ) -> List[Dict]:
        """Correct ASR output for a specific dialect."""
        if dialect not in self.matchers:
            raise ValueError(f"Unknown dialect: {dialect}")
        return self.matchers[dialect].correct_segment(asr_text, **kwargs)


# ============================================================
# CLI Demo
# ============================================================

if __name__ == "__main__":
    import sys
    
    dict_dir = os.path.join(os.path.dirname(__file__), "dictionaries")
    
    print("=" * 60)
    print("Hakka Phonetic Matching Module - Demo")
    print("=" * 60)
    
    # Load all dialects
    print("\nLoading dictionaries...")
    multi = MultiDialectMatcher(dict_dir)
    
    print("\n" + "=" * 60)
    print("Test 1: Pinyin similarity")
    print("=" * 60)
    
    test_pairs = [
        ("mai55", "mai24"),    # 賣 vs 買 (四縣)
        ("am hong", "am fung"),  # similar
        ("ngien", "ngien"),     # very close
    ]
    for a, b in test_pairs:
        sim = phonetic_similarity(a, b)
        print(f"  '{a}' vs '{b}': similarity = {sim:.3f}")
    
    print("\n" + "=" * 60)
    print("Test 2: Dictionary lookup")
    print("=" * 60)
    
    sixian = multi.matchers.get("sixian")
    if sixian:
        test_words = ["阿爸", "買", "賣", "地動", "民宿"]
        for w in test_words:
            pinyin = sixian.dictionary.get_pinyin(w)
            print(f"  {w} → {pinyin or '(not found)'}")
    
    print("\n" + "=" * 60)
    print("Test 3: Find phonetic candidates")
    print("=" * 60)
    
    if sixian:
        # Simulate: ASR outputs "不是" but correct might be "不時"
        test_text = "不是"
        print(f"\n  Query: '{test_text}'")
        candidates = sixian.find_candidates_by_text(test_text, top_k=5, max_distance=0.5)
        for entry, sim in candidates:
            print(f"    → {entry['text']} ({entry['pinyin']}) sim={sim:.3f}")
    
    print("\n" + "=" * 60)
    print("Test 4: Correct ASR segment")  
    print("=" * 60)
    
    if sixian:
        # From Anna's example: 「臺灣不時有地動」→ ASR: 「台湾不是由铁通」
        asr_output = "台湾不是由铁通"
        print(f"\n  ASR output: '{asr_output}'")
        suggestions = sixian.correct_segment(
            asr_output, 
            window_sizes=[2, 3],
            top_k=3,
            min_similarity=0.5
        )
        
        if suggestions:
            for s in suggestions:
                print(f"\n  Position {s['position']}: '{s['original']}' (pinyin: {s['original_pinyin']})")
                for c in s['candidates']:
                    print(f"    → {c['text']} ({c['pinyin']}) sim={c['similarity']}")
        else:
            print("  No suggestions (many chars might be unknown in Hakka dict)")
            print("  This is expected — the ASR output is Mandarin chars, not Hakka chars")
            print("  The real pipeline needs Hakka Whisper output (客語漢字) as input")
    
    print("\n✅ Module ready.")
