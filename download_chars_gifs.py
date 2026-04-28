import os
import requests
import urllib.parse
import re
import time
from concurrent.futures import ThreadPoolExecutor

def download_gif(char, base_out_dir):
    try:
        encoded = urllib.parse.quote(char)
        page_url = f"https://www.strokeorder.com/chinese/{encoded}"
        resp = requests.get(page_url, timeout=10)
        resp.raise_for_status()
        html = resp.text

        m = re.search(r'<img\s+[^>]*src="(/assets/bishun/animation/\d+\.gif)"', html)
        if not m:
            print(f"No GIF found for {char}")
            return
        
        gif_url = urllib.parse.urljoin(page_url, m.group(1))
        out_path = os.path.join(base_out_dir, f"{char}.gif")

        with requests.get(gif_url, stream=True, timeout=10) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Done: {char}")
    except Exception as e:
        print(f"Error for {char}: {e}")

def main():
    input_file = "input_files/characters_idk.txt"
    out_dir = "output_files/stroke-order-gif"
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove duplicates and whitespace
    chars = list(set([ch for ch in content if not ch.isspace()]))

    print(f"Starting download of {len(chars)} unique characters...")

    # Using 10 concurrent workers for speed
    with ThreadPoolExecutor(max_workers=10) as executor:
        for ch in chars:
            executor.submit(download_gif, ch, out_dir)

if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"Total time: {time.time() - start_time:.2f} seconds")