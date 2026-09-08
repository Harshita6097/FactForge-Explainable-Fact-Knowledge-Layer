RELATIONSHIP_EXPLANATION_PROMPT = """You are an analyst explaining why two facts from different documents are related.

Fact A:
- Entity: {entity_a}
- Attribute: {attribute_a}
- Value: {value_a}
- Period: {period_a}
- Source: {source_a} (page {page_a})
- Snippet: "{snippet_a}"

Fact B:
- Entity: {entity_b}
- Attribute: {attribute_b}
- Value: {value_b}
- Period: {period_b}
- Source: {source_b} (page {page_b})
- Snippet: "{snippet_b}"

Relationship type detected: {relationship_type}

Write a single concise sentence (max 30 words) explaining this relationship.
Focus on: what matches, what differs, and why it is a {relationship_type}.
Return only the explanation sentence, nothing else."""
