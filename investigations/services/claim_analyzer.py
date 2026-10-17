import logging
import re

logger = logging.getLogger(__name__)


def compute_text_similarity(s1: str, s2: str) -> float:
    words1 = set(re.findall(r'\b[a-zA-Z]{4,}\b', s1.lower()))
    words2 = set(re.findall(r'\b[a-zA-Z]{4,}\b', s2.lower()))
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)


class ClaimAnalyzer:
    """
    Cross-references claims across sources to discover corroboration,
    isolated reports, and potential disagreements or competing perspectives.
    """

    def analyze_and_corroborate(self, extracted_claims_by_source: list[dict]) -> list[dict]:
        """
        Input: list of { 'source_obj': Source, 'claim_data': dict }
        Output: list of consolidated claim dicts with multiple sources attached:
        [{
            'claim_text': str,
            'evidence_status': str,
            'confidence_assessment': str,
            'dispute_reason': str | None,
            'sources': list[Source]
        }]
        """
        consolidated = []

        for item in extracted_claims_by_source:
            source = item['source']
            raw_claim = item['claim']
            claim_text = raw_claim['claim_text']
            initial_status = raw_claim.get('evidence_status', 'SUPPORTED')
            initial_dispute = raw_claim.get('dispute_reason')

            # Check if this claim closely matches an already consolidated claim
            matched = False
            for existing in consolidated:
                sim = compute_text_similarity(claim_text, existing['claim_text'])
                if sim >= 0.45:  # Shared key terms & context
                    matched = True
                    if source not in existing['sources']:
                        existing['sources'].append(source)
                    # Corroborated by multiple sources
                    if len(existing['sources']) > 1:
                        if existing['evidence_status'] != 'DISPUTED':
                            existing['evidence_status'] = 'SUPPORTED'
                            existing['confidence_assessment'] = f"Corroborated across {len(existing['sources'])} independent sources"
                    break

            if not matched:
                status = 'SINGLE_SOURCE' if initial_status == 'SUPPORTED' else initial_status
                confidence = (
                    "Single primary source report" if status == 'SINGLE_SOURCE'
                    else "Competing accounts or noted uncertainty"
                )
                consolidated.append({
                    'claim_text': claim_text,
                    'evidence_status': status,
                    'confidence_assessment': confidence,
                    'dispute_reason': initial_dispute,
                    'sources': [source]
                })

        # Second pass: detect competing claims across consolidated items
        for i in range(len(consolidated)):
            for j in range(i + 1, len(consolidated)):
                c1 = consolidated[i]
                c2 = consolidated[j]
                sim = compute_text_similarity(c1['claim_text'], c2['claim_text'])
                # If they discuss the same topic (sim > 0.3) but express opposing sentiments or projections
                if sim >= 0.3:
                    opposing_terms = [
                        ('increase', 'decrease'), ('exceed', 'miss'), ('growth', 'decline'),
                        ('surplus', 'shortage'), ('delayed', 'on-track'), ('ready', 'unready')
                    ]
                    t1 = c1['claim_text'].lower()
                    t2 = c2['claim_text'].lower()
                    for term_a, term_b in opposing_terms:
                        if (term_a in t1 and term_b in t2) or (term_b in t1 and term_a in t2):
                            c1['evidence_status'] = 'DISPUTED'
                            c1['confidence_assessment'] = 'Competing projections or estimates across sources'
                            c1['dispute_reason'] = f"Disagrees with perspective in: \"{c2['claim_text'][:120]}...\""

                            c2['evidence_status'] = 'DISPUTED'
                            c2['confidence_assessment'] = 'Competing projections or estimates across sources'
                            c2['dispute_reason'] = f"Disagrees with perspective in: \"{c1['claim_text'][:120]}...\""
                            break

        return consolidated
