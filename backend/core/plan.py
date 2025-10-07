def plan(perception):
    print("🧩 Planning next action...")
    if "Login" in perception["screen_text"]:
        return "Enter username and password, then click Login"
    else:
        return "Wait for screen change"
