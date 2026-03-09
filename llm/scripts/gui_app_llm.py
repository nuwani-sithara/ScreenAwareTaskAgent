"""
Desktop GUI Application
Interactive text generation interface with real-time display.
Uses Google Gemini API for step generation.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
from google import genai


class TextGenerationGUI:
    """Desktop GUI for text generation using Gemini API."""
    
    def __init__(self, root):
        """Initialize GUI."""
        self.root = root
        self.root.title("Automation Step Generator - Powered by Gemini AI")
        self.root.geometry("800x600")
        
        # Gemini API setup
        GEMINI_API_KEY = "AIzaSyDmFDeC0Fl8EjRx6UqER0awFQDVm1x-60Y"
        self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        # Try different models in order of preference
        self.models_to_try = ['gemini-2.0-flash', 'gemini-flash-latest', 'gemini-pro-latest']
        self.model_name = self.models_to_try[0]
        
        self.generating = False
        self.generation_queue = queue.Queue()
        
        # Setup UI
        self.setup_ui()
        
        # Start queue processor
        self.process_queue()
    
    def setup_ui(self):
        """Setup user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # ===== API Status Section =====
        status_frame = ttk.LabelFrame(main_frame, text="AI Model", padding="10")
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        status_frame.columnconfigure(1, weight=1)
        
        ttk.Label(status_frame, text="Status:", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=5
        )
        
        self.model_status = ttk.Label(
            status_frame, 
            text="Google Gemini 2.0 Flash - Ready ✓", 
            foreground="green", 
            font=("Arial", 10)
        )
        self.model_status.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        # ===== Prompt Section =====
        prompt_frame = ttk.LabelFrame(main_frame, text="Instruction", padding="10")
        prompt_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        prompt_frame.columnconfigure(0, weight=1)
        
        self.prompt_text = scrolledtext.ScrolledText(
            prompt_frame, height=4, wrap=tk.WORD, font=("Consolas", 10)
        )
        self.prompt_text.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        self.prompt_text.insert(1.0, "login with username and password")
        
        # ===== Output Section =====
        output_frame = ttk.LabelFrame(main_frame, text="Generated Steps", padding="10")
        output_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, wrap=tk.WORD, font=("Consolas", 11), state=tk.DISABLED
        )
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # ===== Control Buttons =====
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        button_frame.columnconfigure(0, weight=1)
        
        self.generate_btn = ttk.Button(
            button_frame, text="✨ Generate Steps", command=self.start_generation
        )
        self.generate_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)
        
        self.clear_btn = ttk.Button(button_frame, text="Clear", command=self.clear_output)
        self.clear_btn.grid(row=0, column=1, padx=5)
        
        # ===== Status Bar =====
        self.status_var = tk.StringVar(value="Ready to generate automation steps using Gemini AI")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=2)
    
    def start_generation(self):
        """Start text generation in background thread."""
        if self.generating:
            return
        
        instruction = self.prompt_text.get(1.0, tk.END).strip()
        if not instruction:
            messagebox.showwarning("Warning", "Please enter an instruction.")
            return
        
        # Update UI
        self.generating = True
        self.generate_btn.config(state=tk.DISABLED, text="⏳ Generating...")
        self.status_var.set("🤖 Generating steps with Gemini AI...")
        
        # Clear previous output
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        # Start generation thread
        thread = threading.Thread(
            target=self.generate_text_thread,
            args=(instruction,),
            daemon=True
        )
        thread.start()
    
    def generate_text_thread(self, instruction):
        """Generate text in background thread using Gemini API with fallback models."""
        try:
            print(f"\n[DEBUG] Starting Gemini generation:")
            print(f"  Instruction: {instruction}")
            
            # Build prompt
            prompt = f"""You are a human-like UI test automation agent.

Your task is to convert a user's instruction into clear, executable UI test steps.

Rules:
- Generate only UI interaction steps.
- Each step must start with a strong action verb (e.g., Open, Click, Enter, Select, Navigate, Verify).
- Steps must be sequential and logical.
- Do NOT include planning, coding, or implementation steps.
- Do NOT explain — only output the steps.

Format:
Steps:
1. <Step one>
2. <Step two>
3. <Step three>
...

Instruction: {instruction}

Steps:
1."""
            
            # Try each model until one works
            last_error = None
            for model_name in self.models_to_try:
                try:
                    print(f"[DEBUG] Trying model: {model_name}")
                    
                    # Generate content using Gemini
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    
                    # Extract text
                    if response.text:
                        steps = response.text.strip()
                        
                        # Format output
                        if not steps.startswith("Steps:"):
                            if steps.startswith("1."):
                                steps = "Steps:\n" + steps
                            else:
                                steps = "Steps:\n1. " + steps
                        
                        print(f"[DEBUG] Generation complete with {model_name}: {len(steps)} characters")
                        self.model_name = model_name  # Update to working model
                        self.generation_queue.put(('done', steps))
                        return
                    else:
                        last_error = "No response generated"
                        continue
                        
                except Exception as e:
                    error_msg = str(e)
                    print(f"[DEBUG] Model {model_name} failed: {error_msg}")
                    last_error = error_msg
                    
                    # If it's a 503 or overload error, try next model
                    if '503' in error_msg or 'overloaded' in error_msg.lower():
                        continue
                    # If it's other error, also try next model
                    continue
            
            # If all models failed, report error
            self.generation_queue.put(('error', f"All models failed. Last error: {last_error}"))
            
        except Exception as e:
            print(f"[DEBUG] Generation error: {e}")
            import traceback
            traceback.print_exc()
            self.generation_queue.put(('error', str(e)))
    
    def process_queue(self):
        """Process generation queue for UI updates."""
        try:
            while True:
                msg_type, data = self.generation_queue.get_nowait()
                
                if msg_type == 'done':
                    # Update output text
                    self.output_text.config(state=tk.NORMAL)
                    self.output_text.delete(1.0, tk.END)
                    self.output_text.insert(1.0, data)
                    self.output_text.see(tk.END)
                    self.output_text.config(state=tk.DISABLED)
                    
                    self.generating = False
                    self.generate_btn.config(state=tk.NORMAL, text="✨ Generate Steps")
                    self.status_var.set("✓ Generation complete!")
                
                elif msg_type == 'error':
                    self.generating = False
                    self.generate_btn.config(state=tk.NORMAL, text="✨ Generate Steps")
                    self.status_var.set("❌ Error during generation.")
                    messagebox.showerror("Error", f"Generation failed:\n{data}")
        
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.process_queue)
    
    def clear_output(self):
        """Clear output text."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.status_var.set("Ready to generate automation steps using Gemini AI")


def main():
    """Launch GUI application."""
    root = tk.Tk()
    app = TextGenerationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
