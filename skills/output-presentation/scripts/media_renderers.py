"""Content-driven writing, SVG, interactive HTML and narrated video renderers."""
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]


def selected_blocks(request, spec):
    ids = {bid for section in spec['sections'] for bid in section['source_block_ids']}
    return [b for b in request['result']['blocks'] if b['id'] in ids]


def effective_text(block, spec):
    return spec['adaptation'].get('explanation_overrides', {}).get(block['id'],
        spec.get('writing', {}).get('rewrites', {}).get(block['id'], block['data'].get('content', '')))


def explain_blocks(request, spec):
    sections = {section['id']: section for section in spec['sections']}
    ids = {bid for sid in spec['views']['explain']['section_ids'] for bid in sections[sid]['source_block_ids']}
    return [block for block in request['result']['blocks'] if block['id'] in ids]


def change_details(request, spec):
    old = (request.get('baseline') or {}).get('result', {})
    current = request['result']
    details = []
    for change in spec['change_set']['changes']:
        kind = change['kind']
        if kind == 'summary_changed':
            before, after = old.get('summary'), current['summary']
        elif kind in ('evidence_changed', 'uncertainty_changed'):
            field = 'evidence' if kind == 'evidence_changed' else 'uncertainties'
            before = [item for item in old.get(field, []) if item['id'] in change['subject_ids']]
            after = [item for item in current[field] if item['id'] in change['subject_ids']]
        else:
            before = [block for block in old.get('blocks', []) if block['id'] in change['before_block_ids']]
            after = [block for block in current['blocks'] if block['id'] in change['after_block_ids']]
        details.append({**change, 'before': before, 'after': after})
    return details


def readable_value(value):
    if value is None or value == []: return '无记录'
    if isinstance(value, str): return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def markdown_text(value):
    literal=html.escape(str(value),quote=False)
    return re.sub(r'([\\`*_{}\[\]#|])', r'\\\1', literal).replace('\n', ' / ')


def writing_report(request, spec):
    policy = spec.get('writing', {})
    profile = policy.get('profile', 'plain')
    max_words = policy.get('max_sentence_words', 20 if profile == 'ste-inspired' else 25)
    max_chars = policy.get('max_sentence_chars', 70)
    texts = [('summary', policy.get('summary', request['result']['summary']))]
    for block in selected_blocks(request, spec):
        value = effective_text(block, spec)
        if value: texts.append((block['id'], value))
        if block['kind'] == 'steps': texts.extend((block['id'], text) for text in block['data']['items'])
    if spec['presentation']['format'] == 'mp4':
        texts.extend((scene['id'],scene['narration']) for scene in spec.get('video',{}).get('scenes',[]))
    violations = []
    count = 0
    for source, text in texts:
        sentences = re.split(r'(?<=[。！？])|(?<=[.!?])\s+', text)
        for sentence in filter(str.strip, sentences):
            count += 1
            chinese = bool(re.search(r'[\u4e00-\u9fff]', sentence))
            size = len(re.sub(r'\s', '', sentence)) if chinese else len(re.findall(r"\b[\w'-]+\b", sentence))
            limit = max_chars if chinese else max_words
            if size > limit:
                violations.append({'source': source, 'sentence': sentence, 'size': size, 'limit': limit})
    return {'profile': profile, 'sentences_checked': count, 'violations': violations,
            'glossary': policy.get('glossary', []), 'asd_ste100_compliance': 'not_claimed',
            'semantic_review': 'requires_review'}


def readable_markdown(request,spec,continuations):
    result=request['result'];policy=spec.get('writing',{});lines=['# '+markdown_text(request['intent']['goal']),markdown_text(policy.get('summary',result['summary']))]
    lines+=['## 理解要点','\n'.join('- '+markdown_text(g['description']) for g in request['comprehension_goals'])]
    for block in explain_blocks(request,spec):
        if block['id'] in spec['adaptation']['deemphasized_block_ids']:
            lines.append('已了解的背景已简化，完整内容保留在原始结果中。')
            continue
        value=effective_text(block,spec)
        if value:lines.append(markdown_text(value))
        elif block['kind']=='relations':
            names={n['id']:n['label'] for n in block['data']['nodes']}
            lines.append('\n'.join('- '+markdown_text(names[e['from']])+' → '+markdown_text(names[e['to']])+'：'+markdown_text(e['label']) for e in block['data']['edges']))
        elif block['kind']=='steps':lines.append('\n'.join(f'{i+1}. '+markdown_text(item) for i,item in enumerate(block['data']['items'])))
        else:
            if block['kind']=='series':
                columns=['时间或类别','数值','单位'];rows=[[p['label'],'缺失'if p['value']is None else p['value'],block['data']['unit']]for p in block['data']['points']]
            else:columns=block['data']['columns'];rows=[[row[c] if row[c]is not None else'未知'for c in columns]for row in block['data']['rows']]
            escape=markdown_text
            lines.append('| '+' | '.join(escape(c)for c in columns)+' |\n| '+' | '.join('---'for c in columns)+' |\n'+'\n'.join('| '+' | '.join(escape(v)for v in row)+' |'for row in rows))
    for aid in spec['learning_aids']:lines+=['## '+markdown_text(aid['label']),markdown_text(aid['content']),'假设：'+markdown_text('；'.join(aid['assumptions']))]
    if policy.get('glossary'):lines+=['## 术语','\n'.join('- **'+markdown_text(g['term'])+'**：'+markdown_text(g['definition'])for g in policy['glossary'])]
    lines+=['## 依据与限制','\n'.join('- '+markdown_text(e['title'])+'：'+markdown_text(e['locator'])for e in result['evidence'])or'未提供来源。','\n'.join('- '+markdown_text(u['text'])for u in result['uncertainties'])]
    if spec['change_set']['changes']:
        lines.append('## 变化')
        for change in change_details(request,spec):
            lines += [markdown_text(change['description']+'；'+change['reason']), '原内容：'+markdown_text(readable_value(change['before'])), '新内容：'+markdown_text(readable_value(change['after']))]
    if continuations:lines+=['## 继续思考','\n'.join('- '+markdown_text(c['task']['instruction'])for c in continuations),'[完整后续任务](continuations.json) · [原始结果](baseline.json)']
    if spec['adaptation']['check_offer']=='accepted':lines+=['## 可选理解检查','\n'.join('- '+markdown_text(q['question'])for q in spec['adaptation'].get('questions',[]))]
    elif spec['adaptation']['check_offer']=='offered':lines+=['## 可选理解检查','如愿意，可以在当前会话选择简短理解检查；也可以跳过。']
    return '\n\n'.join(lines)+'\n'


def wrap_text(value, width=18):
    if re.search(r'[\u4e00-\u9fff]', value):
        return [value[i:i+width] for i in range(0, len(value), width)] or ['']
    lines, line = [], ''
    words = [chunk for word in value.split() for chunk in ([word[i:i+width] for i in range(0,len(word),width)] if len(word)>width else [word])]
    for word in words:
        if len(line + ' ' + word) > width and line:
            lines.append(line); line = word
        else: line = (line + ' ' + word).strip()
    return lines + [line]


def graph_geometry(block):
    data = block['data']
    if block['kind'] == 'steps':
        nodes = [{'id': str(i), 'label': text} for i, text in enumerate(data['items'])]
        edges = [{'id': str(i), 'from': str(i), 'to': str(i+1), 'label': '下一步'} for i in range(len(nodes)-1)]
    else:
        nodes, edges = data['nodes'], data['edges']
    if not nodes or len(nodes) > 36:
        raise ValueError('Diagram needs 1–36 nodes per block; split a larger graph into focused blocks.')
    incoming = {n['id']: 0 for n in nodes}
    ranks = {n['id']: 0 for n in nodes}
    for e in edges: incoming[e['to']] += 1
    queue = [n['id'] for n in nodes if incoming[n['id']] == 0]
    visited = []
    while queue:
        node = queue.pop(0); visited.append(node)
        for edge in edges:
            if edge['from'] == node:
                ranks[edge['to']] = max(ranks[edge['to']], ranks[node]+1)
                incoming[edge['to']] -= 1
                if incoming[edge['to']] == 0: queue.append(edge['to'])
    cyclic = len(visited) != len(nodes)
    max_rank = max(ranks.values())
    # Wrap long chains into rows; cycles retain every edge in a stable grid.
    if cyclic or max_rank > 3:
        columns = min(4, len(nodes)); positions = {n['id']: (i % columns, i // columns) for i,n in enumerate(nodes)}
    else:
        used = {}; positions = {}
        for n in nodes:
            col = ranks[n['id']]; row = used.get(col,0); used[col] = row+1
            positions[n['id']] = (col,row)
    height = max(86, max(len(wrap_text(n['label'],11)) for n in nodes)*22+35)
    result = []
    for n in nodes:
        col,row = positions[n['id']]
        result.append({**n, 'x': 50+col*290, 'y': 60+row*(height+80), 'w': 220, 'h': height})
    return result, edges, max(n['y']+height for n in result)+70


def diagram_block_svg(block, interactive=False):
    esc = html.escape
    bid = esc(block['id'], quote=True)
    elements = []
    if block['kind'] in ('relations','steps'):
        nodes,edges,height = graph_geometry(block)
        lookup = {n['id']:n for n in nodes}
        for edge in edges:
            a,b = lookup[edge['from']],lookup[edge['to']]
            ax,ay = a['x']+a['w'],a['y']+a['h']/2
            bx,by = b['x'],b['y']+b['h']/2
            skip_row=a['y']==b['y'] and b['x']-a['x']>400
            if skip_row:
                ax,ay=a['x']+a['w']/2,a['y'];bx,by=b['x']+b['w']/2,b['y']
                route=f'M {ax} {ay} C {ax} {ay-48}, {bx} {by-48}, {bx} {by}'
            elif bx <= ax:
                ax,ay = a['x']+a['w']/2,a['y']+a['h']; bx,by = b['x']+b['w']/2,b['y']
                route=f'M {ax} {ay} C {ax} {ay+45}, {bx} {by-45}, {bx} {by}'
            else: route=f'M {ax} {ay} C {ax+40} {ay}, {bx-40} {by}, {bx} {by}'
            label_y=min(ay,by)-40 if skip_row else (ay+by)/2-12
            elements.append(f'<g class="diagram-edge" data-edge-id="{esc(edge["id"],quote=True)}"><path d="{route}" stroke="#6999dd" stroke-width="2" fill="none" marker-end="url(#arrow)"/><text x="{(ax+bx)/2}" y="{label_y}" text-anchor="middle" font-size="12" fill="#5d7595">{esc(edge["label"])}</text><title>{esc(edge["label"])}</title></g>')
        for node in nodes:
            x,y,w,h = (node[k] for k in ('x','y','w','h'))
            lines = ''.join(f'<tspan x="{x+w/2}" y="{y+31+i*22}">{esc(line)}</tspan>' for i,line in enumerate(wrap_text(node['label'],11)))
            role='role="button" tabindex="0"' if interactive else 'role="group"'
            elements.append(f'<g class="diagram-node" {role} aria-label="{esc(node["label"],quote=True)}" data-block-id="{bid}" data-node-id="{esc(node["id"],quote=True)}"><title>{esc(node["label"])}</title><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#f1f6ff" stroke="#9fc4ff"/><text text-anchor="middle" font-size="17" fill="#183b70">{lines}</text></g>')
        return ''.join(elements),height
    if block['kind']=='series':
        points = block['data']['points']
        if len(points)>80: raise ValueError('Split series with more than 80 points into focused charts.')
        values=[p['value'] for p in points if p['value'] is not None]
        low=min([0]+values);high=max([1]+values);span=high-low or 1
        y=lambda value:300-(value-low)/span*220
        elements.append(f'<text x="70" y="35" fill="#4b698d" font-size="15">单位：{esc(block["data"]["unit"])}</text><line x1="70" y1="{y(0)}" x2="1110" y2="{y(0)}" stroke="#c3d3e8"/>')
        step=1000/max(1,len(points));bar=min(65,step*.65)
        for i,point in enumerate(points):
            x=90+i*step;v=point['value']
            if v is not None:
                top=min(y(v),y(0));bh=abs(y(v)-y(0))
                elements.append(f'<rect class="series-mark" data-block-id="{bid}" data-value="{v}" x="{x}" y="{top}" width="{bar}" height="{max(1,bh)}" rx="4" fill="#2e75ed"><title>{esc(point["label"])}：{v} {esc(block["data"]["unit"])}</title></rect><text x="{x+bar/2}" y="{top-8}" text-anchor="middle" font-size="12" fill="#42658e">{v}</text>')
            else: elements.append(f'<text x="{x+bar/2}" y="280" text-anchor="middle" font-size="12" fill="#8196af">缺失</text>')
            elements.append(f'<text x="{x+bar/2}" y="335" text-anchor="middle" font-size="12" fill="#637d9d">{esc(point["label"])}</text>')
        return ''.join(elements),380
    if block['kind']=='comparison':
        data=block['data'];cols=data['columns'];cw=1040/max(1,len(cols))
        rows=[dict(zip(cols,cols))]+data['rows']
        for j,row in enumerate(rows):
            yy=50+j*52;elements.append(f'<rect x="60" y="{yy}" width="1040" height="50" rx="5" fill="{"#eaf2ff" if j==0 else "#f8fafc"}"/>')
            for i,col in enumerate(cols):
                value=row[col];label='未知' if value is None else str(value)
                elements.append(f'<text x="{75+i*cw}" y="{yy+31}" font-size="14" fill="#3b577a">{esc(label)}</text>')
        return ''.join(elements),80+len(rows)*52
    lines=wrap_text(block['data']['content'],52)
    for i,line in enumerate(lines):elements.append(f'<text x="65" y="{60+i*30}" font-size="18" fill="#3c5778">{esc(line)}</text>')
    return ''.join(elements),100+len(lines)*30


def diagram_svg(request,spec,interactive=False):
    parts=[];offset=100
    requested = {bid for section in spec['sections'] if section['kind'] in ('diagram','chart') for bid in section['source_block_ids']}
    visual = [b for b in selected_blocks(request,spec) if b['kind'] != 'text' and (not requested or b['id'] in requested)]
    if not visual:
        raise ValueError('SVG needs a structured relationship, process or data block; plan one from the source first.')
    for block in visual:
        body,height=diagram_block_svg(block,interactive)
        parts.append(f'<g transform="translate(0,{offset})" data-block="{html.escape(block["id"],quote=True)}">{body}</g>')
        offset+=height+25
    title=html.escape(request['intent']['goal'])
    role='group' if interactive else 'img'
    cursor='pointer' if interactive else 'default'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {offset+70}" width="1200" role="{role}" aria-labelledby="title"><title id="title">{title}</title><desc>{html.escape(request["result"]["summary"])}</desc><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8Z" fill="#6999dd"/></marker></defs><style>text{{font-family:system-ui,sans-serif}}.diagram-node{{cursor:{cursor}}}.diagram-node:hover rect,.diagram-node:focus rect{{stroke:#1768ed;stroke-width:3}}</style><rect width="1200" height="{offset+70}" fill="white"/><text x="60" y="54" font-size="25" fill="#182d49">{title}</text>{"".join(parts)}<text x="60" y="{offset+40}" font-size="12" fill="#8b9cb0">图形与标签来自本次结果；完整原始值、来源和限制见随附说明页。</text></svg>'


def safe_json(value):
    return json.dumps(value,ensure_ascii=False).replace('<','\\u003c').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')


def interactive_html(request,spec,continuations):
    blocks=selected_blocks(request,spec)
    explained=explain_blocks(request,spec)
    explain_ids={b['id'] for b in explained}
    visual=any(block['kind']!='text' for block in explained)
    diagram_spec=json.loads(json.dumps(spec))
    diagram_spec['sections']=[{**section,'source_block_ids':[bid for bid in section['source_block_ids'] if bid in explain_ids]} for section in spec['sections']]
    diagram=diagram_svg(request,diagram_spec,interactive=True) if visual else ''
    esc=html.escape
    summary=spec.get('writing',{}).get('summary',request['result']['summary'])
    cards=[]
    for block in explained:
        content=effective_text(block,spec)
        if block['id'] in spec['adaptation']['deemphasized_block_ids']:
            cards.append('<details class="content-card"><summary>已了解的背景</summary><p>'+esc(content or readable_value(block['data']))+'</p></details>')
            continue
        if not content: content={'relations':'点击图中的节点，查看相关关系与依据。','series':'在图中查看数值；也可搜索、筛选数据表。','comparison':'按列比较记录，未知值保留为未知。','steps':'沿图中的顺序查看过程。'}[block['kind']]
        rows=''
        if block['kind']=='steps': rows='<ol>'+''.join('<li>'+esc(item)+'</li>' for item in block['data']['items'])+'</ol>'
        if block['kind'] in ('series','comparison'):
            if block['kind']=='series':
                cols=['时间或类别','数值','单位'];data=[{'时间或类别':p['label'],'数值':'缺失' if p['value'] is None else p['value'],'单位':block['data']['unit']}for p in block['data']['points']]
            else:cols=block['data']['columns'];data=block['data']['rows']
            rows='<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+esc(c)+'</th>'for c in cols)+'</tr></thead><tbody>'+''.join('<tr class="data-row">'+''.join('<td>'+esc('未知' if row[c] is None else str(row[c]))+'</td>'for c in cols)+'</tr>'for row in data)+'</tbody></table></div>'
        focus='<span class="focus-label">重点</span>' if block['id'] in spec['adaptation']['focus_block_ids'] else ''
        cards.append('<article class="content-card" data-block="'+esc(block['id'],quote=True)+'">'+focus+'<p>'+esc(content)+'</p>'+rows+'</article>')
    aid_cards=''.join('<article class="learning"><span>'+esc(a['label'])+'</span><p>'+esc(a['content'])+'</p><small>假设：'+esc('；'.join(a['assumptions']) or '依来源说明')+'</small></article>'for a in spec['learning_aids'])
    def source_link(e):
        locator=e['locator'];title=esc(e['title'])
        if locator.startswith(('https://','http://')):
            return '<li><a href="'+esc(locator,quote=True)+'" target="_blank" rel="noopener noreferrer">'+title+'</a></li>'
        return '<li>'+title+' — '+esc(locator)+'</li>'
    sources=''.join(source_link(e) for e in request['result']['evidence']) or '<li>未提供来源，不能据此声称已证实。</li>'
    limits=''.join('<li>'+esc(u['text'])+'</li>'for u in request['result']['uncertainties']) or '<li>未提供额外限制。</li>'
    glossary=''.join('<dt>'+esc(g['term'])+'</dt><dd>'+esc(g['definition'])+'</dd>'for g in spec.get('writing',{}).get('glossary',[]))
    action_controls=''.join('<button class="task-button" data-action="'+esc(a['id'],quote=True)+'">'+{'compare':'比较内容','inspect_evidence':'核验依据','change_assumption':'改变假设','challenge':'检查薄弱点'}[a['operation']]+'</button>'for a in spec['interactions'])
    questions=''
    if spec['adaptation']['check_offer']=='accepted':
        questions='<section><h2>可选理解检查</h2>'+''.join('<p>'+esc(q['question'])+'</p>'for q in spec['adaptation'].get('questions',[]))+'</section>'
    elif spec['adaptation']['check_offer']=='offered':
        questions='<section><h2>可选理解检查</h2><p>如愿意，可以在当前会话选择简短理解检查；也可以跳过。</p></section>'
    payload={'result':request['result'],'blocks':blocks,'spec':spec,'continuations':continuations}
    script=(ROOT/'assets'/'interactive.js').read_text()
    digest=__import__('base64').b64encode(hashlib.sha256(script.encode()).digest()).decode()
    css=(ROOT/'assets'/'interactive.css').read_text()
    title=esc(request['intent']['goal']);lang=esc(request['intent'].get('language','zh-CN'),quote=True)
    changes=''.join('<li>'+esc(c['description'])+'；'+esc(c['reason'])+'<p>原内容：'+esc(readable_value(c['before']))+'</p><p>新内容：'+esc(readable_value(c['after']))+'</p></li>'for c in change_details(request,spec))
    goals='<section class="goals"><h2>理解要点</h2><ul>'+''.join('<li>'+esc(goal['description'])+'</li>' for goal in request['comprehension_goals'])+'</ul></section>'
    cards.insert(0,goals)
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{digest}'; img-src data:"><title>{title}</title><style>{css}</style></head><body><header><span>OUTPUT PRESENTATION</span><span>理解 · 核验 · 继续</span></header><main><h1>{title}</h1><p class="summary">{esc(summary)}</p><div class="toolbar"><div role="tablist" aria-label="阅读视图"><button id="explain-tab" role="tab" aria-selected="true" aria-controls="explain">理解</button><button id="verify-tab" role="tab" aria-selected="false" aria-controls="verify">核验依据</button></div><label>搜索内容 <input id="search" type="search" placeholder="搜索节点、数据或说明"></label></div><section id="explain" role="tabpanel"><div class="graph">{diagram}</div><aside id="node-detail" aria-live="polite">点击图中的节点，可以查看与它有关的输入、输出关系及来源。</aside><div id="cards">{''.join(cards)}</div><div>{aid_cards}</div>{'<dl>'+glossary+'</dl>' if glossary else ''}{questions}</section><section id="verify" role="tabpanel" hidden><h2>原始结果与依据</h2><ul>{sources}</ul><h3>适用限制</h3><ul>{limits}</ul><details><summary>查看原始结果</summary><pre>{esc(json.dumps(request['result'],ensure_ascii=False,indent=2))}</pre></details></section>{'<section><h2>变化与影响</h2><ul>'+changes+'</ul></section>' if changes else ''}<section class="next"><h2>继续思考</h2><div class="actions">{action_controls}</div><div id="comparison" hidden></div><label id="assumption-label" hidden>新的假设 <input id="assumption" type="text"></label><details id="task-details"><summary>查看完整后续任务</summary><textarea id="task" aria-label="可复制的完整后续任务" rows="7" readonly></textarea></details><button id="copy-task">复制后续任务</button><p id="status" role="status"></p></section></main><script id="presentation-data" type="application/json">{safe_json(payload)}</script><script>{script}</script></body></html>'''


def dependencies():
    return {'svg':True,'html':True,'markdown':True,'mp4':bool(shutil.which('ffmpeg') and shutil.which('ffprobe')),
            'local_narration':bool(shutil.which('say') or shutil.which('espeak-ng'))}


def probe(path):
    raw=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=30)
    return json.loads(raw.stdout)


def local_narration(text,path,language,voice=None):
    source=path.with_suffix('.txt');source.write_text(text,encoding='utf-8')
    if shutil.which('say'):
        voices=subprocess.run(['say','-v','?'],capture_output=True,text=True,check=True,timeout=30).stdout
        available=[(m.group(1).strip(),m.group(2))for line in voices.splitlines()if(m:=re.match(r'^(.*?)\s+([a-z]{2}_[A-Z]{2})\s+#',line))]
        if voice and voice not in [v[0]for v in available]:raise ValueError('Requested voice is not locally available.')
        lang=language.replace('-','_').lower()
        options=[name for name,l in available if l.lower()==lang or l.split('_')[0].lower()==lang.split('_')[0]]
        if not options:raise ValueError('No installed narration voice for '+language)
        choice=voice or next((v for prefix in ('Tingting','Samantha','Eddy')for v in options if v.startswith(prefix)),options[0])
        audio=path.with_suffix('.aiff')
        subprocess.run(['say','-v',choice,'-r','180','-f',str(source),'-o',str(audio)],check=True,capture_output=True,timeout=120)
    elif shutil.which('espeak-ng'):
        audio=path.with_suffix('.wav')
        subprocess.run(['espeak-ng','-v',voice or ('cmn'if language.startswith('zh')else'en-us'),'-s','150','-f',str(source),'-w',str(audio)],check=True,capture_output=True,timeout=120)
    else:raise ValueError('Local narration requires macOS say or espeak-ng. Select explicit silent mode if narration is unnecessary.')
    info=probe(audio);duration=float(info['format']['duration'])
    if duration<=0:raise ValueError('Narration audio is empty.')
    return audio,duration


@lru_cache(maxsize=24)
def video_font(size):
    from PIL import ImageFont
    paths=['/System/Library/Fonts/STHeiti Light.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in paths:
        if Path(path).exists():return ImageFont.truetype(path,size)
    raise ValueError('Video renderer needs a local Unicode font.')


def video_frame(request,scene,block,progress,width=1280,height=720):
    from PIL import Image,ImageDraw
    image=Image.new('RGB',(width,height),'#f8fafc');draw=ImageDraw.Draw(image)
    def text(x,y,value,size=22,color='#243e61'):
        for i,line in enumerate(wrap_text(value,45 if size<25 else 31)):
            draw.text((x,y+i*(size+9)),line,font=video_font(size),fill=color)
    text(58,35,request['intent']['goal'],28,'#1768ed');text(58,98,scene['title'],37)
    draw.rounded_rectangle((45,177,width-45,554),18,fill='white',outline='#d9e6f7',width=2)
    if block['kind']in('relations','steps'):
        nodes,edges,gh=graph_geometry(block);lookup={n['id']:n for n in nodes};scale=min((width-120)/1200,315/gh)
        ox=65;oy=205
        for i,edge in enumerate(edges):
            a,b=lookup[edge['from']],lookup[edge['to']]
            x1=ox+(a['x']+a['w']/2)*scale;y1=oy+(a['y']+a['h']/2)*scale;x2=ox+(b['x']+b['w']/2)*scale;y2=oy+(b['y']+b['h']/2)*scale
            if a['y']==b['y'] and b['x']-a['x']>400:
                top=oy+a['y']*scale;via=top-33
                path=[(x1,top),(x1,via),(x2,via),(x2,top-4)]
                color='#1768ed' if i<=progress*max(1,len(edges)) else '#b8cce9'
                draw.line(path,fill=color,width=3,joint='curve')
                draw.polygon([(x2,top-3),(x2-5,top-13),(x2+5,top-13)],fill=color)
                draw.text(((x1+x2)/2-25,via-19),edge['label'],font=video_font(14),fill='#536f94')
                continue
            draw.line((x1,y1,x2,y2),fill='#b8cce9',width=3)
            angle=math.atan2(y2-y1,x2-x1)
            ux,uy=math.cos(angle),math.sin(angle)
            distance=min((b['w']*scale/2)/max(abs(ux),1e-9),(b['h']*scale/2)/max(abs(uy),1e-9))+4
            endx=x2-ux*distance
            endy=y2-uy*distance
            arrow=[(endx,endy),(endx-11*math.cos(angle-.45),endy-11*math.sin(angle-.45)),(endx-11*math.cos(angle+.45),endy-11*math.sin(angle+.45))]
            draw.polygon(arrow,fill='#6999dd')
            draw.text(((x1+x2)/2-24,(y1+y2)/2-22),edge['label'],font=video_font(14),fill='#536f94')
            if i<=progress*max(1,len(edges)):
                t=min(1,max(0,progress*len(edges)-i+1));px=x1+(x2-x1)*t;py=y1+(y2-y1)*t
                draw.line((x1,y1,px,py),fill='#1768ed',width=4)
                draw.ellipse((px-5,py-5,px+5,py+5),fill='#1768ed')
        highlights=scene.get('highlight_node_ids',[])
        for i,node in enumerate(nodes):
            x=ox+node['x']*scale;y=oy+node['y']*scale;w=node['w']*scale;h=node['h']*scale
            active=node['id']in highlights or i==min(len(nodes)-1,int(progress*len(nodes)))
            draw.rounded_rectangle((x,y,x+w,y+h),10,fill='#1768ed'if active else'#f0f6ff',outline='#a9c9f7',width=1)
            for j,line in enumerate(wrap_text(node['label'],11)):
                draw.text((x+12,y+13+j*23),line,font=video_font(max(15,int(18*scale))),fill='white'if active else'#244b7d')
    elif block['kind']=='series':
        points=block['data']['points'];values=[p['value']for p in points if p['value']is not None];lo=min([0]+values);hi=max([1]+values);span=hi-lo or 1
        for i,p in enumerate(points):
            x=90+i*1050/max(1,len(points));v=p['value'];base=510-(0-lo)/span*250
            if v is not None:
                yy=510-(v-lo)/span*250;end=base+(yy-base)*min(1,progress*2)
                draw.rounded_rectangle((x,min(base,end),x+min(55,700/max(1,len(points))),max(base,end)+1),4,fill='#2b77eb')
            text(x,523,p['label'],14)
        text(85,196,'单位：'+block['data']['unit'],18)
    else:
        value=scene.get('on_screen_text')or block['data'].get('content')or json.dumps(block['data'],ensure_ascii=False)
        for i,line in enumerate(wrap_text(value,42)):
            if i<8:draw.text((82,220+i*35),line,font=video_font(25),fill='#274a77')
    narration=scene['narration'];subtitle=wrap_text(narration,44)
    # Split captions across the scene, preserving the full text in SRT and the subtitle track.
    group=min(len(subtitle)-1,int(progress*max(1,len(subtitle))))
    for i,line in enumerate(subtitle[group:group+2]):draw.text((60,585+i*32),line,font=video_font(23),fill='#526d91')
    text(60,690,'来源与限制见随视频交付的说明。',13,'#8a9db5')
    return image


def render_video(request,spec,out_dir):
    from PIL import Image
    if not dependencies()['mp4']:raise ValueError('MP4 renderer requires ffmpeg and ffprobe.')
    plan=spec['video'];out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    target=out/'presentation.mp4'
    if target.exists():raise ValueError('Video output exists; use a new output directory.')
    fps=plan.get('fps',24);language=request['intent'].get('language','zh-CN');clips=[];captions=[];clock=0;story=[]
    blocks={b['id']:b for b in request['result']['blocks']}
    with tempfile.TemporaryDirectory(prefix='presentation-video-')as temp:
        work=Path(temp)
        for index,scene in enumerate(plan['scenes']):
            audio=None;duration=scene.get('duration_seconds',4)
            if plan.get('narration_mode','local')=='local':
                audio,spoken=local_narration(scene['narration'],work/f'audio-{index}',language,plan.get('voice'))
                duration=max(duration,spoken+.6)
            if duration>45:raise ValueError('A scene exceeds 45 seconds; split the narration.')
            clip=work/f'clip-{index}.mp4';count=math.ceil(duration*fps)
            command=['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(fps),'-i','pipe:0']
            if audio:command+=['-i',str(audio),'-af','apad','-c:a','aac','-b:a','128k']
            command+=['-t',str(count/fps),'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(clip)]
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                for frame in range(count):
                    image=video_frame(request,scene,blocks[scene['source_block_ids'][0]],frame/max(1,count-1))
                    process.stdin.write(image.tobytes())
                process.stdin.close();error=process.stderr.read().decode();status=process.wait(timeout=120)
                if status:raise ValueError('Video encoding failed: '+error[:400])
            except Exception:
                process.kill();process.wait();raise
            finally:
                if process.stdin and not process.stdin.closed:
                    try: process.stdin.close()
                    except BrokenPipeError: pass
                if process.stderr: process.stderr.close()
            actual=float(probe(clip)['format']['duration']);captions.append((clock,clock+actual,scene['narration']));clock+=actual;clips.append(clip)
            story.append({**scene,'duration_seconds':actual,'audio_present':audio is not None})
        listing=work/'clips.txt';listing.write_text('\n'.join("file '"+str(p)+"'"for p in clips))
        merged=work/'merged.mp4';subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(merged)],check=True,capture_output=True,timeout=120)
        def stamp(seconds):
            ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'
        srt='\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{text}'for i,(a,b,text)in enumerate(captions))+'\n'
        subtitles=out/'presentation.srt';subtitles.write_text(srt)
        subprocess.run(['ffmpeg','-v','error','-i',str(merged),'-i',str(subtitles),'-map','0','-map','1','-c','copy','-c:s','mov_text','-movflags','+faststart',str(target)],check=True,capture_output=True,timeout=120)
    info=probe(target)
    kinds={stream['codec_type']for stream in info['streams']}
    if 'video'not in kinds or 'subtitle'not in kinds:raise ValueError('Encoded video or subtitle track is missing.')
    if plan.get('narration_mode','local')=='local'and'audio'not in kinds:raise ValueError('Narration audio track is missing.')
    info['format']['filename']=target.name
    (out/'storyboard.json').write_text(json.dumps({'topic':request['intent']['goal'],'scenes':story},ensure_ascii=False,indent=2)+'\n')
    (out/'video-checks.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
    return target,info
