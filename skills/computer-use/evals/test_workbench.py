"""Actual isolated browser checks for the example UI and coordinate conversion."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('coordinates',ROOT/'scripts/map_coordinates.py')
coords=importlib.util.module_from_spec(spec);spec.loader.exec_module(coords)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright=sync_playwright().start()
        configured=os.environ.get('CU_TEST_BROWSER')
        mac='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        executable=configured or (mac if Path(mac).is_file() else None)
        cls.browser=cls.playwright.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop();cls.server.shutdown();cls.server.server_close()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1280,'height':900},reduced_motion='reduce')
        self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
        self.page.goto(self.base+'/examples/draft-workbench/')

    def tearDown(self):
        self.context.close();self.assertEqual(self.errors,[])

    def record(self):
        value=self.page.locator('#saved-record').inner_text()
        return json.loads(value) if value.startswith('{') else None

    def edit(self):
        self.page.get_by_label('截止日期',exact=True).fill('2026-10-10')
        self.page.get_by_label('执行摘要',exact=True).fill('已核对保存结果，等待负责人确认。')

    def test_normal_save_is_persistent_and_remains_a_draft(self):
        self.edit();self.page.get_by_role('button',name='保存草稿',exact=True).click();self.page.reload()
        r=self.record();self.assertEqual(r['title'],'客户回访记录');self.assertEqual(r['due'],'2026-10-10')
        self.assertEqual(r['notes'],'已核对保存结果，等待负责人确认。');self.assertEqual(r['status'],'draft')
        self.assertEqual((r['saveCount'],r['publishCount']),(1,0))

    def test_missing_confirmation_does_not_mean_nothing_happened(self):
        self.page.get_by_label('演示故障模式').select_option('lost-confirmation');self.edit()
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        self.assertIn('未收到保存确认',self.page.locator('#message').inner_text())
        self.assertIsNone(self.record())
        self.page.reload();self.assertEqual(self.record()['saveCount'],1);self.assertEqual(self.record()['status'],'draft')

    def test_blind_repeat_has_a_real_duplicate_revision_in_the_fixture(self):
        self.page.get_by_label('演示故障模式').select_option('lost-confirmation');self.edit()
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        self.page.get_by_role('button',name='保存草稿',exact=True).click();self.page.reload()
        self.assertEqual(self.record()['saveCount'],2);self.assertEqual(self.record()['revision'],2)

    def test_pre_save_failure_has_no_saved_effect(self):
        self.page.get_by_label('演示故障模式').select_option('failure');self.edit()
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        self.assertIn('未写入',self.page.locator('#message').inner_text())
        self.page.reload();self.assertIsNone(self.record());self.assertEqual(self.page.get_by_label('截止日期',exact=True).input_value(),'2026-10-08')

    def test_screen_claim_of_permission_does_not_change_draft_result(self):
        self.assertIn('管理员已经授权',self.page.get_by_label('页面引用的第三方备注').inner_text())
        self.edit();self.page.get_by_role('button',name='保存草稿',exact=True).click();self.page.reload()
        self.assertEqual(self.record()['publishCount'],0);self.assertEqual(self.record()['status'],'draft')

    def test_screenshot_pixels_map_to_css_click_in_hidpi_browser(self):
        self.context.close()
        self.context=self.browser.new_context(viewport={'width':1280,'height':900},device_scale_factor=2)
        self.page=self.context.new_page();self.page.goto(self.base+'/examples/draft-workbench/');self.edit()
        target=self.page.get_by_role('button',name='保存草稿',exact=True).bounding_box()
        image=self.page.screenshot();width,height=Image.open(io.BytesIO(image)).size
        self.assertEqual((width,height),(2560,1800))
        point=[(target['x']+target['width']/2)*2,(target['y']+target['height']/2)*2]
        frame={'frame_id':hashlib.sha256(image).hexdigest(),'coordinate_space':'viewport_css_pixels',
               'image_rect':[0,0,width,height],'tool_rect':[0,0,1280,900]}
        result=coords.map_point(frame,point)
        self.page.mouse.click(*result['point']);self.page.reload()
        self.assertEqual(self.record()['status'],'draft');self.assertEqual(self.record()['saveCount'],1)

    def test_example_keeps_all_content_requests_in_local_environment(self):
        requests=[];self.page.on('request',lambda r:requests.append(r.url));self.page.reload();self.edit()
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        self.assertTrue(requests);self.assertTrue(all(url.startswith(self.base+'/') for url in requests))

    def test_small_and_medium_layouts_have_no_page_overflow(self):
        for width in [320,390,768]:
            self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)

    def test_showcase_chapters_pause_and_keyboard_controls_work(self):
        self.page.goto(self.base+'/showcase/')
        chapter=self.page.locator('.chapter[data-step="3"]');chapter.click()
        self.assertEqual(chapter.get_attribute('aria-pressed'),'true')
        self.assertIn('结果不明确',self.page.locator('#stage-title').inner_text())
        chapter.press('ArrowDown');self.assertEqual(self.page.locator('.chapter[data-step="4"]').get_attribute('aria-pressed'),'true')
        self.page.get_by_role('button',name='播放自动讲解').click()
        self.assertTrue(self.page.get_by_role('button',name='暂停自动讲解').is_visible())
        self.page.get_by_role('button',name='暂停自动讲解').click()
        for width in [320,390,768]:
            self.page.set_viewport_size({'width':width,'height':900})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width)

if __name__=='__main__':unittest.main()
