# -*- coding: utf-8 -*-
"""生成云极智能拆版测试样例：T恤版型 PLT（含前/后片、双袖、领条）。"""
import math
import os


def poly(pts):
    """折线 → HPGL 指令串"""
    s = []
    s.append('PU%d,%d;' % (round(pts[0][0]), round(pts[0][1])))
    s.append('PD')
    s.append(','.join('%d,%d' % (round(x), round(y)) for x, y in pts[1:]))
    s.append(';')
    s.append('PU%d,%d;' % (round(pts[0][0]), round(pts[0][1])))
    return ''.join(s)


def rounded_rect(x, y, w, h, r=15):
    pts = []
    cx, cy = x + w / 2, y + h / 2
    for i, (dx, dy) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)]):
        a0, a1 = 180 + 90 * i, 270 + 90 * i
        for a in range(a0, a1 + 1, 4):
            pts.append((cx + dx * (w / 2 - r) + r * math.cos(math.radians(a)),
                        cy + dy * (h / 2 - r) + r * math.sin(math.radians(a))))
    return pts


def make_front(x, y, w, h):
    """前片：底部大矩形，顶部中间领口缺口"""
    pts = [(x, y), (x + w, y), (x + w, y + h * 0.75)]
    cx = x + w / 2
    for a in range(0, 181, 6):
        pts.append((cx + (w * 0.30) * math.cos(math.radians(a)),
                    y + h * 0.75 + (h * 0.22) * math.sin(math.radians(a))))
    pts.append((x, y + h * 0.75))
    return pts


def make_back(x, y, w, h):
    """后片：矩形，领口浅弧"""
    pts = [(x, y), (x + w, y), (x + w, y + h * 0.82)]
    cx = x + w / 2
    for a in range(0, 181, 6):
        pts.append((cx + (w * 0.26) * math.cos(math.radians(a)),
                    y + h * 0.82 + (h * 0.10) * math.sin(math.radians(a))))
    pts.append((x, y + h * 0.82))
    return pts


def make_sleeve(x, y, w, h):
    """袖片：长条圆角"""
    return rounded_rect(x, y, w, h, r=12)


def make_collar(x, y, w, h):
    """领条：细长条"""
    return rounded_rect(x, y, w, h, r=6)


def main(out='sample_t-shirt.plt'):
    out = os.path.join(os.path.dirname(__file__), out)
    parts = ['IN;SP1;']
    parts.append(poly(make_front(20, 20, 240, 320)))
    parts.append(poly(make_back(300, 20, 240, 320)))
    parts.append(poly(make_sleeve(20, 380, 180, 70)))
    parts.append(poly(make_sleeve(240, 380, 180, 70)))
    parts.append(poly(make_collar(460, 400, 320, 36)))
    parts.append('SP0;')
    with open(out, 'w') as f:
        f.write('\n'.join(parts))
    print('written', out, os.path.getsize(out), 'bytes')
    return out


SIZES = ['S', 'M', 'L']


def make_multi_size(out='sample_t-shirt_3码.plt'):
    """多码数打样样例：S/M/L 三码分行，每码 前/后/左袖/右袖/领条。"""
    out = os.path.join(os.path.dirname(__file__), out)
    parts = ['IN;SP1;']
    row_h = 1000
    for i, size in enumerate(SIZES):
        y0 = 30 + i * row_h
        px = 20
        parts.append(poly(make_front(px, y0 + 150, 170, 230)))
        parts.append(poly(make_back(px + 200, y0 + 150, 170, 230)))
        parts.append(poly(make_sleeve(px + 10, y0 + 20, 120, 45)))
        parts.append(poly(make_sleeve(px + 160, y0 + 20, 120, 45)))
        parts.append(poly(make_collar(px + 300, y0 + 40, 100, 16)))
        parts.append(f'PU{px + 95},{y0 + 260};LB{size}\x03;')
        parts.append('LT1;')
        parts.append(f'PU{px + 40},{y0 + 160};PD{px + 130},{y0 + 160};')
        parts.append('LT0;')
        parts.append(f'PU{px + 60},{y0 + 290};PD{px + 68},{y0 + 290};')
        parts.append(f'PU{px + 60},{y0 + 284};PD{px + 60},{y0 + 296};')
        parts.append(f'PU{px + 150},{y0 + 310};PD{px + 158},{y0 + 310};')
        parts.append(f'PU{px + 150},{y0 + 304};PD{px + 150},{y0 + 316};')
    parts.append('SP0;')
    with open(out, 'w') as f:
        f.write('\n'.join(parts))
    print('written', out, os.path.getsize(out), 'bytes')
    return out


if __name__ == '__main__':
    main()
    make_multi_size()
