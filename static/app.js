(function(){
  const $ = (sel) => document.querySelector(sel);

  const tabChat = $("#tabChat");
  const tabCheck = $("#tabCheck");
  const chatPanel = $("#chatPanel");
  const checkPanel = $("#checkPanel");

  const chatLog = $("#chatLog");
  const chatInput = $("#chatInput");
  const btnSend = $("#btnSend");
  const btnClear = $("#btnClear");

  const sessionIdInput = $("#sessionId");

  const codeInput = $("#codeInput");
  const autoFix = $("#autoFix");
  const includeDiff = $("#includeDiff");
  const btnCheck = $("#btnCheck");
  const btnToChat = $("#btnToChat");

  const resultSummary = $("#resultSummary");
  const violationsEl = $("#violations");
  const fixedCodeEl = $("#fixedCode");
  const unifiedDiffEl = $("#unifiedDiff");

  const STORAGE_KEY = "ai_code_rule_checker_session_id";

  function escapeHtml(str){
    return str.replace(/[&<>"']/g, (c) => ({
      "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;"
    }[c]));
  }

  function now(){
    const d = new Date();
    return d.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
  }

  function setMode(mode){
    if(mode === "chat"){
      tabChat.classList.add("active");
      tabChat.setAttribute("aria-selected","true");
      tabCheck.classList.remove("active");
      tabCheck.setAttribute("aria-selected","false");
      chatPanel.classList.remove("hidden");
      checkPanel.classList.add("hidden");
      chatInput.focus();
      return;
    }
    tabCheck.classList.add("active");
    tabCheck.setAttribute("aria-selected","true");
    tabChat.classList.remove("active");
    tabChat.setAttribute("aria-selected","false");
    checkPanel.classList.remove("hidden");
    chatPanel.classList.add("hidden");
    codeInput.focus();
  }

  function getSessionId(){
    let sid = sessionIdInput.value.trim();
    if(!sid){
      sid = "demo-" + Math.random().toString(16).slice(2, 10);
      sessionIdInput.value = sid;
    }
    localStorage.setItem(STORAGE_KEY, sid);
    return sid;
  }

  function loadSessionId(){
    const sid = localStorage.getItem(STORAGE_KEY);
    if(sid) sessionIdInput.value = sid;
    else sessionIdInput.value = "demo-" + Math.random().toString(16).slice(2, 10);
  }

  function appendBubble(role, text, meta){
    const wrap = document.createElement("div");
    wrap.className = "bubble " + role;

    const metaDiv = document.createElement("div");
    metaDiv.className = "meta";
    metaDiv.innerHTML = `<span>${role === "user" ? "You" : "AI"}</span><span class="pill">${escapeHtml(meta || now())}</span>`;
    wrap.appendChild(metaDiv);

    // basic formatting: if contains triple backticks, render code blocks
    const parts = text.split("```");
    if(parts.length === 1){
      const p = document.createElement("div");
      p.innerHTML = escapeHtml(text);
      wrap.appendChild(p);
    } else {
      // alternating: text, code, text, code...
      parts.forEach((part, idx) => {
        if(idx % 2 === 0){
          if(part.trim().length){
            const p = document.createElement("div");
            p.innerHTML = escapeHtml(part);
            wrap.appendChild(p);
          }
        } else {
          // code part may start with language line
          const lines = part.split("\n");
          if(lines.length && /^[a-zA-Z0-9_-]+$/.test(lines[0].trim())){
            lines.shift();
          }
          const code = lines.join("\n");
          const pre = document.createElement("pre");
          pre.className = "codeblock";
          pre.textContent = code.replace(/^\n+/, "");
          wrap.appendChild(pre);
        }
      });
    }

    chatLog.appendChild(wrap);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  async function postJson(url, data){
    const res = await fetch(url, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(data),
    });
    const text = await res.text();
    if(!res.ok){
      throw new Error(text || ("HTTP " + res.status));
    }
    try{
      return JSON.parse(text);
    }catch(e){
      return {raw: text};
    }
  }

  async function sendChat(){
    const msg = chatInput.value;
    if(!msg.trim()) return;

    const sid = getSessionId();
    appendBubble("user", msg);
    chatInput.value = "";
    chatInput.focus();

    // loading bubble
    const loadingId = "loading-" + Date.now();
    appendBubble("assistant", "생각 중…", loadingId);

    try{
      const out = await postJson("/agent", {session_id: sid, input: msg, debug: false});
      // remove loading bubble: simplest is to append actual answer and keep loading; replace would be more complex
      appendBubble("assistant", out.output || JSON.stringify(out, null, 2));
    }catch(err){
      appendBubble("assistant", "에러: " + String(err.message || err));
    }
  }

  function clearChat(){
    chatLog.innerHTML = "";
    appendBubble("assistant",
      "안내:\n- 규칙을 물어보면 규칙을 설명한다.\n- 코드를 붙여넣으면 규칙 위반을 찾고, 가능한 경우 고친다.\n\n예시 질문:\n1) 팀 내 규칙 전부 알려줘\n2) import 순서 규칙이 뭐야?\n3) 아래 코드를 규칙에 맞게 고쳐줘\n```python\nfrom b import x\nfrom a import y\nprint(1)\n```"
    );
  }

  function renderCheckResult(result){
    resultSummary.textContent = result.summary || "(summary 없음)";
    violationsEl.innerHTML = "";
    fixedCodeEl.textContent = result.fixed_code || "";
    unifiedDiffEl.textContent = result.unified_diff || "";

    const vios = Array.isArray(result.violations) ? result.violations : [];
    if(vios.length === 0){
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "위반이 없다.";
      violationsEl.appendChild(empty);
      return;
    }

    vios.forEach((v) => {
      const box = document.createElement("div");
      box.className = "vio";
      const sev = (v.severity || "warning").toLowerCase();
      const line = (v.start_line && v.end_line) ? `${v.start_line}~${v.end_line}` : (v.start_line ? `${v.start_line}` : "-");
      box.innerHTML = `
        <div class="vio-top">
          <div>
            <div class="vio-title">${escapeHtml(v.title || v.rule_id || "RULE")}</div>
            <div class="vio-meta">${escapeHtml(v.rule_id || "")} · line ${escapeHtml(line)}</div>
          </div>
          <span class="badge ${escapeHtml(sev)}">${escapeHtml(sev)}</span>
        </div>
        <div class="vio-msg">${escapeHtml(v.message || "")}</div>
        ${v.suggestion ? `<div class="vio-suggest">제안: ${escapeHtml(v.suggestion)}</div>` : ""}
      `;
      violationsEl.appendChild(box);
    });
  }

  async function runCheck(){
    const code = codeInput.value;
    if(!code.trim()){
      resultSummary.textContent = "코드를 입력해야 한다.";
      return;
    }
    const sid = getSessionId();
    resultSummary.textContent = "실행 중…";
    violationsEl.innerHTML = "";
    fixedCodeEl.textContent = "";
    unifiedDiffEl.textContent = "";

    try{
      const out = await postJson("/check", {
        session_id: sid,
        language: "python",
        code: code,
        auto_fix: !!autoFix.checked,
        include_diff: !!includeDiff.checked,
      });
      renderCheckResult(out);
    }catch(err){
      resultSummary.textContent = "에러: " + String(err.message || err);
    }
  }

  function pasteResultToChat(){
    const summary = resultSummary.textContent || "";
    const fixed = fixedCodeEl.textContent || "";
    const diff = unifiedDiffEl.textContent || "";
    let msg = `코드 검사 결과:\n${summary}\n`;
    if(fixed.trim()){
      msg += `\nfixed_code:\n\`\`\`python\n${fixed}\n\`\`\`\n`;
    }
    if(diff.trim()){
      msg += `\ndiff:\n\`\`\`diff\n${diff}\n\`\`\`\n`;
    }
    appendBubble("assistant", msg);
    setMode("chat");
  }

  tabChat.addEventListener("click", () => setMode("chat"));
  tabCheck.addEventListener("click", () => setMode("check"));

  btnSend.addEventListener("click", sendChat);
  btnClear.addEventListener("click", clearChat);
  chatInput.addEventListener("keydown", (e) => {
    if(e.key === "Enter" && (e.ctrlKey || e.metaKey)){
      e.preventDefault();
      sendChat();
    }
  });

  btnCheck.addEventListener("click", runCheck);
  btnToChat.addEventListener("click", pasteResultToChat);

  sessionIdInput.addEventListener("change", () => {
    const sid = sessionIdInput.value.trim();
    if(sid) localStorage.setItem(STORAGE_KEY, sid);
  });

  // init
  loadSessionId();
  clearChat();
  setMode("chat");
})();
