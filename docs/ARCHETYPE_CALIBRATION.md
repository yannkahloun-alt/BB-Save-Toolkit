# Default archetype calibration provenance

The default v0.9 role set in `config/archetypes.json` comes from the
`archetypes.json` attachment on GitHub issue
[27](https://github.com/yannkahloun-alt/BB-Save-Toolkit/issues/27). The exact
downloaded source is retained at
`docs/sources/issue-27-archetype-calibration.json` so verification does not depend on
GitHub attachment access.

Source attachment:

- URL: `https://github.com/user-attachments/files/31606746/archetypes.json`
- raw SHA-256: `14ced4ada4274dc94766a804a34b87806607ea3389dae3e3a5ffb39a52de7740`
- canonical `roles` SHA-256:
  `f8d827368308cbd922b638381f2f9ee2278507355ea7bbc90dc6abba651fa1dd`

The canonical digest is calculated by serializing the JSON `roles` array with
UTF-8, sorted object keys, no ASCII escaping, and separators `,` and `:`.
The same digest is produced from the integrated configuration, proving that
role names, stats, targets, baselines, weights, perks, affinities, conflicts,
and ordering match the supplied calibration independent of whitespace. The
configuration contract tests also compare the integrated `roles` value
directly with the retained source.

The repository retains its stronger existing `ceiling` description rather
than copying the attachment's abbreviated wording. This preserves the
documented contract that a ceiling is finite, is at least the target, and caps
Fit valuation only; it does not alter any supplied role because the attachment
defines no stat ceiling.
