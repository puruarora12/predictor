# LeetCode Helper - AI-Powered Productivity Enhancement

## Overview

LeetCode Helper is a Chrome extension that monitors your interactions within the LeetCode platform and uses machine learning to predict your next actions. By offering timely suggestions via a minimally invasive "Press Tab" UI, the extension helps reduce friction and saves you valuable time when solving coding problems.

## Features

### 1. Tab Suggestions
- Predicts your next action based on interaction patterns
- Shows a subtle overlay with "Press Tab to [action]" when confidence is high
- Automatically executes the action when Tab is pressed

### 2. Command Bar Autocomplete
- Monitors what you type in search/command bars
- Suggests completions based on your past searches and common patterns
- Uses LLM to generate context-aware suggestions even for new queries

### 3. Automation Detection
- Identifies repetitive sequences of actions you perform
- Offers to automate these sequences for future use
- Creates shortcuts for multi-step processes you commonly use

### 4. Contest Reminders
- Learns your contest participation patterns
- Reminds you of upcoming contests at your preferred times
- Gets smarter over time by analyzing when you actually participate

## Technical Architecture

The solution consists of three main components:

1. **Chrome Extension**:
   - Content Script: Injects UI overlay and monitors user interactions
   - Background Script: Processes data and communicates with backend
   - Popup UI: Provides user-configurable settings and stats

2. **Python Backend**:
   - Flask API: Processes requests from the extension
   - Machine Learning: RandomForest classifier for action prediction
   - LangChain + OpenAI: Advanced LLM-based predictions and autocomplete
   - User Data Store: Persistent storage of interaction patterns

3. **Prediction System**:
   - Hybrid approach combining traditional ML with LLM capabilities
   - Confidence-based suggestion surfacing
   - Continuous learning from user feedback

## Implementation Details

### Data Collection

The extension monitors:
- Network requests (API calls)
- UI interactions (clicks, form submissions)
- Page navigation events
- Timing patterns (when certain actions are performed)

### ML Prediction Pipeline

1. **Feature Extraction**:
   - Recent sequence of actions
   - Current page context
   - Focused element information
   - Historical patterns

2. **Prediction Models**:
   - Primary: RandomForest classifier trained on user data
   - Backup: LLM-based prediction for novel situations
   - Confidence thresholds to ensure high-quality suggestions

3. **Action Execution**:
   - Mapping predictions to executable actions
   - Handling navigation, form submissions, and API calls

### Extensibility

The architecture is designed to be extensible:
- New prediction features can be added without changing the core system
- Different SaaS applications could be supported with minimal changes
- The ML models can be swapped or enhanced as needed

## Future Improvements

1. **Enhanced UI Integration**:
   - More native-feeling suggestions integrated into LeetCode's UI
   - Keyboard shortcut customization

2. **Advanced ML Capabilities**:
   - Incorporate transformer-based models for sequence prediction
   - Add reinforcement learning from user feedback
   - Implement collaborative filtering using anonymized pattern data

3. **Expanded Feature Set**:
   - Code template suggestions based on problem type
   - Time management recommendations
   - Integration with other development tools

4. **Scalability**:
   - Cloud-based backend for multi-user support
   - Efficient data storage for years of interaction history
   - Privacy-preserving federated learning

## Installation and Setup

1. Clone the repository
2. Set up the Python backend:
   ```
   pip install -r requirements.txt
   export OPENAI_API_KEY="your_api_key_here"
   python app.py
   ```
3. Load the Chrome extension:
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable Developer Mode
   - Click "Load unpacked" and select the extension directory

## Usage

1. Navigate to LeetCode and use the platform as normal
2. Watch for the subtle "Press Tab" suggestions
3. When you see a suggestion that matches your intent, press Tab
4. The extension will automatically execute the action for you
5. Access settings via the extension icon in Chrome's toolbar

