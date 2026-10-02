"""Behavioral acceptance: artifacts, references, failures and version updates."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
module_spec = importlib.util.spec_from_file_location('presentation', ROOT / 'scripts/presentation.py')
p = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(p)


def fixture():
    request = p.read_json(ROOT / 'evals/fixtures/architecture-request.json')
    spec = p.read_json(ROOT / 'evals/fixtures/architecture-spec.json')
    return request, spec


def revise(request, spec, mutation):
    request['baseline'] = {'result': copy.deepcopy(request['result'])}
    request['history_status'] = 'available'
    request['result']['revision'] = '2'
    mutation(request['result'])
    spec['result_ref'] = p.result_ref(request['result'])
    for view in spec['views'].values(): view['result_ref'] = spec['result_ref']
    spec['change_set'] = p.compute_changes(request, spec['goal_coverage'], spec['sections'])


def set_kind(request, kind, data):
    request['result']['blocks'][0].update(kind=kind, data=data)


class Behaviors(unittest.TestCase):
    def render_text(self, request, spec, fmt='markdown'):
        spec['presentation']['format'] = fmt
        spec['render_request']['renderer_id'] = fmt
        with tempfile.TemporaryDirectory() as directory:
            receipt = p.render(request, spec, directory)
            artifact = Path(directory) / ('presentation.md' if fmt == 'markdown' else 'presentation.html')
            self.assertEqual(p.read_json(Path(directory) / 'baseline.json')['result'], request['result'])
            self.assertTrue(receipt['baseline_receipt']['restored'])
            self.assertEqual([c['check_id'] for c in receipt['feature_checks']], ['R1', 'R2', 'R3', 'R4', 'R5', 'R6'])
            return artifact.read_text(), receipt

    def test_baseline_restores_original_result(self):
        r, s = fixture(); text, receipt = self.render_text(r, s)
        self.assertIn('result-001', text)
        self.assertEqual(receipt['status'], 'generated')
        self.assertIn('not_checked', [v['status'] for v in receipt['validation_results']])

    def test_dual_views_preserve_sources_and_limits(self):
        r, s = fixture(); text, _ = self.render_text(r, s)
        self.assertIn('解释视图', text); self.assertIn('核验视图', text)
        for e in r['result']['evidence']: self.assertIn(e['locator'], text)
        for u in r['result']['uncertainties']: self.assertIn(u['text'], text)

    def test_empty_evidence_is_disclosed(self):
        r, s = fixture(); r['result']['evidence']=[]; r['result']['blocks'][0]['evidence_ids']=[]; s['preservation']['required_evidence_ids']=[]
        text, _ = self.render_text(r, s)
        self.assertIn('未提供来源', text)

    def test_missing_value_is_not_zero(self):
        r, s = fixture(); set_kind(r, 'series', {'unit':'%', 'points':[{'label':'Q1','value':None},{'label':'Q2','value':0}]})
        text, _ = self.render_text(r, s)
        self.assertIn('缺失', text); self.assertIn('| Q2 | 0 | % |', text)

    def test_comparison_displays_consistent_dimensions(self):
        r, s = fixture(); set_kind(r,'comparison',{'columns':['方案','成本'], 'rows':[{'方案':'A','成本':20},{'方案':'B','成本':None}]})
        text, _ = self.render_text(r,s)
        self.assertIn('| A | 20 |', text); self.assertIn('| B | 未知 |', text)

    def test_steps_preserve_order(self):
        r,s=fixture();set_kind(r,'steps',{'items':['读取上下文','执行工具','回传结果']})
        text,_=self.render_text(r,s)
        self.assertLess(text.index('读取上下文'), text.index('执行工具'))

    def test_relation_direction_and_label_survive(self):
        r,s=fixture();text,_=self.render_text(r,s)
        self.assertIn('上下文管理 → 工具执行：提供任务上下文', text)

    def test_generated_learning_aid_stays_labeled(self):
        r,s=fixture();r['intent']['learning_aids_required']=True
        s['learning_aids']=[{'id':'l1','kind':'counterexample','target_block_ids':['b1'],'content':'有上下文不代表工具已经执行。','origin':'generated','label':'教学示例','assumptions':['只讨论示例关系'],'evidence_ids':[]}]
        s['sections'][1]['learning_aid_ids']=['l1'];s['learning_aids_reason']='纠正把输入信息当作已执行结果的误解。'
        text,_=self.render_text(r,s);self.assertIn('教学示例',text);self.assertIn('不构成业务证据',text)

    def test_source_learning_aid_keeps_citation(self):
        r,s=fixture();s['learning_aids']=[{'id':'l1','kind':'contrast','target_block_ids':['b1'],'content':'示例说明信息提供关系。','origin':'source','label':'来源对照','assumptions':[],'evidence_ids':['src1']}]
        s['sections'][1]['learning_aid_ids']=['l1'];text,_=self.render_text(r,s);self.assertIn('来源对照',text)

    def test_all_four_operations_build_complete_tasks(self):
        r,s=fixture()
        for i,operation in enumerate(p.OPERATIONS):
            action=copy.deepcopy(s['interactions'][0]);action.update(id='a'+str(i),operation=operation)
            if operation=='change_assumption':
                action.update(parameter_constraints={'assumption':{'type':'string','minLength':1}},required_parameters=['assumption'],default_parameters={'assumption':'工具没有接收任何上下文'})
            s['interactions']=[action]
            task=p.continue_task(r,s,action['id'])
            self.assertEqual(task['source_blocks'],r['result']['blocks'])
            self.assertEqual(task['evidence'],r['result']['evidence'])
            self.assertEqual(task['result_ref'],p.result_ref(r['result']))
            self.assertEqual(task['operation'],operation)

    def test_scenario_does_not_mutate_real_result(self):
        r,s=fixture();before=copy.deepcopy(r)
        a=s['interactions'][0];a['operation']='change_assumption';a['parameter_constraints']={'assumption':{'type':'string','minLength':1}}
        a['required_parameters']=['assumption']
        task=p.continue_task(r,s,'a1',{'assumption':'没有上下文更新'})
        self.assertTrue(task['preserve_original_result']);self.assertTrue(task['scenario_id'].startswith('scenario-'));self.assertEqual(r,before)

    def test_prompt_artifact_has_raw_context_not_dead_button(self):
        r,s=fixture();text,_=self.render_text(r,s)
        self.assertIn('copy_to_upstream_agent',text);self.assertIn('source_blocks',text)

    def test_withdrawn_evidence_shows_change_even_if_claim_same(self):
        r,s=fixture();revise(r,s,lambda result: result['evidence'][0].update(locator='fixture:withdrawn-source'))
        self.assertIn('evidence_changed',[c['kind'] for c in s['change_set']['changes']])
        text,_=self.render_text(r,s);self.assertIn('依据新增、修改或撤回',text)

    def test_new_uncertainty_is_preserved(self):
        r,s=fixture();revise(r,s,lambda result: result['uncertainties'].append({'id':'u2','text':'新增边界','affected_block_ids':['b1']}));s['preservation']['required_uncertainty_ids'].append('u2')
        text,_=self.render_text(r,s);self.assertIn('新增边界',text);self.assertIn('uncertainty_changed',[c['kind'] for c in s['change_set']['changes']])

    def test_summary_change_is_detected(self):
        r,s=fixture();revise(r,s,lambda result: result.update(summary='当前示例只表示简化的信息传递。'))
        self.assertIn('summary_changed',[c['kind'] for c in s['change_set']['changes']]);self.render_text(r,s)

    def test_unknown_change_reason_not_invented(self):
        r,s=fixture();revise(r,s,lambda result: result['blocks'][0]['data']['edges'][0].update(label='传递相关信息'))
        self.assertEqual(s['change_set']['changes'][0]['reason'],'原因未提供')

    def test_explicit_change_reason_is_used(self):
        r,s=fixture();revise(r,s,lambda result: result.update(summary='修订摘要',change_reasons={'summary':'上游修订说明'}))
        self.assertEqual(next(c for c in s['change_set']['changes'] if c['kind']=='summary_changed')['reason'],'上游修订说明')

    def test_unchanged_snapshot_has_no_fake_changes(self):
        r,s=fixture();r['baseline']={'result':copy.deepcopy(r['result'])};r['history_status']='available';s['change_set']=p.compute_changes(r,s['goal_coverage'],s['sections'])
        self.assertEqual(s['change_set']['status'],'unchanged');self.render_text(r,s)

    def test_feedback_changes_explanation_but_original_survives(self):
        r,s=fixture();r['session_refs']=['message-2'];r=p.add_feedback(r,'f1','没理解信息流','message-2',['b1'])
        s['adaptation'].update(applied_signal_ids=['f1'],focus_block_ids=['b1'],explanation_overrides={'b1':'先读取相关信息，再把这些信息交给工具执行。'},reason='聚焦用户指出的信息流困惑。')
        text,_=self.render_text(r,s);self.assertIn('先读取相关信息',text);self.assertIn('提供任务上下文',text)

    def test_declined_quiz_does_not_block_explanation(self):
        r,s=fixture();r['learner_context']['check_consent']='declined';s['adaptation']['check_offer']='declined'
        text,_=self.render_text(r,s);self.assertNotIn('## 可选理解检查',text)

    def test_accepted_quiz_has_goal_linked_questions(self):
        r,s=fixture();r['learner_context']['check_consent']='accepted';s['adaptation'].update(check_offer='accepted',questions=[{'goal_id':'g1','question':'信息传递方向是什么？','answer_criteria':'指出 context 到 execution'}])
        text,_=self.render_text(r,s);self.assertIn('信息传递方向是什么',text)

    def test_offered_quiz_does_not_show_questions(self):
        r,s=fixture();s['adaptation']['check_offer']='offered';text,_=self.render_text(r,s);self.assertIn('也可以跳过',text)

    def test_html_is_offline_and_escapes_untrusted_input(self):
        r,s=fixture();r['result']['summary']='<script>alert(1)</script>'
        text,_=self.render_text(r,s,'html');self.assertNotIn('<script>',text);self.assertIn('Content-Security-Policy',text);self.assertIn('href="#part-',text)

    def test_explicit_html_is_obeyed(self):
        r,s=fixture();r['intent']['explicit_format']='html';text,_=self.render_text(r,s,'html');self.assertTrue(text.startswith('<!doctype html>'))

    def test_prepare_infers_goal_without_guessing_first_version(self):
        r,s=fixture();del r['comprehension_goals'];normalized=p.prepare(r)
        self.assertEqual(normalized['comprehension_goals'][0]['origin'],'inferred')

    def test_blocked_spec_is_valid_and_cannot_render(self):
        r,s=fixture();blocked={k:s[k] for k in ('schema_version','spec_id','request_id','result_ref','rationale')};blocked.update(decision='unsupported',interactions=[],issues=[{'code':'format','message':'PDF renderer unavailable','required_action':'Provide a PDF renderer'}])
        p.validate_spec(blocked,r)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(p.ContractError):p.render(r,blocked,d)

    def test_cli_prepare_validate_and_render(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'request.json'
            script=str(ROOT/'scripts/presentation.py')
            for args in [['prepare',str(ROOT/'evals/fixtures/architecture-request.json'),'-o',str(out)],['validate','request',str(out)],['render',str(out),str(ROOT/'evals/fixtures/architecture-spec.json'),'--out-dir',str(Path(d)/'artifacts')]]:
                result=subprocess.run([sys.executable,script,*args],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)

    def test_different_existing_artifact_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'presentation.md';target.write_text('user work')
            r,s=fixture()
            with self.assertRaises(p.ContractError):p.render(r,s,d)
            self.assertEqual(target.read_text(),'user work')

    def test_budget_stops_before_creating_artifact(self):
        r,s=fixture();r['constraints']['max_output_bytes']=1
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(p.ContractError):p.render(r,s,d)
            self.assertFalse((Path(d)/'presentation.md').exists())

    def test_known_background_is_shortened_only_in_explanation(self):
        r,s=fixture();r['session_refs']=['m1'];r['learner_context']['known_concepts']=[{'id':'k1','text':'懂上下文输入','source_ref':'m1','block_ids':['b1']}]
        s['adaptation'].update(applied_signal_ids=['k1'],focus_block_ids=[],deemphasized_block_ids=['b1'],reason='背景已知，保留核验原文。')
        text,_=self.render_text(r,s)
        explain=text.split('## 解释视图')[1].split('## 核验视图')[0]
        verify=text.split('## 核验视图')[1]
        self.assertNotIn('提供任务上下文',explain);self.assertIn('提供任务上下文',verify)

    def test_added_block_is_detected(self):
        r,s=fixture();revise(r,s,lambda result: result['blocks'].append({'id':'b2','kind':'text','data':{'content':'新增说明'},'evidence_ids':[],'uncertainty_ids':[]}))
        self.assertIn('added',[c['kind'] for c in s['change_set']['changes']])

    def test_removed_block_is_detected(self):
        r,s=fixture();r['baseline']={'result':copy.deepcopy(r['result'])};r['baseline']['result']['blocks'].append({'id':'old','kind':'text','data':{'content':'撤回说明'},'evidence_ids':[],'uncertainty_ids':[]});r['history_status']='available';r['result']['revision']='2'
        changes=p.compute_changes(r,s['goal_coverage'],s['sections'])
        self.assertEqual(next(c for c in changes['changes'] if c['kind']=='removed')['before_block_ids'],['old'])

    def test_same_revision_cannot_hide_modified_content(self):
        r,s=fixture();r['baseline']={'result':copy.deepcopy(r['result'])};r['history_status']='available';r['result']['summary']='修改结论'
        with self.assertRaises(p.ContractError):p.validate_request(r)

    def test_continuation_rejects_undeclared_parameters(self):
        r,s=fixture()
        with self.assertRaises(p.ContractError):p.continue_task(r,s,'a1',{'run_command':'anything'})

    def test_html_table_has_real_headers_and_missing_values(self):
        r,s=fixture();set_kind(r,'series',{'unit':'%', 'points':[{'label':'Q1','value':None}]})
        text,_=self.render_text(r,s,'html');self.assertIn('<th scope="col">单位</th>',text);self.assertIn('<td>缺失</td>',text)

    def test_feedback_cannot_reuse_identical_explanation(self):
        r,s=fixture();r['session_refs']=['m1'];r=p.add_feedback(r,'f1','仍不懂','m1',['b1']);s['adaptation'].update(applied_signal_ids=['f1'],explanation_overrides={'b1':p.block_markdown(r['result']['blocks'][0])})
        with self.assertRaises(p.ContractError):p.validate_spec(s,r)

    def test_evidence_title_change_displays_both_versions(self):
        r,s=fixture();revise(r,s,lambda result:result['evidence'][0].update(title='修订的示例说明'))
        text,_=self.render_text(r,s)
        changes=text.split('## 变化与影响')[1].split('## 解释视图')[0]
        self.assertIn('示例架构说明',changes);self.assertIn('修订的示例说明',changes)

    def test_new_limit_is_visible_in_change_summary(self):
        r,s=fixture();revise(r,s,lambda result:result['uncertainties'].append({'id':'u2','text':'工具成功需独立验证','affected_block_ids':['b1']}));s['preservation']['required_uncertainty_ids'].append('u2')
        text,_=self.render_text(r,s)
        changes=text.split('## 变化与影响')[1].split('## 解释视图')[0]
        self.assertIn('工具成功需独立验证',changes)

    def test_skill_runs_after_copying_only_its_directory(self):
        with tempfile.TemporaryDirectory() as d:
            skill=Path(d)/'output-presentation';shutil.copytree(ROOT,skill,ignore=shutil.ignore_patterns('__pycache__'))
            command=[sys.executable,str(skill/'scripts/presentation.py'),'render',str(skill/'evals/fixtures/architecture-request.json'),str(skill/'evals/fixtures/architecture-spec.json'),'--out-dir',str(Path(d)/'artifacts')]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((Path(d)/'artifacts/baseline.json').exists())

    def test_documented_relative_references_exist(self):
        import re
        for doc in [ROOT/'SKILL.md',*(ROOT/'references').glob('*.md')]:
            for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
                if not link.startswith(('https://','http://','#')):
                    self.assertTrue((doc.parent/link).exists(),f'{doc}: {link}')

    def test_rendered_scenario_contains_concrete_default_assumption(self):
        r,s=fixture();a=s['interactions'][0];a.update(operation='change_assumption',parameter_constraints={'assumption':{'type':'string','minLength':1}},required_parameters=['assumption'],default_parameters={'assumption':'没有上下文输入'})
        with tempfile.TemporaryDirectory() as d:
            p.render(r,s,d);task=p.read_json(Path(d)/'continuations.json')[0]['task']
            self.assertEqual(task['parameters']['assumption'],'没有上下文输入');self.assertIn('scenario_id',task)

    def test_render_rejects_missing_required_assumption_before_output(self):
        r,s=fixture();a=s['interactions'][0];a.update(operation='change_assumption',parameter_constraints={'assumption':{'type':'string','minLength':1}},required_parameters=['assumption'])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(p.ContractError):p.render(r,s,d)
            self.assertFalse((Path(d)/'presentation.md').exists())

    def test_explicit_scenario_parameter_overrides_default(self):
        r,s=fixture();a=s['interactions'][0];a.update(operation='change_assumption',parameter_constraints={'assumption':{'type':'string','minLength':1}},required_parameters=['assumption'],default_parameters={'assumption':'默认情况'})
        task=p.continue_task(r,s,'a1',{'assumption':'新情况'});self.assertEqual(task['parameters']['assumption'],'新情况')

    def test_showcase_includes_animation_and_static_cover(self):
        showcase=ROOT/'showcase'
        gif=(showcase/'demo.gif').read_bytes()
        self.assertTrue(gif.startswith(b'GIF89a'));self.assertIn(b'NETSCAPE2.0',gif)
        self.assertIn('<svg',(showcase/'cover.svg').read_text())
        self.assertIn('prefers-reduced-motion',(showcase/'style.css').read_text())

    def test_showcase_has_six_chapters_and_playback_controls(self):
        from html.parser import HTMLParser
        class Chapters(HTMLParser):
            def __init__(self):super().__init__();self.steps=[];self.toggle=False
            def handle_starttag(self,tag,attrs):
                attrs=dict(attrs)
                if tag=='button' and 'data-step' in attrs:self.steps.append(int(attrs['data-step']))
                if tag=='button' and attrs.get('id')=='toggle':self.toggle=True
        parser=Chapters();parser.feed((ROOT/'showcase/index.html').read_text())
        self.assertEqual(parser.steps,list(range(6)));self.assertTrue(parser.toggle)


NEGATIVE_CASES = [
 ('duplicate_block',lambda r,s:r['result']['blocks'].append(copy.deepcopy(r['result']['blocks'][0]))),
 ('unknown_evidence',lambda r,s:r['result']['blocks'][0]['evidence_ids'].append('absent')),
 ('unknown_uncertainty',lambda r,s:r['result']['blocks'][0]['uncertainty_ids'].append('absent')),
 ('invalid_edge',lambda r,s:r['result']['blocks'][0]['data']['edges'][0].update(to='absent')),
 ('nonfinite_value',lambda r,s:set_kind(r,'series',{'unit':'%', 'points':[{'label':'Q1','value':float('nan')}]})),
 ('missing_units',lambda r,s:set_kind(r,'series',{'points':[]})),
 ('inconsistent_columns',lambda r,s:set_kind(r,'comparison',{'columns':['A','B'],'rows':[{'A':1}]})),
 ('unknown_section_source',lambda r,s:s['sections'][1]['source_block_ids'].append('absent')),
 ('unrestricted_summary_field',lambda r,s:s['sections'][0].update(source_field='result.secret')),
 ('missing_goal_coverage',lambda r,s:s.update(goal_coverage=[])),
 ('duplicate_goal_coverage',lambda r,s:s['goal_coverage'].append(copy.deepcopy(s['goal_coverage'][0]))),
 ('different_view_revision',lambda r,s:s['views']['verify'].update(result_ref={'result_id':'result-001','revision':'99'})),
 ('missing_verification_block',lambda r,s:s['sections'][2].update(source_block_ids=[])),
 ('dropped_evidence',lambda r,s:s['preservation'].update(required_evidence_ids=[])),
 ('dropped_limit',lambda r,s:s['preservation'].update(required_uncertainty_ids=[])),
 ('invented_preservation',lambda r,s:s['preservation']['required_evidence_ids'].append('absent')),
 ('unknown_renderer',lambda r,s:s['render_request'].update(renderer_id='video')),
 ('silent_format_change',lambda r,s:r['intent'].update(explicit_format='pdf')),
 ('upstream_evidence_needed',lambda r,s:r['constraints'].update(requires_new_evidence=True)),
 ('automatic_action_unavailable',lambda r,s:r['constraints'].update(requires_automatic_actions=True)),
 ('fake_agent_callback',lambda r,s:s['interactions'][0].update(delivery_mode='agent')),
 ('action_unknown_goal',lambda r,s:s['interactions'][0].update(goal_ids=['absent'])),
 ('action_unknown_block',lambda r,s:s['interactions'][0].update(target_block_ids=['absent'])),
 ('empty_prompt',lambda r,s:s['interactions'][0].update(prompt_text='')),
 ('untrusted_signal',lambda r,s:r['learner_context']['known_concepts'].append({'id':'k1','text':'了解概念','source_ref':'absent'})),
 ('invented_applied_signal',lambda r,s:s['adaptation'].update(applied_signal_ids=['absent'])),
 ('unbound_override',lambda r,s:s['adaptation'].update(explanation_overrides={'b1':'新解释'})),
 ('focus_and_hide_same_block',lambda r,s:s['adaptation'].update(deemphasized_block_ids=['b1'])),
 ('quiz_without_consent',lambda r,s:s['adaptation'].update(check_offer='accepted',questions=[{'goal_id':'g1','question':'测验','answer_criteria':'内容'}])),
 ('ignored_quiz_refusal',lambda r,s:r['learner_context'].update(check_consent='declined')),
 ('fabricated_first_version_changes',lambda r,s:s['change_set'].update(status='changed')),
 ('missing_history_status',lambda r,s:r.pop('history_status')),
 ('history_present_without_baseline',lambda r,s:r.update(history_status='available')),
 ('history_unavailable_not_first',lambda r,s:r.update(history_status='unavailable')),
 ('required_aid_omitted',lambda r,s:r['intent'].update(learning_aids_required=True)),
 ('unknown_top_level',lambda r,s:r.update(unknown_field=True)),
]


def rejection_test(mutate):
    def run(self):
        r,s=fixture();mutate(r,s)
        with self.assertRaises((p.ContractError,ValueError)):p.validate_spec(s,r)
    return run


for name,mutate in NEGATIVE_CASES:
    setattr(Behaviors,'test_reject_'+name,rejection_test(mutate))


if __name__ == '__main__':
    unittest.main()
