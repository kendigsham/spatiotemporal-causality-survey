"""Backward snowballing: collect the reference list of each seed in seeds_22.csv.

Saves every record found (one row per seed and cited paper) to
output/backward_raw.csv, and where each seed was found to
output/backward_seed_log.csv. Run remove_duplicates.py afterwards.

Run:
    python backward_search.py
"""

import os

import pandas as pd

from use_api import run_search

SEEDS_FILE = 'seeds_22.csv'
OUTPUT_DIR = 'output'


os.makedirs(OUTPUT_DIR, exist_ok=True)
seeds = pd.read_csv(SEEDS_FILE)

rows, log = run_search(seeds, 'references')

pd.DataFrame(rows).to_csv(f'{OUTPUT_DIR}/backward_raw.csv', index=False)
pd.DataFrame(log).to_csv(f'{OUTPUT_DIR}/backward_seed_log.csv', index=False)
print(f'\nBackward: {len(rows)} records from {len(seeds)} seeds, saved in {OUTPUT_DIR}/')


