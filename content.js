(function pinCommandBar() {
  const style = document.createElement('style');
  style.id = 'leetcode-helper-sticky-bar';
  style.textContent = `
    /* stick LeetCode’s global header + command bar */
    header[data-cy="header"] {
      position: sticky !important;
      top: 0;
      z-index: 10050 !important;  /* above overlay, but below DevTools */
      box-shadow: 0 1px 3px rgba(0,0,0,.12);
    }
  `;
  document.head.appendChild(style);
})();
class LeetCodeHelperUI {
  constructor() {
      this.suggestionActive = false;
      this.initUI();
      this.setupListeners();
      this.networkMonitor = new NetworkMonitor();
      this.interactionMonitor = new InteractionMonitor();
      this.debug = true;
      this.commandHistory = []; // Store recent command history
      // Connect to background.js
      this.port = chrome.runtime.connect({ name: "leetcode-helperx" });
      this.setupMessageHandlers();
  }
 
  
  initUI() {
      // Suggestion overlay
      this.overlay = document.createElement('div');
      this.overlay.className = 'leetcode-helper-overlay';
      this.overlay.style.cssText = `
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: rgba(50, 50, 50, 0.8);
          color: white;
          padding: 10px 15px;
          border-radius: 5px;
          font-family: 'Arial', sans-serif;
          font-size: 14px;
          z-index: 10000;
          display: none;
          align-items: center;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
          backdrop-filter: blur(5px);
          border: 1px solid rgba(255, 255, 255, 0.1);
          transition: all 0.3s ease;
      `;

      this.tabIcon = document.createElement('span');
      this.tabIcon.textContent = '⇥';
      this.tabIcon.style.cssText = `font-weight: bold; margin-right: 8px; font-size: 16px;`;

      this.messageText = document.createElement('span');
      this.messageText.textContent = '';

      this.overlay.appendChild(this.tabIcon);
      this.overlay.appendChild(this.messageText);
      document.body.appendChild(this.overlay);

      // Autocomplete suggestion UI
      this.commandAutocomplete = document.createElement('div');
      this.commandAutocomplete.className = 'leetcode-helper-autocomplete';
      this.commandAutocomplete.style.cssText = `
          position: absolute;
          background: rgba(40, 40, 40, 0.95);
          color: #ccc;
          padding: 8px 12px;
          border-radius: 4px;
          font-style: italic;
          display: none;
          z-index: 99999;
          pointer-events: none;
          border: 1px solid #888;
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
      `;
      document.body.appendChild(this.commandAutocomplete);
  }

  setupListeners() {
      document.addEventListener('keydown', (event) => {
          // Tab to execute suggestions
          if (event.key === 'Tab' && this.suggestionActive) {
              event.preventDefault();
              this.executeCurrentSuggestion();
          }
          
          // Tab to complete autocomplete in input fields
          if (event.key === 'Tab' && this.currentAutocomplete && this.currentInputElement) {
              event.preventDefault();
              this.applyAutocomplete();
          }
      });

      // Enhanced input event handling
      document.addEventListener('input', (event) => {
          const target = event.target;
          
          // Log all input events if debugging
          if (this.debug && target.tagName === 'INPUT') {
              console.log('Input event:', {
                  element: target,
                  value: target.value,
                  isCommandBar: this.isCommandBar(target)
              });
          }
          
          if (this.isCommandBar(target) && target.value.length >= 2) {
              this.requestAutocomplete(target);
              
              // Add to command history on space or punctuation
              if (target.value.endsWith(' ') || target.value.endsWith('.')) {
                  this.addToCommandHistory(target.value.trim());
              }
          } else if (this.currentInputElement === target) {
              // Hide suggestions if input is too short
              this.hideAutocomplete();
          }
      });

      // Add focus event to capture command bars when focused
      document.addEventListener('focusin', (event) => {
          const target = event.target;
          if (this.isCommandBar(target) && target.value.length >= 2) {
              this.requestAutocomplete(target);
          }
      });

      // Capture command submissions to store in history
      document.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' && this.isCommandBar(event.target)) {
              this.addToCommandHistory(event.target.value.trim());
          }
      });
      
      window.addEventListener('resize', () => {
          this.updateAutocompletePosition();
      });
  }

  // Enhanced command bar detection
  isCommandBar(element) {
      if (!element || element.tagName !== 'INPUT') return false;
      
      // More comprehensive detection of command/search inputs
      return (
          // Check placeholder text
          element.placeholder?.toLowerCase().includes('search') || 
          element.placeholder?.toLowerCase().includes('command') ||
          element.placeholder?.toLowerCase().includes('type') ||
          
          // Check ID and class attributes
          element.id?.toLowerCase().includes('command') || 
          element.id?.toLowerCase().includes('search') ||
          element.classList.contains('search-input') ||
          element.classList.contains('command-input') ||
          
          // Check aria attributes
          element.getAttribute('aria-label')?.toLowerCase().includes('search') ||
          element.getAttribute('role')?.toLowerCase() === 'searchbox' ||
          
          // Check parent containers
          element.closest('form')?.classList.contains('search') ||
          element.closest('div')?.classList.contains('search-container') ||
          element.closest('[role="search"]') !== null ||
          
          // Check for common LeetCode-specific classes
          element.classList.contains('command-bar') ||
          element.classList.contains('filter-input') ||
          
          // Check if element has autocomplete attribute
          element.getAttribute('autocomplete') === 'off' &&
          (element.type === 'text' || element.type === 'search')
      );
  }

  addToCommandHistory(command) {
      if (!command || command.length < 2) return;
      
      // Add to local history
      if (!this.commandHistory.includes(command)) {
          this.commandHistory.unshift(command);
          this.commandHistory = this.commandHistory.slice(0, 20); // Keep last 20 commands
      }
      
      // Send to backend to store in vector DB
      if (this.port) {
          this.port.postMessage({
              type: 'store_command',
              command: command
          });
      }
      
      console.log('Command added to history:', command);
  }

  updateAutocompletePosition() {
      if (!this.currentInputElement || this.commandAutocomplete.style.display === 'none') return;

      const rect = this.currentInputElement.getBoundingClientRect();
      
      // Position below the input
      this.commandAutocomplete.style.top = `${rect.bottom + 5}px`;
      this.commandAutocomplete.style.left = `${rect.left}px`;
      this.commandAutocomplete.style.width = `${Math.max(rect.width, 200)}px`;
      
      if (this.debug) {
          console.log('Autocomplete positioned at:', {
              top: this.commandAutocomplete.style.top,
              left: this.commandAutocomplete.style.left,
              width: this.commandAutocomplete.style.width
          });
      }
  }

  requestAutocomplete(inputElement) {
      const partialCommand = inputElement.value.trim();
      
      if (this.debug) {
          console.log('Autocomplete request:', {
              element: inputElement,
              value: partialCommand
          });
      }
      
      if (this.port) {
          this.port.postMessage({
              type: 'autocomplete_request',
              partial_command: partialCommand
          });
      }
      
      this.currentInputElement = inputElement;
  }

  applyAutocomplete() {
      if (!this.currentInputElement || !this.currentAutocomplete) return;
      
      const partialCommand = this.currentInputElement.value;
      const completion = this.currentAutocomplete;
      
      // Only apply if it's a completion of the current text
      if (completion.startsWith(partialCommand)) {
          this.currentInputElement.value = completion;
          this.currentInputElement.dispatchEvent(new Event('input', { bubbles: true }));
          this.hideAutocomplete();
          
          // Move cursor to end
          this.currentInputElement.selectionStart = completion.length;
          this.currentInputElement.selectionEnd = completion.length;
      }
  }

  showSuggestion(message, action) {
      this.messageText.textContent = message;
      this.currentAction = action;
      this.overlay.style.display = 'flex';
      this.suggestionActive = true;

      clearTimeout(this.hideTimeout);
      this.hideTimeout = setTimeout(() => this.hideSuggestion(), 8000);
  }

  hideSuggestion() {
      this.overlay.style.display = 'none';
      this.suggestionActive = false;
      this.currentAction = null;
      clearTimeout(this.hideTimeout);
  }

  showAutocomplete(suggestion, partialCommand) {
      if (!this.currentInputElement) return;

      // Handle case where suggestion is the same as input
      if (suggestion === partialCommand) {
          this.hideAutocomplete();
          return;
      }

      // Show the completion part in gray
      const displayText = suggestion.startsWith(partialCommand)
          ? partialCommand + suggestion.substring(partialCommand.length)
          : suggestion;

      this.commandAutocomplete.innerHTML = displayText
          .replace(partialCommand, `<span style="color: white; font-weight: bold;">${partialCommand}</span>`)
          + '<span style="margin-left: 8px; font-size: 12px; opacity: 0.7;">[Tab]</span>';
          
      this.commandAutocomplete.style.display = 'block';
      this.updateAutocompletePosition();

      this.currentAutocomplete = suggestion;
      
      if (this.debug) {
          console.log('Showing autocomplete:', {
              input: partialCommand,
              suggestion: suggestion,
              display: displayText
          });
      }
  }

  hideAutocomplete() {
      this.commandAutocomplete.style.display = 'none';
      this.currentAutocomplete = null;
  }

  executeCurrentSuggestion() {
      if (!this.suggestionActive || !this.currentAction) return;

      if (this.currentAction.url) {
          window.location.href = this.currentAction.url;
      } else if (this.currentAction.function) {
          this.currentAction.function();
      } else if (this.currentAction.api && this.port) {
          this.port.postMessage({
              type: 'execute_api_call',
              api: this.currentAction.api,
              method: this.currentAction.method || 'GET',
              data: this.currentAction.data || {}
          });
      }

      this.hideSuggestion();
  }

  // Enhance the setupMessageHandlers method to add more debugging
  setupMessageHandlers() {
      this.port.onMessage.addListener((message) => {
          if (this.debug) {
              console.log('Received message from background:', message);
          }
          
          switch (message.type) {
              case 'tab_suggestion':
                  this.showSuggestion(message.message, message.action);
                  break;
              case 'autocomplete_suggestion':
                  if (message.suggestion && this.currentInputElement) {
                      this.showAutocomplete(message.suggestion, message.partial_command);
                  } else {
                      this.hideAutocomplete();
                  }
                  break;
              case 'automation_suggestion':
                  this.showSuggestion(message.message, {
                      function: () => this.confirmAutomation(message.sequence)
                  });
                  break;
              case 'api_response':
                  console.log('API call completed:', message.result);
                  break;
          }
      });
  }

  confirmAutomation(sequence) {
      const confirmed = confirm(`Create automation for these ${sequence.length} steps?\n\n${sequence.join(' → ')}`);
      if (confirmed && this.port) {
          this.port.postMessage({
              type: 'save_automation',
              sequence: sequence
          });
          alert('Automation saved!');
      }
  }
}

class NetworkMonitor {
  constructor() {
    this.setupFetchInterceptor();
  }

  setupFetchInterceptor() {
    if (window._leetcodeFetchWrapped) return;
    window._leetcodeFetchWrapped = true;

    const originalFetch = window.fetch;

    window.fetch = function (...args) {
      const startTime = performance.now();
      const url      = args[0];
      const opts     = args[1] || {};
      const method   = opts.method || 'GET';
      const body     = opts.body   || null;
      const headers  = opts.headers|| {};

      /* keep your prints */
      console.log('[FETCH-OUT]', method, url);

      return originalFetch.apply(this, args)
        .then(async (res) => {
          const endTime = performance.now();
          const timeMs  = endTime - startTime;
          let json      = null;

          try {
            const ct = res.headers.get('content-type') || '';
            if (ct.includes('application/json')) json = await res.clone().json();
          } catch (e) { /* swallow */ }

          console.log('[FETCH-IN ]', res.status, url, 'in', timeMs.toFixed(1), 'ms');

          chrome.runtime.sendMessage({
            type           : 'network_request',
            url            : url,
            method         : method,
            status         : res.status,
            response_time  : timeMs,
            request_headers: headers,
            request_body   : body,
            response       : json
          });

          return res;
        })
        .catch((err) => {
          console.error('[FETCH-ERR]', method, url, err);
          chrome.runtime.sendMessage({
            type          : 'network_request',
            url           : url,
            method        : method,
            status        : 'NETWORK_ERROR',
            response_time : performance.now() - startTime,
            error         : err.message || 'unknown'
          });
          throw err;
        });
    };
  }
}

class InteractionMonitor {
  constructor() {
    this.currentPage = window.location.pathname;
    this.setupListeners();
    this.logPageView();
  }

  /* helper: walk up to first actionable ancestor */
  findClickable(el) {
    while (el && el !== document.body) {
      if (
        el.tagName === 'BUTTON' ||
        el.tagName === 'A'      ||
        (el.tagName === 'INPUT' && /button|submit/i.test(el.type)) ||
        el.getAttribute('role') === 'button' ||
        typeof el.onclick === 'function'
      ) return el;
      el = el.parentElement;
    }
    return el || document.body;
  }

  /* helper: unique-ish selector */
  cssPath(el) {
    if (!el || el === document.body) return 'body';
    const segs = [];
    while (el && el !== document.body) {
      let tag = el.tagName.toLowerCase();
      if (el.id) { segs.unshift(`${tag}#${el.id}`); break; }
      const sibs = [...el.parentNode.children].filter(n => n.tagName === el.tagName);
      if (sibs.length > 1) {
        const idx = sibs.indexOf(el) + 1;
        tag += `:nth-of-type(${idx})`;
      }
      segs.unshift(tag);
      el = el.parentElement;
    }
    return segs.join(' > ');
  }

  getElementInfo(el, clickEvt) {
    const outer = el.outerHTML ? el.outerHTML.slice(0, 160) + '…' : '';
    return {
      tag       : el.tagName?.toLowerCase() || '',
      id        : el.id || '',
      classList : Array.from(el.classList || []),
      type      : el.getAttribute?.('type')  || '',
      name      : el.getAttribute?.('name')  || '',
      href      : el.getAttribute?.('href')  || '',
      selector  : this.cssPath(el),
      outerHTML : outer,
      coords    : clickEvt ? { x: clickEvt.clientX, y: clickEvt.clientY } : null,
      text      : (el.textContent || '').trim().slice(0, 80)
    };
  }

  setupListeners() {
    /* clicks */
    document.addEventListener('click', (e) => {
      const target = this.findClickable(e.target);
      chrome.runtime.sendMessage({
        type   : 'user_interaction',
        action : 'click',
        page   : window.location.pathname,
        element: this.getElementInfo(target, e)
      });
    });

    /* form submits */
    document.addEventListener('submit', (e) => {
      const form = e.target;
      chrome.runtime.sendMessage({
        type   : 'user_interaction',
        action : 'submit',
        page   : window.location.pathname,
        element: {
          tag   : 'form',
          id    : form.id,
          action: form.action,
          method: form.method
        }
      });
    });

    /* SPA navigation */
    const push = history.pushState;
    history.pushState = function (...args) {
      const r = push.apply(this, args);
      window.dispatchEvent(new Event('locationchange'));
      return r;
    };
    window.addEventListener('popstate', () => window.dispatchEvent(new Event('locationchange')));
    window.addEventListener('locationchange', () => {
      const newPage = window.location.pathname;
      if (newPage !== this.currentPage) {
        this.currentPage = newPage;
        this.logPageView();
      }
    });
  }

  logPageView() {
    chrome.runtime.sendMessage({
      type   : 'user_interaction',
      action : 'view',
      page   : this.currentPage,
      element: 'page'
    });
  }
}

/* Immediately boot UI */
new LeetCodeHelperUI();