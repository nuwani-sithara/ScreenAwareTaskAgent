"""
Example Integration: Visual Perception → LLM → HID
Demonstrates the complete flow from screen analysis to command execution
"""

import json
import time
import requests
from typing import Dict, Any, List


class VisualAwareAgent:
    """
    Simple agent that uses visual perception to generate and execute HID commands
    """
    
    def __init__(
        self,
        llm_url: str = "http://localhost:8002",
        vision_url: str = "http://localhost:8001",
        hid_url: str = "http://localhost:3000"
    ):
        self.llm_url = llm_url
        self.vision_url = vision_url
        self.hid_url = hid_url
    
    def perceive(self) -> Dict[str, Any]:
        """
        Step 1: Get visual perception of current screen
        
        Returns:
            Visual perception data with detected elements
        """
        print("👁️  [PERCEIVE] Analyzing screen...")
        
        try:
            # For this example, we'll simulate visual perception
            # In production, call the vision service
            
            # response = requests.get(f"{self.vision_url}/vision/session/latest")
            # visual_data = response.json()
            
            # Simulated visual data (replace with actual vision service call)
            visual_data = {
                "status": "stopped",
                "session_id": "session_example",
                "session_data": {
                    "screens": [{
                        "screen_index": 0,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "elements": [
                            {
                                "id": "elem_0",
                                "type": "button",
                                "label": "Send",
                                "bbox": [0.023, 0.875, 0.237, 0.933],
                                "state": "enabled",
                                "confidence": 0.95
                            },
                            {
                                "id": "elem_1",
                                "type": "input_field",
                                "label": "Message",
                                "bbox": [0.051, 0.381, 0.626, 0.606],
                                "state": "enabled",
                                "confidence": 0.95
                            }
                        ]
                    }]
                }
            }
            
            num_elements = len(visual_data["session_data"]["screens"][0]["elements"])
            print(f"   ✓ Detected {num_elements} interactive elements")
            
            return visual_data
            
        except Exception as e:
            print(f"   ✗ Perception failed: {e}")
            return {}
    
    def plan(self, instruction: str, visual_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Step 2: Generate HID commands using LLM + visual context
        
        Args:
            instruction: User's task instruction
            visual_data: Visual perception output
        
        Returns:
            List of HID commands ready for execution
        """
        print(f"\n🧠 [PLAN] Generating HID commands for: '{instruction}'")
        
        try:
            response = requests.post(
                f"{self.llm_url}/llm/generate_hid",
                json={
                    "instruction": instruction,
                    "visual_data": visual_data,
                    "model": "mistral",
                    "max_tokens": 300
                },
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result["status"] == "success":
                commands = result["hid_commands"]
                print(f"   ✓ Generated {len(commands)} HID commands")
                
                # Log commands
                for i, cmd in enumerate(commands, 1):
                    cmd_type = cmd.get("cmd")
                    print(f"   {i}. {cmd_type}")
                
                return commands
            else:
                print(f"   ✗ Planning failed: {result.get('error')}")
                return []
                
        except Exception as e:
            print(f"   ✗ Planning failed: {e}")
            return []
    
    def act(self, hid_commands: List[Dict[str, Any]]) -> bool:
        """
        Step 3: Execute HID commands on the device
        
        Args:
            hid_commands: List of HID protocol commands
        
        Returns:
            True if all commands executed successfully
        """
        print(f"\n🤖 [ACT] Executing {len(hid_commands)} HID commands...")
        
        try:
            for i, cmd in enumerate(hid_commands, 1):
                cmd_type = cmd.get("cmd")
                
                # Handle special delay command (not sent to HID device)
                if cmd_type == "delay":
                    duration = cmd.get("duration_ms", 100)
                    print(f"   {i}. delay {duration}ms")
                    time.sleep(duration / 1000.0)
                    continue
                
                # Send command to HID device
                # In production, send to HID device-shadow service
                # response = requests.post(
                #     f"{self.hid_url}/api/command",
                #     json=cmd
                # )
                
                # For this example, just log the command
                details = {k: v for k, v in cmd.items() if k not in ['cmd', 'meta']}
                print(f"   {i}. {cmd_type} {details}")
                
                # Small delay between commands for smooth execution
                time.sleep(0.05)
            
            print("   ✓ All commands executed successfully")
            return True
            
        except Exception as e:
            print(f"   ✗ Execution failed: {e}")
            return False
    
    def run_task(self, instruction: str) -> bool:
        """
        Complete task execution: Perceive → Plan → Act
        
        Args:
            instruction: User's task instruction
        
        Returns:
            True if task completed successfully
        """
        print("\n" + "="*60)
        print(f"TASK: {instruction}")
        print("="*60)
        
        # Step 1: Perceive
        visual_data = self.perceive()
        if not visual_data:
            print("\n❌ Task failed: No visual data")
            return False
        
        # Step 2: Plan
        hid_commands = self.plan(instruction, visual_data)
        if not hid_commands:
            print("\n❌ Task failed: No commands generated")
            return False
        
        # Step 3: Act
        success = self.act(hid_commands)
        
        if success:
            print("\n✅ Task completed successfully")
        else:
            print("\n❌ Task failed during execution")
        
        return success


def demo_single_task():
    """Demo: Execute a single task"""
    agent = VisualAwareAgent()
    
    instruction = "Type 'Hello World' in the message field and click Send"
    agent.run_task(instruction)


def demo_multi_task():
    """Demo: Execute multiple tasks in sequence"""
    agent = VisualAwareAgent()
    
    tasks = [
        "Click the message input field",
        "Type 'Hello from the agent!'",
        "Click the Send button",
        "Wait 2 seconds",
        "Type 'This is automated'",
        "Press Enter key"
    ]
    
    print("\n" + "#"*60)
    print("# MULTI-TASK DEMO")
    print("#"*60)
    print(f"\nExecuting {len(tasks)} tasks sequentially...\n")
    
    results = []
    for task in tasks:
        success = agent.run_task(task)
        results.append({"task": task, "success": success})
        
        if not success:
            print("\n⚠️  Task failed, stopping execution")
            break
        
        time.sleep(1)  # Delay between tasks
    
    # Summary
    print("\n" + "="*60)
    print("EXECUTION SUMMARY")
    print("="*60)
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} {r['task']}")


def demo_with_real_visual_data():
    """
    Demo: Use actual visual perception data
    
    To use this, you need:
    1. Vision service running at http://localhost:8001
    2. A screen capture session with detected elements
    """
    agent = VisualAwareAgent()
    
    try:
        # Get latest session from vision service
        response = requests.get("http://localhost:8001/vision/session/latest")
        visual_data = response.json()
        
        print("Fetched real visual data from vision service")
        
        # Plan with real data
        instruction = input("Enter task instruction: ")
        hid_commands = agent.plan(instruction, visual_data)
        
        if hid_commands:
            print(f"\nGenerated {len(hid_commands)} commands:")
            for cmd in hid_commands:
                print(f"  {json.dumps(cmd, indent=2)}")
            
            # Ask before executing
            confirm = input("\nExecute these commands? (y/n): ")
            if confirm.lower() == 'y':
                agent.act(hid_commands)
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to vision service")
        print("Make sure vision service is running at http://localhost:8001")


if __name__ == "__main__":
    import sys
    
    print("="*60)
    print("Visual-Aware Agent Integration Demo")
    print("="*60)
    print("\nThis demonstrates the complete flow:")
    print("  1. Perceive: Analyze screen with vision service")
    print("  2. Plan: Generate HID commands with LLM")
    print("  3. Act: Execute commands via HID device")
    print("\nPrerequisites:")
    print("  • LLM service running (python -m llm.api)")
    print("  • Ollama running with mistral model")
    print("  • Optional: Vision service for real perception")
    print("="*60)
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "multi":
            demo_multi_task()
        elif mode == "real":
            demo_with_real_visual_data()
        else:
            # Custom instruction
            agent = VisualAwareAgent()
            instruction = " ".join(sys.argv[1:])
            agent.run_task(instruction)
    else:
        # Default: single task demo
        demo_single_task()
