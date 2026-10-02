#!/usr/bin/env python3
"""Offline contracts, version differences, continuations and artifact delivery."""
import argparse
import copy
import hashlib
import html
import json
import re
import sys
import tempfile
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    raise SystemExit('Install requirements.txt in your Python environment (jsonschema 4).')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import media_renderers as media
OPERATIONS = ('compare', 'inspect_evidence', 'change_assumption', 'challenge')


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def read_json(path):
    def bad_constant(value):
        raise ContractError('Non-finite JSON value: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=bad_constant)


def write_file(path, text):
    """Never replace a different existing artifact; save and read back atomically."""
    write_bytes(path, text.encode('utf-8'))


def write_bytes(path, data):
    path = Path(path)
    if path.exists():
        require(path.read_bytes() == data, f'Output already exists with different content: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        # A hard link makes creation atomic and does not overwrite a raced-in file.
        import os
        os.link(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
    require(path.read_bytes() == data, 'Saved artifact did not survive readback')


def write_json(path, value):
    write_file(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def schema_check(kind, value):
    canonical(value)
    name = {'request': 'presentation-request', 'spec': 'presentation-spec', 'receipt': 'render-receipt'}[kind]
    schema = read_json(ROOT / 'schemas' / (name + '.schema.json'))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    require(not errors, '; '.join(f'{list(e.path)}: {e.message}' for e in errors[:5]))


def indexed(items, label):
    ids = [x['id'] for x in items]
    require(len(ids) == len(set(ids)), f'Duplicate {label} IDs')
    return {x['id']: x for x in items}


def result_ref(result):
    return {k: result[k] for k in ('result_id', 'revision')}


def validate_result(result):
    blocks = indexed(result['blocks'], 'block')
    evidence = indexed(result['evidence'], 'evidence')
    uncertainties = indexed(result['uncertainties'], 'uncertainty')
    for block in blocks.values():
        require(set(block['evidence_ids']) <= evidence.keys(), 'Unresolved block evidence')
        require(set(block['uncertainty_ids']) <= uncertainties.keys(), 'Unresolved block uncertainty')
        data, kind = block['data'], block['kind']
        if kind == 'text':
            require(isinstance(data.get('content'), str) and data['content'], 'text data needs content')
        elif kind == 'relations':
            nodes = indexed(data.get('nodes', []), 'node')
            require(nodes and all(isinstance(n.get('label'), str) for n in nodes.values()), 'Relations need labeled nodes')
            indexed(data.get('edges', []), 'edge')
            for edge in data.get('edges', []):
                require(edge.get('from') in nodes and edge.get('to') in nodes and isinstance(edge.get('label'), str), 'Invalid edge endpoints or label')
        elif kind == 'comparison':
            columns, rows = data.get('columns'), data.get('rows')
            require(isinstance(columns, list) and columns and all(isinstance(c, str) for c in columns) and len(set(columns)) == len(columns), 'Comparison needs unique columns')
            require(isinstance(rows, list) and all(isinstance(r, dict) and set(r) == set(columns) for r in rows), 'Comparison rows must match columns')
        elif kind == 'series':
            require(isinstance(data.get('unit'), str) and bool(data['unit']), 'Series needs a unit')
            require(isinstance(data.get('points'), list), 'Series needs points')
            for point in data['points']:
                require(isinstance(point.get('label'), str) and 'value' in point, 'Series point needs label and value')
                require(point['value'] is None or (isinstance(point['value'], (int, float)) and not isinstance(point['value'], bool)), 'Series values must be numbers or explicit null')
        elif kind == 'steps':
            require(isinstance(data.get('items'), list) and all(isinstance(x, str) for x in data['items']), 'Steps need string items')
    for uncertainty in uncertainties.values():
        require(set(uncertainty['affected_block_ids']) <= blocks.keys(), 'Unresolved uncertainty target')
    # A globally relevant limit can bind every block or have an empty target list.
    return blocks


def signals(request):
    context = request['learner_context']
    values = context['known_concepts'] + context['confusions'] + context['feedback']
    if context['preferred_depth'] is not None:
        values.append(context['preferred_depth'])
    return values


def validate_request(request):
    schema_check('request', request)
    blocks = validate_result(request['result'])
    indexed(request['comprehension_goals'], 'goal')
    for signal in indexed(signals(request), 'signal').values():
        require(signal['source_ref'] in request['session_refs'], 'Signal has no trusted current-session source')
        require(set(signal.get('block_ids', [])) <= blocks.keys(), 'Signal targets unknown block')
    status, baseline = request['history_status'], request['baseline']
    require((status == 'available') == (baseline is not None), 'history_status and baseline disagree')
    if baseline:
        old_blocks = validate_result(baseline['result'])
        old = baseline['result']
        if old['result_id'] != request['result']['result_id']:
            require(bool(baseline.get('id_map')), 'Different result IDs need explicit baseline id_map')
        id_map = baseline.get('id_map', {})
        require(set(id_map) <= old_blocks.keys() and set(id_map.values()) <= blocks.keys(), 'Invalid baseline id_map')
        require(len(id_map.values()) == len(set(id_map.values())), 'Baseline id_map is not one-to-one')
        if result_ref(old) == result_ref(request['result']):
            require(canonical(old) == canonical(request['result']), 'Changed content reused the same result revision')
    return request


def prepare(raw):
    request = copy.deepcopy(raw)
    request.setdefault('schema_version', '1.0')
    request.setdefault('constraints', {})
    request.setdefault('session_refs', [])
    require('history_status' in request, 'Explicit history_status is required; missing history is not a first version')
    request.setdefault('baseline', None)
    request.setdefault('learner_context', {})
    context = request['learner_context']
    for key in ('known_concepts', 'confusions', 'feedback'):
        context.setdefault(key, [])
    context.setdefault('preferred_depth', None)
    context.setdefault('check_consent', 'not_asked')
    if not request.get('comprehension_goals'):
        goal = request.get('intent', {}).get('goal')
        require(bool(goal), 'User goal is missing')
        request['comprehension_goals'] = [{'id': 'g1', 'description': goal, 'success_criteria': '能够指出结果中的结论、相关依据和适用限制。', 'origin': 'inferred'}]
    return validate_request(request)


def compute_changes(request, coverage=None, sections=None):
    current = request['result']
    status = request['history_status']
    if status != 'available':
        return {'status': 'first_version' if status == 'first' else 'baseline_unavailable', 'baseline_ref': None, 'changes': [], 'unchanged_block_ids': []}
    baseline = request['baseline']
    old = baseline['result']
    before = {b['id']: b for b in old['blocks']}
    after = {b['id']: b for b in current['blocks']}
    mapping = baseline.get('id_map', {})
    mapped = {mapping.get(key, key): key for key in before}
    changes = []
    goals = [g['id'] for g in request['comprehension_goals']]
    coverage = coverage or []
    sections = {s['id']: s for s in sections or []}

    def add(kind, before_ids, after_ids, text, reason_key):
        impacted = set(before_ids + after_ids)
        affected = []
        for goal in coverage:
            target = {bid for sid in goal['section_ids'] for bid in sections[sid]['source_block_ids']}
            if not impacted or impacted & target:
                affected.append(goal['goal_id'])
        changes.append({'change_id': 'c' + str(len(changes) + 1), 'kind': kind, 'subject_ids': [reason_key], 'before_block_ids': before_ids, 'after_block_ids': after_ids, 'description': text, 'reason': current.get('change_reasons', {}).get(reason_key, '原因未提供'), 'affected_goal_ids': affected if coverage else goals})

    for bid in sorted(after):
        oid = mapped.get(bid)
        if oid is None:
            add('added', [], [bid], '新增内容 ' + bid, bid)
        elif canonical({k: v for k, v in before[oid].items() if k != 'id'}) != canonical({k: v for k, v in after[bid].items() if k != 'id'}):
            add('modified', [oid], [bid], '内容或引用映射改变 ' + bid, bid)
    for oid in sorted(before):
        if mapping.get(oid, oid) not in after:
            add('removed', [oid], [], '移除内容 ' + oid, oid)
    if old['summary'] != current['summary']:
        add('summary_changed', [], [], '核心结论摘要发生变化', 'summary')
    for key, kind, link in [('evidence', 'evidence_changed', 'evidence_ids'), ('uncertainties', 'uncertainty_changed', 'uncertainty_ids')]:
        old_items = {x['id']: x for x in old[key]}
        new_items = {x['id']: x for x in current[key]}
        for item_id in sorted(old_items.keys() | new_items.keys()):
            if old_items.get(item_id) != new_items.get(item_id):
                before_ids = [bid for bid, b in before.items() if item_id in b[link]]
                after_ids = [bid for bid, b in after.items() if item_id in b[link]]
                if key == 'uncertainties':
                    before_ids = sorted(set(before_ids) | set(old_items.get(item_id, {}).get('affected_block_ids', [])))
                    after_ids = sorted(set(after_ids) | set(new_items.get(item_id, {}).get('affected_block_ids', [])))
                add(kind, before_ids, after_ids, ('依据' if key == 'evidence' else '限制') + '新增、修改或撤回 ' + item_id, item_id)
    touched = {bid for c in changes for bid in c['after_block_ids']}
    return {'status': 'changed' if changes else 'unchanged', 'baseline_ref': result_ref(old), 'changes': changes, 'unchanged_block_ids': sorted(bid for bid in after if bid in mapped and bid not in touched)}


def validate_spec(spec, request):
    validate_request(request)
    schema_check('spec', spec)
    require(spec['request_id'] == request['request_id'] and spec['result_ref'] == result_ref(request['result']), 'Spec is bound to another request or revision')
    if spec['decision'] != 'selected':
        require(bool(spec['issues']), 'Blocked decision must describe issues')
        require(not spec['interactions'], 'Blocked decisions cannot dispatch actions')
        return spec
    require(not request['constraints'].get('requires_new_evidence'), 'User task requires upstream evidence')
    require(request['history_status'] != 'unavailable', 'Historical baseline is unavailable; do not claim complete differences')
    fmt = request['intent'].get('explicit_format')
    require(not fmt or spec['presentation']['format'] == fmt, 'Explicit requested format was changed')
    require(spec['render_request']['renderer_id'] in request['capabilities']['renderers'], 'Renderer is not available')
    sections = indexed(spec['sections'], 'section')
    blocks = {b['id']: b for b in request['result']['blocks']}
    require(bool(sections), 'Selected spec has no sections')
    aids = indexed(spec['learning_aids'], 'learning aid')
    for section in sections.values():
        bids = section['source_block_ids']
        require(set(bids) <= blocks.keys(), 'Section source does not resolve')
        require(bool(bids) != ('source_field' in section), 'Section needs blocks OR the restricted summary field')
        require(set(section.get('learning_aid_ids', [])) <= aids.keys(), 'Section learning aid does not resolve')
    require(set(spec['render_request']['section_ids']) == sections.keys(), 'Render request dropped or invented sections')
    goals = indexed(request['comprehension_goals'], 'goal')
    coverage_ids = [g['goal_id'] for g in spec['goal_coverage']]
    require(set(coverage_ids) == goals.keys() and len(coverage_ids) == len(set(coverage_ids)), 'Understanding goals are not uniquely covered')
    for goal in spec['goal_coverage']:
        require(bool(goal['section_ids']) and set(goal['section_ids']) <= sections.keys(), 'Goal has no valid content coverage')
    for view in spec['views'].values():
        require(view['result_ref'] == spec['result_ref'], 'Views show different result versions')
        require(bool(view['section_ids']) and set(view['section_ids']) <= sections.keys(), 'View has no valid content')
    verify_sections = [sections[sid] for sid in spec['views']['verify']['section_ids']]
    verify_blocks = {bid for section in verify_sections for bid in section['source_block_ids']}
    shown = {bid for section in sections.values() for bid in section['source_block_ids']}
    require(shown <= verify_blocks, 'A displayed conclusion lacks a verification target')
    require(any(s['kind'] == 'evidence_and_limits' for s in verify_sections), 'Verification view has no evidence and limits section')
    preservation = spec['preservation']
    evidence = {x['id'] for x in request['result']['evidence']}
    limits = {x['id'] for x in request['result']['uncertainties']}
    require(set(preservation['required_evidence_ids']) <= evidence and set(preservation['required_uncertainty_ids']) <= limits, 'Invented preservation references')
    needed_evidence = {eid for bid in shown for eid in blocks[bid]['evidence_ids']}
    # Limits stay visible even when the affected detail is omitted.
    require(needed_evidence <= set(preservation['required_evidence_ids']) and limits == set(preservation['required_uncertainty_ids']), 'Evidence or limitations were dropped')
    require(set(preservation['omitted_block_ids']) == blocks.keys() - shown, 'Omissions were not disclosed exactly')
    if request['intent'].get('learning_aids_required'):
        require(bool(aids), 'This task requires a contrast, counterexample or analogy boundary')
    require(bool(spec['learning_aids_reason']), 'Learning aid applicability must be explained')
    for aid in aids.values():
        require(bool(aid['target_block_ids']) and set(aid['target_block_ids']) <= blocks.keys(), 'Learning aid target is invalid')
        require(set(aid['evidence_ids']) <= evidence, 'Learning aid evidence is invalid')
        if aid['origin'] == 'generated':
            require(aid['label'] in ('教学示例', '假设示例') and bool(aid['assumptions']) and not aid['evidence_ids'], 'Generated learning example masquerades as evidence or has no assumptions')
        else:
            require(bool(aid['evidence_ids']), 'Source learning aid needs evidence')
        placement = [s for s in sections.values() if aid['id'] in s.get('learning_aid_ids', [])]
        require(all(set(aid['target_block_ids']) <= set(s['source_block_ids']) for s in placement), 'Learning aid is placed against a different concept')
    placed = {aid_id for section in sections.values() for aid_id in section.get('learning_aid_ids', [])}
    require(placed == aids.keys(), 'Learning aids were not placed in the artifact')
    action_ids = indexed(spec['interactions'], 'interaction')
    for action in action_ids.values():
        require(bool(action['target_block_ids']) and set(action['target_block_ids']) <= blocks.keys(), 'Action target is invalid')
        require(bool(action['goal_ids']) and set(action['goal_ids']) <= goals.keys(), 'Action goal is invalid')
        mode = action['delivery_mode']
        required_params = action.get('required_parameters', [])
        defaults = action.get('default_parameters', {})
        require(set(required_params) <= action['parameter_constraints'].keys(), 'Required parameter is undeclared')
        if action['operation'] == 'change_assumption':
            require(bool(required_params), 'Changing an assumption needs declared required parameters')
        validate_parameters(action, defaults)
        if mode == 'agent':
            require(request['capabilities']['agent_callbacks'], 'Host has no Agent callback bridge')
        if mode == 'prompt':
            require(bool(action.get('prompt_text')), 'Prompt continuation must be usable')
            require(not request['constraints'].get('requires_automatic_actions'), 'Prompt continuation cannot satisfy automatic execution')
    adaptation = spec['adaptation']
    signal_map = indexed(signals(request), 'signal')
    require(set(adaptation['applied_signal_ids']) <= signal_map.keys(), 'Invented learner signal')
    require(set(adaptation['focus_block_ids'] + adaptation['deemphasized_block_ids']) <= blocks.keys(), 'Adaptation refers to unknown content')
    require(not (set(adaptation['focus_block_ids']) & set(adaptation['deemphasized_block_ids'])), 'A block cannot be focused and deemphasized')
    overrides = adaptation.get('explanation_overrides', {})
    require(set(overrides) <= blocks.keys(), 'Explanation override target is invalid')
    require(not overrides or bool(adaptation['applied_signal_ids']), 'Explanation adaptation needs grounded learner signals')
    for signal in request['learner_context']['feedback'] + request['learner_context']['confusions']:
        targets = set(signal.get('block_ids', []))
        if targets:
            require(signal['id'] in adaptation['applied_signal_ids'] and targets <= set(adaptation['focus_block_ids']), 'A targeted understanding gap was ignored')
            require(targets <= overrides.keys(), 'Targeted feedback needs a revised explanation')
            require(all(overrides[bid] != block_markdown(blocks[bid]) for bid in targets), 'Targeted feedback retained the identical explanation')
    consent = request['learner_context']['check_consent']
    require((adaptation['check_offer'] == 'accepted') == (consent == 'accepted'), 'Understanding-check consent does not match')
    require(consent != 'declined' or adaptation['check_offer'] == 'declined', 'User refusal was ignored')
    questions = adaptation.get('questions', [])
    require(not questions or consent == 'accepted', 'Do not expose a quiz before acceptance')
    require(all(q['goal_id'] in goals for q in questions), 'Quiz refers to unknown understanding goal')
    require(consent != 'accepted' or bool(questions), 'Accepted check needs questions')
    expected = compute_changes(request, spec['goal_coverage'], spec['sections'])
    require(spec['change_set'] == expected, 'Version differences are incomplete or fabricated; use changes command')
    writing = spec.get('writing', {})
    rewrites = writing.get('rewrites', {})
    require(set(rewrites) <= shown, 'Writing rewrite targets content outside the presentation')
    require(all(blocks[bid]['kind'] == 'text' for bid in rewrites), 'Writing rewrites apply to text blocks; keep graph facts structured')
    glossary = writing.get('glossary', [])
    require(len({g['term'].strip().casefold() for g in glossary}) == len(glossary), 'A glossary term has multiple definitions')
    if spec['presentation']['format'] == 'mp4':
        require('video' in spec, 'MP4 needs a content-driven video scene plan')
        scenes = spec['video']['scenes']; indexed(scenes, 'video scene')
        referenced = {bid for scene in scenes for bid in scene['source_block_ids']}
        require(referenced == shown, 'Video scenes must cover the displayed result blocks exactly')
        for scene in scenes:
            block = blocks[scene['source_block_ids'][0]]
            nodes = {n['id'] for n in block['data'].get('nodes', [])}
            require(set(scene.get('highlight_node_ids', [])) <= nodes, 'Video highlights an unknown node')
            if block['kind'] == 'relations':
                require(len(nodes) <= 12, 'Split video graphs larger than 12 nodes into focused scenes')
    return spec


def validate_parameters(action, params):
    require(isinstance(params, dict), 'Continuation parameters must be an object')
    allowed = action['parameter_constraints']
    require(set(params) <= set(allowed), 'Undeclared continuation parameters')
    for key, value in params.items():
        if isinstance(allowed[key], list):
            values = value if isinstance(value, list) else [value]
            require(set(values) <= set(allowed[key]), 'Parameter is outside the declared allowed values')
        elif isinstance(allowed[key], dict):
            # Parameter constraints are local schemas without remote references.
            require('$ref' not in canonical(allowed[key]), 'Remote parameter references are unsupported')
            errors = list(Draft202012Validator(allowed[key]).iter_errors(value))
            require(not errors, 'Parameter does not satisfy the declared type/range')
        else:
            raise ContractError('Parameter constraints must be an allowed-value list or local JSON Schema')


def continue_task(request, spec, action_id, params=None):
    validate_spec(spec, request)
    require(spec['decision'] == 'selected', 'Cannot continue a blocked plan')
    action = next((a for a in spec['interactions'] if a['id'] == action_id), None)
    require(action is not None, 'Unknown interaction')
    require(params is None or isinstance(params, dict), 'Continuation parameters must be an object')
    params = {**action.get('default_parameters', {}), **(params or {})}
    validate_parameters(action, params)
    require(set(action.get('required_parameters', [])) <= params.keys(), 'Continuation is missing required parameters; provide defaults or --params')
    selected = [b for b in request['result']['blocks'] if b['id'] in action['target_block_ids']]
    instructions = {
        'compare': '按一致维度比较所列内容；缺失数据标记未知，不能补造。',
        'inspect_evidence': '核验所列结论、原始依据、单位与限制；无法读取来源时明确缺口。',
        'change_assumption': '在独立假设场景中分析这些内容；新研究或重算交回上游，保留真实结果。',
        'challenge': '检查结论的依据、适用边界和薄弱环节；区分已验证问题与待调查假说。',
    }
    task = {'operation': action['operation'], 'request_id': request['request_id'], 'result_ref': result_ref(request['result']), 'target_block_ids': action['target_block_ids'], 'goal_ids': action['goal_ids'], 'parameters': params, 'source_blocks': selected, 'evidence': request['result']['evidence'], 'uncertainties': request['result']['uncertainties'], 'instruction': instructions[action['operation']], 'planner_prompt': action.get('prompt_text', ''), 'execution': 'copy_to_upstream_agent'}
    if action['operation'] == 'change_assumption':
        task['scenario_id'] = 'scenario-' + hashlib.sha256(canonical({'action': action_id, 'result': task['result_ref'], 'params': params}).encode()).hexdigest()[:16]
        task['preserve_original_result'] = True
    return task


def add_feedback(request, signal_id, text, source_ref, targets, consent=None):
    request = copy.deepcopy(request)
    require(source_ref in request['session_refs'], 'Feedback source is not in the trusted current session')
    request['learner_context']['feedback'].append({'id': signal_id, 'text': text, 'source_ref': source_ref, 'block_ids': targets})
    if consent:
        request['learner_context']['check_consent'] = consent
    return validate_request(request)


def md(value):
    value = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)
    return re.sub(r'([\\`*_{}\[\]<>#|])', r'\\\1', value).replace('\n', ' / ')


def block_markdown(block):
    data, kind = block['data'], block['kind']
    if kind == 'text':
        return md(data['content'])
    if kind == 'steps':
        return '\n'.join(f'{i}. {md(x)}' for i, x in enumerate(data['items'], 1))
    if kind == 'relations':
        labels = {n['id']: n['label'] for n in data['nodes']}
        return '\n'.join(f'- {md(labels[e["from"]])} → {md(labels[e["to"]])}：{md(e["label"])}' for e in data['edges']) + '\n\n节点：' + '、'.join(md(v) for v in labels.values())
    if kind == 'series':
        columns = ['时间或类别', '数值', '单位']
        rows = [[p['label'], '缺失' if p['value'] is None else p['value'], data['unit']] for p in data['points']]
    else:
        columns = data['columns']
        rows = [[r[c] if r[c] is not None else '未知' for c in columns] for r in data['rows']]
    return '| ' + ' | '.join(md(c) for c in columns) + ' |\n| ' + ' | '.join('---' for c in columns) + ' |\n' + '\n'.join('| ' + ' | '.join(md(v) for v in row) + ' |' for row in rows)


def make_chunks(request, spec):
    result = request['result']
    blocks = {b['id']: b for b in result['blocks']}
    aids = {a['id']: a for a in spec['learning_aids']}
    overrides = spec['adaptation'].get('explanation_overrides', {})
    chunks = [('理解目标', '\n'.join('- ' + md(g['description']) + '；检查：' + md(g['success_criteria']) for g in request['comprehension_goals']))]
    changes = spec['change_set']
    change_text = {'first_version': '首次交付，已建立本次版本基线。', 'unchanged': '业务结果与依据没有变化。', 'changed': '以下内容或依据发生变化。'}[changes['status']]
    for c in changes['changes']:
        change_text += '\n- ' + md(c['description']) + '；' + md(c['reason']) + '；目标：' + md(', '.join(c['affected_goal_ids']))
        old = request['baseline']['result']
        if c['kind'] in ('evidence_changed', 'uncertainty_changed'):
            collection = 'evidence' if c['kind'] == 'evidence_changed' else 'uncertainties'
            previous_items = {x['id']: x for x in old[collection]}
            current_items = {x['id']: x for x in result[collection]}
            for item_id in c['subject_ids']:
                change_text += '\n  原记录：' + md(canonical(previous_items[item_id]) if item_id in previous_items else '此前不存在')
                change_text += '\n  新记录：' + md(canonical(current_items[item_id]) if item_id in current_items else '已撤回')
            continue
        if c['kind'] == 'summary_changed':
            change_text += '\n  原摘要：' + md(old['summary']) + '\n  新摘要：' + md(result['summary'])
            continue
        for bid in c['before_block_ids']:
            b = next(b for b in old['blocks'] if b['id'] == bid)
            change_text += '\n  原内容 ' + md(bid) + '：' + md(canonical(b['data']))
        for bid in c['after_block_ids']:
            change_text += '\n  新内容 ' + md(bid) + '：' + md(canonical(blocks[bid]['data']))
    chunks.append(('变化与影响', change_text))
    sections = {s['id']: s for s in spec['sections']}
    for mode, title in [('explain', '解释视图'), ('verify', '核验视图')]:
        lines = ['结果版本：' + md(result['result_id']) + ' / ' + md(result['revision'])]
        for sid in spec['views'][mode]['section_ids']:
            section = sections[sid]
            lines.append('\n### ' + md(sid))
            if section.get('source_field'):
                lines.append(md(result['summary']))
            for bid in section['source_block_ids']:
                block = blocks[bid]
                if mode == 'explain' and bid in spec['adaptation']['deemphasized_block_ids']:
                    lines.append('\n[' + md(bid) + '] 用户已了解的背景，完整内容可在核验视图查看。')
                else:
                    focus = '重点：' if mode == 'explain' and bid in spec['adaptation']['focus_block_ids'] else ''
                    rewrite = media.effective_text(block, spec) if mode == 'explain' else ''
                    lines.append('\n[' + md(bid) + '] ' + focus + '\n\n' + (md(rewrite) if rewrite else block_markdown(block)))
                if mode == 'verify':
                    lines.append('引用：' + md(', '.join(block['evidence_ids']) or '未提供') + '；限制：' + md(', '.join(block['uncertainty_ids']) or '无单独映射'))
                    lines.append('原始数据：' + md(canonical(block['data'])))
            if mode == 'explain':
                for aid_id in section.get('learning_aid_ids', []):
                    aid = aids[aid_id]
                    lines.append('\n' + md(aid['label']) + '：' + md(aid['content']) + '\n假设：' + md('；'.join(aid['assumptions']) or '来源说明') + '\n证据：' + md(', '.join(aid['evidence_ids']) or '生成示例，不构成业务证据'))
        if mode == 'verify':
            lines.append('\n### 来源与限制')
            for e in result['evidence']:
                lines.append('- [' + md(e['id']) + '] ' + md(e['title']) + '：' + md(e['locator']))
            if not result['evidence']:
                lines.append('未提供来源；不能据此声称已经证实。')
            for u in result['uncertainties']:
                lines.append('- [' + md(u['id']) + '] ' + md(u['text']))
            if spec['preservation']['omitted_block_ids']:
                lines.append('省略详情：' + md(', '.join(spec['preservation']['omitted_block_ids'])))
            lines.append('完整原始结果保存在同目录 baseline.json。')
        chunks.append((title, '\n\n'.join(lines)))
    adaptation = spec['adaptation']
    chunks.append(('本次解释调整', md(adaptation['reason']) + '\n重点：' + md(', '.join(adaptation['focus_block_ids']) or '通用') + '\n理解检查：' + md(adaptation['check_offer'])))
    if adaptation['check_offer'] == 'accepted':
        chunks.append(('可选理解检查', '\n'.join('- ' + md(q['question']) for q in adaptation['questions'])))
    elif adaptation['check_offer'] == 'offered':
        chunks.append(('可选理解检查', '如愿意，可在当前会话接受简短理解检查；也可以跳过。'))
    glossary = spec.get('writing', {}).get('glossary', [])
    if glossary:
        chunks.append(('术语说明', '\n'.join('- ' + md(g['term']) + '：' + md(g['definition']) for g in glossary)))
    return chunks


def render(request, spec, out_dir):
    """Build a complete bundle before publishing files into the chosen directory."""
    out = Path(out_dir).resolve()
    if spec.get('presentation', {}).get('format') == 'mp4':
        require(not (out / 'presentation.mp4').exists(), 'Video output exists; use a new output directory')
    with tempfile.TemporaryDirectory(prefix='presentation-bundle-') as directory:
        staging = Path(directory)
        receipt = _render_bundle(request, spec, staging)
        files = [path for path in staging.iterdir() if path.is_file()]
        for path in files:
            target = out / path.name
            require(not target.exists() or target.read_bytes() == path.read_bytes(), f'Output already exists with different content: {target}')
        for path in files:
            write_bytes(out / path.name, path.read_bytes())
    return receipt


def _render_bundle(request, spec, out_dir):
    validate_spec(spec, request)
    require(request['mode'] == 'render' and spec['decision'] == 'selected', 'Render needs render mode and a selected spec')
    fmt = spec['presentation']['format']
    require(fmt in ('markdown', 'html', 'svg', 'mp4') and spec['render_request']['renderer_id'] == fmt, 'Available renderers: markdown, html, svg, mp4; use a host renderer for other formats')
    require(all(a['delivery_mode'] == 'prompt' or (fmt == 'html' and a['delivery_mode'] == 'local' and a['operation'] in ('compare', 'inspect_evidence')) for a in spec['interactions']), 'Use prompt continuations, or HTML local compare/inspect; host callbacks need a host adapter')
    style = media.writing_report(request, spec)
    if 'writing' in spec:
        require(not style['violations'], 'Writing exceeds configured sentence limits: ' + canonical(style['violations'][:3]))
    out = Path(out_dir).resolve()
    require(not (out / 'presentation.mp4').exists() if fmt == 'mp4' else True, 'Video output exists; use a new output directory')
    chunks = make_chunks(request, spec)
    continuations = [dict(id=a['id'], task=continue_task(request, spec, a['id'])) for a in spec['interactions']]
    for continuation in continuations:
        chunks.append(('继续思考 ' + continuation['id'], '将以下完整任务复制给上游 Agent：\n\n```json\n' + json.dumps(continuation['task'], ensure_ascii=False, indent=2) + '\n```'))
    title = request['intent']['goal']
    if fmt == 'markdown':
        artifact = media.readable_markdown(request,spec,continuations) if 'writing' in spec else '# ' + md(title) + '\n\n' + '\n\n'.join('## ' + name + '\n\n' + body for name, body in chunks) + '\n'
        mime = 'text/markdown'
    elif fmt == 'html':
        artifact = media.interactive_html(request, spec, continuations)
        mime = 'text/html'
    elif fmt == 'svg':
        artifact = media.diagram_svg(request, spec)
        mime = 'image/svg+xml'
    else:
        artifact = None; mime = 'video/mp4'
    if fmt == 'markdown': mime = 'text/markdown'
    suffix = {'markdown': 'md', 'html': 'html', 'svg': 'svg', 'mp4': 'mp4'}[fmt]
    artifact_path = out / ('presentation.' + suffix)
    video_info = None
    if artifact is not None:
        require(len(artifact.encode()) <= request['constraints'].get('max_output_bytes', sys.maxsize), 'Artifact exceeds max_output_bytes')
        write_file(artifact_path, artifact)
    else:
        artifact_path, video_info = media.render_video(request, spec, out)
        require(artifact_path.stat().st_size <= request['constraints'].get('max_output_bytes', sys.maxsize), 'Encoded video exceeds max_output_bytes; simplify the scene plan')
    additional = []
    if fmt in ('svg', 'mp4'):
        guide = media.interactive_html(request, spec, continuations)
        write_file(out / 'guide.html', guide)
        additional.append({'ref': 'guide.html', 'format': 'html', 'media_type': 'text/html', 'sha256': hashlib.sha256(guide.encode()).hexdigest()})
    write_json(out / 'writing-report.json', style)
    write_json(out / 'continuations.json', continuations)
    baseline = {'result': request['result'], 'spec_ref': spec['spec_id'], 'artifact_refs': [{'ref': artifact_path.name, 'format': fmt}]}
    write_json(out / 'baseline.json', baseline)
    restored = read_json(out / 'baseline.json')
    require(restored == baseline, 'Baseline restore failed')
    passed = lambda name, message: {'check_id': name, 'status': 'passed', 'message': message}
    checks = [passed('R1', '理解目标已映射到内容与检查方法'), passed('R2', '解释/核验绑定同一版本并保留原始数据'), passed('R3', spec['learning_aids_reason']), passed('R4', f'{len(continuations)} 个可复制完整任务；未执行外部回调'), passed('R5', spec['change_set']['status'] + '；基线已回读恢复'), passed('R6', spec['adaptation']['reason'])]
    digest = lambda data: hashlib.sha256(data).hexdigest()
    writing_check={'check_id':'writing_rules','status':'failed' if style['violations'] else 'passed','message':f'{style["sentences_checked"]} sentences checked; profile {style["profile"]}; ASD compliance not claimed'}
    validations = [passed('contracts_and_bindings', '结构、引用、版本与同目录文件保存已检查'), writing_check, {'check_id': 'semantic_review', 'status': 'not_checked', 'message': '人工核对解释和教学示例是否忠于事实'}, {'check_id': 'visual_review', 'status': 'not_checked', 'message': '打开真实产物检查可读性和导航'}]
    if video_info:
        validations.append(passed('video_streams', 'ffprobe verified video/subtitles and requested narration audio'))
    receipt = {'schema_version': '1.0', 'request_id': request['request_id'], 'result_ref': result_ref(request['result']), 'spec_id': spec['spec_id'], 'renderer_id': fmt, 'status': 'generated', 'artifact_refs': [{'ref': artifact_path.name, 'format': fmt, 'media_type': mime, 'sha256': digest(artifact_path.read_bytes())}] + additional, 'validation_results': validations, 'warnings': ['静态检查不证明用户已经理解；人工语义与视觉检查需单独记录。'], 'feature_checks': checks, 'baseline_receipt': {'ref': 'baseline.json', 'result_ref': result_ref(request['result']), 'sha256': digest((out / 'baseline.json').read_bytes()), 'restored': True}, 'continuation_refs': ['continuations.json']}
    schema_check('receipt', receipt)
    write_json(out / 'receipt.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    p = sub.add_parser('lint-writing'); p.add_argument('request'); p.add_argument('spec'); p.add_argument('-o', '--output', required=True)
    p = sub.add_parser('prepare'); p.add_argument('request'); p.add_argument('-o', '--output', required=True)
    p = sub.add_parser('validate'); p.add_argument('kind', choices=['request', 'spec', 'receipt']); p.add_argument('file'); p.add_argument('--request')
    p = sub.add_parser('changes'); p.add_argument('request'); p.add_argument('--spec'); p.add_argument('-o', '--output', required=True)
    p = sub.add_parser('render'); p.add_argument('request'); p.add_argument('spec'); p.add_argument('--out-dir', required=True)
    p = sub.add_parser('continue'); p.add_argument('request'); p.add_argument('spec'); p.add_argument('action_id'); p.add_argument('--params', default='{}'); p.add_argument('-o', '--output', required=True)
    p = sub.add_parser('feedback'); p.add_argument('request'); p.add_argument('--id', required=True); p.add_argument('--text', required=True); p.add_argument('--source-ref', required=True); p.add_argument('--blocks', nargs='+', required=True); p.add_argument('--consent', choices=['accepted', 'declined']); p.add_argument('-o', '--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            print(json.dumps(media.dependencies(), ensure_ascii=False))
        elif args.command == 'lint-writing':
            request = validate_request(read_json(args.request)); spec = validate_spec(read_json(args.spec), request)
            write_json(args.output, media.writing_report(request, spec))
        elif args.command == 'prepare':
            write_json(args.output, prepare(read_json(args.request)))
        elif args.command == 'validate':
            value = read_json(args.file)
            if args.kind == 'request': validate_request(value)
            elif args.kind == 'spec':
                require(bool(args.request), '--request is required for spec semantic checks')
                validate_spec(value, read_json(args.request))
            else: schema_check('receipt', value)
            print('Valid ' + args.kind)
        else:
            request = validate_request(read_json(args.request))
            if args.command == 'changes':
                spec = read_json(args.spec) if args.spec else None
                write_json(args.output, compute_changes(request, spec.get('goal_coverage') if spec else None, spec.get('sections') if spec else None))
            elif args.command == 'render':
                receipt = render(request, read_json(args.spec), args.out_dir)
                print(json.dumps({'status': receipt['status'], 'artifact_refs': receipt['artifact_refs']}, ensure_ascii=False))
            elif args.command == 'continue':
                write_json(args.output, continue_task(request, read_json(args.spec), args.action_id, json.loads(args.params)))
            elif args.command == 'feedback':
                write_json(args.output, add_feedback(request, args.id, args.text, args.source_ref, args.blocks, args.consent))
    except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
