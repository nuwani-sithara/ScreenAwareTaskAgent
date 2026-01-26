"""
Advanced Step Validation Techniques
Uses semantic analysis, workflow patterns, and completeness checks
"""
import re
from collections import defaultdict

class AdvancedStepValidator:
    """Advanced validation using multiple techniques"""
    
    # UI workflow patterns - what should come before what
    WORKFLOW_PATTERNS = {
        'navigate': ['open', 'launch', 'start'],  # Must open/launch before navigate
        'click': ['open', 'navigate', 'go'],      # Must have UI visible before clicking
        'enter': ['click', 'select', 'focus'],    # Must focus field before entering
        'type': ['click', 'select', 'focus'],     # Must focus field before typing
        'submit': ['enter', 'type', 'fill'],      # Must enter data before submitting
        'verify': ['click', 'submit', 'enter'],   # Must have action before verifying
    }
    
    # Common UI patterns for completeness
    LOGIN_KEYWORDS = ['login', 'signin', 'sign in', 'log in', 'authenticate']
    SEARCH_KEYWORDS = ['search', 'find', 'look for', 'query']
    CREATE_KEYWORDS = ['create', 'new', 'add', 'make', 'generate']
    
    def __init__(self):
        self.validation_methods = [
            self.validate_workflow_logic,
            self.validate_completeness,
            self.validate_specificity,
            self.validate_action_coverage,
            self.validate_semantic_coherence
        ]
    
    def validate_all(self, steps_text, instruction):
        """Run all advanced validation checks"""
        results = {
            'overall_score': 0.0,
            'checks': {},
            'insights': [],
            'advanced_issues': []
        }
        
        steps = self._parse_steps(steps_text)
        if not steps:
            results['advanced_issues'].append("No parseable steps found")
            return results
        
        # Run all validation methods
        scores = []
        for method in self.validation_methods:
            try:
                check_result = method(steps, instruction)
                method_name = method.__name__.replace('validate_', '')
                results['checks'][method_name] = check_result
                scores.append(check_result['score'])
            except Exception as e:
                results['advanced_issues'].append(f"Error in {method.__name__}: {str(e)}")
        
        # Calculate overall score
        results['overall_score'] = sum(scores) / len(scores) if scores else 0.0
        
        # Generate insights
        results['insights'] = self._generate_insights(results['checks'], instruction)
        
        return results
    
    def validate_workflow_logic(self, steps, instruction):
        """Check if steps follow logical UI workflow order"""
        result = {
            'score': 1.0,
            'issues': [],
            'description': 'Checks if actions follow logical UI workflow'
        }
        
        actions = [self._extract_action_verb(s['text']) for s in steps]
        
        # Check prerequisites
        for i, action in enumerate(actions):
            if action in self.WORKFLOW_PATTERNS:
                required_predecessors = self.WORKFLOW_PATTERNS[action]
                # Check if any required action appears before current one
                predecessors = actions[:i]
                has_prerequisite = any(pred in required_predecessors for pred in predecessors)
                
                if not has_prerequisite and i > 0:  # Allow first step flexibility
                    result['issues'].append(
                        f"Step {i+1} '{action}' typically requires a preceding action like {required_predecessors[:2]}"
                    )
                    result['score'] -= 0.15
        
        # Check for logical impossible sequences
        if 'close' in actions and 'click' in actions:
            close_idx = actions.index('close')
            click_after_close = [i for i, a in enumerate(actions[close_idx:]) if a == 'click']
            if click_after_close:
                result['issues'].append("Found 'click' actions after 'close' - might be illogical")
                result['score'] -= 0.2
        
        result['score'] = max(0, result['score'])
        return result
    
    def validate_completeness(self, steps, instruction):
        """Check if steps cover all aspects mentioned in instruction"""
        result = {
            'score': 1.0,
            'issues': [],
            'description': 'Checks if all instruction requirements are covered'
        }
        
        instruction_lower = instruction.lower()
        steps_text = ' '.join([s['text'].lower() for s in steps])
        
        # Extract key entities from instruction
        entities = self._extract_entities(instruction)
        
        # Check if entities are mentioned in steps
        missing_entities = []
        for entity_type, values in entities.items():
            for value in values:
                if value.lower() not in steps_text:
                    missing_entities.append(f"{entity_type}: {value}")
        
        if missing_entities:
            result['issues'].append(f"Steps missing mentioned items: {', '.join(missing_entities[:3])}")
            result['score'] -= 0.3
        
        # Pattern-specific completeness checks
        if any(kw in instruction_lower for kw in self.LOGIN_KEYWORDS):
            has_username = any(word in steps_text for word in ['username', 'email', 'user', 'id'])
            has_password = any(word in steps_text for word in ['password', 'pass', 'pwd'])
            has_submit = any(word in steps_text for word in ['login', 'submit', 'sign in', 'click'])
            
            if not has_username:
                result['issues'].append("Login task missing username/email entry step")
                result['score'] -= 0.25
            if not has_password:
                result['issues'].append("Login task missing password entry step")
                result['score'] -= 0.25
            if not has_submit:
                result['issues'].append("Login task missing submit/login button step")
                result['score'] -= 0.2
        
        if any(kw in instruction_lower for kw in self.SEARCH_KEYWORDS):
            has_search_action = any(word in steps_text for word in ['search', 'find', 'type', 'enter'])
            has_search_term = len(steps_text.split()) > 5  # Basic check
            
            if not has_search_action:
                result['issues'].append("Search task missing search action")
                result['score'] -= 0.3
        
        result['score'] = max(0, result['score'])
        return result
    
    def validate_specificity(self, steps, instruction):
        """Check if steps are specific enough (not too vague)"""
        result = {
            'score': 1.0,
            'issues': [],
            'description': 'Checks if steps have enough specific details'
        }
        
        vague_phrases = [
            'somewhere', 'something', 'anything', 'somehow',
            'the button', 'the field', 'the page', 'the form',
            'appropriate', 'relevant', 'necessary'
        ]
        
        generic_actions = [
            'do the action', 'perform', 'execute', 'run the task',
            'complete the step', 'finish'
        ]
        
        vague_count = 0
        for step in steps:
            text_lower = step['text'].lower()
            
            # Check for vague phrases
            for vague in vague_phrases:
                if vague in text_lower:
                    vague_count += 1
                    result['issues'].append(f"Step {step['number']} uses vague term: '{vague}'")
            
            # Check for generic actions
            for generic in generic_actions:
                if generic in text_lower:
                    result['issues'].append(f"Step {step['number']} uses generic action: '{generic}'")
                    result['score'] -= 0.15
            
            # Check if step is too short (likely not specific enough)
            if len(text_lower.split()) < 3:
                result['issues'].append(f"Step {step['number']} might be too vague: '{step['text'][:40]}'")
                result['score'] -= 0.1
        
        # Penalize based on vague count
        if vague_count > 0:
            result['score'] -= min(0.4, vague_count * 0.15)
        
        result['score'] = max(0, result['score'])
        return result
    
    def validate_action_coverage(self, steps, instruction):
        """Check if steps have diverse, appropriate action types"""
        result = {
            'score': 1.0,
            'issues': [],
            'description': 'Checks for appropriate variety and distribution of actions'
        }
        
        actions = [self._extract_action_verb(s['text']) for s in steps]
        action_counts = defaultdict(int)
        for action in actions:
            action_counts[action] += 1
        
        # Check for repetitive actions
        total_steps = len(steps)
        for action, count in action_counts.items():
            percentage = count / total_steps
            if percentage > 0.5 and total_steps > 3:  # More than 50% same action
                result['issues'].append(
                    f"Action '{action}' appears too frequently ({count}/{total_steps} steps)"
                )
                result['score'] -= 0.25
        
        # Check for missing critical action types based on instruction
        instruction_lower = instruction.lower()
        
        if 'website' in instruction_lower or 'url' in instruction_lower or 'http' in instruction_lower:
            if not any(a in actions for a in ['open', 'navigate', 'go', 'visit']):
                result['issues'].append("Website task missing navigation step (open/navigate)")
                result['score'] -= 0.3
        
        if 'type' in instruction_lower or 'enter' in instruction_lower or 'write' in instruction_lower:
            if not any(a in actions for a in ['type', 'enter', 'input']):
                result['issues'].append("Data entry task missing type/enter action")
                result['score'] -= 0.3
        
        result['score'] = max(0, result['score'])
        return result
    
    def validate_semantic_coherence(self, steps, instruction):
        """Check if steps semantically relate to the instruction"""
        result = {
            'score': 1.0,
            'issues': [],
            'description': 'Checks semantic relationship between steps and instruction'
        }
        
        instruction_words = set(re.findall(r'\w+', instruction.lower()))
        instruction_words = {w for w in instruction_words if len(w) > 3}  # Filter short words
        
        # Common stop words to ignore
        stop_words = {'the', 'and', 'with', 'from', 'this', 'that', 'have', 'been', 'will', 'your', 'their'}
        instruction_words -= stop_words
        
        # Extract keywords from steps
        all_step_text = ' '.join([s['text'].lower() for s in steps])
        step_words = set(re.findall(r'\w+', all_step_text))
        step_words = {w for w in step_words if len(w) > 3}
        step_words -= stop_words
        
        # Calculate overlap
        if instruction_words:
            overlap = len(instruction_words & step_words)
            overlap_ratio = overlap / len(instruction_words)
            
            if overlap_ratio < 0.2:  # Less than 20% overlap
                result['issues'].append(
                    f"Low semantic overlap ({overlap_ratio:.0%}) - steps may not address instruction"
                )
                result['score'] -= 0.4
            elif overlap_ratio < 0.4:  # Less than 40% overlap
                result['issues'].append(
                    f"Moderate semantic overlap ({overlap_ratio:.0%}) - consider more specificity"
                )
                result['score'] -= 0.2
        
        # Check for completely unrelated content
        tech_domains = {
            'email': ['gmail', 'outlook', 'mail', 'inbox'],
            'shopping': ['amazon', 'cart', 'buy', 'purchase', 'shop'],
            'social': ['facebook', 'twitter', 'instagram', 'post', 'share'],
            'file': ['folder', 'file', 'directory', 'document']
        }
        
        instruction_domain = None
        for domain, keywords in tech_domains.items():
            if any(kw in instruction.lower() for kw in keywords):
                instruction_domain = domain
                break
        
        if instruction_domain:
            domain_keywords = tech_domains[instruction_domain]
            has_domain_words = any(kw in all_step_text for kw in domain_keywords)
            if not has_domain_words:
                result['issues'].append(
                    f"Steps don't mention expected {instruction_domain}-related terms"
                )
                result['score'] -= 0.3
        
        result['score'] = max(0, result['score'])
        return result
    
    def _parse_steps(self, text):
        """Parse steps from text"""
        steps = []
        text = re.sub(r'^Steps:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)[\.)]\s*(.+)$', line)
            if match:
                steps.append({'number': int(match.group(1)), 'text': match.group(2).strip()})
        
        return steps
    
    def _extract_action_verb(self, text):
        """Extract the main action verb from step text"""
        text = text.lower().strip()
        # Remove common prefixes
        text = re.sub(r'^(then |next |now |finally )', '', text)
        
        words = text.split()
        if words:
            return re.sub(r'[^\w]', '', words[0])
        return ''
    
    def _extract_entities(self, instruction):
        """Extract entities like emails, URLs, names from instruction"""
        entities = {
            'emails': re.findall(r'\b[\w.-]+@[\w.-]+\.\w+\b', instruction),
            'urls': re.findall(r'https?://[\w./%-]+', instruction),
            'names': re.findall(r'\b[A-Z][a-z]+\b', instruction),
            'numbers': re.findall(r'\b\d+\b', instruction)
        }
        return {k: v for k, v in entities.items() if v}
    
    def _generate_insights(self, checks, instruction):
        """Generate actionable insights from validation results"""
        insights = []
        
        # Analyze overall patterns
        low_scores = [name for name, check in checks.items() if check['score'] < 0.6]
        
        if 'workflow_logic' in low_scores:
            insights.append("💡 Steps may be out of logical order - ensure open/navigate before click/enter")
        
        if 'completeness' in low_scores:
            insights.append("💡 Some instruction requirements appear missing - review original task")
        
        if 'specificity' in low_scores:
            insights.append("💡 Steps are too vague - add specific field names, button labels, or URLs")
        
        if 'action_coverage' in low_scores:
            insights.append("💡 Action variety issue - check for repetitive or missing critical actions")
        
        if 'semantic_coherence' in low_scores:
            insights.append("💡 Steps may not align with instruction - verify semantic relevance")
        
        # Check if multiple categories failed
        if len(low_scores) >= 3:
            insights.append("⚠️ Multiple validation issues detected - consider regenerating with better prompt")
        
        return insights


def advanced_validate(steps_text, instruction, verbose=True):
    """
    Run advanced validation
    
    Args:
        steps_text: Generated steps as string
        instruction: Original instruction
        verbose: Print detailed report
        
    Returns:
        Advanced validation results
    """
    validator = AdvancedStepValidator()
    result = validator.validate_all(steps_text, instruction)
    
    if verbose:
        print("\n" + "="*70)
        print("ADVANCED VALIDATION REPORT")
        print("="*70)
        print(f"\n📊 Overall Score: {result['overall_score']:.1%}")
        
        print(f"\n🔍 Detailed Checks:")
        for check_name, check_result in result['checks'].items():
            score_icon = "✅" if check_result['score'] >= 0.7 else "⚠️" if check_result['score'] >= 0.5 else "❌"
            print(f"\n  {score_icon} {check_name.replace('_', ' ').title()}: {check_result['score']:.1%}")
            print(f"     {check_result['description']}")
            
            if check_result['issues']:
                for issue in check_result['issues'][:2]:  # Show first 2
                    print(f"     • {issue}")
                if len(check_result['issues']) > 2:
                    print(f"     ... and {len(check_result['issues']) - 2} more issues")
        
        if result['insights']:
            print(f"\n💡 Key Insights:")
            for insight in result['insights']:
                print(f"  {insight}")
        
        if result['advanced_issues']:
            print(f"\n❌ Validation Errors:")
            for issue in result['advanced_issues']:
                print(f"  • {issue}")
        
        print("\n" + "="*70 + "\n")
    
    return result


# Test if run directly
if __name__ == "__main__":
    test_cases = [
        {
            'instruction': 'Login to Gmail with username test@gmail.com and password Test123',
            'steps': """Steps:
1. Open web browser
2. Navigate to gmail.com
3. Click on email field
4. Enter test@gmail.com
5. Click on password field
6. Enter Test123
7. Click Login button"""
        },
        {
            'instruction': 'Search for laptop on Amazon',
            'steps': """Steps:
1. Search for laptop
2. Click on something
3. Do the task
4. Finish"""  # Bad - vague
        },
        {
            'instruction': 'Create new folder on desktop',
            'steps': """Steps:
1. Click Login button
2. Enter password
3. Navigate to facebook.com"""  # Bad - wrong task
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST CASE {i}: {test['instruction']}")
        print(f"{'='*70}")
        advanced_validate(test['steps'], test['instruction'])
