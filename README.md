# Spatiotemporal Causality: A Survey of Methods and Challenges

Code for the citation snowballing in the survey
"Spatiotemporal Causality: A Survey of Methods and Challenges"

Starting from 22 seed papers, the scripts collect
- **forward**: the papers that cite each seed
- **backward**: the papers each seed cites

using the Semantic Scholar API, with the OpenAlex API as a backup.
They then remove duplicates and papers already screened, and give the
lists of papers to screen.

## Files

| File | What it does |
|---|---|
| `seeds_22.csv` | The 22 seed papers (title, first author, year, level, DOI) |
| `use_api.py` | Functions for the Semantic Scholar and OpenAlex APIs |
| `forward_search.py` | Forward search, saves `output/forward_raw.csv` |
| `backward_search.py` | Backward search, saves `output/backward_raw.csv` |
| `remove_duplicates.py` | Removes duplicates (by DOI, then title) and papers already screened; keeps backward papers cited by at least 2 seeds |

## Notes

- Some steps were done by hand and are not in the code: checking
  near-duplicate titles, removing duplicate, filling in
  missing abstracts, and the screening itself.

## License

MIT, see `LICENSE`.
