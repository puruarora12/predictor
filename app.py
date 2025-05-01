# app.py - Flask API for LeetCode Helper
import threading
import pyreadline3 as readline  
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import collections
import time
from collections import defaultdict
import numpy as np
from langchain_community.llms import OpenAI
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import uuid
from langchain_openai import OpenAIEmbeddings

from pinecone import Pinecone ,ServerlessSpec

from typing import List, Optional

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome extension

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

PINECONE_API_KEY =  os.environ.get('PINECONE_API_KEY')
pinecone = Pinecone(api_key = PINECONE_API_KEY)
INDEX_NAME = "predict"

 
user_histroy = []

#pinecone.create_index(name=INDEX_NAME, dimension=3072, spec=ServerlessSpec(cloud="aws", region="us-east-1") )
#pinecone.create_index(name="pattern", dimension=3072, spec=ServerlessSpec(cloud="aws", region="us-east-1") )
#pinecone.create_index(name='autocomplete', dimension=3072, spec=ServerlessSpec(cloud="aws", region="us-east-1") )
        
index = pinecone.Index(INDEX_NAME)
pattern_index = pinecone.Index("pattern")

api_key = os.environ.get('OPENAI_API_KEY')
if api_key:
    llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=api_key 
)
else:
    print("WARNING: OpenAI API key not found. LLM features will not work.")
def initialize_app():
    global llm
    
def upsert(user_history: list[str], n: int = 4):
 
    if len(user_histroy) <= n:                       
        return
    prefix      = user_histroy[-n-1:-1]          
    next_action = user_histroy[-1]                   
    vec         = embedding_model.embed_query(" → ".join(prefix))
    meta = {
        "prefix": prefix,                     
        "next_action": next_action              
    }
    index.upsert([(str(uuid.uuid4()), vec, meta)])


@app.route('/api/monitor/interaction', methods=['POST'])
def monitor_interaction():
    data = request.json
    print(f"data : {data} \n")
  
    data['timestamp'] = time.time()
 
  
    return jsonify({'status': 'success'})


def format(context):
    # print(type(context))
    # print(context)
    # print(context.keys())
    s = ""
    for key in context.keys():
        s= s+ f"{key}: {context[key]}, "
    return s

@app.route('/api/predict', methods=['POST'])
def predict():
    context = request.json.get('context')
    if not context:
        return jsonify({'prediction': None})
    
    
    q =format(context)
    user_histroy.append(q)
    print("adding data to vector database")
    upsert(user_histroy)
    upsert_pattern(user_histroy)

    llm_prediction = predict_with_llm(context)
    if llm_prediction:
        return jsonify({'prediction': llm_prediction})
    
    return jsonify({'prediction': None})


def retrieve_similar(history: list[str], n: int = 3, k: int = 5):
    if len(history) < n:
        return []
    query_vec = embedding_model.embed_query(" → ".join(history[-n:]))
    res = index.query(vector=query_vec, top_k=k, include_metadata=True)
    examples = []
    for m in res.get("matches", []):
        meta = m["metadata"]
        examples.append((meta["prefix"], meta["next_action"]))
    return examples


@app.route('/api/execute', methods=['POST'])
def execute_api():
    return jsonify({'status': 'success', 'result': 'API call executed'})


def predict_with_llm(context):
    remaining, conf = rag_pattern_completion(user_histroy)
    print("multi step pattern ", remaining, conf)
    
    if remaining and conf==1.0:
        template = ("""
            Given the following user interactions and network requests on LeetCode, predict the next action the user is likely to take:
            Current page: {current_page}
            Current element focus: {current_element}
            
            predicted pattern for this user:
            {results}
            
            Based on this information, what is the most likely next action the user will take?
        
            Respond with ONLY these three lines (no explanations and no extra text):
            1. Action :The predicted action (What the user is going to do next based on previous interactions) 
            2. Score :A confidence score between 0 and 1 
            3. URL: The corresponding URL or API endpoint if applicable
            """,    
            context.get('path', ''),
            json.dumps(context.get('focused_element', {})),
            json.dumps(remaining, indent=2)
            )

    else:
        # time.sleep(2)
        print("getting results")
        results = retrieve_similar(user_histroy)
        
        template = ("""
        Given the following user interactions and network requests on LeetCode, predict the next action the user is likely to take:
        
        Current page: {current_page}
        Current element focus: {current_element}
        
        Common patterns for this user:
        {results}
        
        Based on this information, what is the most likely next action the user will take?
    
        Respond with ONLY these three lines (no explanations and no extra text):
        1. Action :The predicted action (What the user is going to do next based on previous interactions) 
        2. Score :A confidence score between 0 and 1 
        3. URL: The corresponding URL or API endpoint if applicable
        """,    
                context.get('path', ''),
                json.dumps(context.get('focused_element', {})),
                json.dumps(results, indent=2)
                )

    try:
       
        result=llm.invoke(template)
        # Parse LLM response
        print("LLM ans")
        print(result.content)
        # pass
        # break
        lines = result.content.split("\n")
        print(lines)
        if len(lines) < 2:
            return None
        
        action = lines[0].split(": ")[1]
        confidence = float(lines[1].split(": ")[1])
        endpoint = lines[2].split(": ")[1]
        # print("printing ans")
        print(action, confidence, endpoint)
        if confidence < 0.7: 
            return None
        if remaining:
            action = "Multi step pattern Identified :"+action
        return {
            'message': f"Press Tab to {action} \n context {endpoint}",
            'confidence': confidence,
            'action': {
                'url': endpoint if endpoint and endpoint.startswith('http') else None,
                'api': endpoint if endpoint and not endpoint.startswith('http') else None
            }
        }
        
    except Exception as e:
        print(f"Error in LLM prediction: {e}")
        return None


MAX_PAT_LEN = 4          
MIN_SUFFIX  = 2          
PAT_THRESH  = 1          

JOIN = " → "        

def clean(step: str) -> str:
    return step.strip()

def upsert_pattern(history, max_n=4):
    if len(history) < 2:
        return
    suffix = clean(history[-1])
    for n in range(1, min(max_n, len(history))):
        prefix = [clean(s) for s in history[-(n+1):-1]]
        vec    = embedding_model.embed_query(JOIN.join(prefix))
        meta   = {"prefix": prefix, "suffix": suffix}
        pattern_index.upsert([(str(uuid.uuid4()), vec, meta)],
                             namespace="pattern")

def retrieve_suffix_candidates(history, k=4, n=2):
    if len(history) < n:
        return []

    prefix = [clean(s) for s in history[-n:]]          
    qvec   = embedding_model.embed_query(JOIN.join(prefix))

    res = pattern_index.query(                      
            vector=qvec,
            top_k=k,
            namespace="pattern",
            include_metadata=True)

    cands = []
    for m in res.get("matches", []):
        meta = m["metadata"]
        if prefix == [clean(s) for s in meta["prefix"]]:
            cands.append(meta)

    return cands

PAT_PROMPT = PromptTemplate(
    input_variables=["recent", "examples"],
    template=(
      "You are an assistant that completes multi-step workflows.\n\n"
      "User so far:\n{recent}\n\n"
      "Similar cases & how they ended:\n{examples}\n\n"
      "Predict ONLY the remaining steps (comma-separated, keep order)."
    )
)
pat_chain = LLMChain(llm=llm, prompt=PAT_PROMPT)

def rag_pattern_completion(history, n=2, top_k=4):
  
    cands = retrieve_suffix_candidates(history, k=top_k, n=n)
    if not cands:
        return [], 0.0
    print("len of cands ", len(cands))
    example_lines = [
        f"- {JOIN.join(c['prefix'])}  =>  {c['suffix']}"
        for c in cands
    ]
    recent = JOIN.join(history[-n:])

    answer = pat_chain.run({
        "recent":   recent,
        "examples": "\n".join(example_lines)
    }).strip()

   
    if "→" in answer:
        remaining = [part.strip() for part in answer.split("→") if part.strip()]
    else:
        remaining = [part.strip() for part in answer.split(",") if part.strip()]

    first_steps = [c["suffix"] for c in cands]         
    freq = collections.Counter(first_steps)
    confidence = freq.most_common(1)[0][1] / len(first_steps)

    return remaining, confidence



@app.route('/api/monitor/network', methods=['POST'])
def monitor_network():
    data = request.json
    data['timestamp'] = time.time()
    
    return jsonify({'status': 'success'})


def upsert_autocomplete(user_history: list[str],user_input,
                                partial: str,
                                completion: str) -> None:
    """
    Store one training example:
        vector   = embed(ctx[-CTX_LEN:] + [partial])
        meta     = {ctx, partial, completion}
    """
    print(f"user history {user_history[-2:]}\n")
    ctx_clean = [s.strip() for s in user_history[-2:]]
    
    ctx_clean =ctx_clean+ [s.strip() for s in user_input[-2:]]
    
    print(f"ctx_clean {ctx_clean}\n")
    key_text  = JOIN.join(ctx_clean + [partial.strip()])

    vec  = embedding_model.embed_query(key_text)
    meta = {"ctx": ctx_clean, "partial": partial.strip(),
            "completion": completion.strip()}

    pinecone.Index('autocomplete').upsert([(str(uuid.uuid4()), vec, meta)])


def server_autocomplete(partial: str, ctx: list[str]) -> dict:
    """
    Return {intent, completion, examples}
    Uses the last CTX_LEN history items + current partial for retrieval.
    """
    ctx_clean   = [s.strip() for s in ctx[-3:]]
    query_vec   = embedding_model.embed_query(JOIN.join(ctx_clean + [partial]))

    hits = pinecone.Index('autocomplete').query(vector=query_vec,
                            top_k=TOP_K,
                            include_metadata=True).matches

    examples = "\n".join(
        f"- {JOIN.join(h.metadata['ctx'])} + `{h.metadata['partial']}`"
        f"  ⇒  {h.metadata['completion']}"
        for h in hits
    )

    prompt = f"""
    USER CONTEXT  : {JOIN.join(ctx_clean)}
    USER PARTIAL  : `{partial}`

    ### SIMILAR PAST CASES
    {examples or '(none yet)'}

    TASK1 →In ≤12 words, say what the user probably wants to do next.
    TASK2 →Complete the user's partial command in a single line.

    FORMAT:
    intent: <TASK1>
    completion: <TASK2>
    """.strip()

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    lines  = llm.invoke(prompt).content.strip().splitlines()
    parsed = {k.strip(): v.strip()
              for k, v in (line.split(":", 1) for line in lines if ":" in line)}

    return {
        "intent":     parsed.get("intent", ""),
        "completion": parsed.get("completion", ""),
        "examples":   examples
    }


TOP_K      = 5

user_inputs = []
def cli_loop():
    print("🔧  Autocomplete CLI — type partial commands (Ctrl-D to quit)\n")
    try:
        while True:
            partial = input("› ").strip()
            if not partial:
                continue
            result = server_autocomplete(partial, user_histroy)
            user_inputs.append(partial)
            print(f"   intent     → {result['intent']}")
            print(f"   completion → {result['completion']}\n")

            final_cmd = result['completion'] or partial
            upsert_autocomplete(user_histroy, user_inputs, partial, final_cmd)
            user_inputs.append(final_cmd)
           
    except (EOFError, KeyboardInterrupt):
        print("\nbye!")

if __name__ == "__main__":
    initialize_app()       
    threading.Thread(target=cli_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
