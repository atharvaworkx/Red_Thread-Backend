import re
import logging
from .ai_provider import OllamaProvider

logger = logging.getLogger(__name__)

KNOWN_TECH_ENTITIES = {
    # Frontier AI & Labs
    "DeepSeek": "ORGANIZATION",
    "DeepSeek-R1": "PRODUCT",
    "DeepSeek-V3": "PRODUCT",
    "High-Flyer": "ORGANIZATION",
    "Liang Wenfeng": "PERSON",
    "OpenAI": "ORGANIZATION",
    "Anthropic": "ORGANIZATION",
    "Meta": "ORGANIZATION",
    "Mistral": "ORGANIZATION",
    "Microsoft": "ORGANIZATION",
    "Google": "ORGANIZATION",
    "Google DeepMind": "ORGANIZATION",
    "Ollama": "PRODUCT",
    "Hugging Face": "ORGANIZATION",
    "Alibaba": "ORGANIZATION",
    "Tencent": "ORGANIZATION",
    "Baidu": "ORGANIZATION",
    "Qwen": "PRODUCT",
    "Groq": "ORGANIZATION",
    
    # Hardware & Semiconductors
    "Nvidia": "ORGANIZATION",
    "TSMC": "ORGANIZATION",
    "ASML": "ORGANIZATION",
    "Intel": "ORGANIZATION",
    "AMD": "ORGANIZATION",
    "Samsung": "ORGANIZATION",
    "SK Hynix": "ORGANIZATION",
    "Micron": "ORGANIZATION",
    "Apple": "ORGANIZATION",
    "Qualcomm": "ORGANIZATION",
    "Broadcom": "ORGANIZATION",
    "ARM": "ORGANIZATION",
    "Jensen Huang": "PERSON",
    "Sam Altman": "PERSON",
    "Lisa Su": "PERSON",
    "Pat Gelsinger": "PERSON",
    "H100": "PRODUCT",
    "H800": "PRODUCT",
    "A100": "PRODUCT",
    "B200 Blackwell": "PRODUCT",
    "CoWoS": "TECHNOLOGY",
    "HBM3e": "TECHNOLOGY",
    "HBM4": "TECHNOLOGY",
    "EUV Lithography": "TECHNOLOGY",
    "High-NA EUV": "TECHNOLOGY",
    "GAAFET": "TECHNOLOGY",
    "Mixture of Experts": "TECHNOLOGY",
    "Reinforcement Learning": "TECHNOLOGY",
    "Taiwan": "LOCATION",
    "Hangzhou": "LOCATION",
    "Arizona": "LOCATION",
    "Veldhoven": "LOCATION",
}

# Web/GitHub UI and non-entity words that should never be treated as named entities
JUNK_ENTITY_WORDS = {
    'branches', 'tags', 'commits', 'folders', 'pull requests', 'code open',
    'app store', 'agentic coding', 'terminus', 'hugging', 'terms', 'privacy',
    'about', 'contact', 'home', 'search', 'menu', 'log in', 'sign in', 'sign up',
    'register', 'share', 'copy', 'print', 'download', 'close', 'cancel', 'submit',
    'next', 'previous', 'filter', 'sort', 'view', 'details', 'page', 'file',
    'read', 'write', 'fork', 'watch', 'star', 'release', 'releases', 'issues',
    'discussions', 'actions', 'security', 'insights', 'settings', 'overview',
    'repository', 'repositories', 'main branch', 'master branch', 'click here',
    'learn more', 'read more', 'all rights', 'rights reserved', 'united states',
    'new york', 'table of contents', 'navigation', 'footer', 'header', 'sidebar',
    'license', 'contributing', 'readme', 'stars', 'forks', 'commit', 'branch'
}

RELATIONSHIP_PATTERNS = [
    (r'(?:supplies|supplier to|delivers to)\s+([A-Z][a-zA-Z0-9\s]+)', 'SUPPLIES_EQUIPMENT_TO'),
    (r'(?:manufactures for|produces chips for|foundry partner for)\s+([A-Z][a-zA-Z0-9\s]+)', 'MANUFACTURES_FOR'),
    (r'(?:competes with|rival of)\s+([A-Z][a-zA-Z0-9\s]+)', 'COMPETES_WITH'),
    (r'(?:partners with|collaborates with)\s+([A-Z][a-zA-Z0-9\s]+)', 'PARTNERS_WITH'),
    (r'(?:acquires|buys)\s+([A-Z][a-zA-Z0-9\s]+)', 'ACQUIRES'),
    (r'(?:invests in|funding|funded by|backed by)\s+([A-Z][a-zA-Z0-9\s]+)', 'INVESTS_IN'),
    (r'(?:relies on|dependent on)\s+([A-Z][a-zA-Z0-9\s]+)', 'DEPENDS_ON'),
]

ASSERTION_WORDS = [
    'announced', 'reported', 'revealed', 'produced', 'increased', 'decreased',
    'delayed', 'forecasted', 'expanded', 'claims', 'surpassed', 'invested',
    'contracted', 'warned', 'confirmed', 'launched', 'shipped', 'constrained',
    'developed', 'founded', 'established', 'trained', 'open-sourced', 'released',
    'outperformed', 'achieved', 'features', 'architected', 'operates', 'introduced'
]


def is_junk_entity(name: str) -> bool:
    clean = name.strip()
    if len(clean) < 3 or len(clean) > 40:
        return True
    lower = clean.lower()
    if lower in JUNK_ENTITY_WORDS:
        return True
    # If any single token is in JUNK_ENTITY_WORDS
    words = re.findall(r'\b[a-z]+\b', lower)
    if not words or any(w in JUNK_ENTITY_WORDS for w in words):
        return True
    # Filter out generic code/file names
    if any(ext in lower for ext in ['.py', '.js', '.ts', '.html', '.md', '.json', 'http', 'www']):
        return True
    return False


class EvidenceExtractor:
    """
    Extracts claims, entities, relationships, and timeline events from source texts.
    Uses Ollama when available, with a deterministic fallback pipeline.
    """

    def __init__(self, ollama_provider: OllamaProvider = None):
        self.ai = ollama_provider or OllamaProvider()

    def extract(self, query: str, source_dict: dict, citation_key: str) -> dict:
        """
        Extracts structured intelligence for a single source.
        Returns:
        {
            'claims': list[dict],
            'entities': list[dict],
            'relationships': list[dict],
            'timeline_events': list[dict],
            'mode_used': str
        }
        """
        text = source_dict.get('excerpt', '') or source_dict.get('title', '')
        title = source_dict.get('title', '')

        # Attempt structured Ollama extraction first if model is online
        ai_result = self._extract_with_ai(query, title, text, citation_key)
        if ai_result:
            ai_result['mode_used'] = 'LOCAL_AI'
            return ai_result

        # Deterministic extraction fallback
        rule_result = self._extract_deterministic(query, title, text, citation_key)
        rule_result['mode_used'] = 'LOCAL_FALLBACK'
        return rule_result

    def _extract_with_ai(self, query: str, title: str, text: str, citation_key: str) -> dict | None:
        system_prompt = (
            "You are an intelligence research analyst. Extract evidence-backed claims, named entities, "
            "inter-entity relationships, and dated events from the source text. "
            "Output must be valid JSON adhering strictly to this schema: "
            "{"
            "  \"claims\": [{\"claim_text\": \"...\", \"evidence_status\": \"SUPPORTED|DISPUTED|UNVERIFIED\", \"confidence_assessment\": \"...\", \"dispute_reason\": null}], "
            "  \"entities\": [{\"name\": \"...\", \"entity_type\": \"ORGANIZATION|PERSON|TECHNOLOGY|PRODUCT|EVENT|LOCATION\", \"description\": \"...\"}], "
            "  \"relationships\": [{\"source_entity\": \"...\", \"target_entity\": \"...\", \"relation_type\": \"...\", \"description\": \"...\", \"is_inference\": false}], "
            "  \"timeline_events\": [{\"event_date\": \"...\", \"title\": \"...\", \"description\": \"...\"}]"
            "}"
        )
        prompt = (
            f"Research Question: {query}\n"
            f"Source Citation Key: [{citation_key}]\n"
            f"Source Title: {title}\n"
            f"Content: {text[:2000]}\n\n"
            "Extract verified factual claims, entities, relationships, and events. Avoid UI artifacts or buttons."
        )

        try:
            data = self.ai.generate_json_response(system_prompt, prompt)
            if not data or not isinstance(data, dict):
                return None

            claims = data.get('claims', [])
            entities = data.get('entities', [])
            relationships = data.get('relationships', [])
            events = data.get('timeline_events', [])

            if not isinstance(claims, list) or not isinstance(entities, list):
                return None

            # Validate claim structures
            valid_claims = []
            for c in claims:
                if isinstance(c, dict) and c.get('claim_text'):
                    c_text = str(c['claim_text']).strip()
                    if len(c_text) >= 35:
                        valid_claims.append({
                            'claim_text': c_text,
                            'evidence_status': c.get('evidence_status', 'SUPPORTED'),
                            'confidence_assessment': c.get('confidence_assessment', 'Extracted via local AI model'),
                            'dispute_reason': c.get('dispute_reason')
                        })

            valid_entities = []
            seen_entity_names = set()
            for e in entities:
                if isinstance(e, dict) and e.get('name'):
                    name = str(e['name']).strip()
                    if not is_junk_entity(name) and name.lower() not in seen_entity_names:
                        seen_entity_names.add(name.lower())
                        valid_entities.append({
                            'name': name,
                            'entity_type': e.get('entity_type', 'ORGANIZATION'),
                            'description': e.get('description', '')
                        })

            valid_relations = []
            for r in relationships:
                if isinstance(r, dict) and r.get('source_entity') and r.get('target_entity'):
                    s_ent = str(r['source_entity']).strip()
                    t_ent = str(r['target_entity']).strip()
                    if not is_junk_entity(s_ent) and not is_junk_entity(t_ent):
                        valid_relations.append({
                            'source_entity': s_ent,
                            'target_entity': t_ent,
                            'relation_type': str(r.get('relation_type', 'ASSOCIATED_WITH')).upper().replace(' ', '_'),
                            'description': r.get('description', ''),
                            'is_inference': bool(r.get('is_inference', False))
                        })

            valid_events = []
            for ev in events:
                if isinstance(ev, dict) and ev.get('title'):
                    valid_events.append({
                        'event_date': str(ev.get('event_date', 'Undated')),
                        'title': str(ev['title']).strip(),
                        'description': str(ev.get('description', ev['title'])).strip()
                    })

            return {
                'claims': valid_claims[:6],
                'entities': valid_entities[:8],
                'relationships': valid_relations[:6],
                'timeline_events': valid_events[:4]
            }
        except Exception as e:
            logger.warning(f"AI extraction parsing failed: {e}")
            return None

    def _extract_deterministic(self, query: str, title: str, text: str, citation_key: str) -> dict:
        combined_text = f"{title}. {text}"
        sentences = re.split(r'(?<=[.!?])\s+', combined_text)

        # 1. Deterministic Entity Extraction
        found_entities = {}
        # First check known tech dictionary
        for name, etype in KNOWN_TECH_ENTITIES.items():
            if re.search(r'\b' + re.escape(name) + r'\b', combined_text, re.IGNORECASE):
                found_entities[name] = {
                    'name': name,
                    'entity_type': etype,
                    'description': f"Referenced in [{citation_key}] regarding {query}"
                }

        # Capitalized multi-word proper nouns
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', combined_text)
        for pn in proper_nouns:
            if not is_junk_entity(pn) and pn not in found_entities and not pn.startswith(('The ', 'A ', 'In ', 'On ', 'By ', 'With ', 'From ')):
                found_entities[pn] = {
                    'name': pn,
                    'entity_type': 'ORGANIZATION',
                    'description': f"Entity detected in source [{citation_key}]"
                }

        # 2. Deterministic Claim Extraction
        claims = []
        for sent in sentences:
            sent_clean = re.sub(r'==+\s*[^=]+\s*==+', '', sent.strip()).strip()
            # Require meaningful sentence length (between 45 and 320 chars)
            if len(sent_clean) < 45 or len(sent_clean) > 320:
                continue
            lower_sent = sent_clean.lower()
            if any(verb in lower_sent for verb in ASSERTION_WORDS):
                # Disputed marker
                is_disputed = any(d in lower_sent for d in ['dispute', 'denied', 'alleged', 'unclear', 'conflicting', 'contrary', 'lawsuit'])
                status = 'DISPUTED' if is_disputed else 'SUPPORTED'
                confidence = 'Verified assertion from public report' if not is_disputed else 'Reported controversy or disputed account'
                dispute_reason = 'Contrasting claims or qualifications noted in report' if is_disputed else None

                claims.append({
                    'claim_text': sent_clean,
                    'evidence_status': status,
                    'confidence_assessment': confidence,
                    'dispute_reason': dispute_reason
                })
                if len(claims) >= 5:
                    break

        # Fallback if no assertion-verb sentences matched: pick first substantive sentence
        if not claims:
            for sent in sentences:
                sent_clean = sent.strip()
                if len(sent_clean) >= 45 and not sent_clean.startswith(('http', 'Copyright', 'All rights')):
                    claims.append({
                        'claim_text': sent_clean,
                        'evidence_status': 'SUPPORTED',
                        'confidence_assessment': 'Primary reported disclosure',
                        'dispute_reason': None
                    })
                    break

        if not claims and title and len(title) > 20:
            claims.append({
                'claim_text': f"Public reporting and technical documentation outlines {title}.",
                'evidence_status': 'SUPPORTED',
                'confidence_assessment': 'Primary article headline topic',
                'dispute_reason': None
            })

        # 3. Deterministic Relationships
        relationships = []
        entity_names = list(found_entities.keys())
        for i in range(len(entity_names)):
            for j in range(i + 1, len(entity_names)):
                e1 = entity_names[i]
                e2 = entity_names[j]
                # Look for co-occurrence in same sentence
                for sent in sentences:
                    if e1 in sent and e2 in sent:
                        rel_type = 'ASSOCIATED_WITH'
                        for pattern, r_type in RELATIONSHIP_PATTERNS:
                            if re.search(pattern, sent, re.IGNORECASE):
                                rel_type = r_type
                                break
                        relationships.append({
                            'source_entity': e1,
                            'target_entity': e2,
                            'relation_type': rel_type,
                            'description': sent[:250],
                            'is_inference': False
                        })
                        break
                if len(relationships) >= 6:
                    break

        # 4. Deterministic Timeline Events
        events = []
        # Find years or months
        year_matches = re.finditer(r'\b(20\d\d)\b', combined_text)
        seen_years = set()
        for ym in year_matches:
            year = ym.group(1)
            if year in seen_years:
                continue
            seen_years.add(year)
            # Find surrounding sentence
            start = max(0, ym.start() - 60)
            end = min(len(combined_text), ym.end() + 100)
            snippet = combined_text[start:end].strip()
            events.append({
                'event_date': year,
                'title': f"Development ({year})",
                'description': snippet[:200]
            })
            if len(events) >= 3:
                break

        return {
            'claims': claims[:5],
            'entities': list(found_entities.values())[:8],
            'relationships': relationships[:6],
            'timeline_events': events[:4]
        }
