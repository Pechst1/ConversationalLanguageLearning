# Pilot density and hierarchy pass

Scope: La Une, Courrier, Feuilleton, Épreuve, Cahiers, Studio, review, and
L’administration at the iPhone viewport.

The pass uses one hierarchy contract:

1. one serif hero owns the first read;
2. no more than one adjacent line of kicker-level marginalia;
3. secondary metadata stays in a single horizontally scrollable line when space is
   tight rather than wrapping into a second wall of uppercase labels;
4. major journal sections receive at least 18–20 px of vertical breathing room;
5. completion/correction state is carried by the stamp or proofreader mark, not
   another competing label.

Implemented in `web-frontend/styles/globals.css` under “Pilot density pass”.
No content, state, routing, or control was removed.

The deterministic capture surface remains `web-frontend/pages/mobile-visual-qa.tsx`.
For the final light/dark comparison, run the signed-in capture recipe from
`web-frontend/README.md` at the 390 × 844 viewport after the preview browser is
allowed to open the local app. The current Codex browser session blocks
`127.0.0.1:3000`, so no screenshot artifact is claimed in this document.
