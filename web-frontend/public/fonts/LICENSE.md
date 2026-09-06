# Vendored webfonts — Atelier V2

Both families are licensed under the **SIL Open Font License, Version 1.1**
(<https://scripts.sil.org/OFL>), which permits bundling, self-hosting and
redistribution with an application provided the licence travels with the fonts.
That is what this file is for.

Downloaded 2026-09-06 from the Google Fonts CSS API (`fonts.gstatic.com`),
`latin` and `latin-ext` subsets only. Both are **variable** fonts: Google serves
one identical file for every weight in the family's axis range, so a single file
per family/style/subset is stored here and the `@font-face` rules in
`web-frontend/styles/atelier-v2.css` declare a `font-weight` *range* rather than
one rule per weight.

| File | Family | Style | Weight axis | Subset | Bytes |
|---|---|---|---|---|---|
| `eb-garamond-italic-latin.woff2` | EB Garamond | italic | 400–800 | latin | 47,824 |
| `eb-garamond-italic-latin-ext.woff2` | EB Garamond | italic | 400–800 | latin-ext | 88,392 |
| `instrument-sans-latin.woff2` | Instrument Sans | normal | 400–700 | latin | 29,904 |
| `instrument-sans-latin-ext.woff2` | Instrument Sans | normal | 400–700 | latin-ext | 11,092 |

Total 180 KB, all `font-display: swap`, all with a real fallback stack.

Only the **italic** cut of EB Garamond is vendored: the design uses Garamond
exclusively in italic (the one headline per screen, French content, and
numerals). The roman cut is deliberately not shipped, and nothing in
`atelier-v2.css` asks for it.

## Copyright and licence notices

**EB Garamond** — Copyright 2017 The EB Garamond Project Authors
(<https://github.com/octaviopardo/EBGaramond12>).
Licensed under the SIL Open Font License, Version 1.1.
Reserved Font Name: "EB Garamond".

**Instrument Sans** — Copyright 2022 The Instrument Sans Project Authors
(<https://github.com/Instrument/instrument-sans>).
Licensed under the SIL Open Font License, Version 1.1.
Reserved Font Name: "Instrument Sans".

The full OFL 1.1 text is reproduced below once; it is identical for both.

## Font family naming — deliberate, and reversible in one line

`atelier-v2.css` registers these files under the CSS family names
**`AtelierSerif`** and **`AtelierSans`**, not under `EB Garamond` and
`Instrument Sans`.

That is not a font rename or a derivative work — the binaries are unmodified and
the Reserved Font Names are untouched. It is a CSS-local identifier chosen so
that vendoring the fonts changes **nothing on legacy pages while Atelier V2 is
off**. `styles/globals.css` already declares
`--app-serif: "EB Garamond", Garamond, "Times New Roman", serif`, which today
resolves to Times on nearly every machine. Registering the real name would
silently restyle every legacy journal, Feuilleton and Cahiers surface — a visual
change outside this work package's remit.

To flip the whole app onto the vendored faces later, add the real names as
additional families to the same `@font-face` rules:

```css
@font-face { font-family: 'EB Garamond';    /* …same src… */ }
@font-face { font-family: 'Instrument Sans'; /* …same src… */ }
```

---

## SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007

PREAMBLE

The goals of the Open Font License (OFL) are to stimulate worldwide development
of collaborative font projects, to support the font creation efforts of academic
and linguistic communities, and to provide a free and open framework in which
fonts may be shared and improved in partnership with others.

The OFL allows the licensed fonts to be used, studied, modified and redistributed
freely as long as they are not sold by themselves. The fonts, including any
derivative works, can be bundled, embedded, redistributed and/or sold with any
software provided that any reserved names are not used by derivative works. The
fonts and derivatives, however, cannot be released under any other type of
license. The requirement for fonts to remain under this license does not apply to
any document created using the fonts or their derivatives.

DEFINITIONS

"Font Software" refers to the set of files released by the Copyright Holder(s)
under this license and clearly marked as such. This may include source files,
build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the copyright
statement(s).

"Original Version" refers to the collection of Font Software components as
distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to, deleting, or
substituting -- in part or in whole -- any of the components of the Original
Version, by changing formats or by porting the Font Software to a new
environment.

"Author" refers to any designer, engineer, programmer, technical writer or other
person who contributed to the Font Software.

PERMISSION & CONDITIONS

Permission is hereby granted, free of charge, to any person obtaining a copy of
the Font Software, to use, study, copy, merge, embed, modify, redistribute, and
sell modified and unmodified copies of the Font Software, subject to the
following conditions:

1) Neither the Font Software nor any of its individual components, in Original or
Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy contains the
above copyright notice and this license. These can be included either as
stand-alone text files, human-readable headers or in the appropriate
machine-readable metadata fields within text or binary files as long as those
fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font Name(s)
unless explicit written permission is granted by the corresponding Copyright
Holder. This restriction only applies to the primary font name as presented to
the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font Software
shall not be used to promote, endorse or advertise any Modified Version, except
to acknowledge the contribution(s) of the Copyright Holder(s) and the Author(s)
or with their explicit written permission.

5) The Font Software, modified or unmodified, in part or in whole, must be
distributed entirely under this license, and must not be distributed under any
other license. The requirement for fonts to remain under this license does not
apply to any document created using the Font Software.

TERMINATION

This license becomes null and void if any of the above conditions are not met.

DISCLAIMER

THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF COPYRIGHT, PATENT, TRADEMARK, OR
OTHER RIGHT. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL,
OR CONSEQUENTIAL DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM OTHER
DEALINGS IN THE FONT SOFTWARE.
