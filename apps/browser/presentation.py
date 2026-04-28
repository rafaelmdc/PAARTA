from __future__ import annotations


def format_repeat_pattern(amino_acid_sequence: str | None) -> str:
    """Return compact run-length architecture for an amino-acid repeat region."""
    sequence = (amino_acid_sequence or "").strip()
    if not sequence:
        return ""

    parts: list[str] = []
    current_residue = sequence[0]
    current_count = 1

    for residue in sequence[1:]:
        if residue == current_residue:
            current_count += 1
            continue
        parts.append(f"{current_count}{current_residue}")
        current_residue = residue
        current_count = 1

    parts.append(f"{current_count}{current_residue}")
    return "".join(parts)


def format_protein_position(start: int | None, end: int | None, protein_length: int | None) -> str:
    """Return compact protein coordinates, with midpoint percent when available."""
    if start is None or end is None:
        return ""

    coordinates = f"{start}-{end}"
    if not protein_length or protein_length <= 0:
        return coordinates

    midpoint = (start + end) / 2
    midpoint_percent = round((midpoint / protein_length) * 100)
    return f"{coordinates} ({midpoint_percent}%)"
