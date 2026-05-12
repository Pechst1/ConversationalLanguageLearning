# Atelier Language Asset Recipe

Atelier stores stable learning assets in three layers:

1. `atelier_language_packs`: one reviewed convention pack per language and version.
2. `grammar_concepts`: the canonical human-readable concept catalog.
3. `atelier_concept_blueprints`: one reviewed Atelier blueprint per concept, language, and asset version.

Daily exercises are not source material. They stay cached in `atelier_exercise_sets`; the blueprint is the source of truth for pedagogy, motif recipes, exercise recipes, correction rubrics, and detection hints.

## Universal Generation Input

```yaml
language_pack:
  target_language: "<language name>"
  language_code: "<ISO code>"
  learner_native_language: "English"
  supported_levels: ["A1", "A2", "B1", "B2", "C1"]
  writing_system: "<Latin/Cyrillic/etc>"
  correction_style:
    address: "you"
    max_why_sentences: 2
    max_repair_sentences: 1
    avoid_phrases: ["the learner", "the user"]
  atelier_design_language:
    style: "editorial Bauhaus"
    motif_constraints:
      - "use geometric primitives"
      - "use semantic labels sparingly"
      - "no decorative generic icons"
      - "icon must explain the grammar relation"

concept_input:
  external_id: "<LANG_LEVEL_CATEGORY_NUMBER>"
  cefr_level: "<A1-C1>"
  category: "<grammar category>"
  subskill: "<specific skill>"
  concept_name: "<learner-facing name>"
  parent_external_id: "<optional>"
  prerequisite_ids: ["<optional>"]
  teaching_order: 0
  is_foundation: true
  core_rule_seed: "<short rule or source note>"
  anchor_examples_seed:
    - "<example 1>"
    - "<example 2>"
```

## Expected Blueprint Output

```yaml
pedagogy:
  core_rule: "one direct learner-facing sentence"
  when_to_use: "2-3 sentences"
  pattern: "explicit form pattern"
  main_traps: ["3-5 common traps"]
  anchor_examples: ["3-5 examples"]
  contrast_notes: ["what this is often confused with"]

sentence_xray:
  sentence: "<canonical example>"
  marks:
    - token: "<word/span>"
      role: "<grammar role>"
      explanation: "<short explanation>"

visual_motif:
  style: "atelier_bauhaus_v1"
  concept_metaphor: "<semantic metaphor>"
  canvas: { width: 84, height: 84 }
  primitives:
    - type: "rect|line|circle|arrow|path|text"
      role: "<semantic role>"
      fill: "ink|paper|red|blue|yellow|none"
  accessibility_label: "<screen-reader description>"

exercise_recipe:
  recognize:
    fill: { subitems: 3 }
    word_bank: { subitems: 3, scrambled_order_required: true }
    classify: { subitems: 3 }
  transform:
    directed_rewrite: { subitems: 1 }
    contrast_rewrite: { subitems: 1 }
    repair_rewrite: { subitems: 1 }
  output_ladder:
    short_sentence: { subitems: 1 }
    paragraph: { target_count: "<per concept>" }
    spoken_response: { subitems: 1 }
    conversation_turn: { subitems: 1 }

correction_rubric:
  errata_labels: ["accessible labels"]
  recurring_rules: ["which errors become SRS errata"]
  task_compliance_rules: ["which misses are shown but not scheduled"]
  why_templates: ["direct explanation templates using you"]
  repair_templates: ["actionable repair templates"]

detection_hints:
  positive_patterns: ["regex or structured hints"]
  common_wrong_patterns: ["regex or structured hints"]
  lexical_links: ["optional vocabulary mappings"]
```

Blueprints start as generated drafts unless they are produced by a deterministic, locally validated backfill. Human-reviewed or validated blueprints can be marked `approved`; deprecated blueprints remain stored for traceability.
