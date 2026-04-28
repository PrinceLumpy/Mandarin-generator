import csv
import re
import os
from wordfreq import word_frequency
from chinese_english_lookup import Dictionary

# --- PinyinToneMark and decode_pinyin ---
PinyinToneMark = {
    0: "aoeiuv\u00fc",
    1: "\u0101\u014d\u0113\u012b\u016b\u01d6\u01d6",
    2: "\u00e1\u00f3\u00e9\u00ed\u00fa\u01d8\u01d8",
    3: "\u01ce\u01d2\u011b\u01d0\u01d4\u01da\u01da",
    4: "\u00e0\u00f2\u00e8\u00ec\u00f9\u01dc\u01dc",
}

def decode_pinyin(s):
    s = s.lower()
    r = ""
    t = ""
    for c in s:
        if c >= 'a' and c <= 'z':
            t += c
        elif c == ':':
            assert t[-1] == 'u'
            t = t[:-1] + "\u00fc"
        else:
            if c >= '0' and c <= '5':
                tone = int(c) % 5
                if tone != 0:
                    m = re.search("[aoeiuv\u00fc]+", t)
                    if m is None:
                        t += c
                    elif len(m.group(0)) == 1:
                        t = t[:m.start(0)] + PinyinToneMark[tone][PinyinToneMark[0].index(m.group(0))] + t[m.end(0):]
                    else:
                        if 'a' in t:
                            t = t.replace("a", PinyinToneMark[tone][0])
                        elif 'o' in t:
                            t = t.replace("o", PinyinToneMark[tone][1])
                        elif 'e' in t:
                            t = t.replace("e", PinyinToneMark[tone][2])
                        elif t.endswith("ui"):
                            t = t.replace("i", PinyinToneMark[tone][3])
                        elif t.endswith("iu"):
                            t = t.replace("u", PinyinToneMark[tone][4])
                        else:
                            t += "!"
            r += t
            t = ""
    r += t
    return r

def main():
    # 1. Setup paths and initialize Dictionary
    input_file = "input_files/words_idk.txt"
    output_txt = "output_files/sorted_words_idk.txt"
    output_csv = "output_files/sorted_words_idk.csv"
    
    os.makedirs("output_files", exist_ok=True)
    lookup_dict = Dictionary()

    # 2. Read and parse input file
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find '{input_file}'.")
        return

    # Split by commas or whitespace, then filter out empty strings
    words = [w.strip() for w in re.split(r'[,\s]+', content) if w.strip()]
    unique_words = list(set(words))

    # 3. Sort words by frequency (descending)
    unique_words.sort(key=lambda w: word_frequency(w, 'zh'), reverse=True)

    # 4. Save the sorted list to a text file separated by commas
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(",".join(unique_words))
    
    print(f"Sorted {len(unique_words)} words. List saved to {output_txt}.")

    # 5. Extract data and write to CSV
    # utf-8-sig ensures Excel opens the Chinese characters correctly
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        # Standard comma-separated writer
        writer = csv.writer(f, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["Characters", "Meaning", "Pronunciation"])
        
        for word in unique_words:
            meaning = "N/A"
            pronunciation = "N/A"
            
            try:
                word_entry = lookup_dict.lookup(word)
                if word_entry and word_entry.definition_entries:
                    # Access the first definition object
                    entry = word_entry.definition_entries[0]
                    
                    # Convert niu2 you2 guo3 -> niúyóuguǒ
                    pronunciation = decode_pinyin(entry.pinyin)
                    
                    # Join definition list into a string using semicolons
                    meaning = "; ".join(entry.definitions)
            except Exception as e:
                # Silently skip errors for unrecognized words
                pass

            writer.writerow([word, meaning, pronunciation])

    print(f"Success! CSV data saved to {output_csv}.")

if __name__ == "__main__":
    main()