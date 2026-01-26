"""
Automation GUI - Using Transformers Model
Simple GUI using your existing fine-tuned T5 model for step generation.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

class AutomationGUI:
    """GUI for automation step generation using transformers model."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Automation Step Generator")
        self.root.geometry("800x600")
        
        self.model = None
        self.tokenizer = None
        self.generating = False
        self.queue = queue.Queue()
        
        self.setup_ui()
        self.load_model_background()
        self.process_queue()
    
    def setup_ui(self):
        """Setup user interface."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Instruction Section
        inst_frame = ttk.LabelFrame(main_frame, text="Instruction", padding="10")
        inst_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        inst_frame.columnconfigure(0, weight=1)
        
        self.inst_text = scrolledtext.ScrolledText(
            inst_frame, height=3, wrap=tk.WORD, font=("Consolas", 10)
        )
        self.inst_text.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        self.inst_text.insert(1.0, "login with username and password")
        
        # Parameters Section
        params_frame = ttk.LabelFrame(main_frame, text="Generation Parameters", padding="10")
        params_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        params_frame.columnconfigure(1, weight=1)
        
        #Max length
        ttk.Label(params_frame, text="Max Steps:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.max_length_var = tk.IntVar(value=150)
        max_scale = ttk.Scale(
            params_frame, from_=50, to=300, variable=self.max_length_var,
            orient=tk.HORIZONTAL, command=self.update_max_label
        )
        max_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=3)
        self.max_label = ttk.Label(params_frame, text="150")
        self.max_label.grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Temperature
        ttk.Label(params_frame, text="Temperature:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.temp_var = tk.DoubleVar(value=0.7)
        temp_scale = ttk.Scale(
            params_frame, from_=0.1, to=1.5, variable=self.temp_var,
            orient=tk.HORIZONTAL, command=self.update_temp_label
        )
        temp_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=3)
        self.temp_label = ttk.Label(params_frame, text="0.70")
        self.temp_label.grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Output Section
        output_frame = ttk.LabelFrame(main_frame, text="Generated Steps", padding="10")
        output_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(
            output_frame, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED
        )
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        
        self.generate_btn = ttk.Button(
            button_frame, text="Generate Steps", command=self.start_generation,
            state=tk.DISABLED
        )
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Clear", command=self.clear_output).pack(
            side=tk.LEFT, padx=5
        )
        
        # Status
        self.status_var = tk.StringVar(value="Loading model...")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def update_max_label(self, value):
        self.max_label.config(text=str(int(float(value))))
    
    def update_temp_label(self, value):
        self.temp_label.config(text=f"{float(value):.2f}")
    
    def load_model_background(self):
        """Load model in background thread."""
        def load():
            try:
                model_path = "../llm/fine_tuned_js_model/checkpoint-3"
                self.queue.put(('status', 'Loading tokenizer...'))
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                
                self.queue.put(('status', 'Loading model (this may take a moment)...'))
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
                self.model.eval()
                
                self.queue.put(('loaded', None))
            except Exception as e:
                self.queue.put(('error', str(e)))
        
        threading.Thread(target=load, daemon=True).start()
    
    def start_generation(self):
        """Start generation in background."""
        if self.generating or not self.model:
            return
        
        instruction = self.inst_text.get(1.0, tk.END).strip()
        if not instruction:
            messagebox.showwarning("Warning", "Please enter an instruction.")
            return
        
        self.generating = True
        self.generate_btn.config(state=tk.DISABLED)
        self.status_var.set("Generating steps...")
        
        # Clear output
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        
        max_length = self.max_length_var.get()
        temperature = self.temp_var.get()
        
        threading.Thread(
            target=self.generate_thread,
            args=(instruction, max_length, temperature),
            daemon=True
        ).start()
    
    def generate_thread(self, instruction, max_length, temperature):
        """Generate in background thread."""
        try:
            # Tokenize input
            inputs = self.tokenizer(instruction, return_tensors="pt", max_length=512, truncation=True)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_length,
                    temperature=temperature,
                    top_k=50,
                    top_p=0.9,
                    do_sample=True,
                    num_beams=3,  # Beam search for better quality
                    early_stopping=True
                )
            
            # Decode
            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            self.queue.put(('done', generated_text))
            
        except Exception as e:
            self.queue.put(('gen_error', str(e)))
    
    def process_queue(self):
        """Process message queue."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                
                if msg_type == 'status':
                    self.status_var.set(data)
                
                elif msg_type == 'loaded':
                    self.status_var.set("✓ Model loaded! Ready to generate steps.")
                    self.generate_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("Success", "Model loaded successfully!\n\nEnter an instruction and click 'Generate Steps'.")
                
                elif msg_type == 'error':
                    self.status_var.set("Error loading model")
                    messagebox.showerror("Error", f"Failed to load model:\n{data}")
                
                elif msg_type == 'done':
                    self.output_text.config(state=tk.NORMAL)
                    self.output_text.delete(1.0, tk.END)
                    self.output_text.insert(1.0, data)
                    self.output_text.config(state=tk.DISABLED)
                    self.generating = False
                    self.generate_btn.config(state=tk.NORMAL)
                    self.status_var.set("Generation complete!")
                
                elif msg_type == 'gen_error':
                    self.generating = False
                    self.generate_btn.config(state=tk.NORMAL)
                    self.status_var.set("Error during generation")
                    messagebox.showerror("Error", f"Generation failed:\n{data}")
        
        except queue.Empty:
            pass
        
        self.root.after(100, self.process_queue)
    
    def clear_output(self):
        """Clear output text."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

def main():
    """Launch GUI."""
    root = tk.Tk()
    app = AutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
