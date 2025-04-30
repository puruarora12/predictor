# app.py - Flask API for LeetCode Helper

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
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

# Global variables
USER_DATA_FILE = 'user_data.json'
ML_MODEL_FILE = 'leetcode_prediction_model.pkl'
user_data = None
ml_model = None
feature_encoder = None
llm = True
PREDICTION_MODE = 'RAG'
NETWORK_LOG_FILE = 'network_logs.json'  # JSON Lines format
embedding_model = OpenAIEmbeddings()


pinecone = Pinecone(api_key = PINECONE_API_KEY)
INDEX_NAME = "user-actions"

# Global structures
# user_data = []
next_id_counter = 0
transitions = {}  # (prev1, prev2) -> next_action -> count
sequence_counts = {}  # full tuple -> count
patterns = []

# Create index if not exists (using 1536 dimensions for OpenAI embeddings by default)
# print(pinecone.list_indexes()[0]['name'])
if INDEX_NAME not in pinecone.list_indexes()[0]['name']:
    pinecone.create_index(name=INDEX_NAME, dimension=1536, spec=ServerlessSpec(cloud="aws", region="us-east-1") )
        
index = pinecone.Index(INDEX_NAME)

def append_network_log(entry):
    """Append a network event to the log file in JSON Lines format."""
    try:
        with open(NETWORK_LOG_FILE, 'a') as f:
            json.dump(entry, f)
            f.write('\n')
            print("log saved")
    except Exception as e:
        print(f"Error saving network log: {e}")

def initialize_app():
    global user_data, ml_model, feature_encoder, llm
    
    # Load user data if exists
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            user_data = json.load(f)
    else:
        user_data = {
            "interaction_history": [],
            "network_requests": [],
            "action_patterns": {},
            "contest_participation": [],
            "automations": []
        }
    
    # Initialize LangChain LLM
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        # base_url="...",
        # organization="...",
        # other params...
    )
    else:
        print("WARNING: OpenAI API key not found. LLM features will not work.")


    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vector_store = InMemoryVectorStore(embeddings)
 
user_histroy = []
    
def format(data):
    s  = f" type: { data['type']}, action: {data['action']}, pagee : {data['page']}, type: {data['type']}, href: {data['href']}  "


@app.route('/api/monitor/interaction', methods=['POST'])
def monitor_interaction():
    data = request.json
    print(f"data : {data} \n")
    # Add timestamp
    data['timestamp'] = time.time()
    
    # Store interaction
    append_network_log(data)
    # user_histroy.append(format(data))
    # print(user_data['interaction_history'][-1])
  
    return jsonify({'status': 'success'})



@app.route('/api/predict', methods=['POST'])
def predict():
    context = request.json.get('context')
    # f = user_histroy[-1]
    # f = f+ f"title: {context['title']} , url: {context['url']}"
    # user_histroy[-1]=f
    # print("f ",f,"\m")
    print(f"context: {context} \n")
    if not context:
        return jsonify({'prediction': None})

    llm_prediction = predict_with_llm(context)
    if llm_prediction:
        return jsonify({'prediction': llm_prediction})
    
    # If both fail, return none
    return jsonify({'prediction': None})

@app.route('/api/execute', methods=['POST'])
def execute_api():
    api_data = request.json
    
    # In a real implementation, this would execute the API call
    # Here we just simulate a successful response
    
    return jsonify({'status': 'success', 'result': 'API call executed'})


def predict_with_llm(context):
    """Use LLM to predict next action when ML is not confident"""
    if not llm:
        return None
    
    # Extract recent interactions
    recent_interactions = user_data['interaction_history'][-10:] if len(user_data['interaction_history']) > 10 else user_data['interaction_history']
    recent_requests = user_data['network_requests'][-5:] if len(user_data['network_requests']) > 5 else user_data['network_requests']
    
    # Format the patterns for the prompt
    patterns_list = []
    for k, v in user_data['action_patterns'].items():
        if v['count'] > 2:  # Only include relatively common patterns
            next_actions = ", ".join([f"{action}({count} times)" for action, count in v['next_actions'].items() if count > 1])
            patterns_list.append(f"Sequence '{k}' occurs {v['count']} times, leading to: {next_actions}")
    
    formatted_patterns = "\n".join(patterns_list)
    
    template = ("""
    Given the following user interactions and network requests on LeetCode, predict the next action the user is likely to take:
    
    Current page: {current_page}
    Current element focus: {current_element}
    
    Recent interactions:
    {recent_interactions}
    
    Recent network requests:
    {recent_requests}
    
    Common patterns for this user:
    {patterns}
    
    Based on this information, what is the most likely next action the user will take?
   
    Respond with ONLY these three lines (no explanations and no extra text):
    1. Action :The predicted action (What the user is going to do next based on previous interactions) 
    2. Score :A confidence score between 0 and 1 
    3. URL: The corresponding URL or API endpoint if applicable
    """,    
            context.get('path', ''),
            json.dumps(context.get('focused_element', {})),
            json.dumps(recent_interactions[-3:], indent=2),
            json.dumps(recent_requests[-2:], indent=2),
            formatted_patterns
            )
    
    prompt = ChatPromptTemplate.from_messages( 
        [("system" ,'''Given the following user interactions and network requests on LeetCode, predict the next action the user is likely to take:
    
    Current page: {current_page}
    Current element focus: {current_element}
    
    Recent interactions:
    {recent_interactions}
    
    Recent network requests:
    {recent_requests}
    
    Common patterns for this user:
    {patterns}
    
    Based on this information, what is the most likely next action the user will take?
    Respond with answer without any explanations and the format should be like this
                action: "The action user might do",
                Confidence : "Confidence in the action to be performed",
                URL : "corrsponding URL or API Endpoint"
                ''')
        ]
            )
    # print(prompt)
    chain = prompt | llm
    # print(chain)
    try:
        result = chain.invoke({
            "current_page": context.get('path', ''),
            "current_element": json.dumps(context.get('focused_element', {})),
            "recent_interactions": json.dumps(recent_interactions[-3:], indent=2),
            "recent_requests": json.dumps(recent_requests[-2:], indent=2),
            "patterns": formatted_patterns
        })
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
            'message': f"Press Tab to {action}",
            'confidence': confidence,
            'action': {
                'url': endpoint if endpoint and endpoint.startswith('http') else None,
                'api': endpoint if endpoint and not endpoint.startswith('http') else None
            }
        }
        
    except Exception as e:
        print(f"Error in LLM prediction: {e}")
        return None


@app.route('/api/monitor/network', methods=['POST'])
def monitor_network():
    data = request.json
    data['timestamp'] = time.time()
    user_data['network_requests'].append(data)
    append_network_log(data)
    return jsonify({'status': 'success'})


# Initialize app data
initialize_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)