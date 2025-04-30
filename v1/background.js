class LeetCodeHelperBackend {
    constructor() {
        this.pythonBackendUrl = 'http://localhost:5000'; // Your Python backend
        this.activeConnections = {};
        this.setupMessageListeners();
    }

    setupMessageListeners() {
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            const tabId = sender.tab?.id;
            if (!tabId) return;

            switch (message.type) {
                case 'network_request':
                    this.handleNetworkRequest(message, tabId);
                    break;

                case 'user_interaction':
                    this.handleUserInteraction(message, tabId);
                    break;
            }

            return true; // for async messages
        });

        chrome.runtime.onConnect.addListener((port) => {
            if (port.name === 'leetcode-helperx') {
                const tabId = port.sender.tab?.id;
                if (!tabId) return;

                this.activeConnections[tabId] = port;

                port.onMessage.addListener((message) => {
                    this.handlePortMessage(message, port, tabId);
                });

                port.onDisconnect.addListener(() => {
                    delete this.activeConnections[tabId];
                });
            }
        });
    }

    handleNetworkRequest(request, tabId) {
        console.log(`[NETWORK] ${request.method} ${request.url}`);

        fetch(`${this.pythonBackendUrl}/api/monitor/network`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        })
        .then(response => response.json())
        .then(data => {
            console.log(`[NETWORK] Backend response:`, data);
            if (data.suggestion && this.activeConnections[tabId]) {
                this.activeConnections[tabId].postMessage(data.suggestion);
            }
        })
        .catch(error => console.error('Error sending network data:', error));
    }

    handleUserInteraction(interaction, tabId) {
        console.log(`[USER] Interaction:`, interaction);

        fetch(`${this.pythonBackendUrl}/api/monitor/interaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(interaction)
        })
        .then(response => response.json())
        .then(data => {
            console.log(`[USER] Backend response:`, data);
            if (data.suggestion && this.activeConnections[tabId]) {
                this.activeConnections[tabId].postMessage(data.suggestion);
            }

            // 🔥 Trigger prediction after any interaction
            this.triggerPredictionFromInteraction(tabId);
        })
        .catch(error => console.error('Error sending interaction data:', error));
    }

    handlePortMessage(message, port, tabId) {
        switch (message.type) {
            case 'autocomplete_request':
                this.handleAutocompleteRequest(message, port);
                break;

            case 'execute_api_call':
                this.executeApiCall(message, port);
                break;

            case 'save_automation':
                this.saveAutomation(message, tabId);
                break;
        }
    }

    handleAutocompleteRequest(request, port) {
        fetch(`${this.pythonBackendUrl}/api/autocomplete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ partial_command: request.partial_command })
        })
        .then(response => response.json())
        .then(data => {
            port.postMessage({
                type: 'autocomplete_suggestion',
                suggestion: data.suggestion,
                partial_command: request.partial_command
            });
        })
        .catch(error => console.error('Error getting autocomplete:', error));
    }

    executeApiCall(request, port) {
        fetch(`${this.pythonBackendUrl}/api/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        })
        .then(response => response.json())
        .then(data => {
            port.postMessage({
                type: 'api_response',
                result: data
            });
        })
        .catch(error => console.error('Error executing API call:', error));
    }

    saveAutomation(request, tabId) {
        fetch(`${this.pythonBackendUrl}/api/automation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sequence: request.sequence })
        })
        .then(response => response.json())
        .then(data => {
            console.log('Automation saved:', data);
        })
        .catch(error => console.error('Error saving automation:', error));
    }

    triggerPredictionFromInteraction(tabId) {
        chrome.scripting.executeScript({
            target: { tabId: tabId },
            func: () => ({
                url: window.location.href,
                path: window.location.pathname,
                title: document.title,
                focused_element: document.activeElement ? {
                    tag: document.activeElement.tagName.toLowerCase(),
                    id: document.activeElement.id,
                    classList: Array.from(document.activeElement.classList),
                    type: document.activeElement.type
                } : null
            })
        }, (results) => {
            if (chrome.runtime.lastError || !results || !results[0]) return;
            const context = results[0].result;
            this.requestPrediction(context, tabId);
        });
    }

    requestPrediction(context, tabId) {
        fetch(`${this.pythonBackendUrl}/api/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ context })
        })
        .then(response => response.json())
        .then(data => {
            console.log(`[PREDICTION]`, data);
            if (data.prediction && this.activeConnections[tabId]) {
                this.activeConnections[tabId].postMessage({
                    type: 'tab_suggestion',
                    message: data.prediction.message,
                    action: data.prediction.action
                });
            }
        })
        .catch(error => console.error('Error getting prediction:', error));
    }
}

// Init
const backend = new LeetCodeHelperBackend();

chrome.contextMenus.create({
    id: 'leetcode-helper',
    title: 'LeetCode Helper',
    contexts: ['all']
});

chrome.contextMenus.create({
    id: 'leetcode-helper-automate',
    parentId: 'leetcode-helper',
    title: 'Create automation from recent actions',
    contexts: ['all']
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === 'leetcode-helper-automate') {
        chrome.tabs.sendMessage(tab.id, {
            type: 'request_automation'
        });
    }
});

console.log("✅ LeetCode Helper background loaded.");
