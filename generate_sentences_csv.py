#!/usr/bin/env python3
"""
tatoeba_flashcards.py
─────────────────────
Generates Anki cloze-deletion flashcards from a word list using Tatoeba sentences.

Input files (put in input_files/):
  words_input.txt   – comma-separated target words
  known_words.txt   – comma-separated words you already know (read-only, never overwritten)

Output files (written to output_files/):
  flashcards.txt       – tab-separated Anki import file (Hanzi / hint / TopDownWords / Audio)
  audio_download.csv   – word, sentence_id pairs for bulk audio download + rename

Install deps:
  pip install tatoebatools chinese-english-lookup jieba wordfreq
"""

import csv
import os
import re
from collections import defaultdict

import jieba
from tatoebatools import tatoeba
from chinese_english_lookup import Dictionary

# --- Monkey patch to force UTF-8 ---
import chinese_english_lookup.dictionary as d

_original_open = open
def utf8_open(*args, **kwargs):
    if "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
    return _original_open(*args, **kwargs)

d.open = utf8_open
# -----------------------------------

# ── Pinyin decoder (same as generate_words_csv.py) ──────────────────────────
PinyinToneMark = {
    0: "aoeiuv\u00fc",
    1: "\u0101\u014d\u0113\u012b\u016b\u01d6\u01d6",
    2: "\u00e1\u00f3\u00e9\u00ed\u00fa\u01d8\u01d8",
    3: "\u01ce\u01d2\u011b\u01d0\u01d4\u01da\u01da",
    4: "\u00e0\u00f2\u00e8\u00ec\u00f9\u01dc\u01dc",
}

def decode_pinyin(s):
    s = s.lower()
    r, t = "", ""
    for c in s:
        if "a" <= c <= "z":
            t += c
        elif c == ":":
            t = t[:-1] + "\u00fc"
        else:
            if "0" <= c <= "5":
                tone = int(c) % 5
                if tone:
                    m = re.search("[aoeiuv\u00fc]+", t)
                    if m is None:
                        t += c
                    elif len(m.group()) == 1:
                        t = (
                            t[: m.start()]
                            + PinyinToneMark[tone][PinyinToneMark[0].index(m.group())]
                            + t[m.end() :]
                        )
                    else:
                        if "a" in t:
                            t = t.replace("a", PinyinToneMark[tone][0])
                        elif "o" in t:
                            t = t.replace("o", PinyinToneMark[tone][1])
                        elif "e" in t:
                            t = t.replace("e", PinyinToneMark[tone][2])
                        elif t.endswith("ui"):
                            t = t.replace("i", PinyinToneMark[tone][3])
                        elif t.endswith("iu"):
                            t = t.replace("u", PinyinToneMark[tone][4])
                        else:
                            t += "!"
            r += t
            t = ""
    return r + t


# ── Dictionary helpers ───────────────────────────────────────────────────────

def lookup_word(word: str, d: Dictionary):
    """Return pinyin_str or None."""
    try:
        entry = d.lookup(word)
        if not entry or not entry.definition_entries:
            return None
        de = entry.definition_entries[0]
        pinyin = decode_pinyin(de.pinyin)
        return pinyin
    except Exception:
        return None


# ── Known-words file helpers ─────────────────────────────────────────────────

def load_known_words(path: str) -> set:
    """Read known words from file. Handles commas, newlines, and spaces."""
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        # 1. Read the whole file
        content = f.read()
        # 2. Replace commas with spaces so everything is whitespace-separated
        content = content.replace(",", " ")
        # 3. .split() without arguments splits by ANY whitespace (space, tab, newline)
        return set(w.strip() for w in content.split() if w.strip())

# ── Unknown-word detection ───────────────────────────────────────────────────

def find_unknown_words(sentence: str, target_word: str, known_words: set, d: Dictionary):
    """
    Tokenise sentence with jieba, return list of (word, pinyin, meaning)
    for multi-char tokens not already in known_words.
    """
    unknown = []
    seen = set()
    tokens = list(jieba.cut(sentence, cut_all=False))

    for tok in tokens:
        tok = tok.strip()
        if not tok or tok == target_word or tok in seen:
            continue
        if tok in known_words:
            continue
        pinyin = lookup_word(tok, d)
        if pinyin:
            unknown.append((tok, pinyin))
            seen.add(tok)

    return unknown


# ── Sentence scoring ─────────────────────────────────────────────────────────

def score_sentence(text: str, word: str, has_audio: bool) -> int:
    score = 0
    length = len(text)
    if length <= 12:   score += 4
    elif length <= 20: score += 3
    elif length <= 30: score += 2
    elif length <= 45: score += 1
    # Exactly one occurrence = unambiguous cloze
    if text.count(word) == 1: score += 3
    # Not at the very start = more context visible
    if not text.startswith(word): score += 1
    # Audio is a bonus but not the primary factor
    if has_audio: score += 2
    return score


# ── Single-char guard ────────────────────────────────────────────────────────

def word_is_standalone(text: str, word: str) -> bool:
    """
    For single-char words: confirm the char is not swallowed inside a longer compound.
    We check that neither the char before nor after forms a known 2-char compound
    by doing a simple context check.
    This is a heuristic — jieba tokenisation of the sentence is the real guard.
    """
    if len(word) > 1:
        return True  # multi-char words always fine
    for m in re.finditer(re.escape(word), text):
        start, end = m.start(), m.end()
        # If surrounded by other CJK chars it might be inside a compound
        before = text[start - 1] if start > 0 else ""
        after  = text[end]       if end < len(text) else ""
        is_cjk = lambda c: "\u4e00" <= c <= "\u9fff"
        if is_cjk(before) or is_cjk(after):
            # Check jieba tokenisation to see if word stands alone
            tokens = list(jieba.cut(text, cut_all=False))
            if word in tokens:
                return True
            return False
    return True


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("input_files",  exist_ok=True)
    os.makedirs("output_files", exist_ok=True)

    INPUT_WORDS    = "input_files/words_input_for_sentence_generation.txt"
    KNOWN_WORDS    = "input_files/known_words.txt"
    OUT_CARDS      = "output_files/setence_flashcards.csv"
    OUT_AUDIO_DL   = "output_files/audio_download.csv"   # word + sentence_id for bulk download

    # ── Load target words ──
    with open(INPUT_WORDS, "r", encoding="utf-8") as f:
        raw = f.read()
    words = [w.strip() for w in raw.split(",") if w.strip()]
    words = list(dict.fromkeys(words))          # deduplicate, preserve order
    print(f"Target words: {len(words)}")

    # ── Known words ──
    known_words = load_known_words(KNOWN_WORDS)
    print(f"Known words loaded: {len(known_words)}")

    # ── Dictionary ──
    lookup_dict = Dictionary()

    # ── Download Tatoeba data (skips if already cached) ──
    print("Checking Tatoeba data (first run may take a few minutes)…")
    tatoeba.get(["sentences_with_audio", "eng"])

    # ── Build audio-sentence ID set ──
    print("Loading audio index…")
    audio_ids: set = set()
    try:
        for s in tatoeba.sentences_with_audio("cmn"):
            # attribute name may vary: try both .sentence_id and .id
            sid = getattr(s, "sentence_id", None) or getattr(s, "id", None)
            if sid:
                audio_ids.add(sid)
        print(f"  {len(audio_ids)} Chinese sentences have audio.")
    except Exception as e:
        print(f"  Warning: audio index unavailable ({e})")

    # ── Scan parallel corpus once ──
    print("Scanning sentence pairs (this takes ~1–2 min)…")
    word_set = set(words)
    # word → list of (score, zh_text, en_text, sentence_id, has_audio)
    candidates: dict[str, list] = defaultdict(list)

    pair_count = 0
    for zh, en in tatoeba.parallel_corpus("cmn", "eng"):
        pair_count += 1
        if pair_count % 100_000 == 0:
            print(f"  …{pair_count:,} pairs scanned")

        zh_text = getattr(zh, "text", None) or str(zh)
        en_text = getattr(en, "text", None) or str(en)
        zh_id   = getattr(zh, "id",   None) or getattr(zh, "sentence_id", None)

        for word in word_set:
            if word not in zh_text:
                continue
            if len(word) == 1 and not word_is_standalone(zh_text, word):
                continue
            has_audio = zh_id in audio_ids
            sc = score_sentence(zh_text, word, has_audio)
            candidates[word].append((sc, zh_text, en_text, zh_id, has_audio))

    print(f"Scan complete. {pair_count:,} pairs checked.")

    # ── Write flashcard file ──
    with open(OUT_CARDS, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_ALL)
        writer.writerow(["Hanzi", "hint", "TopDownWords", "Audio"])

        for word in words:
            known_words.add(word)

            if not candidates[word]:
                print(f"  [!] No sentence found for: {word}")
                continue

            best = max(candidates[word], key=lambda x: x[0])
            _, zh_text, en_text, sent_id, has_audio = best

            cloze = zh_text.replace(word, f"{{{{c1::{word}}}}}", 1)
            if has_audio:
              audio_field = f"[sound:{word}.mp3]"
            else: ""

            unknown = find_unknown_words(zh_text, word, known_words, lookup_dict)
            # We keep the <br> for Anki display, but the CSV writer will wrap 
            # this whole string in quotes automatically.
            top_down_str = "\n".join(f"{w} {p} - {m}" for w, p, m in unknown)

            writer.writerow([cloze, en_text, top_down_str, audio_field])
            card_count += 1

    # ── Audio id CSV ──
    with open(OUT_AUDIO_DL, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "audio_id"])
        for word, aid in audio_map:
            writer.writerow([word, sid])

    # ── Summary ──
    print(f"\n{'─'*50}")
    print(f"✓  Flashcards : {OUT_CARDS}  ({card_count} cards)")
    print(f"✓  Audio list : {OUT_AUDIO_DL}  ({len(audio_map)} entries)")
    if no_sentence:
        print(f"✗  No sentence: {', '.join(no_sentence)}")


if __name__ == "__main__":
    main()
