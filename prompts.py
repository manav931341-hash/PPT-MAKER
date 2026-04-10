"""
prompts.py — All LLM prompt templates + complete design spec library.

Design philosophy:
  - LLM picks layouts/themes/colors FROM our library (not freely)
  - This guarantees quality — LLM does structure, our code does rendering
"""

# ════════════════════════════════════════════════════════════════════════════
# DESIGN LIBRARY  — fed to LLM as context in every prompt
# ════════════════════════════════════════════════════════════════════════════

PPTX_DESIGN_LIBRARY = """
=== PPTX DESIGN LIBRARY ===

THEMES (pick one theme_id):
  professional  → Navy #0D1B4B, Accent #1E88E5, Text #FFFFFF/#1A1A2E, best: corporate/investor
  creative      → Purple #6C2EB9, Accent #E91E8C, Text #FFFFFF/#1A0035, best: marketing/brand
  minimal       → Charcoal #212121, Accent #BDBDBD, Text #FFFFFF/#212121, best: exec summary
  startup       → Dark #0A0E1A, Accent #00E5FF/#FF6D00, Text #FFFFFF, best: pitch/demo
  nature        → Forest #1B5E20, Accent #66BB6A, Text #FFFFFF/#1B5E20, best: sustainability
  sunset        → Deep red #B71C1C, Accent #FF8F00, Text #FFFFFF, best: energy/passion
  ocean         → Deep blue #01579B, Accent #00B0FF, Text #FFFFFF, best: tech/data
  corporate_gold→ Dark #1A1200, Accent #FFD600, Text #FFFFFF, best: luxury/finance
  rose_gold     → Blush #880E4F, Accent #F48FB1, Text #FFFFFF, best: fashion/beauty
  monochrome    → Black #000000, Accent #FFFFFF, Text #FFFFFF, best: bold/editorial

FONT PAIRS (pick one font_pair_id):
  montserrat_lato       → Headers: Montserrat Bold, Body: Lato Regular
  playfair_lato         → Headers: Playfair Display, Body: Lato Regular
  raleway_opensans      → Headers: Raleway Bold, Body: Open Sans
  roboto_roboto         → Headers: Roboto Bold, Body: Roboto Regular
  oswald_sourcesans     → Headers: Oswald Bold, Body: Source Sans Pro

SLIDE LAYOUTS (pick layout_id per slide):
  title_hero        → Full bleed background, giant title centred, subtitle below
  title_left        → Left-aligned title + subtitle, accent bar on left edge
  bullets_header    → Coloured header band, 4-6 bullet points with icon dots
  bullets_numbered  → Header + numbered list, good for steps/process
  two_col_equal     → Two equal columns, header spans full width
  two_col_60_40     → 60/40 split, main content left, sidebar right
  image_left        → Image left 50%, text/bullets right 50%
  image_right       → Text left 50%, image right 50%
  image_full        → Full-bleed image with overlay text
  chart_full        → Header + full-width chart (bar/line/pie)
  chart_with_text   → Chart left 60%, key insight text right 40%
  data_table        → Header + formatted table, max 6 cols × 8 rows
  quote_big         → Large centred quote with attribution, accent colour bg
  timeline          → Horizontal or vertical timeline, up to 6 nodes
  icon_grid         → 2×3 or 3×2 grid of icon + label + short desc
  team_cards        → 2-3 team member cards with role + bio
  stats_highlight   → 3-4 big numbers with labels (KPI slide)
  section_divider   → Full-colour slide, section title only, visual break
  closing_cta       → Full-colour closing slide, CTA + contact info

BACKGROUND STYLES (pick one bg_style per slide):
  solid_primary     → Solid primary theme colour
  solid_dark        → Very dark shade of primary
  solid_white       → White / off-white
  gradient_lr       → Left-to-right gradient, primary → accent
  gradient_tb       → Top-to-bottom gradient, primary → dark
  image_overlay     → Photo background with dark overlay (triggers Unsplash fetch)
  accent_band_top   → White slide with thick accent colour band at top
  accent_band_left  → White slide with thick accent colour band on left
  split_diagonal    → Diagonal split, primary left / white right
"""

XLSX_DESIGN_LIBRARY = """
=== XLSX DESIGN LIBRARY ===

THEMES (pick one theme_id):
  corporate_blue  → Header #1565C0 white text, alt rows #E3F2FD
  dark_modern     → Header #212121 white text, alt rows #F5F5F5
  forest_green    → Header #2E7D32 white text, alt rows #E8F5E9
  sunset_orange   → Header #E65100 white text, alt rows #FFF3E0
  purple_pro      → Header #4A148C white text, alt rows #F3E5F5
  rose_business   → Header #880E4F white text, alt rows #FCE4EC
  ocean_data      → Header #01579B white text, alt rows #E1F5FE
  minimal_gray    → Header #424242 white text, alt rows #FAFAFA

COLUMN STYLES (assign per column based on data type):
  currency        → Right-align, $ prefix, 2 decimal, thousands separator
  percentage      → Right-align, % suffix, 1 decimal, progress bar conditional fmt
  integer         → Right-align, thousands separator
  date            → Centre-align, YYYY-MM-DD format
  text_wrap       → Left-align, wrap text, auto row height
  status_badge    → Centre-align, colour fill by value (green/yellow/red)
  rating          → Centre-align, star characters or 1-5 scale
  url_link        → Left-align, blue underline hyperlink style
  formula_sum     → Auto-sum formula at bottom, bold
  progress_bar    → Data bar conditional formatting

SHEET FEATURES (list which to enable):
  freeze_header         → Freeze row 1 (header always visible)
  freeze_first_col      → Freeze column A
  auto_filter           → Dropdown filters on all header columns
  zebra_rows            → Alternating row background colours
  bold_totals_row       → Bold bottom row with totals/averages
  conditional_heatmap   → Colour scale on numeric columns (green→yellow→red)
  traffic_lights        → Icon set (green/yellow/red) on status columns
  data_bars             → In-cell data bar on numeric columns
  sparklines            → Mini chart in last column summarising row trend
  dropdown_validation   → Dropdown list for categorical columns
  named_range           → Define Excel named ranges for data tables
  print_titles          → Header row repeats on each printed page
"""

# ════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT SHARED BASE
# ════════════════════════════════════════════════════════════════════════════

_BASE_SYSTEM = """You are an expert presentation and spreadsheet designer AI.
You ALWAYS return ONLY valid JSON — no markdown, no explanation, no preamble.
Never wrap your response in ```json``` code fences.
Follow the exact JSON schema specified in each prompt."""


# ════════════════════════════════════════════════════════════════════════════
# C1 — INTENT DETECTION
# ════════════════════════════════════════════════════════════════════════════

INTENT_SYSTEM = _BASE_SYSTEM

INTENT_USER = """Analyse this goal and return JSON:

Goal: "{goal}"

Return this exact schema:
{{
  "file_type": "pptx" | "xlsx" | "both",
  "confidence": 0.0-1.0,
  "reasoning": "one sentence",
  "suggested_title": "short title for the file",
  "domain": "business|education|marketing|finance|tech|hr|sales|other",
  "estimated_slides_or_rows": 8
}}"""


# ════════════════════════════════════════════════════════════════════════════
# C2 — STRUCTURE PLANNING
# ════════════════════════════════════════════════════════════════════════════

STRUCTURE_SYSTEM = _BASE_SYSTEM + "\n" + PPTX_DESIGN_LIBRARY + "\n" + XLSX_DESIGN_LIBRARY

STRUCTURE_USER_PPTX = """Create 3 different PPTX structure options for this goal.
Goal: "{goal}"
Domain: "{domain}"

Return this exact schema:
{{
  "options": [
    {{
      "key": "A",
      "label": "Option name",
      "description": "One line description",
      "slide_count": 10,
      "slides": [
        {{
          "slide_number": 1,
          "title": "Slide title",
          "layout_id": "title_hero",
          "bg_style": "gradient_lr",
          "content_hint": "What goes on this slide"
        }}
      ]
    }},
    {{ "key": "B", ... }},
    {{ "key": "C", ... }}
  ]
}}"""

STRUCTURE_USER_XLSX = """Create 3 different XLSX structure options for this goal.
Goal: "{goal}"
Domain: "{domain}"

Return this exact schema:
{{
  "options": [
    {{
      "key": "A",
      "label": "Option name",
      "description": "One line description",
      "sheets": [
        {{
          "sheet_name": "Main Data",
          "purpose": "What this sheet tracks",
          "columns": [
            {{"name": "Column Name", "col_style": "text_wrap", "sample_values": ["val1","val2"]}}
          ],
          "features": ["freeze_header", "auto_filter", "zebra_rows"]
        }}
      ]
    }},
    {{ "key": "B", ... }},
    {{ "key": "C", ... }}
  ]
}}"""


# ════════════════════════════════════════════════════════════════════════════
# C3 — STYLE SELECTION  (static options, no LLM call needed)
# ════════════════════════════════════════════════════════════════════════════

PPTX_STYLE_OPTIONS = [
    {"key": "A", "theme_id": "professional", "font_pair_id": "montserrat_lato",
     "label": "Professional", "description": "Navy + Blue — Corporate, investor-facing"},
    {"key": "B", "theme_id": "creative", "font_pair_id": "playfair_lato",
     "label": "Creative", "description": "Purple + Pink — Marketing, brand decks"},
    {"key": "C", "theme_id": "minimal", "font_pair_id": "raleway_opensans",
     "label": "Minimal", "description": "Charcoal + White — Executive summaries"},
    {"key": "D", "theme_id": "startup", "font_pair_id": "oswald_sourcesans",
     "label": "Startup", "description": "Dark + Cyan/Orange — Pitch decks, demo days"},
    {"key": "E", "theme_id": "ocean", "font_pair_id": "roboto_roboto",
     "label": "Ocean", "description": "Deep Blue + Cyan — Tech, data-heavy"},
    {"key": "F", "theme_id": "nature", "font_pair_id": "raleway_opensans",
     "label": "Nature", "description": "Forest Green — Sustainability, environment"},
    {"key": "G", "theme_id": "corporate_gold", "font_pair_id": "playfair_lato",
     "label": "Gold", "description": "Dark + Gold — Luxury, finance"},
    {"key": "H", "theme_id": "sunset", "font_pair_id": "oswald_sourcesans",
     "label": "Sunset", "description": "Red + Orange — Energy, passion"},
]

XLSX_STYLE_OPTIONS = [
    {"key": "A", "theme_id": "corporate_blue", "style": "simple",
     "label": "Simple", "description": "Blue headers, alternating rows, auto-filter"},
    {"key": "B", "theme_id": "dark_modern", "style": "analytical",
     "label": "Analytical", "description": "Dark headers + conditional formatting + colour scales"},
    {"key": "C", "theme_id": "forest_green", "style": "advanced",
     "label": "Advanced", "description": "Green theme + summary formulas + freeze panes + data validation"},
    {"key": "D", "theme_id": "ocean_data", "style": "analytical",
     "label": "Ocean Data", "description": "Ocean blue + data bars + traffic light icons"},
    {"key": "E", "theme_id": "purple_pro", "style": "advanced",
     "label": "Purple Pro", "description": "Purple headers + sparklines + named ranges"},
]

TONE_OPTIONS = [
    {"key": "1", "tone": "professional", "label": "Professional — Formal, business language"},
    {"key": "2", "tone": "conversational", "label": "Conversational — Friendly, approachable"},
    {"key": "3", "tone": "data_driven", "label": "Data-Driven — Numbers-first, concise"},
    {"key": "4", "tone": "inspirational", "label": "Inspirational — Motivating, bold statements"},
]


# ════════════════════════════════════════════════════════════════════════════
# C4 — CONTENT GENERATION
# ════════════════════════════════════════════════════════════════════════════

CONTENT_SYSTEM = _BASE_SYSTEM + "\n" + PPTX_DESIGN_LIBRARY + "\n" + XLSX_DESIGN_LIBRARY

CONTENT_USER_PPTX = """Generate complete slide content for a PPTX presentation.

Goal: "{goal}"
Theme: "{theme_id}"
Font pair: "{font_pair_id}"
Tone: "{tone}"
Structure chosen:
{structure_json}

For EACH slide, return full content using this schema:
{{
  "slides": [
    {{
      "slide_number": 1,
      "layout_id": "title_hero",
      "bg_style": "gradient_lr",
      "theme_id": "{theme_id}",
      "title": "Slide title",
      "subtitle": "Optional subtitle",
      "bullets": ["Point 1", "Point 2", "Point 3"],
      "left_col": {{"heading": "...", "bullets": ["..."]}},
      "right_col": {{"heading": "...", "bullets": ["..."]}},
      "quote": "Optional quote text",
      "quote_author": "Author name",
      "stats": [{{"value": "94%", "label": "Customer satisfaction"}}],
      "timeline_nodes": [{{"year": "2020", "event": "Founded"}}],
      "chart_data": {{
        "chart_type": "bar",
        "title": "Chart title",
        "categories": ["Q1","Q2","Q3","Q4"],
        "series": [{{"name": "Revenue", "values": [120,145,178,210]}}]
      }},
      "table_data": {{
        "headers": ["Col1","Col2"],
        "rows": [["val","val"]]
      }},
      "image_search_query": "Optional: search query for background image",
      "speaker_notes": "Notes for presenter"
    }}
  ]
}}"""

CONTENT_USER_XLSX = """Generate complete spreadsheet content for an XLSX file.

Goal: "{goal}"
Theme: "{theme_id}"
Style: "{style}"
Tone: "{tone}"
Structure chosen:
{structure_json}

Return this schema:
{{
  "sheets": [
    {{
      "sheet_name": "Sheet name",
      "theme_id": "{theme_id}",
      "features": ["freeze_header","auto_filter","zebra_rows"],
      "columns": [
        {{
          "name": "Column Name",
          "col_style": "currency",
          "width": 15
        }}
      ],
      "rows": [
        ["value1", "value2", "value3"]
      ],
      "chart": {{
        "chart_type": "bar",
        "title": "Chart title",
        "data_column_indices": [1, 2, 3],
        "label_column_index": 0
      }},
      "summary_row": ["Total", "=SUM(B2:B100)", "=AVERAGE(C2:C100)"]
    }}
  ]
}}"""


# ════════════════════════════════════════════════════════════════════════════
# REFINEMENT (iterative chat)
# ════════════════════════════════════════════════════════════════════════════

REFINE_SYSTEM = _BASE_SYSTEM + "\n" + PPTX_DESIGN_LIBRARY + "\n" + XLSX_DESIGN_LIBRARY

REFINE_USER = """The user wants to refine their generated {file_type} file.

Original goal: "{goal}"
Current content (JSON):
{current_content_json}

User's refinement request: "{user_message}"

Apply the user's changes to the content and return the COMPLETE updated content JSON
using the exact same schema as the original. Do not omit any slides/sheets.
Only change what the user asked for."""


# ════════════════════════════════════════════════════════════════════════════
# REFERENCE FILE ANALYSIS (upload a sample PPT/Excel)
# ════════════════════════════════════════════════════════════════════════════

REFERENCE_ANALYSIS_SYSTEM = _BASE_SYSTEM

REFERENCE_ANALYSIS_USER = """Analyse this extracted structure from a reference {file_type} file
and return a design spec the user wants to replicate.

Extracted raw structure:
{raw_structure}

Return this schema:
{{
  "detected_theme": "description of colour scheme",
  "detected_layouts": ["list of layout types used"],
  "slide_count_or_sheet_count": 10,
  "font_style": "formal|casual|bold|minimal",
  "content_density": "light|medium|heavy",
  "suggested_theme_id": "one of our theme_ids",
  "suggested_font_pair_id": "one of our font_pair_ids",
  "replication_notes": "What to replicate and what to adapt",
  "structure_to_use": {{}}
}}"""
