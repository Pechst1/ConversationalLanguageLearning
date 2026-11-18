# Playing L'Atelier as a learner — shared brief

L'Atelier is a French-learning app built around a daily serial («La clé d'Odile») in which the learner plays a part. The owner wants an honest product review before ten real learners use it for a week. You are one of several players. You play the app in a phone-sized browser as a real learner would, and you write down exactly what happened. You do NOT review code, fix anything, or edit any file in the repository. Your only outputs are your log file and named screenshots.

The bar is «the best language-learning app there is», not «it works». But your job is first of all to be an accurate witness: what the screen said, what you did, what came back. I (the reviewer) will judge your screenshots and transcript myself, so verbatim quotes and screenshot names matter more than your conclusions.

## How to drive the app

A harness runs a real stack with real model output (it costs money: do not replay things needlessly). You drive it with a helper:

    P=/private/tmp/claude-501/-Users-vincentpechstein--claude-spares-spare-8BRKzU/24979350-c568-4d32-a313-976ff75f7f81/scratchpad/p
    $P PORT snap                              # what is on screen: text, numbered controls, fields; saves NNN.png
    P_FULL=1 $P PORT snap                     # same, with up to 6000 chars of text
    $P PORT click '{"text":"Weiter"}'         # tap by visible text   (add "exact":true if ambiguous)
    $P PORT click '{"index":3}'               # tap by number from the last snap
    $P PORT type '{"text":"Bonjour"}'         # fill the visible text field (field:N for the Nth)
    $P PORT key '{"key":"Enter"}'
    $P PORT goto '{"path":"/atelier"}'        # /atelier is Home
    $P PORT scroll '{"dy":600}'
    $P PORT wait '{"ms":4000}'                # wait then snap (generation can take 10–80 s; a screen that says it is preparing is not stuck)
    $P PORT shot '{"name":"a1-d1-home","full":true}'   # a NAMED full-page screenshot — take one for every screen worth judging
    $P PORT clock '{"days":N}'                # the server's «today» = real today + N days (absolute offset, not relative)
    $P PORT walk '{"path":"/__walk/prefetch","body":{"email":"LEARNER_EMAIL"}}'   # the night run: writes tomorrow's page with the writer model
    $P PORT walk '{"path":"/__walk/spend"}'   # money spent so far and the cap

Every click/goto returns the new screen, so you rarely need a separate snap. Screenshots land in the run folder given in your task; view a screenshot with the Read tool whenever layout, density or typography matters (do this for every new kind of screen at least once, and whenever text looks odd).

**Moving to the next day.** In production a night job writes the next day's page. To play day N+1: `clock` with the next offset, then the `prefetch` walk call (it can take 30–90 s), then `goto /atelier`. Do this unless your task tells you to skip the prefetch for a specific day.

**Money.** Check `/__walk/spend` at the start of each day and write the figure in your log. If `usd` is within US$0.70 of `cap`, stop playing, write up, and say so.

**Do not**: call `stop` on the harness, touch the other port, start servers, edit repo files, or run git commands. If the harness itself dies or a screen is stuck for more than 3 minutes after reloads, write down what you saw and go on with another surface; if nothing works, finish your log and report.

## How to play

Play honestly as the learner described in your task — their level, their native language, their patience.
- Write replies the way that learner would: at A1 short, with typical mistakes (missing articles, wrong gender, infinitive instead of conjugated verb, a German or English word when stuck); at B1 full sentences with typical B1 errors (wrong past tense, preposition, subjunctive missing).
- Do not always give the answer the scene wants. On each day, at least once do something different: refuse, say something off-topic, make a choice a compliant learner would not make, or give a very short answer. Note precisely whether the story reacts (quote the lines) or carries on as if you had said the expected thing.
- In practice steps (La Forge, vocabulary, recall), get about one item in four wrong on purpose, in the way a real learner would, and record the feedback verbatim: does it show the solution before the retry? is the explanation right, in the learner's language, useful?
- Tap words, hints, translations and audio buttons where they exist, to see what help a stuck learner gets.
- Count roughly how many taps and how many minutes of real reading/writing each step would take a human.

## What to record (your log file)

Append to your log file as you go (after every step, not at the end — if you run out of room the log must already hold everything). For each step:

    ### Day N · <step name>  (shots: 031.png, a1-d1-scene.png)
    - Screen said: «verbatim French/German/English text that matters»
    - I did: …  (my reply verbatim)
    - It answered: «verbatim»
    - Taps / est. minutes for a human:
    - Observed: facts only
    - My read (inference): one or two lines against these questions —
      learns something they could name? fun or merely completed? longer than it is worth? fits where it sits and connects to before/after? still wanted on day 10? did the story react to what I did? is the screen clean, intuitive, coherent with the rest?

Be specific. «Four cards in a row ask for the same word» is useful; «engagement could be improved» is not. Record good things in one line and move on. Record every language mix-up (French/English/German chrome on the wrong screen), every sentence that is wrong French, every feedback that is wrong, every dead end, every wait over 5 s (with seconds), every place you did not know what to do next.

Keep a running list at the top of the log: **Carry-over** — things from earlier days that later days did or did not pick up (a name you gave, a choice you made, a word you learned, a mistake you made).

## Your final message

A short summary (under 400 words): which days and surfaces you actually played, which you could not reach and why, the spend figure, the path of your log, and the ten observations you think matter most, each with its screenshot name. No padding.
