/* MCN website — theme toggle, copy buttons and a small MCN syntax highlighter.
   Shared by the landing page and the docs app; no dependencies. */
(function () {
  "use strict";

  // ── Theme ──────────────────────────────────────────────────────────────
  var KEY = "mcn-theme";
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function apply(theme) {
    if (theme) document.documentElement.setAttribute("data-theme", theme);
    else document.documentElement.removeAttribute("data-theme");
  }
  apply(stored());
  function currentTheme() {
    var t = document.documentElement.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function toggleTheme() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    apply(next);
    try { localStorage.setItem(KEY, next); } catch (e) { /* private mode */ }
  }

  // ── MCN highlighter ────────────────────────────────────────────────────
  var KEYWORDS = ("var function return if else for in while break continue try catch finally throw " +
    "and or not true false null use test assert service endpoint port component state on render app " +
    "title theme layout tabs tab sidebar nav main routes route pipeline stage workflow step contract " +
    "prompt agent task await schedule event include").split(" ");
  var DECL = { "function": 1, "service": 1, "endpoint": 1, "component": 1, "app": 1, "pipeline": 1,
               "stage": 1, "workflow": 1, "step": 1, "contract": 1, "prompt": 1, "agent": 1 };
  var KW = {}; KEYWORDS.forEach(function (k) { KW[k] = 1; });

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  function highlightMCN(src) {
    var out = "", i = 0, n = src.length, expectDecl = false;
    while (i < n) {
      var c = src[i], rest = src.slice(i), m;
      if (c === "/" && src[i + 1] === "/") {
        m = rest.match(/^\/\/[^\n]*/); out += '<span class="tok-com">' + esc(m[0]) + "</span>"; i += m[0].length; continue;
      }
      if (c === "#" && (i === 0 || src[i - 1] === "\n" || /\s/.test(src[i - 1]))) {
        m = rest.match(/^#[^\n]*/); out += '<span class="tok-com">' + esc(m[0]) + "</span>"; i += m[0].length; continue;
      }
      if (rest.startsWith('"""')) {
        var end = src.indexOf('"""', i + 3); end = end < 0 ? n : end + 3;
        out += '<span class="tok-str">' + esc(src.slice(i, end)) + "</span>"; i = end; continue;
      }
      if (c === '"' || c === "'") {
        m = rest.match(c === '"' ? /^"(?:[^"\\\n]|\\.)*"?/ : /^'(?:[^'\\\n]|\\.)*'?/);
        out += '<span class="tok-str">' + esc(m[0]) + "</span>"; i += m[0].length; continue;
      }
      if (/[0-9]/.test(c) && !/[A-Za-z_]/.test(src[i - 1] || "")) {
        m = rest.match(/^\d+(\.\d+)?/); out += '<span class="tok-num">' + m[0] + "</span>"; i += m[0].length; continue;
      }
      if (/[A-Za-z_]/.test(c)) {
        m = rest.match(/^[A-Za-z_][A-Za-z0-9_]*/); var w = m[0]; i += w.length;
        var prev = src.slice(0, i - w.length).replace(/[ \t]+$/, "").slice(-1);
        if (expectDecl) { out += '<span class="tok-decl">' + w + "</span>"; expectDecl = false; continue; }
        if (KW[w] && prev !== ".") { out += '<span class="tok-kw">' + w + "</span>"; expectDecl = !!DECL[w]; continue; }
        if (src[i] === "(") { out += '<span class="tok-fn">' + w + "</span>"; continue; }
        out += w; continue;
      }
      if (c === "\n") expectDecl = false;
      out += esc(c); i++;
    }
    return out;
  }

  // Error reports and shell sessions get light colouring too
  function highlightOutput(src) {
    return esc(src).split("\n").map(function (line) {
      if (/^(Syntax|Name|Runtime|Type) error\b/.test(line)) return '<span class="tok-err">' + line + "</span>";
      if (/^Hint:/.test(line)) return '<span class="tok-ok">' + line + "</span>";
      if (/^\s*\d* \|/.test(line)) return '<span class="tok-dim">' + line + "</span>";
      return line;
    }).join("\n");
  }
  function highlightShell(src) {
    return esc(src).split("\n").map(function (line) {
      if (/^\s*#/.test(line)) return '<span class="tok-com">' + line + "</span>";
      return line.replace(/(\s#\s.*)$/, '<span class="tok-com">$1</span>')
                 .replace(/^(\s*)(mcn|pip|cd|git|python3?|npm|flutter|export|curl)\b/, '$1<span class="tok-fn">$2</span>');
    }).join("\n");
  }

  function highlight(code, lang) {
    if (lang === "mcn") return highlightMCN(code);
    if (lang === "bash" || lang === "sh" || lang === "shell") return highlightShell(code);
    if (lang === "output" || lang === "text") return highlightOutput(code);
    return esc(code);
  }

  var COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';

  function copyText(text, btn) {
    var done = function () { var t = btn.innerHTML; btn.textContent = "Copied"; setTimeout(function () { btn.innerHTML = t; }, 1400); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () {});
    else {
      var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done(); } catch (e) { /* ignore */ } ta.remove();
    }
  }

  /** Turn every <pre><code class="language-x"> into a highlighted block with a copy button. */
  function enhanceCode(root) {
    (root || document).querySelectorAll("pre > code").forEach(function (codeEl) {
      var pre = codeEl.parentElement;
      if (pre.parentElement && pre.parentElement.classList.contains("code")) return;
      var lang = ((codeEl.className.match(/language-(\w+)/) || [])[1] || "").toLowerCase();
      var raw = codeEl.textContent.replace(/\n$/, "");
      codeEl.innerHTML = highlight(raw, lang);
      var wrap = document.createElement("div"); wrap.className = "code";
      var head = document.createElement("div"); head.className = "code-head";
      var label = { mcn: "MCN", bash: "Terminal", output: "Output", json: "JSON", text: "Text" }[lang] || lang.toUpperCase() || "Code";
      head.innerHTML = "<span>" + label + "</span>";
      var btn = document.createElement("button"); btn.className = "copy-btn"; btn.type = "button";
      btn.innerHTML = COPY_ICON + "Copy"; btn.setAttribute("aria-label", "Copy code");
      btn.addEventListener("click", function () { copyText(raw, btn); });
      head.appendChild(btn);
      pre.parentElement.insertBefore(wrap, pre); wrap.appendChild(head); wrap.appendChild(pre);
    });
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-theme-toggle]");
    if (t) toggleTheme();
    var c = e.target.closest && e.target.closest("[data-copy]");
    if (c) copyText(c.getAttribute("data-copy"), c);
  });

  window.MCNSite = { highlight: highlight, enhanceCode: enhanceCode, copyText: copyText };
})();
