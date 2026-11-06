"""Turn the raw search results into the lists of papers to screen.

Reads output/forward_raw.csv and output/backward_raw.csv (made by
forward_search.py and backward_search.py) and
  1. merges duplicates, first by DOI and then by title,
  2. drops papers already screened in the database search
     (the backward list also drops papers found by the forward search),
  3. keeps only backward papers cited by at least two seeds.

Saves output/forward_all.csv and output/backward_all.csv (every unique paper)
and output/forward_to_screen.csv and output/backward_to_screen.csv.

Run:
    python remove_duplicates.py
"""

import os

import pandas as pd
from rapidfuzz import fuzz, process

from use_api import clean_doi, clean_title

DATABASE_FILE = 'inputs/all_databases_papers.xlsx'  # database search results, not included
OUTPUT_DIR = 'output'

TITLE_MATCH = 95  # title similarity (0-100) needed to call two papers the same
MIN_SEEDS = 2     # backward search: keep papers cited by at least this many seeds


def combine_duplicates(raw):
    ### combine duplicates by DOI and then by title
    papers = []
    doi_to_paper = {}
    title_to_paper = {}
    for row in raw.to_dict('records'):
        doi = clean_doi(row['doi'])
        title = clean_title(row['title'])

        number = None
        if doi and doi in doi_to_paper:
            number = doi_to_paper[doi]
        elif title in title_to_paper:
            number = title_to_paper[title]

        if number is None:
            paper = dict(row)
            paper['seeds'] = []
            papers.append(paper)
            number = len(papers) - 1

        paper = papers[number]
        if row['seed'] not in paper['seeds']:
            paper['seeds'].append(row['seed'])
        if clean_doi(paper['doi']) == '' and doi:
            paper['doi'] = row['doi']
        if doi:
            doi_to_paper[doi] = number
        title_to_paper[title] = number

    table = pd.DataFrame(papers).drop(columns='seed')
    table['n_seeds'] = table['seeds'].map(len)
    table['seeds'] = table['seeds'].map(' | '.join)
    return table


def mark_already_screened(table, screened):
    ### make sets of seen DOIs and titles
    seen_dois = set(screened['doi'].map(clean_doi)) - {''}
    seen_titles = [t for t in screened['title'].map(clean_title) if t]

    flags = []
    for _, paper in table.iterrows():
        if clean_doi(paper['doi']) in seen_dois:
            flags.append(True)
            continue
        match = process.extractOne(clean_title(paper['title']), seen_titles,
                                   scorer=fuzz.token_sort_ratio)
        flags.append(match is not None and match[1] >= TITLE_MATCH)
    table['already_screened'] = flags
    return table


def load_database():
    ### load the papers that were already screened in the database search
    if not os.path.exists(DATABASE_FILE):
        print(f'{DATABASE_FILE} not found, so papers from the database search '
              'are not removed\n')
        return pd.DataFrame(columns=['title', 'doi'])
    data = pd.read_excel(DATABASE_FILE)
    data = data.rename(columns={'Document Title': 'title', 'DOI': 'doi'})
    return data[['title', 'doi']]



database = load_database()
forward_raw = pd.read_csv(f'{OUTPUT_DIR}/forward_raw.csv')
backward_raw = pd.read_csv(f'{OUTPUT_DIR}/backward_raw.csv')

# forward
forward = combine_duplicates(forward_raw)
forward = mark_already_screened(forward, database)
forward_new = forward[~forward['already_screened']]
forward.to_csv(f'{OUTPUT_DIR}/forward_all.csv', index=False)
forward_new.to_csv(f'{OUTPUT_DIR}/forward_to_screen.csv', index=False)

# backward, also skipping what the forward search found
backward = combine_duplicates(backward_raw)
seen = pd.concat([database, forward[['title', 'doi']]], ignore_index=True)
backward = mark_already_screened(backward, seen)
backward_new = backward[~backward['already_screened']]
backward_core = backward_new[backward_new['n_seeds'] >= MIN_SEEDS]
backward.to_csv(f'{OUTPUT_DIR}/backward_all.csv', index=False)
backward_core.to_csv(f'{OUTPUT_DIR}/backward_to_screen.csv', index=False)

print(f'Forward:  {len(forward_raw)} records, {len(forward)} unique papers, '
        f'{len(forward_new)} not screened before')
print(f'Backward: {len(backward_raw)} records, {len(backward)} unique papers, '
        f'{len(backward_new)} not screened before, '
        f'{len(backward_core)} cited by at least {MIN_SEEDS} seeds')
print(f'Results saved in {OUTPUT_DIR}/')

