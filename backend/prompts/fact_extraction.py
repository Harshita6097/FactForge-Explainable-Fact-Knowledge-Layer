FACT_EXTRACTION_PROMPT = """You are a precise fact extraction engine. Extract structured facts from the document text below.

Return ONLY a valid JSON array. No explanation, no markdown, no code blocks — just the raw JSON array.

Each fact must follow this exact structure:
{{
  "entity": "the subject (organization, person, country, product, etc.)",
  "attribute": "what is being measured or described (Revenue, CEO, GDP Growth, Employees, etc.)",
  "raw_value": "exact value as written in the text",
  "unit": "unit if applicable (Crore, %, USD, Million, etc.) or null",
  "period": "time period if mentioned (FY2024, Q4 2023, 2024, etc.) or null",
  "confidence": 0.0 to 1.0 based on how clearly the fact is stated,
  "snippet": "the exact sentence or phrase from the text that supports this fact"
}}

Rules:
- Extract numbers, percentages, money, dates, people, organizations, locations, operational and business metrics
- Do NOT summarize or paraphrase — use exact values from the text
- Do NOT invent facts not present in the text
- If a value has no unit, set unit to null
- If no time period is mentioned, set period to null
- Confidence: 0.9+ for explicit numeric facts, 0.7-0.9 for clearly stated facts, 0.5-0.7 for inferred facts
- Extract ALL meaningful facts, not just financial ones
- Return empty array [] if no facts found

Document text (page {page_number} of {total_pages}, source: {filename}):
---
{text}
---

Return only the JSON array:"""


BATCH_FACT_EXTRACTION_PROMPT = """You are a precise fact extraction engine. Extract structured facts from the document pages below.

Return ONLY a valid JSON array. No explanation, no markdown, no code blocks — just the raw JSON array.

Each fact must follow this exact structure:
{{
  "entity": "the subject (organization, person, country, product, etc.)",
  "attribute": "what is being measured or described",
  "raw_value": "exact value as written in the text",
  "unit": "unit if applicable or null",
  "period": "time period if mentioned or null",
  "confidence": 0.0 to 1.0,
  "snippet": "exact supporting sentence from the text",
  "page_number": the page number where this fact was found
}}

Rules:
- Extract numbers, percentages, money, dates, people, organizations, metrics
- Use exact values, do not paraphrase
- Confidence: 0.9+ for explicit numeric facts, 0.7-0.9 for clearly stated, 0.5-0.7 for inferred
- Return empty array [] if no facts found

Pages:
---
{pages_text}
---

Return only the JSON array:"""
