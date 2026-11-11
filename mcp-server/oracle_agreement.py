"""Agreement between oracle runs: how often paired saved characters hold the same value.

This module reads completed run reports and their snapshots; it never contacts a
game. One run is the reference. Every other run is compared with it, checkpoint
by checkpoint (matched by checkpoint name, never by file order) and character by
character (paired by complete saved handle, with the campaign comparator's
fields). For each field it counts the pairs where both sides have a value and
the pairs where the two values are equal.

A run of the reference's own engine gives the noise floor: how far two runs of
the same engine already disagree. A candidate's number is only meaningful next
to it.

Known differences are data, not code. A rules file names classes of pairs that
a documented cause explains (for example a load-order artefact of the reference
engine). Only pairs that differ can be set aside, the number over all pairs is
always shown first, and every class is counted on the same-engine comparison
too, so a class that never fires between two reference runs is visible as such.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from oracle_compare import DEFAULT_TOLERANCES, character_fields, field_family, saved_sets
from oracle_comparison import read_json
from oracle_schema import COMPARABLE_STATE_SCHEMA_VERSIONS

RULES_FORMAT = 'agreement-rules-0.1'
LEDGER_FORMAT = 'agreement-ledger-0.1'
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
MAX_CLASSES = 64
MAX_TOP = 200
EXAMPLES = 3
_WHEN_KEYS = ('squad_template', 'values', 'reference_value', 'candidate_value', 'candidate_value_not',
              'related_absent', 'squad_absent_at_first_checkpoint')


# ---------------------------------------------------------------- rules

def _strings(value, label, *, allow_empty=False):
    if (type(value) is not list or (not value and not allow_empty)
            or not all(type(item) is str and item for item in value) or len(set(value)) != len(value)):
        raise ValueError(f'{label} must be a list of distinct non-empty strings')
    return value


def validate_rules(rules):
    """Check a rules document and return it. Unknown keys are refused, not ignored."""
    if type(rules) is not dict or set(rules) - {'format', 'description', 'classes'}:
        raise ValueError('Agreement rules must be an object with format, classes and an optional description')
    if rules.get('format') != RULES_FORMAT:
        raise ValueError(f'Agreement rules must declare format {RULES_FORMAT}')
    if 'description' in rules and type(rules['description']) is not str:
        raise ValueError('Agreement rules description must be a string')
    classes = rules.get('classes')
    if type(classes) is not list or not 1 <= len(classes) <= MAX_CLASSES:
        raise ValueError(f'Agreement rules need 1 to {MAX_CLASSES} classes')
    names = set()
    for index, entry in enumerate(classes):
        label = f'classes[{index}]'
        if type(entry) is not dict or set(entry) != {'name', 'field', 'reason', 'evidence', 'when'}:
            raise ValueError(f'{label} must have exactly name, field, reason, evidence and when')
        for key in ('name', 'field', 'reason', 'evidence'):
            if type(entry[key]) is not str or not entry[key].strip():
                raise ValueError(f'{label}.{key} must be a non-empty string')
        if entry['name'] in names:
            raise ValueError(f'{label}.name repeats an earlier class')
        names.add(entry['name'])
        when = entry['when']
        if type(when) is not dict or not when or set(when) - set(_WHEN_KEYS):
            raise ValueError(f'{label}.when must use at least one of: ' + ', '.join(_WHEN_KEYS))
        for key in ('squad_template', 'reference_value', 'candidate_value', 'candidate_value_not'):
            if key in when:
                _strings(when[key], f'{label}.when.{key}')
        if 'values' in when:
            pairs = when['values']
            if type(pairs) is not list or not pairs:
                raise ValueError(f'{label}.when.values must be a list of two-value pairs')
            for pair in pairs:
                if len(_strings(pair, f'{label}.when.values entry')) != 2:
                    raise ValueError(f'{label}.when.values entries must hold exactly two different values')
        if 'related_absent' in when:
            related = when['related_absent']
            if type(related) is not dict or set(related) - {'related', 'held_value'} or 'related' not in related:
                raise ValueError(f'{label}.when.related_absent must have related and an optional held_value')
            mapping = related['related']
            if (type(mapping) is not dict or not mapping
                    or not all(type(k) is str and k and type(v) is str and v for k, v in mapping.items())):
                raise ValueError(f'{label}.when.related_absent.related must map character ids to character ids')
            if 'held_value' in related and (type(related['held_value']) is not str or not related['held_value']):
                raise ValueError(f'{label}.when.related_absent.held_value must be a non-empty string')
        if 'squad_absent_at_first_checkpoint' in when and when['squad_absent_at_first_checkpoint'] is not True:
            raise ValueError(f'{label}.when.squad_absent_at_first_checkpoint can only be true')
    return rules


def load_rules(path):
    raw = Path(path).read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Agreement rules exceed 4 MiB')
    rules = validate_rules(read_json(path, 4 * 1024 * 1024))
    return rules, hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------- runs

def _snapshot_path(report_path, execution, capture):
    """The capture's recorded file when it lies in the run directory, else its place by convention.

    Reports record absolute paths; a run directory that was moved or copied keeps
    its layout ``<repetition>/<checkpoint>.json`` next to ``report.json``.
    """
    root = report_path.parent
    recorded = Path(str(capture.get('path', '')))
    if not recorded.is_absolute():
        recorded = root / recorded
    try:
        recorded = recorded.resolve()
        if recorded.is_relative_to(root) and recorded.is_file():
            return recorded
    except OSError:
        pass
    return root / str(execution) / (str(capture.get('name')) + '.json')


def load_run(path):
    """Read one completed run: its report and the snapshots of its completed repetitions.

    Each snapshot must have the SHA-256 its report recorded when the runner
    validated it; the schema is not validated a second time. Only the clock,
    characters and squads are kept.
    """
    report_path = Path(path).resolve()
    if report_path.is_dir():
        report_path /= 'report.json'
    report = read_json(report_path)
    report.pop('variability', None)
    scenario = report.get('scenario')
    if type(scenario) is not dict or type(scenario.get('checkpoints')) is not list or not scenario['checkpoints']:
        raise ValueError(f'{report_path}: not an oracle run report (no scenario checkpoints)')
    if report.get('target') not in ('original', 'meitou'):
        raise ValueError(f'{report_path}: the report names no target')
    checkpoints = [(point['name'], point['at']) for point in scenario['checkpoints']]
    names = {name for name, _ in checkpoints}
    repetitions, seeds, warnings = {}, {}, []
    for execution in report.get('executions') or []:
        number = execution.get('execution')
        if execution.get('status') != 'completed':
            warnings.append(f'repetition {number} is {execution.get("status")}: left out')
            continue
        states = {}
        for capture in execution.get('checkpoints') or []:
            name = capture.get('name')
            if name not in names:
                raise ValueError(f'{report_path}: repetition {number} has an unknown checkpoint {name!r}')
            source = _snapshot_path(report_path, number, capture)
            if source.stat().st_size > MAX_SNAPSHOT_BYTES:
                raise ValueError(f'{source}: snapshot exceeds the shared state size limit')
            payload = source.read_bytes()
            if hashlib.sha256(payload).hexdigest() != capture.get('sha256'):
                raise ValueError(f'{source}: snapshot differs from the hash recorded in its report')
            state = json.loads(payload)
            if state.get('schema_version') not in COMPARABLE_STATE_SCHEMA_VERSIONS:
                raise ValueError(f'{source}: state schema {state.get("schema_version")} cannot be compared')
            states[name] = {key: state[key] for key in ('schema_version', 'clock', 'characters', 'squads')}
        missing = [name for name, _ in checkpoints if name not in states]
        if missing:
            warnings.append(f'repetition {number} lacks checkpoints: ' + ', '.join(missing))
        repetitions[number] = states
        seed = (execution.get('provenance') or {}).get('seed')
        if seed is not None:
            seeds[str(number)] = str(seed)
    if not repetitions:
        raise ValueError(f'{report_path}: no completed repetition')
    schemas = {state['schema_version'] for states in repetitions.values() for state in states.values()}
    if len(schemas) != 1:
        raise ValueError(f'{report_path}: snapshots use several state schemas')
    return dict(path=str(report_path), run=report_path.parent.name, target=report['target'],
                scenario=scenario.get('name'), save=scenario.get('save'),
                source_fingerprint=report.get('source_fingerprint'), state_schema=schemas.pop(),
                build_commit=report.get('build_commit'), checkpoints=checkpoints, repetitions=repetitions,
                seeds=seeds, warnings=warnings)


def _require_same_experiment(reference, other):
    for key, label in (('save', 'save'), ('source_fingerprint', 'save fingerprint'),
                       ('state_schema', 'state schema'), ('checkpoints', 'checkpoint list')):
        if reference[key] != other[key]:
            raise ValueError(f'{other["path"]}: its {label} differs from the reference run; '
                             'agreement needs the same save, state schema and checkpoints')


# ---------------------------------------------------------------- pairing

def _same(key, left, right, tolerances):
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        absolute = tolerances['position' if key.startswith(('position/', 'order/position/')) else 'number']
        return left == right if absolute == 0 else math.isclose(left, right, rel_tol=0.0, abs_tol=absolute)
    return left == right


def _selected(key, fields):
    return not fields or any(key == prefix or key.startswith(prefix + '/') for prefix in fields)


class _Class:
    """One rules class with its sticky state for one pair of repetitions."""

    def __init__(self, entry):
        self.name, self.field, self.when = entry['name'], entry['field'], entry['when']
        related = self.when.get('related_absent') or {}
        self.related, self.held_value = related.get('related'), related.get('held_value')
        self.held = set()
        self.pairs = [frozenset(pair) for pair in self.when.get('values', [])]

    def observe(self, identity, value, present):
        """Advance the sticky state from the reference alone; return whether its related character is away."""
        if self.related is None:
            return False
        absent = identity in self.related and self.related[identity] not in present
        if self.held_value is not None:
            if value == self.held_value and (absent or identity in self.held):
                self.held.add(identity)
            else:
                self.held.discard(identity)
        return absent or identity in self.held

    def explains(self, away, left, right, template, squad_was_absent):
        when = self.when
        if 'squad_template' in when and template not in when['squad_template']:
            return False
        if self.pairs and frozenset((left, right)) not in self.pairs:
            return False
        if 'reference_value' in when and left not in when['reference_value']:
            return False
        if 'candidate_value' in when and right not in when['candidate_value']:
            return False
        if 'candidate_value_not' in when and right in when['candidate_value_not']:
            return False
        if self.related is not None and not away:
            return False
        if when.get('squad_absent_at_first_checkpoint') and not squad_was_absent:
            return False
        return True


def _templates(states):
    """Squad id -> template id over every checkpoint of one repetition (first seen wins)."""
    result = {}
    for state in states.values():
        for squad in state['squads']:
            result.setdefault(squad['id'], squad.get('template_id'))
    return result


class _Tally:
    """Counts of one comparison (a reference run against one other run)."""

    def __init__(self, class_names):
        self.fields = defaultdict(lambda: dict(comparable=0, equal=0, one_sided=0, both_unknown=0, set_aside=0))
        self.detail = defaultdict(lambda: dict(classes=Counter({name: 0 for name in class_names}),
                                               confusion=Counter(), examples=defaultdict(list),
                                               templates=defaultdict(lambda: [0, 0, 0])))
        self.pairs, self.missing = [], []
        self.paired = self.only_reference = self.only_candidate = self.checkpoints = 0


def _compare_repetitions(tally, reference, candidate, checkpoints, numbers, fields, detail_fields, rules, tolerances):
    """One reference repetition against one candidate repetition, over the checkpoints in order."""
    classes = [_Class(entry) for entry in rules]
    templates = _templates(reference)
    first = next((reference[name] for name, _ in checkpoints if name in reference), None)
    early_squads = {row.get('squad_id') for row in first['characters']} if first else set()
    pair = dict(reference_repetition=numbers[0], candidate_repetition=numbers[1],
                fields={field: dict(comparable=0, equal=0, set_aside=0) for field in detail_fields})
    for name, _ in checkpoints:
        left_state, right_state = reference.get(name), candidate.get(name)
        if left_state is None or right_state is None:
            tally.missing.append(dict(checkpoint=name, reference_repetition=numbers[0],
                                      candidate_repetition=numbers[1],
                                      missing='reference' if left_state is None else 'candidate'))
            if left_state is None:
                continue
        present = {row['id'] for row in left_state['characters']}
        left_saved = saved_sets(left_state)
        right_saved = saved_sets(right_state) if right_state is not None else (set(), set())
        right_rows = ({row['id']: row for row in right_state['characters'] if row['id'] in right_saved[0]}
                      if right_state is not None else {})
        if right_state is not None:
            tally.checkpoints += 1
            tally.only_candidate += len(right_saved[0] - left_saved[0])
        for row in left_state['characters']:
            identity = row['id']
            saved = identity in left_saved[0]
            a = character_fields(left_state, row, saved=left_saved) if saved or classes else {}
            # The sticky state of a class follows the reference alone, paired or not.
            away = [entry.observe(identity, a.get(entry.field), present) for entry in classes]
            if not saved or right_state is None:
                continue
            other = right_rows.get(identity)
            if other is None:
                tally.only_reference += 1
                continue
            tally.paired += 1
            b = character_fields(right_state, other, saved=right_saved)
            template = templates.get(row.get('squad_id'))
            for key in a.keys() | b.keys():
                if not _selected(key, fields) and key not in detail_fields:
                    continue
                left, right = a.get(key), b.get(key)
                counts = tally.fields[field_family(key)]
                if left is None or right is None:
                    counts['both_unknown' if left is None and right is None else 'one_sided'] += 1
                    continue
                same = _same(key, left, right, tolerances)
                counts['comparable'] += 1
                counts['equal'] += same
                if key not in detail_fields:
                    continue
                detail, mine = tally.detail[key], pair['fields'][key]
                mine['comparable'] += 1
                mine['equal'] += same
                per_template = detail['templates'][template]
                per_template[0] += 1
                per_template[1] += same
                if same:
                    continue
                cause = next((entry.name for entry, gone in zip(classes, away) if entry.field == key
                              and entry.explains(gone, left, right, template,
                                                 row.get('squad_id') not in early_squads)), None)
                if cause is not None:
                    detail['classes'][cause] += 1
                    counts['set_aside'] += 1
                    mine['set_aside'] += 1
                    continue
                per_template[2] += 1
                detail['confusion'][(str(left), str(right))] += 1
                examples = detail['examples'][(str(left), str(right))]
                if len(examples) < EXAMPLES:
                    examples.append(dict(id=identity, name=row.get('name'), squad_template=template, checkpoint=name,
                                         reference_repetition=numbers[0], candidate_repetition=numbers[1]))
    tally.pairs.append(pair)


def _share(equal, total):
    return round(100.0 * equal / total, 1) if total else None


def _labels(runs):
    """A short name per run: its path without the part all runs share, cut to its two ends."""
    parts = [Path(run['path']).parent.parts for run in runs]
    shared = 0
    while len(parts) > 1 and all(len(p) > shared + 1 for p in parts) and len({p[shared] for p in parts}) == 1:
        shared += 1
    for run, own in zip(runs, parts):
        rest = own[shared:] if len(parts) > 1 else own[-1:]
        run['label'] = '/'.join(rest) if len(rest) <= 2 else rest[0] + '/.../' + rest[-1]


def _summary(run):
    return dict(path=run['path'], run=run['run'], label=run['label'], target=run['target'],
                build_commit=run['build_commit'],
                repetitions=sorted(run['repetitions']), seeds=run['seeds'], warnings=run['warnings'])


def _comparison(reference, candidate, pairs, fields, detail_fields, rules, tolerances, top, *, label):
    class_names = [entry['name'] for entry in rules]
    tally = _Tally(class_names)
    for left, right in pairs:
        _compare_repetitions(tally, reference['repetitions'][left], candidate['repetitions'][right],
                             reference['checkpoints'], (left, right), fields, detail_fields, rules, tolerances)
    rows = []
    for field in sorted(tally.fields):
        counts = tally.fields[field]
        kept = counts['comparable'] - counts['set_aside']
        rows.append(dict(field=field, comparable=counts['comparable'], equal=counts['equal'],
                         agreement=_share(counts['equal'], counts['comparable']),
                         set_aside=counts['set_aside'], kept_comparable=kept,
                         kept_agreement=_share(counts['equal'], kept),
                         one_sided_unknown=counts['one_sided'], both_unknown=counts['both_unknown']))
    details = []
    for field in detail_fields:
        detail = tally.detail[field]
        row = {key: sum(pair['fields'][field][key] for pair in tally.pairs)
               for key in ('comparable', 'equal', 'set_aside')}
        row['kept_comparable'] = row['comparable'] - row['set_aside']
        row['agreement'] = _share(row['equal'], row['comparable'])
        row['kept_agreement'] = _share(row['equal'], row['kept_comparable'])
        confusion = sorted(detail['confusion'].items(), key=lambda item: (-item[1], item[0]))
        templates = sorted(((name, counts) for name, counts in detail['templates'].items() if counts[2]),
                           key=lambda item: (-item[1][2], str(item[0])))
        details.append(dict(
            field=field, comparable=row['comparable'], equal=row['equal'], agreement=row['agreement'],
            set_aside=row['set_aside'], kept_comparable=row['kept_comparable'], kept_agreement=row['kept_agreement'],
            classes=[dict(name=name, pairs=detail['classes'][name]) for name in class_names
                     if any(entry['name'] == name and entry['field'] == field for entry in rules)],
            differences=[dict(reference=key[0], candidate=key[1], pairs=count, examples=detail['examples'][key])
                         for key, count in confusion[:top]],
            differences_truncated=len(confusion) > top,
            squad_templates=[dict(squad_template=name, comparable=counts[0], equal=counts[1], remaining=counts[2])
                             for name, counts in templates[:top]],
            repetition_pairs=[dict(reference_repetition=pair['reference_repetition'],
                                   candidate_repetition=pair['candidate_repetition'], **pair['fields'][field])
                              for pair in tally.pairs]))
    return dict(label=label, candidate=_summary(candidate), same_engine=candidate['target'] == reference['target'],
                repetition_pairs=len(pairs), checkpoints_compared=tally.checkpoints,
                missing_checkpoints=tally.missing,
                characters=dict(paired=tally.paired, only_reference=tally.only_reference,
                                only_candidate=tally.only_candidate),
                fields=rows, details=details)


def agreement(reference_path, candidate_paths, *, rules_path=None, fields=None, detail_fields=None, top=12,
              position_tolerance=None, number_tolerance=None):
    """Compare every candidate run with the reference run; return counts, never a verdict."""
    if type(candidate_paths) is not list or not all(isinstance(path, (str, Path)) for path in candidate_paths):
        raise ValueError('candidates must be a list of run report paths')
    if fields is not None and (type(fields) is not list or not all(type(f) is str and f for f in fields)):
        raise ValueError('fields must be a list of non-empty field prefixes, such as ["goal", "order/type"]')
    if detail_fields is not None and (type(detail_fields) is not list
                                      or not all(type(f) is str and f for f in detail_fields)):
        raise ValueError('detail_fields must be a list of exact field names, such as ["goal/type"]')
    if type(top) is not int or not 1 <= top <= MAX_TOP:
        raise ValueError(f'top must be an integer from 1 to {MAX_TOP}')
    tolerances = dict(DEFAULT_TOLERANCES)
    for key, value in (('position', position_tolerance), ('number', number_tolerance)):
        if value is not None:
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f'{key} tolerance must be a nonnegative finite number')
            tolerances[key] = value
    rules, rules_hash = ([], None)
    if rules_path is not None:
        document, rules_hash = load_rules(rules_path)
        rules = document['classes']
    reference = load_run(reference_path)
    candidates = [load_run(path) for path in candidate_paths]
    for run in candidates:
        _require_same_experiment(reference, run)
    _labels([reference] + candidates)
    details = list(detail_fields) if detail_fields else [
        'goal/type' if tuple(int(part) for part in reference['state_schema'].split('.')) >= (0, 5)
        else 'order/type']
    for entry in rules:
        if entry['field'] not in details:
            details.append(entry['field'])
    options = (fields, details, rules, tolerances, top)
    comparisons = []
    own = sorted(reference['repetitions'])
    if len(own) > 1:
        comparisons.append(_comparison(reference, reference, [(a, b) for a in own for b in own if a < b],
                                       *options, label='reference repetitions against each other'))
    for run in candidates:
        comparisons.append(_comparison(reference, run, [(a, b) for a in own for b in sorted(run['repetitions'])],
                                       *options, label=run['label']))
    floor = {}
    for field in details:
        measured = [detail for comparison in comparisons if comparison['same_engine']
                    for detail in comparison['details'] if detail['field'] == field and detail['comparable']]
        floor[field] = (dict(measured=True, comparisons=len(measured),
                             agreement=min(d['agreement'] for d in measured),
                             kept_agreement=min(d['kept_agreement'] for d in measured))
                        if measured else dict(measured=False, comparisons=0, agreement=None, kept_agreement=None))
    notes = ['Counts over paired saved characters; a pair counts for a field when both sides have a value.',
             'One run pair is one observation. Agreement is a distance, not a classification of stability.']
    if not all(entry['measured'] for entry in floor.values()):
        notes.append('Noise floor not measured: add a second run of the reference engine (or a reference run '
                     'with several repetitions) to see how far that engine disagrees with itself.')
    return dict(format='agreement-0.1', reference=_summary(reference), scenario=reference['scenario'],
                save=reference['save'], source_fingerprint=reference['source_fingerprint'],
                state_schema=reference['state_schema'],
                checkpoints=[name for name, _ in reference['checkpoints']],
                rules=dict(path=str(rules_path) if rules_path is not None else None, sha256=rules_hash,
                           classes=[dict(name=e['name'], field=e['field'], reason=e['reason'], evidence=e['evidence'])
                                    for e in rules]),
                tolerances=tolerances, field_filter=fields, detail_fields=details, noise_floor=floor,
                comparisons=comparisons, notes=notes)


# ---------------------------------------------------------------- text and ledger

def _percent(value):
    return '   n/a' if value is None else f'{value:5.1f}%'


def _short(commit):
    return commit[:8] if isinstance(commit, str) and commit else 'unknown'


def render_text(result):
    """A plain-text report of ``agreement``'s result."""
    reference = result['reference']
    lines = [f'Agreement of paired saved characters; save {result["save"]}, state {result["state_schema"]}, '
             f'{len(result["checkpoints"])} checkpoints',
             f'Reference: {reference["target"]} build {_short(reference["build_commit"])}, '
             f'{len(reference["repetitions"])} repetition(s), {reference["label"]}']
    classes = result['rules']['classes']
    lines.append(f'Rules: {result["rules"]["path"]} ({len(classes)} classes)' if classes
                 else 'Rules: none (no pair is set aside)')
    for field in result['detail_fields']:
        lines += ['', field, f'  {"all pairs":>24}  {"known classes set aside":>26}  engine    build     run']
        for comparison in result['comparisons']:
            detail = next(d for d in comparison['details'] if d['field'] == field)
            lines.append('  {:>16} {} {:>18} {}  {:<8}  {:<8}  {}{}'.format(
                f'{detail["equal"]}/{detail["comparable"]}', _percent(detail['agreement']),
                f'{detail["equal"]}/{detail["kept_comparable"]}', _percent(detail['kept_agreement']),
                comparison['candidate']['target'], _short(comparison['candidate']['build_commit']),
                comparison['label'],
                '   <- same engine: noise floor' if comparison['same_engine'] else ''))
        floor = result['noise_floor'][field]
        if not floor['measured']:
            lines.append('  noise floor: NOT MEASURED (no second run of the reference engine)')
        named = [entry['name'] for entry in classes if entry['field'] == field]
        if named:
            lines.append('  pairs set aside by class:')
            for name in named:
                counts = ', '.join('{} in {}'.format(
                    next(c['pairs'] for d in comparison['details'] if d['field'] == field
                         for c in d['classes'] if c['name'] == name), comparison['label'])
                    for comparison in result['comparisons'])
                lines.append(f'    {name}: {counts}')
            if floor['measured']:
                lines.append('  A class with 0 pairs in a same-engine run is not shown to be that engine\'s own variation.')
        for comparison in result['comparisons']:
            detail = next(d for d in comparison['details'] if d['field'] == field)
            if not detail['differences']:
                continue
            lines.append(f'  largest remaining differences, {comparison["label"]} (reference -> other):')
            for row in detail['differences']:
                example = row['examples'][0] if row['examples'] else None
                where = (f'   e.g. {example["name"]} ({example["squad_template"]}) at {example["checkpoint"]}'
                         if example else '')
                lines.append(f'    {row["pairs"]:>5}  {row["reference"]} -> {row["candidate"]}{where}')
            if detail['squad_templates']:
                lines.append(f'  squad templates with remaining differences, {comparison["label"]}:')
                for row in detail['squad_templates']:
                    lines.append(f'    {row["remaining"]:>5} of {row["comparable"]:<5} {row["squad_template"]}')
    lines += ['', 'All fields, share of comparable pairs that are equal (all pairs):',
              '  ' + ''.join(f'{"[" + str(index + 1) + "]":>9}' for index in range(len(result['comparisons']))) + '  field']
    families = sorted({row['field'] for comparison in result['comparisons'] for row in comparison['fields']})
    for family in families:
        cells = []
        for comparison in result['comparisons']:
            row = next((r for r in comparison['fields'] if r['field'] == family), None)
            cells.append(f'{_percent(row["agreement"] if row else None):>9}')
        lines.append('  ' + ''.join(cells) + '  ' + family)
    for index, comparison in enumerate(result['comparisons']):
        people = comparison['characters']
        lines.append(f'  [{index + 1}] {comparison["label"]}: {people["paired"]} pairs over '
                     f'{comparison["checkpoints_compared"]} checkpoint comparisons; only in the reference '
                     f'{people["only_reference"]}, only in the other run {people["only_candidate"]}'
                     + (f'; {len(comparison["missing_checkpoints"])} checkpoint(s) missing'
                        if comparison['missing_checkpoints'] else ''))
    seen = set()
    for run in [reference] + [comparison['candidate'] for comparison in result['comparisons']]:
        if run['path'] in seen:
            continue
        seen.add(run['path'])
        for warning in run['warnings']:
            lines.append(f'  warning, {run["label"]}: {warning}')
    lines += [''] + result['notes']
    return '\n'.join(lines) + '\n'


def ledger_rows(result):
    """One row per (other run, detail field): the numbers a trend across builds needs."""
    rows = []
    for comparison in result['comparisons']:
        if comparison['candidate']['path'] == result['reference']['path']:
            continue
        for detail in comparison['details']:
            rows.append(dict(
                format=LEDGER_FORMAT, scenario=result['scenario'], save=result['save'],
                source_fingerprint=result['source_fingerprint'], state_schema=result['state_schema'],
                reference=dict(run=result['reference']['run'], target=result['reference']['target'],
                               build_commit=result['reference']['build_commit']),
                candidate=dict(run=comparison['candidate']['run'], target=comparison['candidate']['target'],
                               build_commit=comparison['candidate']['build_commit'],
                               seeds=comparison['candidate']['seeds']),
                same_engine=comparison['same_engine'], field=detail['field'], comparable=detail['comparable'],
                equal=detail['equal'], agreement=detail['agreement'], kept_comparable=detail['kept_comparable'],
                kept_agreement=detail['kept_agreement'], rules_sha256=result['rules']['sha256'],
                classes={entry['name']: entry['pairs'] for entry in detail['classes']}))
    return rows


def append_ledger(path, result):
    """Append the rows that the ledger does not already hold; return how many were added."""
    path = Path(path)
    existing = set(path.read_text(encoding='utf-8').splitlines()) if path.exists() else set()
    added = [line for line in (json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False)
                               for row in ledger_rows(result)) if line not in existing]
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8', newline='\n') as handle:
            handle.write(''.join(line + '\n' for line in added))
    return len(added)


def write_outputs(result, output):
    """Write agreement.json and agreement.txt under ``output``; return their paths."""
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    (root / 'agreement.json').write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n',
        encoding='utf-8', newline='\n')
    (root / 'agreement.txt').write_text(render_text(result), encoding='utf-8', newline='\n')
    return dict(json=str(root / 'agreement.json'), text=str(root / 'agreement.txt'))
