## LeetCode Helper — What it is

A small helper that **learns what you usually do on LeetCode** and then:

* **Completes** the command you’re typing in the server’s command-line.
* **Tells** you what it thinks you want to do (“intent”).
* **Suggests skipping** the boring middle steps if you keep repeating the same workflow.

You run a tiny Flask server; a Chrome extension streams what you click and which network calls fire.  
Nothing is stored online except anonymous vectors in your own Pinecone account.

---

## How it works (in one minute)

1. **Browser side**  
   *A content script* watches every click / page change / `fetch` request and sends a short text description to your Flask server.

2. **Server side** (`app.py`)  
   * Keeps a rolling list of your last few actions.  
   * After each new action it stores  
     `last 3 steps  +  command-you-typed  →  next step`  
     as an embedding in Pinecone.
   * When you start typing a command in the CLI it:
     1. Finds similar **contexts** and **partials** in Pinecone.  
     2. Feeds those examples to GPT-4o.  
     3. Prints  
        ```
        intent     → submit solution
        completion → submit
        ```
     4. If lots of past examples end the same way it also prints  
        `⏩  You often end with “submit”. Skip 2 steps?`

---

### Tiny architecture sketch

```
Chrome tab      background.js            Flask server           Pinecone
(click, fetch) ───────────────► /monitor ───────────────► (vectors)
                                  ▲                ▲
                                  │ autocomplete   │ store patterns
                                  └────────────────┘
```

---

## How to use it

| Step | What to do |
|------|------------|
| **1. Clone & install** | ```bash<br>git clone …<br>cd server<br>python -m venv .venv && source .venv/bin/activate<br>pip install -r requirements.txt<br> Set OPEN_API_KEY and PINECONE_API_KEY in env varaibles` |
| **2. Load the extension** | Open `chrome://extensions` → “Load unpacked” → select the `predictor` folder. |
| **3. Open LeetCode** | Keep a tab open; the extension quietly logs your navigation. |
| **4. Use the CLI** | 'python app.py' to run the server, you can use this CLI to try to use the autocomplet and suggestions feature.
| **5. Repeat** | The more you use it, the smarter the completions become. |

*Prerequisites: Python 3.10+, Chrome, OpenAI & Pinecone API keys.*

---

### Change the defaults?

* `CTX_LEN` – how many recent steps define “context” (default 3).  
* `TOP_K` – how many neighbours to fetch from Pinecone (default 5).  
* `JOIN` – separator between steps (`" → "`).  

Open `app.py`, tweak the constants at the top, restart the server.
