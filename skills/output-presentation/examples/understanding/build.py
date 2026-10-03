"""Build the four understanding examples into a new output directory."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

example = Path(__file__).resolve().parent
skill = example.parents[1]
sys.path.insert(0, str(skill / 'scripts'))
import presentation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    destination = args.out_dir.resolve()
    if destination.exists():
        parser.error('Use a new output directory to preserve existing artifacts.')

    request = presentation.prepare(presentation.read_json(example / 'source/request.json'))
    destination.mkdir(parents=True)
    for fmt, folder in [('markdown', 'markdown'), ('svg', 'svg'), ('html', 'html'), ('mp4', 'video')]:
        spec = presentation.read_json(example / f'source/{fmt}-spec.json')
        receipt = presentation.render(request, spec, destination / folder)
        print(json.dumps({'format': fmt, 'status': receipt['status']}, ensure_ascii=False), flush=True)

    video = destination / 'video'
    captions = (video / 'presentation.srt').read_text(encoding='utf-8')
    (video / 'presentation.vtt').write_text(
        'WEBVTT\n\n' + re.sub(r'(?<=\d),(?=\d{3})', '.', captions), encoding='utf-8'
    )
    subprocess.run([
        'ffmpeg', '-v', 'error', '-ss', '3', '-i', str(video / 'presentation.mp4'),
        '-frames:v', '1', str(video / 'poster.png')
    ], check=True)
    print(json.dumps({'output': str(destination)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
