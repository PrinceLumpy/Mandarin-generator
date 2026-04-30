#!/usr/bin/env python3
"""
Generate Anki cloze-deletion flashcards from a word list using Tatoeba sentences.

Inputs (input_files/):
  words_input_for_sentence_generation.txt – comma-separated target words
  known_words.txt                         – comma-separated words you already know

Outputs (output_files/):
  setence_flashcards.csv – Anki import (Hanzi / hint / TopDownWords / Audio)
  audio_download.csv     – word, sentence_id pairs for bulk audio download
"""

import csv
import os
import re
from collections import defaultdict

import jieba
from tatoebatools import tatoeba, ParallelCorpus
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

# region Configuration 
INPUT_WORDS  = "input_files/words_input_for_sentence_generation.txt"
KNOWN_WORDS  = "input_files/known_words.txt"
OUT_CARDS    = "output_files/setence_flashcards.csv"
OUT_AUDIO_DL = "output_files/audio_download.csv"

PINYIN_VOWELS = "aoeiuvü"
PINYIN_TONES = {
    1: "āōēīūǖǖ",
    2: "áóéíúǘǘ",
    3: "ǎǒěǐǔǚǚ",
    4: "àòèìùǜǜ",
}
# endregion


# region Pinyin Accent
def _apply_tone(syllable: str, tone: int) -> str:
    marks = PINYIN_TONES[tone]
    vowels = re.search(f"[{PINYIN_VOWELS}]+", syllable)
    if not vowels:
        return syllable
    group = vowels.group()
    if len(group) == 1:
        idx = PINYIN_VOWELS.index(group)
        return syllable[:vowels.start()] + marks[idx] + syllable[vowels.end():]
    for ch, idx in (("a", 0), ("o", 1), ("e", 2)):
        if ch in syllable:
            return syllable.replace(ch, marks[idx])
    if syllable.endswith("ui"):
        return syllable.replace("i", marks[3])
    if syllable.endswith("iu"):
        return syllable.replace("u", marks[4])
    return syllable


def decode_pinyin(s: str) -> str:
    """Convert numeric pinyin like 'ni3hao3' to tone-marked 'nǐhǎo'."""
    s = s.lower()
    out, syl = "", ""
    for c in s:
        if "a" <= c <= "z":
            syl += c
        elif c == ":":
            syl = syl[:-1] + "ü"
        elif "0" <= c <= "5":
            tone = int(c) % 5
            if tone:
                syl = _apply_tone(syl, tone)
            out += syl
            syl = ""
        else:
            out += syl
            syl = ""
    return out + syl


def lookup_pinyin(word: str, d: Dictionary) -> str | None:
    try:
        entry = d.lookup(word)
    except Exception:
        return None
    if not entry or not entry.definition_entries:
        return None
    return decode_pinyin(entry.definition_entries[0].pinyin)
# endregion


# region Load Input
def load_word_list(path: str) -> list[str]:
    """Read comma/whitespace-separated words, deduped, preserving order."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        tokens = f.read().replace(",", " ").split()
    return list(dict.fromkeys(t for t in tokens if t))
# endregion


# region 1CharWord
def is_cjk(c: str) -> bool:
    return bool(c) and "一" <= c <= "鿿"


def word_is_standalone(text: str, word: str) -> bool:
    """For single-char words, ensure jieba doesn't bind it into a compound."""
    if len(word) > 1:
        return True
    for m in re.finditer(re.escape(word), text):
        before = text[m.start() - 1] if m.start() > 0 else ""
        after = text[m.end()] if m.end() < len(text) else ""
        if not (is_cjk(before) or is_cjk(after)):
            return True
    return word in jieba.cut(text, cut_all=False)
# endregion

# region TopDownWords
def find_unknown_words(sentence, target, known, d: Dictionary):
    """Multi-char tokens not in `known`, with pinyin."""
    seen, unknown = set(), []
    for tok in jieba.cut(sentence, cut_all=False):
        tok = tok.strip()
        if not tok or tok == target or tok in seen or tok in known:
            continue
        seen.add(tok)
        pinyin = lookup_pinyin(tok, d)
        if pinyin:
            unknown.append((tok, pinyin))
    return unknown
# endregion


# region Stnc Scoring
def score_sentence(text: str, word: str, has_audio: bool) -> int:
    score = 0
    n = len(text)
    if   n <= 8: score += 4
    elif n <= 20: score -= 3
    if text.count(word) == 1: score += 3
    if not text.startswith(word): score += 1
    if has_audio: score += 2
    return score
# endregion


# region Scan Tatoeba
def load_audio_map() -> dict:
    """sentence_id -> audio_id for Chinese sentences (one audio per sentence)."""
    print("Loading audio index…")
    audio_map = {}
    try:
        for s in tatoeba.sentences_with_audio("cmn"):
            sid = getattr(s, "sentence_id", None) or getattr(s, "id", None)
            aid = getattr(s, "audio_id", None)
            if sid and aid:
                audio_map[sid] = aid
        print(f"  {len(audio_map)} Chinese sentences have audio.")
    except Exception as e:
        print(f"  Warning: audio index unavailable ({e})")
    return audio_map


def collect_candidates(words: set, audio_map: dict) -> dict[str, list]:
    """Scan parallel corpus, gather (score, zh, en, sid, audio_id) per word."""
    print("Scanning sentence pairs (this takes ~1–2 min)…")
    candidates = defaultdict(list)
    for n, (zh, en) in enumerate(ParallelCorpus("cmn", "eng"), 1):
        if n % 100_000 == 0:
            print(f"  …{n:,} pairs scanned")
        zh_text = getattr(zh, "text", None) or str(zh)
        en_text = getattr(en, "text", None) or str(en)
        zh_id = getattr(zh, "id", None) or getattr(zh, "sentence_id", None)
        for word in words:
            if word not in zh_text:
                continue
            if len(word) == 1 and not word_is_standalone(zh_text, word):
                continue
            audio_id = audio_map.get(zh_id)
            candidates[word].append(
                (score_sentence(zh_text, word, audio_id is not None), zh_text, en_text, zh_id, audio_id)
            )
    print(f"Scan complete. {n:,} pairs checked.")
    return candidates
# endregion


# region CSV
def main():
    os.makedirs("input_files", exist_ok=True)
    os.makedirs("output_files", exist_ok=True)

    input_words_list = load_word_list(INPUT_WORDS)
    known_words_set = set(load_word_list(KNOWN_WORDS))
    print(f"Target words: {len(input_words_list)} | Known words: {len(known_words_set)}")

    lookup_dict = Dictionary()

    print("Checking Tatoeba data (first run may take a few minutes)…")
    tatoeba.get("sentences_with_audio", ["cmn"])
    tatoeba.get("links", ["cmn", "eng"])

    audio_map = load_audio_map()
    candidates = collect_candidates(set(input_words_list), audio_map)

    audio_rows = []
    with open(OUT_CARDS, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["Hanzi", "hint", "TopDownWords", "Audio"])

        for word in input_words_list:
            known_words_set.add(word)
            if not candidates[word]:
                print(f"  [!] No sentence found for: {word}")
                writer.writerow([f"{word}", "NO SENTENCE YET", "", ""])
                continue

            _, zh_text, en_text, _sent_id, audio_id = max(candidates[word], key=lambda x: x[0])
            cloze = zh_text.replace(word, f"{{{{c1::{word}}}}}", 1)
            audio_field = f"[sound:{word}.mp3]" if audio_id else ""
            unknown = find_unknown_words(zh_text, word, known_words_set, lookup_dict)
            top_down = "\n".join(f"{w} {p}" for w, p in unknown)
            writer.writerow([cloze, en_text, top_down, audio_field])

            if audio_id:
                audio_rows.append((word, audio_id))

    with open(OUT_AUDIO_DL, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "audio_id"])
        writer.writerows(audio_rows)

    print(f"\n{'─' * 50}")
    print(f"✓  Flashcards : {OUT_CARDS}")
    print(f"✓  Audio list : {OUT_AUDIO_DL}")


if __name__ == "__main__":
    main()
# endregion
