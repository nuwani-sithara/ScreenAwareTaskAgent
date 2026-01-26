import json

def main(path="llm_n/hybrid_results_pretty.jsonl", n=3):
    try:
        with open(path, "r", encoding="utf-8") as f:
            count = 0
            for line in f:
                if not line.strip():
                    continue
                j = json.loads(line)
                print("--- ENTRY", count+1)
                print("instruction:", j.get("instruction"))
                print("chosen:", j.get("chosen"))
                print("orig_quality:", j.get("original_validation", {}).get("quality", {}).get("quality_score"))
                print("rew_quality:", j.get("rewritten_validation", {}).get("quality", {}).get("quality_score"))
                print("orig_alg_conf:", j.get("original_validation", {}).get("algorithmic", {}).get("confidence"))
                print("rew_alg_conf:", j.get("rewritten_validation", {}).get("algorithmic", {}).get("confidence"))
                print("orig_steps_sample:", j.get("original_steps")[:3])
                print("rew_steps_sample:", j.get("rewritten_steps")[:3])
                print()
                count += 1
                if count >= n:
                    break
    except FileNotFoundError:
        print(path, "not found")

if __name__ == "__main__":
    main()
