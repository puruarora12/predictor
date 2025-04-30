# from pinecone import Pinecone
# from langchain.embeddings.openai import OpenAIEmbeddings
# # from langchain.vectorstores import Pinecone
# import json
# from typing import List, Optional

# pinecone = Pinecone(api_key="pcsk_4Qm7Kd_t7Jz8euNBS3VddRLGCaTTL6moRpDwW2xReppzB1gQbsFMbbhAgoMdF6DMx4itL")
# index ="user-actions"
# PREDICTION_MODE ='RAG'
# embedding_model = OpenAIEmbeddings() 


# class LogEvent():
#     user_id: str
#     event_type: str
#     details: dict
#     timestamp: Optional[float] = None

# # In-memory structures to maintain user history and graph
# user_histories: dict = {}   # user_id -> list of recent actions (as text descriptions)
# SEQ_PREFIX_LENGTH = 3       # number of past actions to use as context for vector storage (prefix length)
# next_id_counter: dict = {}  # user_id -> counter for event sequence IDs (for Pinecone IDs)

# # Graph and pattern predictor
# class GraphPredictor:
#     def __init__(self):
#         # transitions[user_id] maps a history tuple (last 1 or 2 actions) -> dict of next action -> count
#         self.transitions = {}
#         # sequence_counts[user_id] maps sequences (tuples of 2, 3, 4 actions) -> occurrence count for pattern detection
#         self.sequence_counts = {}
#         # discovered repetitive patterns (user_id -> list of patterns (tuples) that occurred frequently)
#         self.patterns = {}
    
#     def add_event(self, user: str, action: str):
#         """Add a new action to the graph for the given user, update transitions and sequence counts."""
#         if user not in self.transitions:
#             self.transitions[user] = {}
#             self.sequence_counts[user] = {}
#             self.patterns[user] = []
#         user_trans = self.transitions[user]
#         user_seq_counts = self.sequence_counts[user]
#         history = user_histories.get(user, [])
#         # Update transitions for last one-action and two-action states
#         if len(history) >= 2:
#             prev_action = history[-2]  # the action before the current one
#             # Update first-order transition (prev_action -> current action)
#             user_trans.setdefault((prev_action,), {})  # key as tuple for consistency
#             user_trans[(prev_action,)][action] = user_trans[(prev_action,)].get(action, 0) + 1
#             if len(history) >= 3:
#                 prev_two = (history[-3], history[-2])
#                 # Update second-order transition ((prev2, prev1) -> current)
#                 user_trans.setdefault(prev_two, {})
#                 user_trans[prev_two][action] = user_trans[prev_two].get(action, 0) + 1
#         elif len(history) == 1:
#             # If this is the first action (no previous), we might skip transition update 
#             # or handle an initial state. (Not much to predict from only one action in isolation.)
#             pass

#         # Update sequence occurrence counts for pattern detection (up to length 4)
#         seq_len = len(history)
#         # We consider sequences of length 2,3,4 that end with this new action
#         for L in range(2, 5):  # sequences of length 2, 3, 4
#             if seq_len >= L:
#                 seq_tuple = tuple(history[-L:])  # last L actions including current
#                 user_seq_counts[seq_tuple] = user_seq_counts.get(seq_tuple, 0) + 1
#                 # If a sequence repeats frequently (e.g., 3 or more times), mark it as a pattern
#                 if user_seq_counts[seq_tuple] == 3:  # threshold for pattern detection
#                     # Only add if not already noted
#                     if seq_tuple not in self.patterns[user]:
#                         self.patterns[user].append(seq_tuple)
    
#     def predict_next(self, user: str):
#         """Predict next action for the user using the transition graph. Returns (action, confidence)."""
#         if user not in self.transitions or user not in user_histories or len(user_histories[user]) == 0:
#             return None, 0.0
#         history = user_histories[user]
#         # Try using the last two actions (2nd order Markov) if available
#         action_prediction = None
#         confidence = 0.0
#         if len(history) >= 2:
#             prev_two = (history[-2], history[-1])
#             if prev_two in self.transitions[user]:
#                 next_counts = self.transitions[user][prev_two]
#                 # Choose the next action with highest count (probability)
#                 total = sum(next_counts.values())
#                 action_prediction = max(next_counts, key=next_counts.get)
#                 confidence = next_counts[action_prediction] / total if total > 0 else 0.0
#         # If no prediction from two-action state, fall back to last single action
#         if action_prediction is None or confidence == 0.0:
#             last_action = history[-1]
#             key = (last_action,)
#             if key in self.transitions[user]:
#                 next_counts = self.transitions[user][key]
#                 total = sum(next_counts.values())
#                 action_prediction = max(next_counts, key=next_counts.get)
#                 confidence = next_counts[action_prediction] / total if total > 0 else 0.0
#         return action_prediction, confidence
    
#     def predict_sequence(self, user: str) -> Optional[List[str]]:
#         """If a known multi-step pattern is detected in the user's recent actions, suggest the remaining steps."""
#         if user not in self.patterns or user not in user_histories:
#             return None
#         history = user_histories[user]
#         # Check each discovered pattern to see if the recent history is a prefix of that pattern
#         for pattern in self.patterns[user]:
#             if len(pattern) < 3:
#                 continue  # only consider patterns of length >=3
#             # If the user's recent actions (suffix) match the beginning of a pattern:
#             prefix_len = len(history)
#             # We consider the last `prefix_len` actions in the pattern
#             if prefix_len < len(pattern) and tuple(history) == pattern[:prefix_len]:
#                 remaining_steps = list(pattern[prefix_len:])  # steps remaining in the pattern
#                 if len(remaining_steps) > 1:
#                     # Suggest multiple remaining steps (automation suggestion)
#                     return remaining_steps
#                 # If only one step remains, it's just the next action (handled in predict_next typically)
#         return None

# # Instantiate the graph predictor
# graph_predictor = GraphPredictor()

# def format_event_description(event: LogEvent) -> str:
#     """Convert a LogEvent into a descriptive text string for logging/embedding."""
#     etype = event.event_type
#     details = event.details or {}
#     desc = ""
#     if etype == "network":
#         url = details.get("url", "")
#         method = details.get("method", "")
#         status = details.get("statusCode", "")
#         # Use endpoint path (e.g., remove domain for brevity)
#         try:
#             # strip protocol and domain from URL to get path
#             path = url.split("://", 1)[1]
#             path = path.split("/", 1)[1]  # remove domain portion
#         except Exception:
#             path = url
#         desc = f"API {method} {path} (status {status})"
#     elif etype == "click":
#         elem = details.get("element", "")
#         page = details.get("page", "")
#         desc = f"Clicked {elem} on page {page}"
#     elif etype == "typing":
#         field = details.get("field", "")
#         key = details.get("key", "")
#         text = details.get("current_text", "")
#         if key and len(key) == 1:
#             key_display = key  # single character
#         else:
#             key_display = f"[{key}]"
#         desc = f"Typed {key_display} in {field} (current text: '{text}')"
#     else:
#         # Fallback for any other event types
#         desc = f"{etype} event: {details}"
#     return desc

# @app.post("/log")
# def log_event(event: LogEvent):
#     """Log a user event (click, typing, network call, etc.), update models, and return next action prediction."""
#     user_id = event.user_id or "anonymous"
#     # Format the event into a descriptive string
#     desc = format_event_description(event)
#     # Append to user history
#     history = user_histories.get(user_id, [])
#     history.append(desc)
#     user_histories[user_id] = history
#     # Update the graph predictor with this new action
#     graph_predictor.add_event(user_id, desc)
#     # Update Pinecone vector store with recent sequence (for RAG)
#     try:
#         # Only index when we have at least SEQ_PREFIX_LENGTH previous actions to provide context
#         if len(history) >= SEQ_PREFIX_LENGTH + 1:
#             # Take the last SEQ_PREFIX_LENGTH actions *before* the current one as context
#             prefix_actions = history[-(SEQ_PREFIX_LENGTH+1):-1]  # sequence ending with the action before current
#             current_action = history[-1]  # the action just performed (to be used as 'next' in stored sequence)
#             prefix_text = " -> ".join(prefix_actions)
#             # Create a vector embedding for the prefix sequence
#             prefix_vector = embedding_model.embed_query(prefix_text)
#             # Upsert into Pinecone: use a unique ID, and store the 'next_action' in metadata
#             seq_id = next_id_counter.get(user_id, 0) + 1
#             next_id_counter[user_id] = seq_id
#             meta = {"user": user_id, "next_action": current_action, "prefix": prefix_actions}
#             index.upsert([(f"{user_id}-seq{seq_id}", prefix_vector, meta)])
#     except Exception as e:
#         print(f"Warning: Pinecone upsert failed: {e}")
#     # Determine next action prediction using selected mode
#     suggestion = None
#     confidence = 0.0
#     multi_step_suggestion = None
#     if PREDICTION_MODE.upper() == "RAG":
#         suggestion, confidence = predict_next_action_rag(user_id)
#     else:  # GRAPH mode
#         suggestion, confidence = graph_predictor.predict_next(user_id)
#     # Check for multi-step pattern suggestion (if a longer sequence can be automated)
#     multi = graph_predictor.predict_sequence(user_id)
#     if multi:
#         multi_step_suggestion = multi
#     return {
#         "suggestion": suggestion,
#         "confidence": confidence,
#         "multi_step": multi_step_suggestion
#     }

# def predict_next_action_rag(user_id: str):
#     """Predict the next action using Retrieval-Augmented Generation (LangChain + Pinecone + GPT)."""
#     if user_id not in user_histories or len(user_histories[user_id]) == 0:
#         return None, 0.0
#     # Formulate the query from the user's recent actions
#     recent_actions = user_histories[user_id]
#     # Use last SEQ_PREFIX_LENGTH actions as the context for querying similar sequences
#     if len(recent_actions) >= SEQ_PREFIX_LENGTH:
#         query_actions = recent_actions[-SEQ_PREFIX_LENGTH:]
#     else:
#         query_actions = recent_actions  # if history is short, use all of it
#     query_text = " -> ".join(query_actions)
#     # Embed the query and search Pinecone for similar past sequences (within the same user or across users if desired)
#     try:
#         query_vector = embedding_model.embed_query(query_text)
#         # Search Pinecone index for similar vectors
#         results = index.query(vector=query_vector, top_k=5, include_metadata=True,
#                                filter={"user": user_id})  # only search within this user's data
#     except Exception as e:
#         print(f"Pinecone query failed: {e}")
#         return None, 0.0
#     # Gather relevant past sequences from results
#     context_docs = []
#     next_actions = []
#     if results and "matches" in results:
#         for match in results["matches"]:
#             meta = match.get("metadata", {})
#             prefix = meta.get("prefix")
#             next_action = meta.get("next_action")
#             if prefix and next_action:
#                 # Construct a brief description of the sequence and its next action
#                 seq_desc = " -> ".join(prefix) + f" -> [Next: {next_action}]"
#                 context_docs.append(seq_desc)
#                 next_actions.append(next_action)
#     # If we found similar sequences, use them to predict; otherwise fall back to graph
#     if context_docs:
#         # Prepare a prompt for GPT with retrieved similar contexts
#         context_text = "\n".join(f"- {doc}" for doc in context_docs)
#         current_context = " -> ".join(query_actions)
#         prompt = (
#             "The user has recently performed the following actions:\n"
#             f"{current_context}\n\n"
#             "Based on similar past sequences of actions and their next steps listed below, "
#             "predict the user's next likely action:\n"
#             f"{context_text}\n\nNext likely action:"
#         )
#         try:
#             response = llm.predict(prompt)
#         except Exception as e:
#             print(f"LLM prediction error: {e}")
#             return None, 0.0
#         predicted_action = response.strip()
#         # Simple confidence estimate: if multiple retrieved sequences had the same next action, confidence is higher
#         confidence = 0.0
#         if next_actions:
#             from collections import Counter
#             freq = Counter(next_actions)
#             top_action, count = freq.most_common(1)[0]
#             if predicted_action and top_action.lower() in predicted_action.lower():
#                 confidence = count / len(next_actions)
#             else:
#                 confidence = count / len(next_actions) * 0.8  # a bit lower if GPT didn't pick the most common explicitly
#         return predicted_action, confidence
#     else:
#         # No similar context found in Pinecone, fallback to graph-based prediction
#         return graph_predictor.predict_next(user_id)























# NETWORK_LOG_FILE = 'network_logs.json'  # JSON Lines format

# def append_network_log(entry):
#     """Append a network event to the log file in JSON Lines format."""
#     try:
#         with open(NETWORK_LOG_FILE, 'a') as f:
#             json.dump(entry, f)
#             f.write('\n')
#             print("log saved")
#     except Exception as e:
#         print(f"Error saving network log: {e}")
