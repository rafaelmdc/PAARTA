# Phase 2 Worked Examples

## Purpose

These examples make the Phase 2 decisions concrete enough to implement and test.

All examples are illustrative.
They are residue-agnostic by design, even though each example uses a specific target residue for readability.

---

## Example 1: Pure-method tract with one tolerated interruption

Target residue:
- `A`

Protein sequence:

```text
MCAAATAAAGP
```

Indexed view:

```text
1  M
2  C
3  A
4  A
5  A
6  T
7  A
8  A
9  A
10 G
11 P
```

Reasoning:
- the tract from positions `3-9` is `AAATAAA`
- it contains `6` target residues
- the only interruption is `T` at position `6`
- the interruption gap length is `1`, which the pure method allows
- leading and trailing non-target residues are trimmed away already

Expected call:

```text
method           pure
start            3
end              9
aa_sequence      AAATAAA
length           7
repeat_residue   A
repeat_count     6
non_repeat_count 1
purity           0.8571428571
```

Why this matters:
- it shows that the pure method is strict on interruption size, not absolute perfection

---

## Example 2: Threshold-method tract that pure should reject

Target residue:
- `A`

Protein sequence:

```text
MQAATVAAAAAK
```

Indexed view:

```text
1  M
2  Q
3  A
4  A
5  T
6  V
7  A
8  A
9  A
10 A
11 A
12 K
```

Reasoning:
- the window at positions `3-10` is `AATVAAAA`
- that window has `6` target residues out of `8`, so it qualifies under the default `6/8` rule
- extension to the right keeps purity above `0.70`, so the final tract becomes positions `3-11`
- the tract `AATVAAAAA` has:
  - `7` target residues
  - `2` non-target residues
  - purity `7/9 = 0.777...`
- the pure method should reject the full tract because it contains a non-target gap of length `2` (`TV`)

Expected call:

```text
method           threshold
start            3
end              11
aa_sequence      AATVAAAAA
length           9
repeat_residue   A
repeat_count     7
non_repeat_count 2
purity           0.7777777778
window_definition A6/8
```

Why this matters:
- it separates the threshold method from the pure method using a concrete impurity pattern

---

## Example 3: Similarity-based tract that threshold should miss

Target residue:
- `A`

Configured fallback template:

```text
AAAAAAAAAA
```

Protein sequence:

```text
MQAASTAAQAAVAP
```

Indexed candidate tract:

```text
3-13 = AASTAAQAAVA
```

Reasoning:
- the candidate tract contains `7` target residues and `4` non-target residues
- every `8`-residue window inside it contains at most `5` target residues
- threshold therefore does not seed a tract under the default `6/8` rule
- pure also fails because the tract contains longer and denser impurity than the pure rule allows
- under the deterministic fallback:
  - `repeat_count = 7`
  - `non_repeat_count = 4`
  - `score = 7*(+2) + 4*(-1) = 10`
  - the segment remains a positive-scoring repeat-like region

Expected call under `template_local` fallback:

```text
method           blast
start            3
end              13
aa_sequence      AASTAAQAAVA
length           11
repeat_residue   A
repeat_count     7
non_repeat_count 4
purity           0.6363636364
template_name    A10
score            10
```

Interpretation note:
- for production `blastp` or `diamond blastp`, the same biological region could be recovered with backend-native bit scores instead of the local fallback score

Why this matters:
- it demonstrates the intended niche of the similarity-based strategy

---

## Example 4: CDS translation rejection

Context:
- `genomic.gff` links transcript `tx1` to gene `geneA`
- the retained CDS sequence is:

```text
ATGGCTGCTTAGA
```

Reasoning:
- the sequence length is `13`
- after checking for a terminal stop codon, the coding length is still not divisible by `3`
- conservative translation is therefore impossible

Expected behavior:
- no canonical protein row is emitted for this CDS
- the CDS record is excluded from protein-based detection
- the failure is recorded in `normalization_warnings.tsv`

Illustrative warning row:

```text
genome_id        g001
sequence_id      s001
warning_code     non_triplet_length
warning_message  CDS length is not divisible by 3 after conservative terminal-stop handling
```

Why this matters:
- it replaces the old CDS/protein-mismatch problem with a cleaner CDS-translation validation rule

---

## Example 5: Ambiguous taxonomy request sent to review queue

Requested input:

```text
request_id   req_003
input_value  bass
input_type   common_name
```

Reasoning:
- the common name is ambiguous and can map to multiple taxa
- deterministic continuation would be unsafe

Expected behavior:
- the row is written to `resolved_requests.tsv` with a review-required status
- the row is also written to `taxonomy_review_queue.tsv`
- no automatic assembly enumeration happens for that request until it is resolved
- other deterministic requests in the same run may continue

Illustrative resolution row:

```text
request_id              req_003
original_input          bass
normalized_input        bass
resolution_status       review_required
review_required         true
matched_taxid
matched_name
matched_rank
warnings                ambiguous common-name resolution
taxonomy_build_version  2026-04-05
```

Why this matters:
- it makes the review-queue policy concrete instead of leaving it as a vague warning concept

---

## Example 6: Contamination note does not block v1 execution

Context:
- a selected RefSeq assembly passes deterministic taxonomy resolution
- provenance review or metadata suggests a potential contamination note

Expected behavior in v1:
- the assembly may receive a warning or note in provenance artifacts
- the row is not auto-deleted from the run purely because of that note
- downstream processing continues unless another hard validation rule fails

Why this matters:
- contamination remains visible without becoming a hidden hard gate during the first rebuild
