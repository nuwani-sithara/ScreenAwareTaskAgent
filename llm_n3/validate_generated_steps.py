"""
Step Validation Module for UI Automation
Validates generated steps for quality and correctness
"""
import re

class StepValidator:
    """Validates generated UI automation steps"""
    
    # Common action verbs that should start steps
    VALID_ACTION_VERBS = {
        'open', 'click', 'select', 'enter', 'type', 'press', 'choose',
        'navigate', 'go', 'visit', 'scroll', 'swipe', 'drag', 'drop',
        'wait', 'verify', 'check', 'confirm', 'close', 'tap', 'touch',
        'hover', 'focus', 'submit', 'upload', 'download', 'copy', 'paste',
        'delete', 'remove', 'add', 'create', 'edit', 'update', 'save',
        'load', 'refresh', 'search', 'filter', 'sort', 'expand', 'collapse',
        'maximize', 'minimize', 'resize', 'move', 'switch', 'toggle',
        'enable', 'disable', 'accept', 'reject', 'cancel', 'skip',
        'right', 'left', 'double'  # for "right click", "left click", etc.
    }
    
    def validate(self, steps_text, instruction=None):
        """
        Validate generated steps
        
        Args:
            steps_text: Generated steps as string
            instruction: Original instruction (optional)
            
        Returns:
            dict with validation results
        """
        result = {
            'is_valid': False,
            'score': 0.0,
            'issues': [],
            'warnings': [],
            'suggestions': [],
            'step_count': 0,
            'details': {}
        }
        
        # Parse steps
        steps = self._parse_steps(steps_text)
        result['step_count'] = len(steps)
        
        if not steps:
            result['issues'].append("No steps found in output")
            return result
        
        # Check if just echoing the instruction
        if instruction and len(steps) == 1:
            if instruction.lower() in steps[0]['text'].lower():
                result['issues'].append("Output is just echoing the instruction, not breaking it down")
                result['warnings'].append("Model needs better prompting or fine-tuning")
                return result
        
        # Validate each check
        score = 100.0
        
        # 1. Check numbering
        numbering_valid, numbering_issues = self._check_numbering(steps)
        if not numbering_valid:
            result['issues'].extend(numbering_issues)
            score -= 20
        
        # 2. Check action verbs
        verb_valid, verb_issues, verb_warnings = self._check_action_verbs(steps)
        if not verb_valid:
            result['warnings'].extend(verb_warnings)
            score -= 15
        
        # 3. Check step length
        length_valid, length_warnings = self._check_step_length(steps)
        if not length_valid:
            result['warnings'].extend(length_warnings)
            score -= 10
        
        # 4. Check for duplicates
        dup_valid, dup_warnings = self._check_duplicates(steps)
        if not dup_valid:
            result['warnings'].extend(dup_warnings)
            score -= 15
        
        # 5. Check minimum steps
        if len(steps) < 2:
            result['warnings'].append("Only 1 step generated - task might need more breakdown")
            score -= 10
        
        # 6. Check for too many steps (likely repetition)
        if len(steps) > 15:
            result['warnings'].append(f"High step count ({len(steps)}) - check for repetition")
            score -= 10
        
        # Calculate final score and validity
        result['score'] = max(0, score) / 100.0
        result['is_valid'] = result['score'] >= 0.6 and not result['issues']
        
        # Add suggestions
        if result['score'] < 0.8:
            result['suggestions'].append("Consider adjusting model parameters (temperature, beam size)")
        if len(steps) < 3 and instruction and len(instruction) > 50:
            result['suggestions'].append("Complex task might need more detailed breakdown")
        
        result['details'] = {
            'numbering_valid': numbering_valid,
            'action_verbs_valid': verb_valid,
            'length_valid': length_valid,
            'duplicate_free': dup_valid
        }
        
        return result
    
    def _parse_steps(self, text):
        """Parse steps from text"""
        steps = []
        
        # Remove "Steps:" prefix if present
        text = re.sub(r'^Steps:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Find numbered steps
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Match patterns like "1.", "1)", "Step 1:", etc.
            match = re.match(r'^(\d+)[\.)]\s*(.+)$', line)
            if match:
                num = int(match.group(1))
                text = match.group(2).strip()
                steps.append({'number': num, 'text': text})
            elif re.match(r'^Step\s+(\d+):\s*(.+)$', line, re.IGNORECASE):
                match = re.match(r'^Step\s+(\d+):\s*(.+)$', line, re.IGNORECASE)
                num = int(match.group(1))
                text = match.group(2).strip()
                steps.append({'number': num, 'text': text})
        
        return steps
    
    def _check_numbering(self, steps):
        """Check if steps are numbered sequentially"""
        issues = []
        expected = 1
        
        for step in steps:
            if step['number'] != expected:
                issues.append(f"Step numbering error: expected {expected}, got {step['number']}")
                return False, issues
            expected += 1
        
        return True, []
    
    def _check_action_verbs(self, steps):
        """Check if steps start with action verbs"""
        warnings = []
        invalid_count = 0
        
        for step in steps:
            text = step['text'].lower()
            first_word = text.split()[0] if text.split() else ''
            
            # Clean punctuation
            first_word = re.sub(r'[^\w]', '', first_word)
            
            if first_word not in self.VALID_ACTION_VERBS:
                warnings.append(f"Step {step['number']} doesn't start with clear action verb: '{step['text'][:50]}...'")
                invalid_count += 1
        
        # Allow some flexibility (70% should have action verbs)
        threshold = len(steps) * 0.3
        is_valid = invalid_count <= threshold
        
        return is_valid, [], warnings
    
    def _check_step_length(self, steps):
        """Check if steps are reasonable length"""
        warnings = []
        
        for step in steps:
            length = len(step['text'])
            if length < 5:
                warnings.append(f"Step {step['number']} is too short: '{step['text']}'")
            elif length > 200:
                warnings.append(f"Step {step['number']} is too long ({length} chars) - consider breaking down")
        
        is_valid = len(warnings) < len(steps) * 0.3
        return is_valid, warnings
    
    def _check_duplicates(self, steps):
        """Check for duplicate or very similar steps"""
        warnings = []
        seen = set()
        
        for step in steps:
            normalized = step['text'].lower().strip()
            if normalized in seen:
                warnings.append(f"Duplicate step found: '{step['text'][:50]}...'")
            seen.add(normalized)
        
        is_valid = len(warnings) == 0
        return is_valid, warnings
    
    def print_report(self, validation_result):
        """Print a formatted validation report"""
        print("\n" + "="*70)
        print("VALIDATION REPORT")
        print("="*70)
        
        status = "✅ VALID" if validation_result['is_valid'] else "❌ INVALID"
        print(f"\nStatus: {status}")
        print(f"Quality Score: {validation_result['score']:.1%}")
        print(f"Steps Found: {validation_result['step_count']}")
        
        if validation_result['issues']:
            print(f"\n❌ ISSUES ({len(validation_result['issues'])})")
            for issue in validation_result['issues']:
                print(f"  • {issue}")
        
        if validation_result['warnings']:
            print(f"\n⚠️  WARNINGS ({len(validation_result['warnings'])})")
            for warning in validation_result['warnings']:
                print(f"  • {warning}")
        
        if validation_result['suggestions']:
            print(f"\n💡 SUGGESTIONS ({len(validation_result['suggestions'])})")
            for suggestion in validation_result['suggestions']:
                print(f"  • {suggestion}")
        
        print("\n" + "="*70 + "\n")


def validate_steps(steps_text, instruction=None, verbose=True):
    """
    Convenience function to validate steps
    
    Args:
        steps_text: Generated steps as string
        instruction: Original instruction (optional)
        verbose: Print detailed report (default True)
        
    Returns:
        Validation result dict
    """
    validator = StepValidator()
    result = validator.validate(steps_text, instruction)
    
    if verbose:
        validator.print_report(result)
    
    return result


# Quick test
if __name__ == "__main__":
    # Test cases
    test_cases = [
        {
            'instruction': 'Login to Gmail',
            'steps': """Steps:
1. Open web browser
2. Navigate to gmail.com
3. Click on email field
4. Enter email address
5. Click on password field
6. Enter password
7. Click Login button"""
        },
        {
            'instruction': 'Search for laptop',
            'steps': """Steps:
1. Search for laptop on Amazon"""  # Bad - just echoing
        },
        {
            'instruction': 'Create folder',
            'steps': """Steps:
1. This is a bad step without action verb
2. Another bad step
3. Click somewhere"""  # Bad - poor action verbs
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST CASE {i}: {test['instruction']}")
        print(f"{'='*70}")
        print(f"\nGenerated Steps:\n{test['steps']}")
        
        result = validate_steps(test['steps'], test['instruction'])
