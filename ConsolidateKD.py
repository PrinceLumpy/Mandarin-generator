"""
Migrate multiple KanjiDamage fields into an existing RTK note type via AnkiConnect.
Pulls KD data directly from Anki -- no CSV export needed.

Requirements:
- Anki open, AnkiConnect add-on installed (code 2055492159)
- RTK note type already has the target fields added (see FIELD_MAP below)

Usage:
    python migrate_kd_fields.py
"""

import json
import urllib.request

ANKI_CONNECT_URL = "http://127.0.0.1:8765"

# ---- CONFIGURE THESE ----
KD_NOTE_TYPE = "KanjiDamage"    # exact note type name for KD notes
KD_KANJI_FIELD = "Kanji"       # field name holding the kanji character on KD note type

RTK_NOTE_TYPE = "RTK"          # exact note type name for RTK notes
RTK_KANJI_FIELD = "Kanji"      # field name holding the kanji character on RTK note type

# Map: KD source field -> RTK target field
FIELD_MAP = {
    "Full used In": "KD_UsedIn",
}
# --------------------------


def invoke(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    req = urllib.request.Request(
        ANKI_CONNECT_URL, json.dumps(payload).encode("utf-8")
    )
    resp = json.load(urllib.request.urlopen(req))
    if resp.get("error") is not None:
        raise Exception(resp["error"])
    return resp["result"]


def get_kd_data():
    """Returns dict: {kanji: {rtk_target_field: value, ...}}"""
    note_ids = invoke("findNotes", query=f'note:"{KD_NOTE_TYPE}"')
    notes = invoke("notesInfo", notes=note_ids)

    kd_data = {}
    for note in notes:
        fields = note["fields"]
        kanji = fields.get(KD_KANJI_FIELD, {}).get("value", "").strip()
        if not kanji:
            continue

        mapped = {}
        for kd_field, rtk_field in FIELD_MAP.items():
            value = fields.get(kd_field, {}).get("value", "").strip()
            mapped[rtk_field] = value

        kd_data[kanji] = mapped
    return kd_data


def find_rtk_note_id(kanji):
    query = f'note:"{RTK_NOTE_TYPE}" "{RTK_KANJI_FIELD}:{kanji}"'
    ids = invoke("findNotes", query=query)
    return ids[0] if ids else None


def main():
    print("Pulling KD notes...")
    kd_data = get_kd_data()
    print(f"Found {len(kd_data)} KD notes.")

    updated = 0
    skipped = []

    for kanji, mapped_fields in kd_data.items():
        note_id = find_rtk_note_id(kanji)
        if note_id is None:
            skipped.append(kanji)
            continue

        invoke(
            "updateNoteFields",
            note={
                "id": note_id,
                "fields": mapped_fields,
            },
        )
        updated += 1

    print(f"Updated {updated} RTK notes.")
    if skipped:
        print(f"Skipped {len(skipped)} kanji with no RTK match:")
        print(", ".join(skipped))


if __name__ == "__main__":
    main()