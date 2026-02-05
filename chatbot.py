from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr
from typing import List, Dict
from rag import SimpleRAG


load_dotenv(override=True)

# Project root (works when run from repo or deployed)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ME_DIR = os.path.join(PROJECT_ROOT, "me")

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class Me:

    def __init__(self, use_rag: bool = False):
        self.gemini = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"), 
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.name = "Shivang Gupta"
        self.use_rag = use_rag
        
        # Load documents (paths relative to project root for portability)
        reader = PdfReader(os.path.join(ME_DIR, "Profile.pdf"))
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open(os.path.join(ME_DIR, "summary.txt"), "r", encoding="utf-8") as f:
            self.summary = f.read()
        reader = PdfReader(os.path.join(ME_DIR, "shivang_resume_detailed_1.pdf"))
        self.resume = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.resume += text
        
        # Initialize RAG system if enabled
        if self.use_rag:
            print("Initializing RAG system...")
            self.rag = SimpleRAG(self.gemini)
            documents = {
                "summary": self.summary,
                "linkedin": self.linkedin,
                "resume": self.resume
            }
            self.rag.add_documents(documents, chunk_size=500, overlap=50)
            print("RAG system ready!")
        else:
            self.rag = None


    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results
    
    def system_prompt(self, retrieved_context: List[Dict] = None):
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        if retrieved_context:
            # Use RAG: include only retrieved relevant chunks
            system_prompt += "\n\n## Relevant Information:\n"
            for i, doc in enumerate(retrieved_context, 1):
                system_prompt += f"\n[{doc['source']} - Chunk {doc['chunk_index'] + 1}]:\n{doc['text']}\n"
        else:
            # Fallback: include all content if RAG is disabled or no context retrieved
            system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        
        system_prompt += f"\nWith this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt
    
    def chat(self, message, history):
        # Retrieve relevant context using RAG if enabled
        retrieved_context = None
        if self.use_rag and self.rag:
            retrieved_context = self.rag.retrieve(message, top_k=5)
            if retrieved_context:
                print(f"[RAG] Retrieved {len(retrieved_context)} relevant chunks")
        
        # Build system prompt with retrieved context
        system_content = self.system_prompt(retrieved_context)
        messages = [{"role": "system", "content": system_content}] + history + [{"role": "user", "content": message}]
        
        done = False
        while not done:
            response = self.gemini.chat.completions.create(model="gemini-3-flash-preview", messages=messages, tools=tools)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
    

if __name__ == "__main__":
    me = Me(use_rag=True)
    port = int(os.environ.get("PORT", 7860))
    gr.ChatInterface(me.chat).launch(server_name="0.0.0.0", server_port=port)
    