"""Build per-dialect dictionary JSON files from g0v/moedict-data-hakka source."""
import json, re, os, unicodedata
from collections import defaultdict

dialects = {
    "四": "sixian", "海": "hailu", "大": "dapu",
    "平": "raoping", "安": "zhaoan", "南": "nansixian"
}
dialect_names_zh = {
    "sixian": "四縣腔", "hailu": "海陸腔", "dapu": "大埔腔",
    "raoping": "饒平腔", "zhaoan": "詔安腔", "nansixian": "南四縣腔"
}

def parse_pinyin(pinyin_str):
    result = {}
    parts = re.split(r'([四海大平安南])[⃞⃣]?', pinyin_str)
    current_dialect = None
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part in dialects:
            current_dialect = dialects[part]
        elif current_dialect:
            result[current_dialect] = part.strip()
            current_dialect = None
    return result

source = "dictionaries/moedict-hakka/dict-hakka.json"
if not os.path.exists(source):
    print(f"ERROR: {source} not found. Run: git clone --depth 1 https://github.com/g0v/moedict-data-hakka.git dictionaries/moedict-hakka")
    exit(1)

with open(source, "r", encoding="utf-8") as f:
    data = json.load(f)

dict_by_dialect = {d: [] for d in dialects.values()}

for entry in data:
    title = entry.get("title", "")
    for het in entry.get("heteronyms", []):
        pinyin_raw = het.get("pinyin", "")
        if not pinyin_raw:
            continue
        pronunciations = parse_pinyin(pinyin_raw)
        definitions = [d.get("def", "") for d in het.get("definitions", []) if d.get("def")]
        examples = [ex for d in het.get("definitions", []) for ex in d.get("example", [])]
        for dialect_key, pinyin_val in pronunciations.items():
            if pinyin_val:
                dict_by_dialect[dialect_key].append({
                    "text": title, "pinyin": pinyin_val,
                    "definitions": definitions, "examples": examples[:2]
                })

os.makedirs("dictionaries", exist_ok=True)
for dialect_key, entries in dict_by_dialect.items():
    seen = set()
    unique = []
    for e in entries:
        key = (e["text"], e["pinyin"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    with open(f"dictionaries/dict_{dialect_key}.json", "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"✅ {dialect_names_zh[dialect_key]}: {len(unique)} entries")
