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
# 4️⃣ Simple Validator (Minimal)
# ----------------------------
class SimpleValidator:
    def validate(self, steps):
        if not steps:
            return False, 0.0

        valid_steps = 0
        for step in steps:
            if len(step["action"].split()) >= 2:
                valid_steps += 1

        confidence = valid_steps / len(steps)
        return confidence >= 0.6, confidence


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
        self.validator = SimpleValidator()
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
        if self.retriever:
            try:
                examples = self.retriever.retrieve_related(goal, k=3)
                if examples:
                    print(f"\n🔎 Retrieved {len(examples)} dataset example(s) for RAG augmentation")
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

        # 4. Validate steps
        is_valid, confidence = self.validator.validate(steps)

        return {
            "steps": steps,
            "is_valid": is_valid,
            "confidence": confidence
        }


# ----------------------------
# 6️⃣ DEMO – LOGIN PAGE
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

    # 🔹 Initialize assistant
    # 👉 Change this path to your fine-tuned model directory
    MODEL_PATH = "./fine_tuned_js_model"

    try:
        # 🔹 Initialize assistant
        assistant = AgenticAssistant(MODEL_PATH)

        # 🔹 Run agentic loop
        result = assistant.process_ui_task(ui_state, goal)

        print("\n✅ FINAL RESULT")
        print(json.dumps(result, indent=2))
    except RuntimeError as e:
        print('\n💥 Runtime error while initializing the model:')
        print(str(e))
        print('\nSuggested fixes:')
        print('- If you are on Windows and see a DLL init error, install a CPU-only PyTorch wheel:')
        print('  pip install torch --index-url https://download.pytorch.org/whl/cpu')
        print('- Or install a matching CUDA-enabled build if you have a GPU and drivers configured.')
        print('- Make sure your Python, Visual C++ redistributable and GPU drivers are up to date.')
