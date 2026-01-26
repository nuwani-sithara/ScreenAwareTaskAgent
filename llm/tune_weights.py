import os
import sys
import itertools

# Add current directory to path to import from demo.py
sys.path.insert(0, os.path.dirname(__file__))

try:
    from demo import SimpleAssistant, validate_steps_hsv_a
    print("✅ Successfully imported modules from demo.py")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure demo.py is in the same directory")
    sys.exit(1)


def main():
    print("=" * 60)
    print("🧪 GRID SEARCH FOR OPTIMAL VALIDATION PARAMETERS")
    print("=" * 60)
    
    # Initialize the assistant
    print("🔄 Initializing Simple Assistant...")
    assistant = SimpleAssistant()
    
    # Test cases for optimization
    test_cases = [
        "What is 2048?",  # Question - should have NO steps (invalid)
        "Play 2048 game: swipe left",  # Should generate steps (valid)
        "Think about software design",  # Non-actionable - should have steps (but maybe low quality)
        "Create a JS app to add 2 numbers",  # Should generate steps (valid)
        "Explain how to play 2048",  # Description - might have steps (valid for explanation)
        "Create a Python calculator to multiply numbers"  # Should generate steps (valid)
    ]
    
    # Expected validation results for each test case
    # 1 = should be valid, 0 = should be invalid
    expected_results = {
        "What is 2048?": 0,  # Questions shouldn't have actionable steps
        "Play 2048 game: swipe left": 1,  # Should have clear steps
        "Think about software design": 0,  # Too vague for actionable steps
        "Create a JS app to add 2 numbers": 1,  # Should have implementation steps
        "Explain how to play 2048": 1,  # Explanation can have steps
        "Create a Python calculator to multiply numbers": 1  # Should have steps
    }
    
    # Collect base outputs (run generation + dataset validator once)
    print("\n📊 Collecting test data...")
    records = []
    for instr in test_cases:
        print(f"  Processing: '{instr}'")
        res = assistant.process_instruction(instr)
        records.append({
            'instruction': instr,
            'steps': res['steps'],
            'category': res['category'],
            'validation': res['validation'],
            'expected_valid': expected_results.get(instr, 1)  # Default to expecting valid
        })
    print(f"✅ Collected {len(records)} test cases")
    
    # Grid search ranges - optimized based on previous results
    w1_vals = [0.30, 0.35, 0.40]      # Action score weight (around optimal 0.35)
    w2_vals = [0.35, 0.40, 0.45]      # Dataset score weight (around optimal 0.40)
    tau_vals = [0.50, 0.55, 0.60]     # Threshold (around optimal 0.55)
    
    print(f"\n🔍 Grid search ranges:")
    print(f"   Action weight (w1): {w1_vals}")
    print(f"   Dataset weight (w2): {w2_vals}")
    print(f"   Threshold (tau): {tau_vals}")
    print(f"   Total combinations: {len(w1_vals) * len(w2_vals) * len(tau_vals)}")
    
    best = None
    results = []
    valid_configs = []
    
    print("\n🔄 Running grid search...")
    
    for w1, w2, tau in itertools.product(w1_vals, w2_vals, tau_vals):
        # Calculate w3 (alignment weight) - ensure it's positive and not too small
        w3 = 1.0 - w1 - w2
        
        # Skip invalid weight combinations
        if w3 <= 0.1 or w3 >= 0.5:  # w3 should be between 0.1 and 0.5
            continue
        
        passed = 0
        total = len(records)
        confidences = []
        correct_predictions = 0
        false_positives = 0
        false_negatives = 0
        
        for r in records:
            instr = r['instruction']
            steps = r['steps']
            category = r['category']
            dataset_conf = r['validation']['confidence']
            expected_valid = r['expected_valid']
            
            # Get dataset patterns for the category
            if category == 'game_2048':
                dataset_key = 'game_2048'
            else:
                dataset_key = 'general'
            
            dataset_patterns = assistant.validator.patterns.get(dataset_key, {})
            
            # Algorithmic validator with current parameters
            algo = assistant.quality_validator.validate_algorithm(
                instr, 
                steps, 
                dataset_patterns, 
                weights=(w1, w2, w3), 
                tau=tau
            )
            
            # HSV-A validator with current parameters
            hsv = validate_steps_hsv_a(
                instruction=instr,
                steps=steps,
                dataset_patterns={
                    'common_verbs': set(dataset_patterns.get('common_verbs', set())),
                    'avg_steps': dataset_patterns.get('avg_steps_per_entry', len(steps))
                },
                similarity_score=r['validation'].get('similarity', 0.5),
                weights=(w1, w2, w3),
                threshold=tau,
                min_action_length=2
            )
            
            # Get confidence scores
            algo_conf = algo.get('confidence', 0.0)
            hsv_conf = hsv.get('confidence', 0.0)
            
            # Decision logic: dataset_conf >= 0.6 OR (algo_conf >= tau and hsv_conf >= tau)
            final_pass = (dataset_conf >= 0.6) or (algo_conf >= tau and hsv_conf >= tau)
            
            # Track accuracy
            if final_pass == (expected_valid == 1):
                correct_predictions += 1
                if final_pass:  # True positive
                    passed += 1
            else:
                if final_pass and expected_valid == 0:
                    false_positives += 1  # Marked valid but shouldn't be
                elif not final_pass and expected_valid == 1:
                    false_negatives += 1  # Marked invalid but should be valid
            
            # Track confidence
            confidences.append(max(dataset_conf, algo_conf, hsv_conf))
        
        # Calculate metrics
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        accuracy = correct_predictions / total if total > 0 else 0
        
        # Store results
        config_result = {
            'weights': (w1, w2, w3),
            'tau': tau,
            'passed': passed,
            'total': total,
            'accuracy': accuracy,
            'avg_confidence': avg_conf,
            'false_positives': false_positives,
            'false_negatives': false_negatives
        }
        
        results.append(config_result)
        valid_configs.append(((w1, w2, w3, tau), passed, accuracy, avg_conf))
        
        # Track best configuration
        if best is None:
            best = config_result
        else:
            # Prefer higher accuracy, then higher confidence, then fewer false positives
            if accuracy > best['accuracy']:
                best = config_result
            elif accuracy == best['accuracy'] and avg_conf > best['avg_confidence']:
                best = config_result
            elif accuracy == best['accuracy'] and avg_conf == best['avg_confidence'] and false_positives < best['false_positives']:
                best = config_result
    
    # Sort results by accuracy, then confidence
    results_sorted = sorted(results, key=lambda x: (x['accuracy'], x['avg_confidence']), reverse=True)
    valid_configs_sorted = sorted(valid_configs, key=lambda x: (x[2], x[3]), reverse=True)
    
    # Print top results
    print("\n" + "=" * 60)
    print("🏆 TOP 5 CONFIGURATIONS")
    print("=" * 60)
    
    for i, config in enumerate(results_sorted[:5]):
        w1, w2, w3 = config['weights']
        print(f"\n{i+1}. weights=({w1:.2f}, {w2:.2f}, {w3:.2f}), tau={config['tau']:.2f}")
        print(f"   Accuracy: {config['accuracy']:.1%} ({config['passed']}/{config['total']} passed)")
        print(f"   Avg Confidence: {config['avg_confidence']:.1%}")
        print(f"   False Positives: {config['false_positives']}, False Negatives: {config['false_negatives']}")
    
    # Print best configuration
    print("\n" + "=" * 60)
    print("🎯 BEST CONFIGURATION")
    print("=" * 60)
    
    if best:
        w1, w2, w3 = best['weights']
        print(f"\nweights=({w1:.2f}, {w2:.2f}, {w3:.2f}), tau={best['tau']:.2f}")
        print(f"Accuracy: {best['accuracy']:.1%} ({best['passed']}/{best['total']} passed)")
        print(f"Average Confidence: {best['avg_confidence']:.1%}")
        print(f"False Positives: {best['false_positives']}")
        print(f"False Negatives: {best['false_negatives']}")
        
        # Print Python code to use this configuration
        print("\n" + "=" * 60)
        print("💻 CODE TO USE BEST CONFIGURATION")
        print("=" * 60)
        print("\nAdd these defaults to step_validators.py:")
        print(f"def validate_algorithm(..., weights=({w1:.2f}, {w2:.2f}, {w3:.2f}), tau={best['tau']:.2f}, ...)")
        print(f"def validate_steps_hsv_a(..., weights=({w1:.2f}, {w2:.2f}, {w3:.2f}), threshold={best['tau']:.2f}, ...)")
    
    # Print detailed analysis for current default
    print("\n" + "=" * 60)
    print("📈 CURRENT DEFAULT PERFORMANCE")
    print("=" * 60)
    
    # Test with current defaults (from step_validators.py)
    default_correct = 0
    default_fp = 0
    default_fn = 0
    
    for r in records:
        instr = r['instruction']
        steps = r['steps']
        expected_valid = r['expected_valid']
        
        # Use current defaults (weights from validate_algorithm default parameters)
        algo = assistant.quality_validator.validate_algorithm(instr, steps, {})
        
        is_valid = algo.get('is_valid', False)
        
        if is_valid == (expected_valid == 1):
            default_correct += 1
        else:
            if is_valid and expected_valid == 0:
                default_fp += 1
            elif not is_valid and expected_valid == 1:
                default_fn += 1
    
    default_accuracy = default_correct / len(records) if records else 0
    print(f"\nCurrent default parameters:")
    print(f"  Accuracy: {default_accuracy:.1%} ({default_correct}/{len(records)})")
    print(f"  False Positives: {default_fp}")
    print(f"  False Negatives: {default_fn}")
    
    # Performance comparison
    if best and default_accuracy < best['accuracy']:
        improvement = ((best['accuracy'] - default_accuracy) / default_accuracy) * 100
        print(f"\n📈 Potential improvement: +{improvement:.1f}% accuracy")
    
    print("\n" + "=" * 60)
    print("✅ Grid search complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()