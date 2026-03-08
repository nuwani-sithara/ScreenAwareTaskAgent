def format_agent_response(agent_output):

    plan = agent_output.get("action_plan", {})
    evaluation = agent_output.get("evaluation", {})

    steps = []

    for step in plan.get("rewritten_steps", []):
        steps.append(step.get("description"))

    success = evaluation.get("success", False)

    if success:
        status = "completed"
        message = "Test completed successfully."
    else:
        status = "failed"
        message = "Test execution failed."

    return {
        "type": "agent_response",
        "status": status,
        "message": message,
        "steps": steps
    }