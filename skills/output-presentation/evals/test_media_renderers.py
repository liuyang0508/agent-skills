"""Acceptance for actual content-driven formats, not the promotional showcase."""
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import presentation as p
import media_renderers as media


def sample(fmt='html'):
    return p.read_json(ROOT/'evals/fixtures/rag-request.json'),p.read_json(ROOT/'evals/fixtures'/f'rag-{fmt}-spec.json')


class MediaBehaviors(unittest.TestCase):
    def test_svg_has_real_nodes_and_directed_edges(self):
        r,s=sample('svg');svg=media.diagram_svg(r,s);ET.fromstring(svg)
        self.assertIn('marker-end="url(#arrow)"',svg)
        self.assertIn('data-node-id="retriever"',svg)
        self.assertIn('取得片段',svg)
        self.assertNotIn('showcase',svg)

    def test_svg_topic_changes_with_input(self):
        r,s=sample('svg');r['intent']['goal']='从需求到交付';r['result']['blocks'][1]['data']['nodes'][0]['label']='项目需求'
        svg=media.diagram_svg(r,s);self.assertIn('从需求到交付',svg);self.assertIn('项目需求',svg)

    def test_svg_preserves_numeric_units_and_missing_values(self):
        r,s=sample('svg');b=r['result']['blocks'][1];b['kind']='series';b['data']={'unit':'ms','points':[{'label':'A','value':0},{'label':'B','value':None},{'label':'C','value':-2}]}
        svg=media.diagram_svg(r,s);self.assertIn('单位：ms',svg);self.assertIn('data-value="0"',svg);self.assertIn('data-value="-2"',svg);self.assertIn('缺失',svg)

    def test_svg_does_not_execute_label_markup(self):
        r,s=sample('svg');r['result']['blocks'][1]['data']['nodes'][0]['label']='<script>alert(1)</script>'
        svg=media.diagram_svg(r,s);self.assertNotIn('<script>',svg);ET.fromstring(svg)

    def test_svg_text_only_is_not_pretended_as_a_diagram(self):
        r,s=sample('svg');r['result']['blocks']=r['result']['blocks'][:1];s['sections']=[{'id':'x','kind':'text','source_block_ids':['overview'],'visibility':'visible'}]
        with self.assertRaises(ValueError):media.diagram_svg(r,s)

    def test_plain_writing_has_short_sentences_and_glossary(self):
        r,s=sample('markdown');report=media.writing_report(r,s)
        self.assertEqual(report['violations'],[]);self.assertEqual(report['asd_ste100_compliance'],'not_claimed');self.assertGreater(report['sentences_checked'],3)

    def test_long_sentence_prevents_claiming_controlled_writing(self):
        r,s=sample('markdown');s['writing']['rewrites']={'overview':' '.join(['long']*31)+'.'}
        with tempfile.TemporaryDirectory()as d:
            with self.assertRaises(p.ContractError):p.render(r,s,d)
            self.assertFalse((Path(d)/'presentation.md').exists())

    def test_writing_rewrite_is_used_but_original_is_restorable(self):
        r,s=sample('markdown');s['writing']['rewrites']={'overview':'先检索资料。再生成回答。最后核验依据。'}
        with tempfile.TemporaryDirectory()as d:
            p.render(r,s,d);text=(Path(d)/'presentation.md').read_text()
            self.assertIn('先检索资料。再生成回答。',text)
            self.assertEqual(p.read_json(Path(d)/'baseline.json')['result'],r['result'])
            self.assertNotIn('schema_version',text)

    def test_unbound_writing_rewrite_is_rejected(self):
        r,s=sample('markdown');s['writing']['rewrites']={'missing':'A short sentence.'}
        with self.assertRaises(p.ContractError):p.validate_spec(s,r)

    def test_glossary_uses_one_definition_per_term(self):
        r,s=sample('markdown');s['writing']['glossary']=[{'term':'RAG','definition':'One.'},{'term':'rag','definition':'Two.'}]
        with self.assertRaises(p.ContractError):p.validate_spec(s,r)

    def test_english_ste_inspired_checks_sentence_length(self):
        r,s=sample('markdown');r['result']['summary']='The retriever finds relevant passages.';s['writing']={'profile':'ste-inspired','rewrites':{'overview':'The generator uses the passages. Check the answer against the evidence.'}}
        report=media.writing_report(r,s);self.assertEqual(report['violations'],[]);self.assertEqual(report['profile'],'ste-inspired')

    def test_html_has_exploration_controls_and_real_svg(self):
        r,s=sample('html')
        with tempfile.TemporaryDirectory()as d:
            p.render(r,s,d);text=(Path(d)/'presentation.html').read_text()
            for feature in ['id="search"','id="node-detail"','role="group"','data-node-id="retriever"','aria-controls="verify"','navigator.clipboard','data-action="assume"']:
                self.assertIn(feature,text)
            self.assertIn('script-src \'sha256-',text)

    def test_html_payload_cannot_close_the_data_script(self):
        r,s=sample('html');r['result']['summary']='</script><script>danger()</script>'
        continuations=[{'id':a['id'],'task':p.continue_task(r,s,a['id'])}for a in s['interactions']]
        text=media.interactive_html(r,s,continuations)
        self.assertNotIn('</script><script>danger()',text);self.assertIn('\\u003c/script',text)

    def test_html_local_inspect_is_supported_without_agent_bridge(self):
        r,s=sample('html');s['interactions'][0]['delivery_mode']='local'
        with tempfile.TemporaryDirectory()as d:
            receipt=p.render(r,s,d);self.assertEqual(receipt['renderer_id'],'html')

    def test_video_plan_must_cover_content_not_fixed_advertising(self):
        r,s=sample('mp4');s['video']['scenes']=s['video']['scenes'][:1]
        with self.assertRaises(p.ContractError):p.validate_spec(s,r)

    def test_video_cannot_highlight_invented_nodes(self):
        r,s=sample('mp4');s['video']['scenes'][1]['highlight_node_ids']=['not-in-data']
        with self.assertRaises(p.ContractError):p.validate_spec(s,r)

    def test_video_frame_depends_on_topic_data(self):
        r,s=sample('mp4');scene=s['video']['scenes'][1];block=r['result']['blocks'][1]
        first=media.video_frame(r,scene,block,.2).tobytes()
        different=copy.deepcopy(block);different['data']['nodes'][0]['label']='另一种输入'
        self.assertNotEqual(first,media.video_frame(r,scene,different,.2).tobytes())

    def test_video_has_actual_progress_between_frames(self):
        r,s=sample('mp4');scene=s['video']['scenes'][1];block=r['result']['blocks'][1]
        self.assertNotEqual(media.video_frame(r,scene,block,.1).tobytes(),media.video_frame(r,scene,block,.8).tobytes())

    def test_video_frame_preserves_edge_meaning(self):
        r,s=sample('mp4');scene=s['video']['scenes'][1];block=r['result']['blocks'][1]
        changed=copy.deepcopy(block);changed['data']['edges'][0]['label']='新的关系'
        self.assertNotEqual(media.video_frame(r,scene,block,.5).tobytes(),media.video_frame(r,scene,changed,.5).tobytes())

    def test_html_keeps_goals_and_procedure_content(self):
        r,s=sample('html');text=media.interactive_html(r,s,[])
        self.assertIn('说明检索和生成如何连接',text)
        self.assertIn('<li>把片段与问题交给生成模型。</li>',text)

    def test_explain_view_respects_verify_only_content(self):
        r,s=sample('html');s['views']['explain']['section_ids']=['s1','s2','s3']
        text=media.interactive_html(r,s,[]);explain=text.split('id="explain"')[1].split('id="verify"')[0]
        self.assertNotIn('<li>把片段与问题交给生成模型。</li>',explain)
        self.assertIn('把片段与问题交给生成模型。',text)

    def test_rich_formats_include_change_before_and_after(self):
        r,s=sample('html');r['baseline']={'result':copy.deepcopy(r['result'])};r['history_status']='available';r['result']['revision']='2'
        r['result']['evidence'][0]['title']='新版参考来源';s['change_set']=p.compute_changes(r,s['goal_coverage'],s['sections'])
        text=media.interactive_html(r,s,[])
        self.assertIn('原内容：',text);self.assertIn('RAG 原始论文',text);self.assertIn('新版参考来源',text)
        self.assertIn('原内容：',media.readable_markdown(r,s,[]))

    def test_conflicting_sidecar_prevents_partial_bundle(self):
        r,s=sample('html')
        with tempfile.TemporaryDirectory()as d:
            (Path(d)/'baseline.json').write_text('user content')
            with self.assertRaises(p.ContractError):p.render(r,s,d)
            self.assertFalse((Path(d)/'presentation.html').exists())
            self.assertEqual((Path(d)/'baseline.json').read_text(),'user content')

    def test_readable_markdown_escapes_untrusted_markup(self):
        r,s=sample('markdown');r['result']['summary']='<img src="https://example.invalid/pixel">'
        text=media.readable_markdown(r,s,[]);self.assertNotIn('<img src=',text)

    def test_offered_check_is_visible_without_premature_questions(self):
        r,s=sample('html');s['adaptation']['check_offer']='offered'
        self.assertIn('也可以跳过',media.interactive_html(r,s,[]))
        self.assertIn('也可以跳过',media.readable_markdown(r,s,[]))

    @unittest.skipUnless(media.dependencies()['mp4']and media.dependencies()['local_narration'],'Local video/TTS tools not installed')
    def test_narrated_mp4_contains_video_audio_subtitles_and_topic(self):
        r,s=sample('mp4');r['intent']['language']='en-US';r['intent']['goal']='RAG process';s['video']['fps']=12
        for i,scene in enumerate(s['video']['scenes']):scene['narration']='Check this step.';scene['title']='Step '+str(i+1);scene['duration_seconds']=1
        with tempfile.TemporaryDirectory()as d:
            receipt=p.render(r,s,d);info=media.probe(Path(d)/'presentation.mp4')
            kinds={x['codec_type']for x in info['streams']};self.assertTrue({'video','audio','subtitle'}<=kinds)
            self.assertGreater(float(info['format']['duration']),2)
            self.assertEqual(p.read_json(Path(d)/'storyboard.json')['topic'],'RAG process')
            self.assertIn('Check this step.',(Path(d)/'presentation.srt').read_text())
            self.assertIn('video_streams',[x['check_id']for x in receipt['validation_results']])


if __name__=='__main__':unittest.main()
