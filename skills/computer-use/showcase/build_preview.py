"""Capture this skill's real guide UI into a GIF and static cover. Development dependencies required."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import io
import threading
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    frames=[]
    try:
        with sync_playwright() as p:
            mac='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            browser=p.chromium.launch(headless=True,**({'executable_path':mac} if Path(mac).is_file() else {}))
            page=browser.new_page(viewport={'width':1280,'height':720},reduced_motion='reduce')
            page.goto(f'http://127.0.0.1:{server.server_port}/showcase/')
            page.evaluate('document.body.classList.add("export-mode")')
            for index in range(6):
                page.locator(f'.chapter[data-step="{index}"]').evaluate('(e)=>e.click()')
                frame=Image.open(io.BytesIO(page.screenshot())).convert('RGB').resize((960,540),Image.Resampling.LANCZOS)
                frames.append(frame.quantize(colors=128,dither=Image.Dither.NONE))
            browser.close()
        output=ROOT/'showcase'
        frames[0].save(output/'demo.gif',save_all=True,append_images=frames[1:],duration=2400,loop=0,disposal=2)
        frames[1].convert('RGB').save(output/'cover.png')
        print('Captured six actual guide chapters into demo.gif and cover.png.')
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
