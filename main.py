import tkinter as tk
from tkinter import messagebox
from openai import OpenAI

APP_TITLE = "QUREO Assistant · OpenRouter"

class App:
    def __init__(self, root):
        self.root=root; root.title(APP_TITLE); root.geometry("850x650")
        tk.Label(root,text="QUREO Assistant",font=("Segoe UI",20,"bold")).pack(pady=10)
        tk.Label(root,text="Generate JavaScript help from a question you paste. You control QUREO and submit your own work.").pack()
        frame=tk.Frame(root); frame.pack(fill="x",padx=14,pady=8)
        tk.Label(frame,text="OpenRouter API key").grid(row=0,column=0,sticky="w")
        self.key=tk.Entry(frame,show="•",width=72); self.key.grid(row=1,column=0,sticky="ew",pady=4)
        tk.Label(frame,text="Model (OpenRouter ID)").grid(row=2,column=0,sticky="w")
        self.model=tk.Entry(frame,width=72); self.model.insert(0,"openai/gpt-4o-mini"); self.model.grid(row=3,column=0,sticky="ew",pady=4)
        frame.columnconfigure(0,weight=1)
        tk.Label(root,text="Question / exercise").pack(anchor="w",padx=14)
        self.prompt=tk.Text(root,height=10,wrap="word"); self.prompt.pack(fill="both",expand=True,padx=14,pady=5)
        tk.Button(root,text="Generate explanation + JavaScript",command=self.generate).pack(pady=7)
        tk.Label(root,text="Generated response").pack(anchor="w",padx=14)
        self.output=tk.Text(root,height=12,wrap="word"); self.output.pack(fill="both",expand=True,padx=14,pady=5)
    def generate(self):
        key=self.key.get().strip(); prompt=self.prompt.get("1.0","end").strip(); model=self.model.get().strip()
        if not key or not prompt or not model:
            messagebox.showwarning("Missing input","Enter your API key, model, and question."); return
        try:
            client=OpenAI(api_key=key,base_url="https://openrouter.ai/api/v1")
            result=client.chat.completions.create(model=model,messages=[{"role":"system","content":"You are a beginner-friendly JavaScript tutor. Explain briefly, then provide correct code. Do not claim to interact with QUREO."},{"role":"user","content":prompt}],temperature=0.2)
            self.output.delete("1.0","end"); self.output.insert("1.0",result.choices[0].message.content or "No response.")
        except Exception as e: messagebox.showerror("OpenRouter error",str(e))

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
