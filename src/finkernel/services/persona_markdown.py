from __future__ import annotations


def build_persona_evidence_from_answers(answers: list[dict]) -> list[dict]:
    items: list[dict] = []
    for answer in answers:
        dimension = answer.get("dimension")
        excerpt = str(answer.get("answer_text") or "").strip()
        if not dimension or not excerpt:
            continue
        items.append(
            {
                "dimension": dimension,
                "excerpt": excerpt,
                "question_id": answer.get("question_id"),
                "question_type": answer.get("question_type"),
                "source_type": answer.get("source_type"),
                "captured_at": answer.get("answered_at"),
            }
        )
    return items
