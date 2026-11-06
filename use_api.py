"""Functions shared by forward_search.py and backward_search.py.

Looks up papers with the Semantic Scholar API, and the OpenAlex API as a
backup when Semantic Scholar cannot find a seed or does not return its
reference list. Also has the title and DOI cleaning used by
remove_duplicates.py.

Settings (environment variables):
    S2_API_KEY       Semantic Scholar API key (without it the search is slow)
    OPENALEX_MAILTO  your email address, optional, gives faster OpenAlex access
"""

import os
import re
import time

import pandas as pd
import requests
from rapidfuzz import fuzz

S2_URL = 'https://api.semanticscholar.org/graph/v1'
OPENALEX_URL = 'https://api.openalex.org'
S2_FIELDS = 'title,year,authors,externalIds,abstract,citationCount'

S2_API_KEY = os.environ.get('S2_API_KEY')
OPENALEX_MAILTO = os.environ.get('OPENALEX_MAILTO')

session = requests.Session()


################ helper functions for API calls and cleaning

def get_json(url, params=None, headers=None):
    ### using the api to get the data
    for attempt in range(6):
        reply = session.get(url, params=params, headers=headers, timeout=60)
        if reply.status_code == 200:
            return reply.json()
        if reply.status_code == 429 or reply.status_code >= 500:
            wait = 10 * (attempt + 1)
            print(f'    API busy ({reply.status_code}), waiting {wait} s')
            time.sleep(wait)
        else:
            return None
    return None


def clean_doi(doi):
    ### make the DOI lower case
    if pd.isna(doi):
        return ''
    doi = str(doi).strip().lower()
    return re.sub(r'^https?://(dx\.)?doi\.org/', '', doi)


def clean_title(title):
    ### Lower case title with only letters, numbers and single spaces.
    if pd.isna(title):
        return ''
    title = re.sub(r'[^a-z0-9 ]', ' ', str(title).lower())
    return ' '.join(title.split())


################# Semantic Scholar

def s2_papers(doi, direction):
    ### we can use the same function for forward and backward snowballing, just changing the direction
    if direction == 'citations':
        key = 'citingPaper'
    else:
        key = 'citedPaper'
    headers = {'x-api-key': S2_API_KEY} if S2_API_KEY else None

    papers = []
    offset = 0
    while True:
        url = f'{S2_URL}/paper/DOI:{doi}/{direction}'
        params = {'fields': S2_FIELDS, 'offset': offset, 'limit': 100}
        reply = get_json(url, params, headers)
        # no reply = seed not found; empty data = publisher withheld the list
        if not reply or not reply.get('data'):
            break
        for item in reply['data']:
            paper = item.get(key) or {}
            if paper:
                papers.append(s2_row(paper))
        if 'next' not in reply:
            break
        offset = reply['next']
        time.sleep(1)
    return papers


def s2_row(paper):
    ids = paper.get('externalIds') or {}
    names = [author.get('name') or '' for author in paper.get('authors') or []]
    return {
        'title': paper.get('title'),
        'year': paper.get('year'),
        'authors': ', '.join(names),
        'doi': ids.get('DOI'),
        'abstract': paper.get('abstract'),
        'citations': paper.get('citationCount'),
        'found_in': 'semantic_scholar',
    }



################# OpenAlex

def openalex_get(path, params=None):
    params = dict(params or {})
    if OPENALEX_MAILTO:
        params['mailto'] = OPENALEX_MAILTO
    return get_json(f'{OPENALEX_URL}/{path}', params)


def openalex_find(title, doi):
    ### using OpenAlex to find papers with DOI and then title
    work = openalex_get(f'works/doi:{doi}')
    if work:
        return work
    reply = openalex_get('works', {'filter': f'title.search:{title}', 'per-page': 5})
    for work in (reply or {}).get('results', []):
        score = fuzz.token_sort_ratio(clean_title(title), clean_title(work.get('title')))
        if score >= 85:
            return work
    return None


def openalex_citing(work):
    ### get papers that cite this one
    work_id = work['id'].split('/')[-1]
    papers = []
    cursor = '*'
    while cursor:
        params = {'filter': f'cites:{work_id}', 'per-page': 200, 'cursor': cursor}
        reply = openalex_get('works', params)
        if not reply or not reply['results']:
            break
        for item in reply['results']:
            papers.append(openalex_row(item))
        cursor = reply['meta'].get('next_cursor')
    return papers


def openalex_cited(work):
    ### get papers that this one cites
    ids = [ref.split('/')[-1] for ref in work.get('referenced_works') or []]
    papers = []
    for start in range(0, len(ids), 50):
        chunk = '|'.join(ids[start:start + 50])
        reply = openalex_get('works', {'filter': f'openalex_id:{chunk}', 'per-page': 50})
        if reply:
            for item in reply['results']:
                papers.append(openalex_row(item))
        time.sleep(1)
    return papers


def openalex_row(work):
    names = [a['author'].get('display_name') or '' for a in work.get('authorships') or []]
    doi = work.get('doi')
    if doi:
        doi = doi.replace('https://doi.org/', '')
    return {
        'title': work.get('title'),
        'year': work.get('publication_year'),
        'authors': ', '.join(names),
        'doi': doi,
        'abstract': rebuild_abstract(work.get('abstract_inverted_index')),
        'citations': work.get('cited_by_count'),
        'found_in': 'openalex',
    }


def rebuild_abstract(index):
    ### get the abstract back in order
    if not index:
        return None
    words = {}
    for word, positions in index.items():
        for position in positions:
            words[position] = word
    return ' '.join(words[position] for position in sorted(words))


####### doing the search

def search_seed(title, doi, direction):
    ### first try Semantic Scholar, then OpenAlex
    papers = s2_papers(doi, direction)
    if papers:
        return papers, 'semantic_scholar'
    work = openalex_find(title, doi)
    if work is None:
        return [], 'not found'
    if direction == 'citations':
        papers = openalex_citing(work)
    else:
        papers = openalex_cited(work)
    return papers, 'openalex'


def run_search(seeds, direction):
    ### search each seed
    if not S2_API_KEY:
        print('S2_API_KEY is not set, Semantic Scholar will be slow\n')
    rows = []
    log = []
    for number, seed in enumerate(seeds.itertuples(), start=1):
        print(f'[{number}/{len(seeds)}] {direction}: {seed.title[:70]}')
        papers, found_in = search_seed(seed.title, seed.doi, direction)
        print(f'    {len(papers)} papers from {found_in}')
        for paper in papers:
            paper['seed'] = seed.title
        rows.extend(papers)
        log.append({'seed': seed.title, 'found_in': found_in, 'papers': len(papers)})
        time.sleep(2)
    return rows, log
