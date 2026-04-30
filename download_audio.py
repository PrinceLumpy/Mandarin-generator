import csv
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT_CSV = "input_files/audio_download.csv"
OUTPUT_DIR = "output_files/audio"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def download(char, audio_id):
    url = f"https://tatoeba.org/audio/download/{audio_id}"
    out_path = os.path.join(OUTPUT_DIR, f"{char}.mp3")

    # Skip if file already exists (useful if the script crashes)
    if os.path.exists(out_path):
        return f"SKIP {char}"

    for attempt in range(5):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 429:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            r.raise_for_status()
            with open(out_path, "wb") as f:
                f.write(r.content)
            return f"✓ {char}"
        except requests.Timeout:
            time.sleep(2 ** attempt)

    return f"✗ {char}: failed after 5 attempts"

with open(INPUT_CSV, newline="", encoding="utf-8") as f:
    rows = [(row["word"].strip(), row["audio_id"].strip()) for row in csv.DictReader(f)]

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(download, char, aid): char for char, aid in rows}
    for future in as_completed(futures):
        print(future.result())