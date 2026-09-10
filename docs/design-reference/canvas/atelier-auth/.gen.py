import os

LIGHT = dict(paper="#f1ece1", card="#f8f3e8", line="#e8e0cf", line2="#d8cdb6",
             ink="#14110d", ink2="#4a4538", muted="#6f6857",
             red="#d8321a", redDeep="#9c2411", onRed="#ffffff",
             blue="#1d3a8a", yellow="#f3c318", green="#2c6a5d",
             tintWrong="#f7e1dc", tintCorrect="#e3efe9", markInk="#14110d")
DARK  = dict(paper="#17140f", card="#221e17", line="#332d22", line2="#4a4234",
             ink="#f5efe1", ink2="#d3c8b5", muted="#a2957e",
             red="#ff6a4d", redDeep="#a8321c", onRed="#17140f",
             blue="#7fa0ff", yellow="#f5cc3c", green="#52b892",
             tintWrong="#33201c", tintCorrect="#1b2d27", markInk="#f5efe1")

HEAD = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,500;1,500;1,600&family=Instrument+Sans:wght@400;600;700&display=swap">
  <style>
    body { margin: 0; }
    * { box-sizing: border-box; }
    a { color: %(ink2)s; } a:hover { color: %(ink)s; }
  </style>
</helmet>
"""

TAIL = """</x-dc>
<script data-dc-script>
class Component extends DCLogic {}
</script>
</body>
</html>
"""

def mark(t, size=22):
    g = size / 2 - 1
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 28 28" aria-hidden="true" style="flex: 0 0 auto">'
            f'<rect x="0" y="0" width="11" height="11" rx="2" fill="{t["markInk"]}"></rect>'
            f'<circle cx="22" cy="6" r="6" fill="{t["blue"]}"></circle>'
            f'<rect x="0" y="17" width="11" height="11" rx="2" fill="{t["yellow"]}"></rect>'
            f'<path d="M17 28L23 16L28 28H17Z" fill="{t["red"]}"></path></svg>')

def screen(t, body, pad_top=59):
    return (f'<div style="width: 390px; height: 844px; display: flex; flex-direction: column; '
            f'background: {t["paper"]}; color: {t["ink"]}; '
            f'font-family: \'Instrument Sans\', system-ui, -apple-system, sans-serif; '
            f'padding: {pad_top}px 20px 34px; overflow: hidden">\n{body}\n</div>')

def label(t, text):
    return (f'<span style="font-size: 12px; font-weight: 700; color: {t["muted"]}; '
            f'line-height: 1.3">{text}</span>')

def field(t, lab, value=None, placeholder="", invalid=False, focused=False, reveal=False):
    border = t["red"] if invalid else (t["blue"] if focused else "transparent")
    shown = value if value else placeholder
    colour = t["ink"] if value else t["muted"]
    eye = ("" if not reveal else
           f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{t["muted"]}" '
           f'stroke-width="1.8" aria-hidden="true" style="flex: 0 0 auto">'
           f'<path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z"></path>'
           f'<circle cx="12" cy="12" r="3"></circle></svg>')
    ring = (f'outline: 3px solid {t["ink"]}; outline-offset: 2px; ' if focused else "")
    return (f'<label style="display: flex; flex-direction: column; gap: 6px; min-width: 0">'
            f'{label(t, lab)}'
            f'<div style="display: flex; align-items: center; gap: 10px; min-height: 52px; '
            f'padding: 12px 16px; border: 2px solid {border}; border-radius: 16px; '
            f'background: {t["card"]}; {ring}">'
            f'<span style="flex: 1 1 auto; font-size: 16px; line-height: 1.45; color: {colour}; '
            f'overflow-wrap: anywhere">{shown}</span>{eye}</div></label>')

def primary(t, text, disabled=False, pending=False):
    face, fg, shadow = (t["line"], t["ink2"], t["line"]) if disabled else (t["red"], t["onRed"], t["redDeep"])
    spinner = ("" if not pending else
               f'<span style="width: 17px; height: 17px; border-radius: 999px; '
               f'border: 2px solid {fg}; border-top-color: transparent; flex: 0 0 auto"></span>')
    return (f'<div style="display: inline-flex; align-items: center; justify-content: center; gap: 8px; '
            f'width: 100%; min-height: 56px; padding: 12px 20px; border-radius: 16px; '
            f'background: {face}; color: {fg}; box-shadow: 0 5px 0 {shadow}; '
            f'font-size: 17px; font-weight: 700; line-height: 1.25; text-align: center">'
            f'{spinner}<span>{text}</span></div>')

def secondary(t, text):
    return (f'<div style="display: inline-flex; align-items: center; justify-content: center; '
            f'width: 100%; min-height: 56px; padding: 12px 20px; border-radius: 16px; '
            f'background: {t["card"]}; color: {t["ink"]}; box-shadow: 0 4px 0 {t["line2"]}; '
            f'font-size: 16px; font-weight: 700; line-height: 1.25">{text}</div>')

def quiet(t, text, align="center"):
    return (f'<div style="display: flex; align-items: center; justify-content: {align}; '
            f'min-height: 44px; font-size: 13px; font-weight: 600; color: {t["ink2"]}">{text}</div>')

def headline(t, text, size=32):
    return (f'<h1 style="margin: 0; font-family: \'EB Garamond\', Georgia, serif; font-style: italic; '
            f'font-weight: 500; font-size: {size}px; line-height: 1.06; color: {t["ink"]}; '
            f'text-wrap: pretty">{text}</h1>')

def body(t, text, size=15):
    return (f'<p style="margin: 0; font-size: {size}px; line-height: 1.45; color: {t["ink2"]}; '
            f'text-wrap: pretty">{text}</p>')

def eyebrow(t, text):
    return (f'<div style="display: flex; align-items: center; gap: 10px">{mark(t, 20)}'
            f'<span style="font-size: 12px; font-weight: 700; color: {t["muted"]}">{text}</span></div>')

def rule(t, top=0, bottom=0):
    return f'<div style="height: 1px; background: {t["line"]}; margin: {top}px 0 {bottom}px"></div>'

def steps(t, done, total):
    seg = []
    for i in range(total):
        fill = t["blue"] if i < done else t["line"]
        seg.append(f'<i style="flex: 1 1 0; height: 4px; border-radius: 2px; background: {fill}"></i>')
    return (f'<div style="display: flex; align-items: center; gap: 10px">'
            f'<div style="display: flex; gap: 4px; flex: 1 1 auto">{"".join(seg)}</div>'
            f'<span style="font-size: 12px; font-weight: 700; color: {t["muted"]}">{done} / {total}</span></div>')

def seg_group(t, lab, options, selected):
    cells = []
    for o in options:
        on = o == selected
        face = t["ink"] if on else t["card"]
        fg = t["paper"] if on else t["ink"]
        shadow = t["ink"] if on else t["line2"]
        cells.append(f'<div style="flex: 1 1 0; min-width: 0; display: flex; align-items: center; '
                     f'justify-content: center; min-height: 44px; padding: 0 6px; border-radius: 12px; '
                     f'background: {face}; color: {fg}; box-shadow: 0 3px 0 {shadow}; font-size: 13px; '
                     f'font-weight: 700; line-height: 1.2; text-align: center; overflow-wrap: anywhere">{o}</div>')
    return (f'<div style="display: flex; flex-direction: column; gap: 8px">{label(t, lab)}'
            f'<div style="display: flex; gap: 6px">{"".join(cells)}</div></div>')

def choice_rows(t, lab, options, selected):
    rows = []
    for o in options:
        on = o == selected
        face = t["card"]
        edge = t["blue"] if on else "transparent"
        dot = (f'<span style="width: 18px; height: 18px; border-radius: 999px; flex: 0 0 auto; '
               f'background: {t["blue"] if on else "transparent"}; '
               f'box-shadow: inset 0 0 0 2px {t["blue"] if on else t["line2"]}"></span>')
        rows.append(f'<div style="display: flex; align-items: center; gap: 12px; min-height: 52px; '
                    f'padding: 10px 14px; border: 2px solid {edge}; border-radius: 16px; background: {face}; '
                    f'box-shadow: 0 3px 0 {t["line2"]}">{dot}'
                    f'<span style="font-size: 15px; font-weight: 600; color: {t["ink"]}; line-height: 1.3">{o}</span></div>')
    return (f'<div style="display: flex; flex-direction: column; gap: 8px">{label(t, lab)}'
            f'<div style="display: flex; flex-direction: column; gap: 8px">{"".join(rows)}</div></div>')

def notice(t, text, tone="alert"):
    tint = t["tintWrong"] if tone == "alert" else t["tintCorrect"]
    accent = t["red"] if tone == "alert" else t["green"]
    glyph = (f'<span style="width: 18px; height: 18px; flex: 0 0 auto; border-radius: 4px; background: {accent}"></span>'
             if tone == "alert" else
             f'<span style="width: 18px; height: 18px; flex: 0 0 auto; border-radius: 999px; background: {accent}"></span>')
    return (f'<div style="display: flex; align-items: flex-start; gap: 10px; padding: 14px 16px; '
            f'border-radius: 16px; background: {tint}">{glyph}'
            f'<p style="margin: 0; font-size: 14px; line-height: 1.45; color: {t["ink"]}; '
            f'text-wrap: pretty">{text}</p></div>')

def col(children, gap=14, grow=False):
    g = "flex: 1 1 auto; " if grow else ""
    return (f'<div style="display: flex; flex-direction: column; gap: {gap}px; min-width: 0; {g}">'
            + "\n".join(children) + "</div>")

def spacer():
    return '<div style="flex: 1 1 auto"></div>'

def write(name, t, inner):
    with open(name, "w", encoding="utf-8") as fh:
        fh.write(HEAD % t + screen(t, inner) + "\n" + TAIL)
    print("wrote", name)
