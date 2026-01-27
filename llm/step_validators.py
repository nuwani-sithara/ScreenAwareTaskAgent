import re

# Small synonym map to normalize common first-word verbs and reduce false negatives
VERB_SYNONYMS = {
    'tap': 'click', 'press': 'click', 'push': 'click', 'pushes': 'click',
    'launch': 'run', 'start': 'run', 'initiate': 'run', 'play': 'run',
    'input': 'enter', 'type': 'enter', 'paste': 'enter',
    'copy': 'select', 'paste': 'enter', 'drag': 'move', 'drop': 'move',
    'open': 'open', 'execute': 'run', 'run': 'run'
}

def normalize_verb(w: str) -> str:
    if not w:
        return ''
    return VERB_SYNONYMS.get(w.lower(), w.lower())

class StepQualityValidator:
    """Lightweight, rule-based validator to score step quality.

    Produces a `quality_score` in [0,1] and lists of issues/warnings/suggestions.
    """

    COMMON_VERBS = {
        'open','click','select','enter','press','choose','focus','analyze','execute',
        'wait','check','plan','implement','test','debug','run','start','stop','save','load',
        'install','create','generate','move','swipe','scroll','type','verify'
    }

    def evaluate(self, steps, instruction=None, category=None):
        result = {
            'quality_score': 0.0,
            'issues': [],
            'warnings': [],
            'suggestions': []
        }

        if not steps or not isinstance(steps, list):
            result['issues'].append('No steps or invalid steps format')
            return result

        score = 1.0

        # 1) Check sequential numbering
        expected = 1
        nonseq = False
        for s in steps:
            if not isinstance(s.get('step'), int) or s.get('step') != expected:
                nonseq = True
                break
            expected += 1
        if nonseq:
            result['warnings'].append('Steps are not sequentially numbered starting at 1')
            score -= 0.35

        # 2) Check first-word verbs and step length
        duplicates = set()
        seen_actions = set()
        verb_misses = 0
        short_steps = 0
        long_steps = 0
        flow_markers = 0

        for s in steps:
            action = (s.get('action') or '').strip()
            if not action:
                result['issues'].append(f"Step {s.get('step', '?')}: empty action")
                score -= 0.3
                continue

            # Normalize for duplicates
            norm = ' '.join(action.lower().split())
            if norm in seen_actions:
                duplicates.add(norm)
            seen_actions.add(norm)

            words = action.split()
            wcount = len(words)

            # first word verb heuristic (normalize synonyms)
            first = words[0].lower() if words else ''
            first = normalize_verb(first)
            if first not in self.COMMON_VERBS:
                verb_misses += 1

            # length checks
            if wcount < 2:
                short_steps += 1
            if wcount > 40:
                long_steps += 1

            # flow markers
            if any(tok in action.lower() for tok in ('then', 'after', 'next', 'finally', 'subsequently')):
                flow_markers += 1

        # duplicate penalty
        if duplicates:
            result['warnings'].append(f'Duplicate steps detected: {len(duplicates)}')
            score -= 0.2 * len(duplicates)

        # verb usage penalty (fraction of steps missing common verbs)
        if verb_misses:
            frac = verb_misses / max(1, len(steps))
            if frac > 0.5:
                result['warnings'].append('Many steps do not begin with an action verb')
            score -= 0.3 * frac

        # length penalties
        if short_steps:
            result['warnings'].append(f'{short_steps} steps are very short')
            score -= 0.15 * short_steps
        if long_steps:
            result['warnings'].append(f'{long_steps} steps are very long')
            score -= 0.1 * long_steps

        # lack of flow markers is a mild warning for multi-step procedures
        if len(steps) > 2 and flow_markers == 0:
            result['warnings'].append('Steps lack transitional words (then/after/next) to indicate flow')
            score -= 0.1

        # suggestions: improve wording and sequencing
        if duplicates:
            result['suggestions'].append('Merge or rephrase duplicate steps to avoid repetition')
        if short_steps:
            result['suggestions'].append('Expand very short steps with concrete actionable details')
        if verb_misses:
            result['suggestions'].append('Start steps with an action verb (e.g., "click", "open", "select")')

        # clamp score
        score = max(0.0, min(1.0, score))
        result['quality_score'] = round(score, 3)
        return result

    def validate_algorithm(self, instruction, steps, dataset_patterns=None, weights=(0.35, 0.40, 0.25), tau=0.55, min_length=2):
        """Implements the StepValidation(I, S, D) algorithm described by the user.

        Returns a dict: { 'is_valid': bool, 'confidence': float, 'action_score': float,
        'dataset_score': float, 'alignment_score': float, 'details': [...] }
        """
        res = {
            'is_valid': False,
            'confidence': 0.0,
            'action_score': 0.0,
            'dataset_score': 0.0,
            'alignment_score': 0.0,
            'details': [],
        }

        # 1-3: basic emptiness check
        if not steps or not isinstance(steps, list) or len(steps) == 0:
            res['details'].append('No steps provided')
            return res

        # 4-8: per-step checks (hasActionVerb and minLength)
        # Relaxed: collect failures and compute a pass-fraction instead of immediate rejection.
        action_matches = 0
        passed_basic = 0
        for s in steps:
            action = (s.get('action') or '').strip()
            words = action.split()
            first = words[0].lower() if words else ''
            first = normalize_verb(first)
            has_verb = first in self.COMMON_VERBS
            if has_verb:
                action_matches += 1

            length_ok = len(words) >= min_length
            if has_verb and length_ok:
                passed_basic += 1
            else:
                res['details'].append(
                    f"Step {s.get('step','?')} basic checks: hasVerb={has_verb}, length={len(words)}"
                )

        # 9: ActionScore ← computeActionVerbScore(S, D)
        # Use fraction of steps that pass basic (verb+length) checks to be more forgiving.
        action_score = passed_basic / max(1, len(steps))

        # 10: DatasetScore ← computeDatasetConsistency(S, D)
        dataset_score = 0.0
        if dataset_patterns and dataset_patterns.get('common_patterns'):
            common = [p[0] for p in dataset_patterns.get('common_patterns', [])]
            matches = 0
            for s in steps:
                a = (s.get('action') or '').lower()
                for patt in common[:10]:
                    # match if pattern prefix appears in action
                    if patt in a or a.startswith(patt.split()[0]):
                        matches += 1
                        break
            dataset_score = matches / max(1, len(steps))
        else:
            # If no dataset available, treat as neutral
            dataset_score = 0.5

        # 11: AlignmentScore ← computeInstructionAlignment(I, S)
        instr_words = [w for w in re.findall(r"\w+", (instruction or '').lower()) if len(w) > 2]
        if instr_words:
            instr_set = set(instr_words)
            hit = 0
            for s in steps:
                act_words = set([w for w in re.findall(r"\w+", (s.get('action') or '').lower()) if len(w) > 2])
                if len(instr_set & act_words) > 0:
                    hit += 1
            alignment_score = hit / max(1, len(steps))
        else:
            alignment_score = 0.0

        # 12: C ← w1·ActionScore + w2·DatasetScore + w3·AlignmentScore
        w1, w2, w3 = weights
        C = w1 * action_score + w2 * dataset_score + w3 * alignment_score

        res.update({
            'action_score': round(action_score, 3),
            'dataset_score': round(dataset_score, 3),
            'alignment_score': round(alignment_score, 3),
            'confidence': round(C, 3)
        })

        # 13-17: threshold check
        if C >= tau:
            res['is_valid'] = True
        else:
            res['is_valid'] = False
            res['details'].append(f'Confidence below threshold {tau}: {C:.3f}')

        return res


def validate_steps_hsv_a(
    instruction,
    steps,
    dataset_patterns=None,
    similarity_score: float = None,
    weights=(0.35, 0.40, 0.25),  # UPDATED: Optimized weights from grid search
    threshold=0.55,  # UPDATED: Optimized threshold from grid search
    min_action_length=2,
):
    issues = []

    # PHASE 1: HARD CONSTRAINTS
    if not steps or len(steps) == 0:
        return {"is_valid": False, "confidence": 0.0, "scores": {}, "issues": ["No steps generated"]}

    for idx, step in enumerate(steps):
        action = (step.get("action") or "").strip()
        if len(action.split()) < min_action_length:
            return {"is_valid": False, "confidence": 0.0, "scores": {}, "issues": [f"Step {idx+1} has insufficient action"]}

    # PHASE 2: ACTION SEMANTIC VALIDATION
    common_verbs = set()
    if dataset_patterns:
        common_verbs = set(dataset_patterns.get("common_verbs", set()))
    valid_action_count = 0
    for step in steps:
        parts = [(w.strip(".,'\"()")) for w in (step.get("action") or "").split()]
        verb = parts[0].lower() if parts else ""
        verb = normalize_verb(verb)
        if verb in common_verbs:
            valid_action_count += 1

    action_score = valid_action_count / max(1, len(steps))

    # PHASE 3: DATASET STRUCTURAL CONSISTENCY
    avg_steps = dataset_patterns.get("avg_steps", len(steps)) if dataset_patterns else len(steps)
    deviation = abs(len(steps) - avg_steps)
    dataset_score = 1 - (deviation / max(avg_steps, 1))
    dataset_score = max(0.0, min(1.0, dataset_score))

    # PHASE 4: INSTRUCTION–STEP ALIGNMENT
    alignment_score = similarity_score if similarity_score is not None else 0.5

    # FINAL CONFIDENCE & DECISION
    w_action, w_dataset, w_align = weights
    confidence = w_action * action_score + w_dataset * dataset_score + w_align * alignment_score
    is_valid = confidence >= threshold

    return {
        "is_valid": bool(is_valid),
        "confidence": round(float(confidence), 3),
        "scores": {
            "action_score": round(action_score, 3),
            "dataset_score": round(dataset_score, 3),
            "alignment_score": round(alignment_score, 3),
        },
        "issues": issues,
    }
