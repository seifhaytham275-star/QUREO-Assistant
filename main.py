import tkinter as tk
from tkinter import messagebox
from openai import OpenAI
import browser_helper

APP_TITLE = "QUREO Assistant · OpenRouter"

class App:
    def __init__(self, root):
        self.root=root; root.title(APP_TITLE); root.geometry("900x720")
        tk.Label(root,text="QUREO Assistant",font=("Segoe UI",20,"bold")).pack(pady=8)
        tk.Label(root,text="Local browser helper: sign in yourself, read the exercise, get guided code help, then review and submit yourself.",wraplength=850).pack()
        frame=tk.Frame(root); frame.pack(fill="x",padx=14,pady=8)
        tk.Label(frame,text="OpenRouter API key").grid(row=0,column=0,sticky="w")
        self.key=tk.Entry(frame,show="•",width=72); self.key.grid(row=1,column=0,sticky="ew",pady=4)
        tk.Label(frame,text="Model (OpenRouter ID)").grid(row=2,column=0,sticky="w")
        self.model=tk.Entry(frame,width=72); self.model.insert(0,"openai/gpt-4o-mini"); self.model.grid(row=3,column=0,sticky="ew",pady=4)
        frame.columnconfigure(0,weight=1)
        controls=tk.Frame(root); controls.pack(fill="x",padx=14,pady=4)
        tk.Button(controls,text="1 · Open QUREO in Edge",command=self.open_browser).pack(side="left",padx=4)
        tk.Button(controls,text="2 · Read current exercise",command=self.read_exercise).pack(side="left",padx=4)
        tk.Label(root,text="Exercise / page text (you can also paste text here)").pack(anchor="w",padx=14)
        self.prompt=tk.Text(root,height=10,wrap="word"); self.prompt.pack(fill="both",expand=True,padx=14,pady=5)
        tk.Button(root,text="Explain + suggest JavaScript",command=self.generate).pack(pady=7)
        tk.Label(root,text="Suggested answer · review before using").pack(anchor="w",padx=14)
        self.output=tk.Text(root,height=12,wrap="word"); self.output.pack(fill="both",expand=True,padx=14,pady=5)
        root.protocol("WM_DELETE_WINDOW",self.close)
    def open_browser(self):
        try:
            browser_helper.open_qureo()
            messagebox.showinfo("QUREO opened","Sign in directly in Edge and open the exercise. Your password is not entered into this app.")
        except Exception as e:
            messagebox.showerror("Browser error",str(e))
    def read_exercise(self):
        try:
            text=browser_helper.read_visible_page()
            self.prompt.delete("1.0","end"); self.prompt.insert("1.0",text)
        except Exception as e:
            messagebox.showerror("Read page",str(e))
    def generate(self):
        key=self.key.get().strip(); prompt=self.prompt.get("1.0","end").strip(); model=self.model.get().strip()
        if not key or not prompt or not model:
            messagebox.showwarning("Missing input","Enter your OpenRouter API key, model, and exercise text."); return
        try:
            client=OpenAI(api_key=key,base_url="https://openrouter.ai/api/v1")
            result=client.chat.completions.create(model=model,messages=[
                {"role":"system","content":"You are a beginner-friendly JavaScript tutor helping a student practice on QUREO. Identify the task, explain the reasoning, and suggest code with a short explanation. Do not claim to control the browser. Never submit answers or automate completing a course. If the page text is incomplete, ask the student to inspect/paste the missing prompt."},
                {"role":"user","content":prompt}],temperature=0.2)
            self.output.delete("1.0","end"); self.output.insert("1.0",result.choices[0].message.content or "No response.")
        except Exception as e: messagebox.showerror("OpenRouter error",str(e))
    def close(self):
        try: browser_helper.close_browser()
        except Exception: pass
        self.root.destroy()

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
