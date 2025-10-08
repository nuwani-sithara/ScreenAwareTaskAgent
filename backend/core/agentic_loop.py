from backend.core.perceive import perceive
from backend.core.plan import plan
from backend.core.act import act

def run_cycle():
    perception = perceive()
    action_plan = plan(perception)
    result = act(action_plan)
    print(f"✅ Result: {result}")
    return result
