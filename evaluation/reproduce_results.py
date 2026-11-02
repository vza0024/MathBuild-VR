"""Recompute the paper's main statistics from the two CSV files (standard library only).
Bootstrap intervals are Monte Carlo estimates (fixed seed, 100,000 resamples over states).
Run from this folder:  python reproduce_results.py
"""
import csv, collections, random

data = list(csv.DictReader(open('evaluation_data.csv', encoding='utf-8')))
pairs = list(csv.DictReader(open('target_pair_classification.csv', encoding='utf-8')))
VIEWS = ['all_visible', 'relevant_visible', 'relevant_partial', 'relevant_hidden', 'relevant_hidden_unseen']
NAME = {'all_visible': 'all-visible', 'relevant_visible': 'relevant-only', 'relevant_partial': 'partial',
        'relevant_hidden': 'hidden-seen', 'relevant_hidden_unseen': 'hidden-unseen'}

def covered(x): return x['category'] in ('1', '2', '4a', '4b')
def evaluable(x): return x['category'] in ('1', '2', '4a')
def grounded(x): return (x['category'] == '1' and x['admissible'] == 'yes'
                         and x['visibility_consistent'] == 'yes' and x['hard_failure_1'] == 'none')

def rq1(cond):
    xs = [x for x in data if x['condition'] == cond]
    ev = [x for x in xs if evaluable(x)]
    return xs, ev

for cond in ('view_conditioned', 'reference'):
    xs, ev = rq1(cond)
    print(f'\n== RQ1, {cond} ==')
    n_yield = sum(x['category'] != '4b' for x in xs)   # all hints except category 4b
    print(f'coverage {sum(map(covered, xs))}/{len(xs)}; grounded success {sum(map(grounded, ev))}/{len(ev)}; '
          f'grounded yield {sum(map(grounded, ev))}/{n_yield}')
    for v in VIEWS:
        vs = [x for x in xs if x['scripted_view'] == v]
        e = [x for x in vs if evaluable(x)]
        print(f'  {NAME[v]:14s} coverage {sum(map(covered, vs))}/{len(vs)}  grounded {sum(map(grounded, e))}/{len(e)}  '
              f'orientation phrase {sum(x["orientation_phrase"] == "yes" for x in vs)}/{len(vs)}')

vc = [x for x in data if x['condition'] == 'view_conditioned']
seen = [x for x in vc if x['scripted_view'] == 'relevant_hidden']
unseen = [x for x in vc if x['scripted_view'] == 'relevant_hidden_unseen']
print('\n== Required opening phrases ==')
print('hidden-seen "Turn toward":', sum(x['hint_text'].startswith('Turn toward') for x in seen), '/', len(seen))
print('hidden-unseen "Turn to find the part of the story":',
      sum(x['hint_text'].startswith('Turn to find the part of the story') for x in unseen), '/', len(unseen))

# ---- RQ2
H = {x['hint_id']: x for x in data}
cls = {frozenset((p['hint_a_id'], p['hint_b_id'])): p['preliminary_classification'] for p in pairs}
idx = {(x['state_id'], x['condition'], x['scripted_view'], int(x['generation_index'])): x for x in data}
states = sorted({x['state_id'] for x in data})
CROSS = [('relevant_visible', 'relevant_partial'), ('relevant_partial', 'relevant_hidden'), ('relevant_visible', 'relevant_hidden')]

def pair_label(a, b):
    if a['mathematical_target'] == b['mathematical_target']:
        return 'same', False
    return cls.get(frozenset((a['hint_id'], b['hint_id'])), 'UNCLASSIFIED'), True

def rq2(cond):
    out = {'cross': [], 'same': []}
    for s in states:
        for g in (1, 2):
            for va, vb in CROSS:
                a, b = idx[(s, cond, va, g)], idx[(s, cond, vb, g)]
                out['cross'].append((s, va, vb) + pair_label(a, b))
        for v in ('relevant_visible', 'relevant_partial', 'relevant_hidden'):
            a, b = idx[(s, cond, v, 1)], idx[(s, cond, v, 2)]
            out['same'].append((s, v, v) + pair_label(a, b))
    return out

res = {c: rq2(c) for c in ('view_conditioned', 'reference')}
print('\n== RQ2 mathematical focus ==')
for cond, r in res.items():
    for kind in ('cross', 'same'):
        L = r[kind]
        diff = sum(l[3] == 'different' for l in L)
        upper = sum(l[3] in ('different', 'region swap', 'uncertain') for l in L)
        tgt = sum(l[4] for l in L)
        unc = sum(l[3] == 'UNCLASSIFIED' for l in L)
        print(f'{cond:17s} {kind:5s} pairs {len(L):3d}  focus change {diff:2d}  upper bound {upper:2d}  '
              f'recorded-target change {tgt:3d}  unclassified {unc}')
vcross = res['view_conditioned']['cross']
print('view-conditioned focus changes by view pair:',
      {f'{NAME[a]} vs {NAME[b]}': sum(1 for l in vcross if (l[1], l[2]) == (a, b) and l[3] == 'different') for a, b in CROSS})
print('states with a focus change:', len({l[0] for l in vcross if l[3] == 'different'}))

# ---- bootstrap over states (percentile, 100,000 resamples)
random.seed(1)
def boot(stat, n=100000):
    vals = []
    for _ in range(n):
        sample = [random.choice(states) for _ in states]
        v = stat(sample)
        if v is not None: vals.append(v)
    vals.sort()
    return round(100 * vals[int(0.025 * len(vals))], 1), round(100 * vals[int(0.975 * len(vals)) - 1], 1)

bys = collections.defaultdict(list)
for x in vc: bys[x['state_id']].append(x)
def cov_stat(sm): xs = [x for s in sm for x in bys[s]]; return sum(map(covered, xs)) / len(xs)
def gs_stat(sm):
    ev = [x for s in sm for x in bys[s] if evaluable(x)]
    return sum(map(grounded, ev)) / len(ev) if ev else None
def rate(kind):
    def f(sm):
        L = [l for s in sm for l in res['view_conditioned'][kind] if l[0] == s]
        return sum(l[3] == 'different' for l in L) / len(L)
    return f
print('\n== Descriptive 95% bootstrap intervals over states (%) ==')
print('coverage', boot(cov_stat), '| grounded success', boot(gs_stat),
      '| focus change cross-view', boot(rate('cross')), '| same-view', boot(rate('same')))
