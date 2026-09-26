def read_contacts(text):
    """Parse CSV text (first row is the header) into a list of dicts."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        values = [v.strip() for v in line.split(",")]
        rows.append(dict(zip(header, values)))
    return rows
