# login.py – Agentic AI + LLM integration (Login Page Example)

import json
import re
import sys
import os

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    np = None
    TfidfVectorizer = None
    cosine_similarity = None

if sys.platform == "win32":
    try:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer)
    except Exception:
        pass

print("🚀 LOGIN DEMO - Agentic LLM Assistant (fallback-capable)")
print("==============================================")

# Try importing transformers and torch; handle failures gracefully so the
# demo script prints actionable guidance instead of crashing with a DLL error
try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
except Exception as e:
    AutoTokenizer = None
    AutoModelForSeq2SeqLM = None
    _transformers_import_error = e
else:
    _transformers_import_error = None

try:
    import torch
except Exception as e:
    torch = None
    _torch_import_error = e
else:
    _torch_import_error = None

# ----------------------------
# 1️⃣ Step Extractor
# ----------------------------
class StepExtractor:
    @staticmethod
    def extract_steps_from_output(output_text):
        steps = []

        # Primary: look for explicit 'Step N:' or 'Step N.' patterns
        matches = re.findall(
            r"Step\s*(\d+)\s*[:\.]\s*(.*?)(?=\s*Step\s*\d+[:\.]|$)",
            output_text,
            re.IGNORECASE | re.DOTALL
        )

        if matches:
            for num, action in matches:
                steps.append({
                    "step": int(num),
                    "action": action.strip()
                })
            return steps

        # Fallback: parse simple numbered lists like '1. Do this' or '1) Do this'
        numbered_matches = re.findall(r"^\s*(\d+)\s*[\.)]\s*(.+)$", output_text, re.MULTILINE)
        if numbered_matches:
            for num, action in numbered_matches:
                steps.append({
                    "step": int(num),
                    "action": action.strip()
                })
            return steps

        # Final fallback: split by lines and enumerate
        for i, line in enumerate(output_text.splitlines(), start=1):
            text = line.strip()
            if not text:
                continue
            steps.append({"step": i, "action": text})

        return steps


# ----------------------------
# 2️⃣ Agentic AI Layer
# ----------------------------
class AgenticAI:
    """
    Responsible for:
    - Taking UI perception JSON
    - Taking test goal
    - Building a structured prompt for the LLM
    """

    def build_prompt(self, ui_state, goal, examples=None):
        elements_desc = []

        for el in ui_state.get("elements", []):
            if el["type"] == "input":
                elements_desc.append(f"- Input field: {el.get('label')}")
            elif el["type"] == "button":
                elements_desc.append(f"- Button: {el.get('text')}")

        prompt_body = f"""
You are a human-like software testing agent.

Current UI state:
{chr(10).join(elements_desc)}

Test goal:
{goal}

Generate clear step-by-step UI actions.
"""
        # If examples (retrieved few-shot) are provided, include them above the prompt body
        if examples:
            ex_texts = [
                f"Instruction: {ex.get('instruction')}\nOutput:\n{ex.get('output')}\n---"
                for ex in examples
            ]
            prompt = "\n".join(ex_texts) + "\n" + prompt_body
        else:
            prompt = prompt_body

        return prompt.strip()


# ----------------------------
# 3️⃣ LLM Wrapper
# ----------------------------
class LLMEngine:
    def __init__(self, model_path):
        if AutoTokenizer is None or AutoModelForSeq2SeqLM is None:
            raise RuntimeError(
                "transformers package failed to import. Original error: %r" % _transformers_import_error
            )

        if torch is None:
            raise RuntimeError(
                "PyTorch failed to import (likely a DLL/driver issue). Original error: %r" % _torch_import_error
            )

        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True)
        self.model.to(torch.device("cpu"))

    def generate(self, prompt):
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(
            inputs["input_ids"],
            max_new_tokens=200,
            num_beams=4,
            do_sample=False
        )
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)


# Lightweight mock LLM for demos when transformers/torch are unavailable
class MockLLMEngine:
    def __init__(self, model_path=None):
        self.model_path = model_path

    def generate(self, prompt):
        # Return the canonical step list (numbered) used for the login demo
        return (
            "1. Enter username in the username field.\n"
            "2. Enter password in the password field.\n"
            "3. Click the login button.\n"
            "4. Validate fields are filled.\n"
            "5. Show error message if credentials are invalid.\n"
            "6. Redirect to dashboard on success."
        )


# ----------------------------
# Dataset Retriever (TF-IDF + cosine similarity)
# ----------------------------
class DatasetRetriever:
    def __init__(self, general_path=None, game_path=None):
        if TfidfVectorizer is None or cosine_similarity is None or np is None:
            raise RuntimeError("Required packages for DatasetRetriever (numpy/sklearn) are not available")

        base = os.path.dirname(os.path.abspath(__file__))
        self.general_path = general_path or os.path.join(base, "llm_dataset.jsonl")
        self.game_path = game_path or os.path.join(base, "rag_2048.jsonl")

        # Load entries from both datasets
        self.entries = []
        for path in (self.general_path, self.game_path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            if "instruction" in item and "output" in item:
                                self.entries.append({
                                    "instruction": item["instruction"],
                                    "output": item["output"]
                                })
                        except Exception:
                            continue
            except FileNotFoundError:
                # Missing dataset file is not fatal; continue
                continue

        self.instructions = [e["instruction"] for e in self.entries]

        if self.instructions:
            self.vectorizer = TfidfVectorizer(stop_words="english")
            try:
                self.matrix = self.vectorizer.fit_transform(self.instructions)
            except Exception:
                self.matrix = None
        else:
            self.vectorizer = None
            self.matrix = None

    def retrieve_related(self, instruction, k=3, min_score=0.2):
        """Return top-k dataset entries similar to the given instruction."""
        if not self.matrix or self.vectorizer is None:
            return []

        q_vec = self.vectorizer.transform([instruction])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        idxs = sims.argsort()[::-1]
        results = []
        for i in idxs[:k]:
            score = float(sims[i])
            if score < min_score:
                continue
            e = self.entries[i].copy()
            e["score"] = score
            results.append(e)

        return results


# ----------------------------
# 4️⃣ Dataset-Driven Validator (Comprehensive)
# ----------------------------
class DatasetDrivenValidator:
    """Validates steps by comparing against patterns in actual datasets"""
    
    def __init__(self, general_dataset_path=None, game_2048_dataset_path=None):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.general_dataset_path = general_dataset_path or os.path.join(current_dir, "llm_dataset.jsonl")
        self.game_2048_dataset_path = game_2048_dataset_path or os.path.join(current_dir, "rag_2048.jsonl")
        
        # Load and analyze datasets
        self.general_dataset = self._load_and_analyze_dataset(self.general_dataset_path)
        self.game_2048_dataset = self._load_and_analyze_dataset(self.game_2048_dataset_path)
        
        # Extract patterns from datasets
        self.patterns = self._extract_patterns_from_datasets()
        
        print(f"✅ Validator loaded patterns from datasets:")
        print(f"   - General: {len(self.general_dataset.get('entries', []))} entries")
        print(f"   - 2048: {len(self.game_2048_dataset.get('entries', []))} entries")
    
    def _load_and_analyze_dataset(self, path):
        """Load dataset and extract patterns"""
        entries = []
        step_patterns = []
        avg_step_length = []
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        entry = json.loads(line)
                        if "instruction" in entry and "output" in entry:
                            entries.append(entry)
                            
                            # Extract steps from output
                            steps = StepExtractor.extract_steps_from_output(entry['output'])
                            
                            # Analyze step patterns
                            for step in steps:
                                action = step.get('action', '').strip()
                                if action:
                                    # Store step length
                                    avg_step_length.append(len(action.split()))
                                    
                                    # Extract patterns (first 3 words as pattern)
                                    words = action.lower().split()[:3]
                                    if len(words) >= 2:
                                        pattern = ' '.join(words)
                                        step_patterns.append(pattern)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            print(f"⚠️ Dataset file not found: {path}")
        
        return {
            'entries': entries,
            'step_patterns': step_patterns,
            'avg_step_length': np.mean(avg_step_length) if avg_step_length else 0,
            'step_length_std': np.std(avg_step_length) if avg_step_length else 0
        }
    
    def _extract_patterns_from_datasets(self):
        """Extract common patterns from both datasets"""
        patterns = {
            'general': {
                'common_patterns': [],
                'structure_patterns': [],
                'avg_steps_per_entry': 0,
                'common_verbs': set(),
                'total_entries': 0,
                'total_steps': 0,
                'word_frequencies': {}
            },
            'game_2048': {
                'common_patterns': [],
                'structure_patterns': [],
                'avg_steps_per_entry': 0,
                'common_verbs': set(),
                'total_entries': 0,
                'total_steps': 0,
                'word_frequencies': {}
            }
        }
        
        # Analyze general dataset
        if self.general_dataset.get('entries'):
            general_patterns = self._analyze_dataset_patterns(self.general_dataset['entries'], "general")
            patterns['general'] = general_patterns
        
        # Analyze 2048 dataset
        if self.game_2048_dataset.get('entries'):
            game_patterns = self._analyze_dataset_patterns(self.game_2048_dataset['entries'], "game_2048")
            patterns['game_2048'] = game_patterns
        
        return patterns
    
    def _analyze_dataset_patterns(self, entries, category):
        """Analyze patterns in a specific dataset"""
        all_steps = []
        all_step_counts = []
        word_frequencies = {}
        verb_patterns = {}
        
        for entry in entries:
            steps = StepExtractor.extract_steps_from_output(entry['output'])
            all_step_counts.append(len(steps))
            
            for step in steps:
                action = step.get('action', '').strip()
                if action:
                    all_steps.append(action)
                    
                    # Analyze first word (potential verb)
                    first_word = action.lower().split()[0] if action.split() else ""
                    if first_word:
                        verb_patterns[first_word] = verb_patterns.get(first_word, 0) + 1
                    
                    # Count word frequencies
                    for word in action.lower().split():
                        if len(word) > 2:  # Skip short words
                            word_frequencies[word] = word_frequencies.get(word, 0) + 1
        
        # Get most common patterns
        common_patterns = []
        if all_steps:
            # Find common starting patterns (first 3-4 words)
            pattern_counts = {}
            for step in all_steps:
                words = step.lower().split()[:4]
                if len(words) >= 2:
                    pattern = ' '.join(words)
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            
            # Get top patterns
            common_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Get most common verbs
        common_verbs = set()
        top_verbs = sorted(verb_patterns.items(), key=lambda x: x[1], reverse=True)[:15]
        for verb, count in top_verbs:
            if count >= 2:  # Appears at least twice
                common_verbs.add(verb)
        
        return {
            'common_patterns': common_patterns,
            'avg_steps_per_entry': np.mean(all_step_counts) if all_step_counts else 0,
            'common_verbs': common_verbs,
            'total_entries': len(entries),
            'total_steps': len(all_steps),
            'word_frequencies': dict(sorted(word_frequencies.items(), key=lambda x: x[1], reverse=True)[:50])
        }
    
    def validate_steps(self, instruction, generated_steps, category, similarity_score=None):
        """
        Validate steps against dataset patterns
        Returns: {
            'is_valid': bool,
            'confidence': float (0-1),
            'has_steps': bool,
            'dataset_match_score': float,
            'structure_score': float,
            'content_score': float,
            'issues': list,
            'warnings': list,
            'suggestions': list,
            'dataset_stats': dict,
            'matched_patterns': list,
            'format_valid': bool
        }
        """
        # Check if instruction was found in dataset (exact or near-exact match)
        if similarity_score is not None and similarity_score >= 0.95:
            # Steps from dataset are valid with high confidence
            return {
                'is_valid': True,
                'confidence': min(1.0, similarity_score),
                'has_steps': self._check_has_steps(generated_steps),
                'dataset_match_score': similarity_score,
                'structure_score': 1.0,
                'content_score': 1.0,
                'issues': [],
                'warnings': [],
                'suggestions': [],
                'dataset_stats': {},
                'matched_patterns': [],
                'format_valid': True
            }
        
        validation_result = {
            'is_valid': True,
            'confidence': 0.5,
            'has_steps': self._check_has_steps(generated_steps),
            'dataset_match_score': similarity_score if similarity_score else 0.0,
            'structure_score': 0.5,  # Start with reasonable base score
            'content_score': 0.5,    # Start with reasonable base score
            'issues': [],
            'warnings': [],
            'suggestions': [],
            'dataset_stats': {},
            'matched_patterns': [],
            'format_valid': True
        }
        
        # Check if steps exist
        if not validation_result['has_steps']:
            validation_result['is_valid'] = False
            validation_result['confidence'] = 0.0
            validation_result['issues'].append("No valid steps generated")
            return validation_result
        
        # Basic format validation
        format_issues = self._validate_step_format(generated_steps)
        if format_issues:
            validation_result['issues'].extend(format_issues)
            validation_result['format_valid'] = False
            validation_result['is_valid'] = False
            # Format errors are critical
            validation_result['structure_score'] = 0.2
        else:
            # Good format increases structure score
            validation_result['structure_score'] = 0.8
        
        # Get appropriate dataset patterns
        dataset_key = "game_2048" if category == "game_2048" else "general"
        dataset_patterns = self.patterns.get(dataset_key, {})
        
        # Store dataset statistics for reference
        validation_result['dataset_stats'] = {
            'avg_steps': dataset_patterns.get('avg_steps_per_entry', 0),
            'common_verbs': list(dataset_patterns.get('common_verbs', set()))[:10],
            'total_entries': dataset_patterns.get('total_entries', 0),
            'total_steps': dataset_patterns.get('total_steps', 0)
        }
        
        # Only validate against dataset patterns if we have data
        if dataset_patterns.get('total_entries', 0) > 0:
            validation_result = self._validate_against_dataset(
                generated_steps, 
                dataset_patterns, 
                category, 
                validation_result
            )
        
        # Calculate overall confidence
        # For UI tasks, prioritize format and content over pattern matching
        validation_result['confidence'] = (
            validation_result['format_valid'] * 0.4 +  # Format is most important
            validation_result['content_score'] * 0.3 +   # Content quality
            validation_result['structure_score'] * 0.3
        )
        
        # If no format issues and has steps, should be valid with reasonable confidence
        if validation_result['format_valid'] and validation_result['has_steps']:
            validation_result['confidence'] = max(0.65, validation_result['confidence'])
        
        # Determine if valid: format must be valid + reasonable confidence
        if not validation_result['format_valid'] or validation_result['confidence'] < 0.5:
            validation_result['is_valid'] = False
        
        # Generate suggestions based on dataset patterns (optional, non-critical)
        if dataset_patterns.get('total_entries', 0) > 0:
            self._generate_dataset_suggestions(generated_steps, dataset_patterns, category, validation_result)
        
        return validation_result
    
    def _validate_against_dataset(self, steps, dataset_patterns, category, validation_result):
        """Validate steps against dataset patterns"""
        if not steps or not dataset_patterns:
            return validation_result
        
        # 1. Check step count against dataset average (informational only, not critical)
        avg_dataset_steps = dataset_patterns.get('avg_steps_per_entry', 0)
        if avg_dataset_steps > 0:
            step_count_diff = abs(len(steps) - avg_dataset_steps) / avg_dataset_steps
            step_count_score = max(0.5, 1 - step_count_diff)  # Minimum 0.5 baseline
            validation_result['structure_score'] = max(validation_result['structure_score'], step_count_score)
            
            # Only warn on extreme differences
            if len(steps) < avg_dataset_steps * 0.3:
                validation_result['warnings'].append(
                    f"Unusually few steps ({len(steps)} vs average {avg_dataset_steps:.1f})"
                )
            elif len(steps) > avg_dataset_steps * 2.0:
                validation_result['warnings'].append(
                    f"Unusually many steps ({len(steps)} vs average {avg_dataset_steps:.1f})"
                )
        
        # 2. Check for common patterns from dataset (optional, just for suggestions)
        common_patterns = dataset_patterns.get('common_patterns', [])
        if common_patterns:
            pattern_matches = self._find_pattern_matches(steps, common_patterns)
            validation_result['matched_patterns'] = pattern_matches
            
            if pattern_matches:
                pattern_score = len(pattern_matches) / min(len(steps), 5)
                validation_result['dataset_match_score'] = max(0.3, pattern_score)
        
        # 3. Check verb usage (informational, increases content score if verbs are common)
        common_verbs = dataset_patterns.get('common_verbs', set())
        if common_verbs:
            verb_matches = self._check_verb_usage(steps, common_verbs)
            if verb_matches > 0:
                verb_score = min(1.0, 0.5 + (verb_matches / len(steps) * 0.5))
                validation_result['content_score'] = max(validation_result['content_score'], verb_score)
        
        # 4. Check step structure for major issues only
        structure_issues = self._check_step_structure(steps, category)
        if structure_issues:
            # Only add critical structure issues as warnings
            critical_issues = [s for s in structure_issues if "Empty action" in s or "Insufficient content" in s]
            if critical_issues:
                validation_result['issues'].extend(critical_issues)
                validation_result['structure_score'] = 0.3  # Significant penalty for critical issues
            else:
                # Non-critical issues become warnings only
                validation_result['warnings'].extend(structure_issues[:2])
        
        # Ensure scores are within [0, 1]
        validation_result['dataset_match_score'] = min(1.0, validation_result['dataset_match_score'])
        validation_result['structure_score'] = min(1.0, max(0.5, validation_result['structure_score']))
        validation_result['content_score'] = min(1.0, max(0.5, validation_result['content_score']))
        
        return validation_result
    
    def _find_pattern_matches(self, steps, dataset_patterns):
        """Find if steps match common patterns from dataset"""
        matches = []
        
        for pattern, pattern_count in dataset_patterns[:10]:  # Check top 10 patterns
            pattern_words = pattern.split()
            
            for step in steps:
                action = step.get('action', '').lower()
                step_words = action.split()[:len(pattern_words)]
                
                if len(step_words) >= len(pattern_words):
                    step_pattern = ' '.join(step_words)
                    
                    # Check for partial match
                    if pattern in step_pattern or step_pattern in pattern:
                        matches.append({
                            'step': step.get('step'),
                            'pattern': pattern,
                            'frequency': pattern_count
                        })
                        break  # Found match for this pattern
        
        return matches
    
    def _check_verb_usage(self, steps, common_verbs):
        """Check if steps use verbs common in the dataset"""
        matches = 0
        
        for step in steps:
            action = step.get('action', '').lower()
            first_word = action.split()[0] if action.split() else ""
            
            if first_word in common_verbs:
                matches += 1
        
        return matches
    
    def _check_step_structure(self, steps, category):
        """Check step structure against dataset norms"""
        issues = []
        
        # Get appropriate dataset for step length norms
        dataset = self.general_dataset if category != "game_2048" else self.game_2048_dataset
        avg_length = dataset.get('avg_step_length', 8)
        std_length = dataset.get('step_length_std', 3)
        
        for i, step in enumerate(steps):
            action = step.get('action', '').strip()
            if not action:
                issues.append(f"Step {i+1}: Empty action")
                continue
            
            word_count = len(action.split())
            
            # Check if step is unusually short or long (based on dataset norms)
            if word_count < avg_length - 2 * std_length:
                issues.append(f"Step {i+1}: Very short ({word_count} words vs avg {avg_length:.1f})")
            elif word_count > avg_length + 2 * std_length:
                issues.append(f"Step {i+1}: Very long ({word_count} words vs avg {avg_length:.1f})")
            
            # Check for minimum content (must have at least 2 words)
            if word_count < 2:
                issues.append(f"Step {i+1}: Insufficient content - needs at least 2 words")
        
        return issues
    
    def _validate_step_format(self, steps):
        """Check if steps follow expected format"""
        issues = []
        
        if not isinstance(steps, list):
            issues.append("Steps must be a list")
            return issues
        
        if len(steps) == 0:
            issues.append("No steps generated")
            return issues
        
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                issues.append(f"Step {i+1}: Not a dictionary")
                continue
            
            if 'step' not in step or 'action' not in step:
                issues.append(f"Step {i+1}: Missing 'step' or 'action' field")
            
            if isinstance(step.get('step'), int) and step['step'] != i + 1:
                issues.append(f"Step {i+1}: Step number mismatch (expected {i+1}, got {step['step']})")
            
            action = step.get('action', '').strip()
            if not action:
                issues.append(f"Step {i+1}: Empty action")
            else:
                # Check action has meaningful content (at least 1 word)
                word_count = len(action.split())
                if word_count < 1:
                    issues.append(f"Step {i+1}: Action contains no words")
        
        return issues
    
    def _generate_dataset_suggestions(self, steps, dataset_patterns, category, validation_result):
        """Generate suggestions based on dataset analysis"""
        suggestions = []
        
        if not steps:
            return
        
        # 1. Suggest based on step count
        avg_steps = dataset_patterns.get('avg_steps_per_entry', 0)
        if avg_steps > 0:
            if len(steps) < avg_steps * 0.7:
                suggestions.append(f"Consider adding more steps (dataset average: {avg_steps:.1f} steps)")
            elif len(steps) > avg_steps * 1.3:
                suggestions.append(f"Consider consolidating steps (dataset average: {avg_steps:.1f} steps)")
        
        # 2. Suggest based on common verbs
        common_verbs = list(dataset_patterns.get('common_verbs', set()))[:5]
        if common_verbs:
            # Check which common verbs are not used
            used_verbs = set()
            for step in steps:
                first_word = step.get('action', '').lower().split()[0] if step.get('action') else ""
                used_verbs.add(first_word)
            
            missing_verbs = [v for v in common_verbs if v not in used_verbs]
            if missing_verbs and len(missing_verbs) > 0:
                suggestions.append(f"Consider using common {category} verbs like: {', '.join(missing_verbs[:3])}")
        
        # 3. Suggest based on patterns
        matched_patterns = validation_result.get('matched_patterns', [])
        if not matched_patterns and dataset_patterns.get('common_patterns'):
            top_patterns = dataset_patterns['common_patterns'][:3]
            if top_patterns:
                pattern_examples = [f"'{p[0]}'" for p in top_patterns]
                suggestions.append(f"Try patterns from dataset: {', '.join(pattern_examples)}")
        
        validation_result['suggestions'].extend(suggestions[:3])  # Limit to top 3
    
    def _check_has_steps(self, steps):
        """Check if meaningful steps exist"""
        if not steps or not isinstance(steps, list):
            return False
        
        if len(steps) == 0:
            return False
        
        # Check if at least one step has meaningful content
        for step in steps:
            if isinstance(step, dict):
                action = step.get('action', '').strip()
                if action and len(action.split()) >= 1:
                    return True
        
        return False


# ----------------------------
# 5️⃣ Main Assistant (Agentic Loop)
# ----------------------------
class AgenticAssistant:
    def __init__(self, model_path):
        self.agent = AgenticAI()
        # Try to initialize the real LLMEngine; fall back to a lightweight mock
        try:
            self.llm = LLMEngine(model_path)
        except Exception as e:
            print("\n⚠️ LLMEngine initialization failed, using MockLLMEngine for demo:")
            print(str(e))
            self.llm = MockLLMEngine(model_path)
        self.extractor = StepExtractor()
        # Try to initialize dataset-driven validator
        try:
            self.validator = DatasetDrivenValidator()
        except Exception as e:
            print(f"\n⚠️ DatasetDrivenValidator initialization failed: {e}")
            self.validator = None
        # Try to initialize dataset retriever (optional)
        try:
            self.retriever = DatasetRetriever()
        except Exception:
            self.retriever = None

    def synthesize_steps_from_examples(self, examples, ui_state, goal):
        """Create a ranked synthesized step list from retrieved examples.

        Strategy:
        - Extract steps from each example output
        - Normalize and count identical actions across examples
        - Order by first appearance, with frequency as tie-breaker
        """
        if not examples:
            return []

        counts = {}
        first_seen = {}

        for ex_idx, ex in enumerate(examples):
            out = ex.get('output', '')
            ex_steps = StepExtractor.extract_steps_from_output(out)
            for s_idx, s in enumerate(ex_steps):
                action = s.get('action', '').strip()
                if not action:
                    continue
                norm = re.sub(r"\s+", " ", action).strip().lower()
                counts[norm] = counts.get(norm, 0) + 1
                if norm not in first_seen:
                    first_seen[norm] = (ex_idx, s_idx)

        # Sort actions by first_seen, then by descending frequency
        norms = list(counts.keys())
        norms.sort(key=lambda n: (first_seen.get(n, (999, 999)), -counts[n]))

        synthesized = []
        for i, norm in enumerate(norms, start=1):
            # Re-capitalize first letter for readability
            action_text = norm[0].upper() + norm[1:] if norm else norm
            synthesized.append({"step": i, "action": action_text})

        return synthesized

    def process_ui_task(self, ui_state, goal):
        # 1. Agentic AI builds prompt
        examples = None
        similarity_score = 0.0
        if self.retriever:
            try:
                examples = self.retriever.retrieve_related(goal, k=3)
                if examples:
                    print(f"\n🔎 Retrieved {len(examples)} dataset example(s) for RAG augmentation")
                    # Get the similarity score from the top match
                    similarity_score = examples[0].get('score', 0.0) if examples else 0.0
            except Exception:
                examples = None

        prompt = self.agent.build_prompt(ui_state, goal, examples=examples)

        print("\n🧠 AGENTIC AI PROMPT:")
        print(prompt)

        # If we have dataset examples and no real LLM, synthesize steps from examples
        steps = None
        if examples and isinstance(self.llm, MockLLMEngine):
            print("\n🔧 Synthesizing steps from retrieved dataset examples (no real LLM available)")
            steps = self.synthesize_steps_from_examples(examples, ui_state, goal)

        # Otherwise call the LLM
        if steps is None:
            # 2. Send prompt to LLM
            llm_output = self.llm.generate(prompt)

            print("\n🤖 LLM OUTPUT:")
            print(llm_output)

            # 3. Extract steps
            steps = self.extractor.extract_steps_from_output(llm_output)

        # 4. Validate steps using DatasetDrivenValidator
        if self.validator:
            category = "general"  # Default category (can be "game_2048" for game tasks)
            validation_result = self.validator.validate_steps(goal, steps, category, similarity_score=similarity_score)
            
            print("\n✅ VALIDATION RESULT:")
            print(f"   Is Valid: {validation_result['is_valid']}")
            print(f"   Confidence: {validation_result['confidence']:.2f}")
            if validation_result['issues']:
                print(f"   Issues: {', '.join(validation_result['issues'][:3])}")
            if validation_result['warnings']:
                print(f"   Warnings: {', '.join(validation_result['warnings'][:3])}")
            if validation_result['suggestions']:
                print(f"   Suggestions: {', '.join(validation_result['suggestions'][:2])}")
            
            return {
                "steps": steps,
                "is_valid": validation_result['is_valid'],
                "confidence": validation_result['confidence'],
                "validation": validation_result
            }
        else:
            # Fallback to simple validation if DatasetDrivenValidator is not available
            is_valid = len(steps) > 0 and all(len(s.get("action", "").split()) >= 2 for s in steps)
            confidence = sum(len(s.get("action", "").split()) >= 2 for s in steps) / len(steps) if steps else 0.0
            
            return {
                "steps": steps,
                "is_valid": is_valid,
                "confidence": confidence
            }


# ----------------------------
# 7️⃣ Validation Report Generator
# ----------------------------
def _get_recommendation(validation):
    """Get recommendation based on validation results"""
    if not validation.get('has_steps'):
        return "✗ No steps generated. Instruction may be invalid."
    
    if validation.get('is_valid') and validation.get('confidence', 0) > 0.8:
        return "✓ Steps are valid and ready for execution"
    elif validation.get('is_valid') and validation.get('confidence', 0) > 0.65:
        return "⚠️ Steps are valid but confidence is moderate. Review before execution."
    elif validation.get('issues'):
        return "✗ Steps have critical issues. Review and regenerate if needed."
    else:
        return "⚠️ Steps have warnings. Consider reviewing for improvements."

def generate_validation_report(ui_state, goal):
    """Generate a detailed validation report for UI task"""
    assistant = AgenticAssistant("./fine_tuned_js_model")
    result = assistant.process_ui_task(ui_state, goal)
    validation = result.get('validation', {})
    
    report = {
        'goal': goal,
        'steps': result['steps'],
        'validation_details': {
            'is_valid': validation.get('is_valid', result.get('is_valid', False)),
            'confidence': validation.get('confidence', result.get('confidence', 0.0)),
            'has_steps': validation.get('has_steps', len(result['steps']) > 0),
            'issues': validation.get('issues', []),
            'warnings': validation.get('warnings', []),
            'format_valid': validation.get('format_valid', True)
        }
    }
    
    return report

def print_validation_report(report):
    """Print a formatted validation report"""
    print("\n" + "="*70)
    print("STEP VALIDATION REPORT")
    print("="*70)
    
    print(f"\n📋 GOAL")
    print(f"  Input: {report['goal']}")
    
    print(f"\n🔄 GENERATED STEPS ({len(report['steps'])} total)")
    for step in report['steps']:
        print(f"  {step['step']}. {step['action']}")
    
    val = report['validation_details']
    
    print(f"\n📊 VALIDATION METRICS")
    print(f"  Status: {'✓ VALID' if val['is_valid'] else '✗ INVALID'}")
    print(f"  Confidence: {val['confidence']:.1%}")
    print(f"  Format Valid: {'✓ Yes' if val['format_valid'] else '✗ No'}")
    
    if val['issues']:
        print(f"\n❌ ISSUES FOUND ({len(val['issues'])})")
        for issue in val['issues'][:5]:
            print(f"  • {issue}")
    
    if val['warnings']:
        print(f"\n⚠️  WARNINGS ({len(val['warnings'])})")
        for warning in val['warnings'][:5]:
            print(f"  • {warning}")
    
    print("\n" + "="*70)


# ----------------------------
# 8️⃣ Main Demo
# ----------------------------
if __name__ == "__main__":

    # 🔹 Simulated Visual Perception Output
    ui_state = {
        "screen": "login_page",
        "elements": [
            {"type": "input", "label": "Username"},
            {"type": "input", "label": "Password"},
            {"type": "button", "text": "Login"}
        ]
    }

    # 🔹 Test Goal
    goal = "Login using valid username and password"

    try:
        # 🔹 Generate and print validation report
        report = generate_validation_report(ui_state, goal)
        print_validation_report(report)
        
        # 🔹 Also output raw JSON for programmatic use
        print("\n✅ RAW OUTPUT (JSON)")
        print(json.dumps(report, indent=2, default=str))
        
    except RuntimeError as e:
        print('\n💥 Runtime error while initializing the model:')
        print(str(e))
        print('\nSuggested fixes:')
        print('- If you are on Windows and see a DLL init error, install a CPU-only PyTorch wheel:')
        print('  pip install torch --index-url https://download.pytorch.org/whl/cpu')
        print('- Or install a matching CUDA-enabled build if you have a GPU and drivers configured.')
        print('- Make sure your Python, Visual C++ redistributable and GPU drivers are up to date.')

