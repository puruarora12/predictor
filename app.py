# app.py - Flask API for LeetCode Helper

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import collections
import datetime
from pydantic import BaseModel
import time
from collections import defaultdict
import numpy as np
from langchain_community.llms import OpenAI
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore
from pinecone import Pinecone ,ServerlessSpec
# from utils import append_network_log
from typing import List, Optional

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome extension

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

PINECONE_API_KEY =  os.environ.get('PINECONE_API_KEY')
pinecone = Pinecone(api_key = PINECONE_API_KEY)
INDEX_NAME = "predict"


# Create index if not exists (using 1536 dimensions for OpenAI embeddings by default)
# print(pinecone.list_indexes()[0]['name'])
# if INDEX_NAME not in pinecone.list_indexes()[1]['name']:
#     pinecone.create_index(name=INDEX_NAME, dimension=3072, spec=ServerlessSpec(cloud="aws", region="us-east-1") )

# if 'pattern' not in pinecone.list_indexes()[1]['name']:
#     pinecone.create_index(name="pattern", dimension=3072, spec=ServerlessSpec(cloud="aws", region="us-east-1") )
        
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
    api_key=api_key ,
    # organization="...",
    # other params...
)
else:
    print("WARNING: OpenAI API key not found. LLM features will not work.")
def initialize_app():
    global llm
    

    
    # Initialize LangChain LLM
    
 
user_histroy = []

import uuid

def upsert_example(user_history: list[str], n: int = 4):
 
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
    # print(q)
    #  print(f"context: {context} \n")
    user_histroy.append(q)
    print("adding data to vector database")
    upsert_example(user_histroy)
    upsert_pattern_examples(user_histroy)

    llm_prediction = predict_with_llm(context)
    if llm_prediction:
        return jsonify({'prediction': llm_prediction})
    
    return jsonify({'prediction': None})


def retrieve_similar(history: list[str], n: int = 3, k: int = 5):
    """
    Embed the last n events and pull back k closest stored prefixes.
    Returns list[tuple[prefix(list[str]), next_action(str)]]
    """
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
    api_data = request.json
    
    # In a real implementation, this would execute the API call
    # Here we just simulate a successful response
    
    return jsonify({'status': 'success', 'result': 'API call executed'})


def predict_with_llm(context):
    """Use LLM to predict next action when ML is not confident"""
    remaining, conf = rag_pattern_completion(user_histroy)
    if remaining:
        return jsonify({
            "message": "skip to {remaining}",
            "confidence": conf,
            "action": remaining
    })
    
    time.sleep(2)
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
        if confidence < 0.7:  # Higher threshold for LLM
            return None
            
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


MAX_PAT_LEN = 6          # we care about patterns up to this length
MIN_SUFFIX  = 2          # only store if ≥2 steps remain
PAT_THRESH  = 3          # use freq for confidence later

def upsert_pattern_examples(history: list[str]):
    """
    For each completed session (or every new event, if you wish) push
    all substrings where   prefix + suffix = full pattern
    """
    n = len(history)
    for L in range(3, MAX_PAT_LEN + 1):               # full length 3-6
        if n >= L:
            full = history[-L:]                       # last L events
            for split in range(1, L - MIN_SUFFIX + 1):
                prefix = full[:split]                 # 1…L-2 actions
                suffix = full[split:]                 # ≥2 remaining
                vec    = embedding_model.embed_query(" → ".join(prefix))
                meta   = {"prefix": prefix,
                          "suffix": suffix,
                          "hits":   1}                # bump later
                pattern_index.upsert([(uuid.uuid4().hex, vec, meta)])

def retrieve_suffix_candidates(history, k=6, n=3):
    if len(history) < n: return []
    qvec = embedding_model.embed_query(" → ".join(history[-n:]))
    res  = index.query(vector = qvec, top_k=k, namespace= "pattern", include_metadata=True)
    cands = []
    for m in res.get("matches", []):
        meta = m["metadata"]
        # keep only if stored prefix is a *prefix* of live history
        if history[-len(meta["prefix"]):] == meta["prefix"]:
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

def rag_pattern_completion(history):
    cands = retrieve_suffix_candidates(history)
    if not cands: return None, 0.0

    lines = []
    for c in cands:
        lines.append(f"- {' → '.join(c['prefix'])}  =>  "
                     f"{' → '.join(c['suffix'])}  (seen {c.get('hits',1)}×)")
    recent = " → ".join(history[-3:])

    answer = pat_chain.run({"recent": recent,
                            "examples": "\n".join(lines)}).strip()
    remaining = [s.strip() for s in answer.split(",") if s.strip()]

    # crude confidence: majority of retrieved suffix[0]
    if cands:
        first_steps = [c["suffix"][0] for c in cands]
        freq = collections.Counter(first_steps)
        conf = freq.most_common(1)[0][1] / len(first_steps)
    else:
        conf = 0.3
    return remaining, conf



@app.route('/api/monitor/network', methods=['POST'])
def monitor_network():
    data = request.json
    data['timestamp'] = time.time()
    return jsonify({'status': 'success'})


# Initialize app data
initialize_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)