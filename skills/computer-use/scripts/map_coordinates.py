"""Map a point from an explicitly recorded image content rectangle to a tool rectangle."""
import argparse
import json
import math
from pathlib import Path


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Coordinates and dimensions must be finite numbers.')
    return value


def rectangle(value, name):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(name + ' needs [x, y, width, height].')
    x,y,w,h = [number(v) for v in value]
    if w <= 0 or h <= 0:
        raise ValueError(name + ' dimensions must be positive.')
    return x,y,w,h


def map_point(frame, point):
    if not isinstance(frame, dict) or not isinstance(frame.get('frame_id'), str) or not frame['frame_id'].strip():
        raise ValueError('Record a nonempty frame_id from the actual capture.')
    if not isinstance(frame.get('coordinate_space'), str) or not frame['coordinate_space'].strip():
        raise ValueError('Record the actual tool coordinate space.')
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise ValueError('Point needs [x, y].')
    px,py = [number(v) for v in point]
    ix,iy,iw,ih = rectangle(frame.get('image_rect'), 'image_rect')
    tx,ty,tw,th = rectangle(frame.get('tool_rect'), 'tool_rect')
    if not (ix <= px < ix+iw and iy <= py < iy+ih):
        raise ValueError('Point is outside image content; do not click padding or guess a target.')
    x = tx + (px-ix)*tw/iw
    y = ty + (py-iy)*th/ih
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError('Mapping overflowed; check the actual frame metadata.')
    return {'frame_id':frame['frame_id'], 'coordinate_space':frame['coordinate_space'],
            'point':[x,y], 'executed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--x',type=float,required=True)
    parser.add_argument('--y',type=float,required=True)
    args=parser.parse_args()
    try:
        result=map_point(json.loads(args.frame.read_text()),[args.x,args.y])
    except (ValueError,OSError) as err:
        parser.error(str(err))
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':main()
