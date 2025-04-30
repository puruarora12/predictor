class LeetCodeHelperUI {
    constructor() {
        this.suggestionActive = false;
        this.initUI();
        this.setupListeners();
        this.networkMonitor = new NetworkMonitor();
        this.interactionMonitor = new InteractionMonitor();

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
            padding: 5px 10px;
            border-radius: 3px;
            font-style: italic;
            display: none;
            z-index: 10000;
            pointer-events: none;
        `;
        document.body.appendChild(this.commandAutocomplete);
    }

    setupListeners() {
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Tab' && this.suggestionActive) {
                event.preventDefault();
                this.executeCurrentSuggestion();
            }
        });

        document.addEventListener('input', (event) => {
            const target = event.target;
            if (this.isCommandBar(target) && target.value.length >= 3) {
                this.requestAutocomplete(target);
            }
        });

        window.addEventListener('resize', () => {
            this.updateAutocompletePosition();
        });
    }

    isCommandBar(element) {
        return element.tagName === 'INPUT' && 
            (element.placeholder?.toLowerCase().includes('search') || 
            element.id?.includes('command') || 
            element.classList.contains('search-input'));
    }

    requestAutocomplete(inputElement) {
        const partialCommand = inputElement.value;
        if (this.port) {
            this.port.postMessage({
                type: 'autocomplete_request',
                partial_command: partialCommand
            });
        }
        this.currentInputElement = inputElement;
    }

    updateAutocompletePosition() {
        if (!this.currentInputElement || this.commandAutocomplete.style.display === 'none') return;

        const rect = this.currentInputElement.getBoundingClientRect();
        const cursorPosition = this.getCursorPosition(this.currentInputElement);

        this.commandAutocomplete.style.top = `${rect.bottom + 5}px`;
        this.commandAutocomplete.style.left = `${rect.left + cursorPosition.left}px`;
    }

    getCursorPosition(inputElement) {
        const textBeforeCursor = inputElement.value.substring(0, inputElement.selectionStart);
        const dummyElement = document.createElement('span');
        dummyElement.textContent = textBeforeCursor;

        try {
            const style = window.getComputedStyle(inputElement);
            dummyElement.style.cssText = `
                position: absolute;
                visibility: hidden;
                white-space: pre;
                font-family: ${style.fontFamily};
                font-size: ${style.fontSize};
            `;
        } catch {
            return { left: 0 };
        }

        document.body.appendChild(dummyElement);
        const width = dummyElement.getBoundingClientRect().width;
        document.body.removeChild(dummyElement);

        return { left: width };
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

        const displayText = suggestion.startsWith(partialCommand)
            ? suggestion.substring(partialCommand.length)
            : suggestion;

        this.commandAutocomplete.textContent = displayText;
        this.commandAutocomplete.style.display = 'block';
        this.updateAutocompletePosition();

        this.currentAutocomplete = suggestion;
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

    setupMessageHandlers() {
        this.port.onMessage.addListener((message) => {
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
  
  /* Immediately boot UI (rest of your file remains unchanged) */
  new LeetCodeHelperUI();