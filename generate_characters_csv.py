import csv
import re
from hanzipy.dictionary import HanziDictionary

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

# --- Main Workflow ---
def main():
    # 1. Initialize configurations and dictionaries
    dict_obj = HanziDictionary()
    input_file = "input_files/characters_idk.txt"
    output_file = "output_files/freq_sorted_characters_idk.csv"

    # 2. Read from the input text file
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find '{input_file}'. Please make sure it's in the same directory.")
        return

    # 3. Filter out non-Chinese characters to isolate unique Hanzi
    unique_chars = [c for c in set(content) if '\u4e00' <= c <= '\u9fff']

    # 4. Sort logic based on hanzipy frequency numbers
    def get_rank(char):
        try:
            freq_list = dict_obj.get_character_frequency(char)
            if freq_list and "number" in freq_list:
                return freq_list["number"]
            return 99999
        except Exception:
            # Handles KeyError/TypeErrors for unrecognized characters
            return 99999

    sorted_chars = sorted(unique_chars, key=get_rank)
    print(f"Read and sorted {len(sorted_chars)} unique Chinese characters. Generating CSV...")

    # 5. Extract data and write to CSV
    # 'utf-8-sig' guarantees proper encoding display in applications like Excel
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        
        # Updated header to include "Keyword"
        writer.writerow(["Character", "Pronunciation", "Keyword", "Writing"])
        
        for char in sorted_chars:
            writing = f'<img src="{char}.gif">'
            accented_pinyin = "N/A"
            keyword = "N/A"
            
            try:
                definitions = dict_obj.get_character_frequency(char)
                if definitions:
                    if 'pinyin' in definitions:
                        # Convert the numbered pinyin to accented pinyin using the provided decode script
                        accented_pinyin = decode_pinyin(definitions['pinyin'])
                    if 'meaning' in definitions:
                        # Grab the meaning to use as our keyword
                        keyword = definitions['meaning']
            except Exception:
                pass
            
            # Write the updated row
            writer.writerow([char, accented_pinyin, keyword, writing])

    print(f"Success! Final data saved to {output_file}.")

if __name__ == "__main__":
    main()