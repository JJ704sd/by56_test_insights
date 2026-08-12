// @ts-check
// Vanilla TypeScript/DOM source deliberately restricted to browser-native syntax.
(() => {
  "use strict";

  const state = { report: null, selectedId: null, full: false, asking: false, componentCanary: null };
  let requestId = 0;
  const pendingRequests = new Map();
  const inline = document.querySelector("#inline");
  const full = document.querySelector("#full");
  const harness = document.querySelector("#harness");

  const esc = (value) => String(value ?? "—")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  const array = (value) => Array.isArray(value) ? value : [];
  const number = (value) => Number.isFinite(value) ? value : 0;
  const badge = (value) => `<span class="status" data-state="${esc(value)}">${esc(value)}</span>`;
  const rpc = (method, params, timeoutMs = 1500) => new Promise((resolve, reject) => {
    const id = `qei-${++requestId}`;
    const timeout = window.setTimeout(() => {
      pendingRequests.delete(id);
      reject(new Error(`${method} timed out`));
    }, timeoutMs);
    pendingRequests.set(id, {
      resolve: (value) => { window.clearTimeout(timeout); resolve(value); },
      reject: (error) => { window.clearTimeout(timeout); reject(error); },
    });
    window.parent.postMessage({ jsonrpc: "2.0", id, method, params }, "*");
  });
  const getContext = () => state.report?.conversation_contexts?.[state.selectedId] ?? null;

  function releaseVerdict(report) {
    const verified = report.compatibility?.status === "VERIFIED" && report.integrity?.status === "VALID";
    if (!verified) return "发布依据未验证（按 fail-closed 处理）";
    return report.authority.release_allowed ? "允许发布" : "不允许发布";
  }

  function compatibilityNotice(report) {
    if (report.compatibility?.status === "VERIFIED" && report.integrity?.status === "VALID") return "";
    const issues = [
      ...array(report.compatibility?.issues).filter((item) => item.status !== "VERIFIED").map((item) => item.message),
      ...array(report.integrity?.issues),
    ];
    return `<div class="notice invalid" role="alert"><strong>数据不可作为发布依据。</strong> ${esc(issues.join("；") || "版本或完整性未验证")}</div>`;
  }

  function inlineMarkup(report) {
    const authority = report.authority;
    const blockers = array(report.blockers).slice(0, 3);
    const domains = array(authority.checks).map((check) =>
      `<div class="domain"><strong>${esc(check.name)}</strong><br>${badge(check.status)}</div>`).join("");
    const blockerList = blockers.length
      ? `<ol class="blockers">${blockers.map((item) => `<li><strong>${esc(item.domain)} · ${esc(item.status)}</strong> — ${esc(item.summary)}</li>`).join("")}</ol>`
      : `<p class="empty">无阻塞项。</p>`;
    return `
      <div class="topline"><h1 id="report-title">Quality Gatekeeper</h1><span class="meta">只读证据快照</span></div>
      ${state.componentCanary ? `<output id="component-only-canary" class="meta">host-validation component canary: ${esc(state.componentCanary)}</output>` : ""}
      ${compatibilityNotice(report)}
      <div class="gate" aria-label="最终 Gate">Gate: ${esc(authority.gate)}</div>
      <p class="verdict">${esc(releaseVerdict(report))} · 原始 release_allowed=${esc(authority.release_allowed)}</p>
      <div class="domains" aria-label="三个必需域">${domains}</div>
      <h2>首要阻塞项（最多 3 条）</h2>${blockerList}
      <p class="meta">policy ${esc(authority.policy_version)} · schema ${esc(report.contract?.version)} · core ${esc(report.producer?.core_version)}<br>
      evaluation fingerprint ${esc(report.provenance?.evaluation_fingerprint)}<br>decision ${esc(report.snapshot?.decision_digest)}</p>
      <div class="actions"><button id="open-full" class="primary" type="button">查看证据</button><button id="ask-inline" type="button">询问 Codex</button></div>
      <p class="meta" data-ask-status role="status"></p>`;
  }

  function overviewMarkup(report) {
    const authority = report.authority;
    const domains = array(authority.checks).map((check) =>
      `<div class="domain"><strong>${esc(check.name)}</strong><br>${badge(check.status)}</div>`).join("");
    return `${compatibilityNotice(report)}
      <div class="gate" aria-label="最终 Gate">Gate: ${esc(authority.gate)}</div>
      <p class="verdict">${esc(releaseVerdict(report))} · 原始 release_allowed=${esc(authority.release_allowed)}</p>
      <div class="domains" aria-label="三个必需域">${domains}</div>
      <p class="meta">policy ${esc(authority.policy_version)} · schema ${esc(report.contract?.version)} · core ${esc(report.producer?.core_version)}<br>
      evaluation fingerprint ${esc(report.provenance?.evaluation_fingerprint)}<br>decision ${esc(report.snapshot?.decision_digest)}</p>`;
  }

  function riskRows(report) {
    return array(report.views?.risk_regression?.dimensions).map((row) => `
      <tr data-risk-disposition="${esc(row.disposition)}"><th scope="row"><button class="object-button" type="button" data-object-id="${esc(row.object_id)}" aria-pressed="${state.selectedId === row.object_id}">${esc(row.dimension)}</button></th>
      <td>${badge(row.disposition)}</td><td>${esc(row.reason || row.evidence)}</td><td>${esc(array(row.scenarios).join("；"))}</td></tr>`).join("");
  }

  function testRows(report) {
    return array(report.views?.risk_regression?.selected_tests).map((row) => `
      <tr><th scope="row"><button class="object-button" type="button" data-object-id="${esc(row.object_id)}" aria-pressed="${state.selectedId === row.object_id}">${esc(row.test_id)}</button></th>
      <td>${esc(row.priority)}</td><td>${esc(row.automated ? "是" : "否")}</td><td>${esc(array(row.reasons).join("；"))}</td><td>${esc(array(row.dimensions).join("、"))}</td></tr>`).join("");
  }

  function agentTotals(cases) {
    return cases.reduce((totals, item) => ({
      runner: totals.runner + number(item.runner_invalid),
      technical: totals.technical + number(item.technical_failures),
      deterministic: totals.deterministic + number(item.deterministic_failures),
      semantic: totals.semantic + number(item.semantic_failures),
    }), { runner: 0, technical: 0, deterministic: 0, semantic: 0 });
  }

  function agentMarkup(report) {
    const agent = report.views?.agent_evaluation;
    if (!agent) return `<p class="empty">Agent 评测非必需。</p>`;
    const cases = array(agent.cases);
    const totals = agentTotals(cases);
    const warningMarkup = array(agent.warnings).map((item) => `<li><strong>${esc(item.code)}</strong> — ${esc(item.text)}</li>`).join("");
    const rows = cases.map((item) => {
      const interval = item.wilson_95 ? `${esc(item.wilson_95.lower)}–${esc(item.wilson_95.upper)}` : "—";
      return `<tr data-agent-status="${esc(item.status)}"><th scope="row"><button class="object-button" type="button" data-object-id="${esc(item.object_id)}" aria-pressed="${state.selectedId === item.object_id}">${esc(item.case_id)}</button></th>
        <td>${esc(item.risk)}</td><td>${badge(item.status)}</td><td>${esc(item.planned)} / ${esc(item.observed)} / ${esc(item.evaluated)}</td>
        <td>${esc(item.pass_rate)} / ${interval}</td><td>${esc(item.runner_invalid)} / ${esc(item.technical_failures)} / ${esc(item.deterministic_failures)} / ${esc(item.semantic_failures)}</td></tr>`;
    }).join("");
    return `
      <p class="meta">agent ${esc(agent.identity?.agent_version)} · dataset ${esc(agent.identity?.dataset_version)} · fingerprint ${esc(agent.identity?.evaluation_fingerprint)}</p>
      ${warningMarkup ? `<div class="notice warning"><strong>不能由平均通过率掩盖的提示</strong><ul>${warningMarkup}</ul></div>` : ""}
      <div class="failure-grid" aria-label="Agent 失败域分布">
        <div><span class="count">${totals.runner}</span>runner invalid<br><small>不进入有效样本</small></div>
        <div><span class="count">${totals.technical}</span>技术失败<br><small>运行进入评测但技术错误</small></div>
        <div><span class="count">${totals.deterministic}</span>确定性业务失败<br><small>断言不满足</small></div>
        <div><span class="count">${totals.semantic}</span>语义复核失败<br><small>人工语义审查否决</small></div>
      </div>
      <div class="filters"><label>Agent 状态 <select id="agent-filter"><option value="ALL">全部</option>${[...new Set(cases.map((item) => item.status))].map((value) => `<option>${esc(value)}</option>`).join("")}</select></label></div>
      <div class="table-wrap"><table><caption>planned / observed / evaluated 与统计判定</caption><thead><tr><th>样本</th><th>风险</th><th>状态</th><th>planned / observed / evaluated</th><th>pass rate / Wilson 95%</th><th>runner / 技术 / 业务 / 语义</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  function selectedDetail() {
    const context = getContext();
    if (!context) return `<p class="empty">选择一条阻塞、风险、测试或 Agent 样本查看最小上下文。</p>`;
    const ref = context.safe_refs?.[0]?.source_pointer ?? "—";
    return `<h3>已选：${esc(context.selected?.kind)} / ${esc(context.selected?.id)}</h3>
      <ul>${array(context.facts).map((fact) => `<li>${esc(fact)}</li>`).join("")}</ul>
      <label for="copy-ref">证据引用</label><input id="copy-ref" class="copy-ref" readonly value="${esc(`${context.decision_digest} ${ref}`)}">
      <p id="copy-help" class="meta">复制按钮不可用时，聚焦引用并按 Ctrl/Cmd+C。</p>
      <div class="actions"><button id="copy-button" type="button">选择并复制引用</button><button id="ask-selected" class="primary" type="button">用最小上下文询问 Codex</button></div>
      <p class="meta" data-ask-status role="status"></p>`;
  }

  function fullMarkup(report) {
    const risk = report.views?.risk_regression ?? {};
    const dispositions = [...new Set(array(risk.dimensions).map((item) => item.disposition))];
    return `
      <nav aria-label="Inspector sections"><a href="#overview">发布总览</a><a href="#risk-regression">风险与回归</a><a href="#agent">Agent 评测</a></nav>
      <div class="toolbar"><button id="close-full" type="button">返回卡片</button><button id="print-report" type="button">打印</button><span class="meta">只读；不提供审批、豁免或发布。</span></div>
      <section id="overview" class="panel"><h2>发布总览</h2>${overviewMarkup(report)}</section>
      <section id="risk-regression" class="panel"><h2>风险与回归覆盖</h2>
        <p>决策：哪些风险缺少显式处置，哪些测试因何进入回归。</p>
        <div class="filters"><label>风险处置 <select id="risk-filter"><option value="ALL">全部</option>${dispositions.map((value) => `<option>${esc(value)}</option>`).join("")}</select></label></div>
        <div class="split"><div>
          <div class="table-wrap"><table><caption>八类风险维度矩阵</caption><thead><tr><th>维度</th><th>处置</th><th>依据</th><th>场景</th></tr></thead><tbody>${riskRows(report)}</tbody></table></div>
          <div class="table-wrap"><table><caption>选中测试与入选原因</caption><thead><tr><th>测试</th><th>优先级</th><th>自动化</th><th>入选原因</th><th>风险维度</th></tr></thead><tbody>${testRows(report)}</tbody></table></div>
        </div><aside id="selection-detail" class="detail" aria-live="polite">${selectedDetail()}</aside></div>
      </section>
      <section id="agent" class="panel"><h2>Agent 评测</h2><p>决策：失败来自运行环境、确定性业务断言，还是语义复核；高风险单次失败单独提示。</p>${agentMarkup(report)}</section>`;
  }

  function bindObjectButtons() {
    document.querySelectorAll("[data-object-id]").forEach((button) => button.addEventListener("click", () => {
      state.selectedId = button.getAttribute("data-object-id");
      document.querySelectorAll("[data-object-id]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
      const detail = document.querySelector("#selection-detail");
      if (detail) detail.innerHTML = selectedDetail();
      bindDetailActions();
      if (window.openai?.setWidgetState) {
        window.openai.setWidgetState({ privateContent: { selectedId: state.selectedId } });
      }
    }));
  }

  function setAskState(asking, message) {
    state.asking = asking;
    document.querySelectorAll("#ask-inline, #ask-selected").forEach((button) => { button.disabled = asking; });
    document.querySelectorAll("[data-ask-status]").forEach((status) => { status.textContent = message; });
  }

  async function askSelected() {
    const context = getContext();
    if (!context || state.asking) return;
    const prompt = `请基于已选择的 ${context.selected.kind} ${context.selected.id}，解释为什么它影响 Gate，并给出下一步最小解阻动作。不要改变或覆盖确定性裁决。`;
    setAskState(true, "正在向模型发送最小脱敏上下文……");
    try {
      await rpc("ui/update-model-context", { content: [{ type: "text", text: JSON.stringify(context) }] });
      if (window.openai?.sendFollowUpMessage) await window.openai.sendFollowUpMessage({ prompt });
      else void rpc("ui/message", { content: [{ type: "text", text: prompt }] }).catch(() => {});
      setAskState(false, "已发送所选对象的最小上下文；确定性 Gate 不会被模型覆盖。");
    } catch (_) {
      setAskState(false, "宿主未确认上下文更新；为避免错配，本次询问未发送。");
    }
  }

  function bindDetailActions() {
    document.querySelector("#ask-selected")?.addEventListener("click", askSelected);
    document.querySelector("#copy-button")?.addEventListener("click", () => {
      const input = document.querySelector("#copy-ref");
      if (!(input instanceof HTMLInputElement)) return;
      input.focus(); input.select();
      const copied = document.execCommand?.("copy") === true;
      const help = document.querySelector("#copy-help");
      if (help) help.textContent = copied ? "引用已复制。" : "引用已选中，请按 Ctrl/Cmd+C。";
    });
  }

  function bindFull() {
    document.querySelector("#close-full")?.addEventListener("click", () => setFull(false));
    document.querySelector("#print-report")?.addEventListener("click", () => window.print());
    document.querySelector("#risk-filter")?.addEventListener("change", (event) => {
      const value = event.target.value;
      document.querySelectorAll("[data-risk-disposition]").forEach((row) => { row.hidden = value !== "ALL" && row.dataset.riskDisposition !== value; });
    });
    document.querySelector("#agent-filter")?.addEventListener("change", (event) => {
      const value = event.target.value;
      document.querySelectorAll("[data-agent-status]").forEach((row) => { row.hidden = value !== "ALL" && row.dataset.agentStatus !== value; });
    });
    bindObjectButtons(); bindDetailActions();
  }

  async function setFull(open) {
    state.full = open;
    full.dataset.open = String(open);
    if (open) {
      if (window.openai?.requestDisplayMode) {
        try { await window.openai.requestDisplayMode({ mode: "fullscreen" }); } catch (_) { /* inline expansion is the fallback */ }
      }
      full.querySelector("#close-full")?.focus();
    } else {
      document.querySelector("#open-full")?.focus();
    }
  }

  function render(report, componentCanary = null) {
    if (!report?.authority || !report?.snapshot) {
      inline.innerHTML = `<div class="notice invalid" role="alert">无法验证报告契约。请使用结构化 MCP/CLI 结果；不要据此允许发布。</div>`;
      return;
    }
    state.report = report;
    state.componentCanary = componentCanary;
    state.selectedId = state.selectedId && report.conversation_contexts?.[state.selectedId]
      ? state.selectedId : (report.blockers?.[0]?.object_id ?? report.views?.risk_regression?.dimensions?.[0]?.object_id ?? null);
    inline.dataset.gate = report.authority.gate;
    inline.innerHTML = inlineMarkup(report);
    full.innerHTML = fullMarkup(report);
    document.querySelector("#open-full")?.addEventListener("click", () => setFull(true));
    document.querySelector("#ask-inline")?.addEventListener("click", askSelected);
    bindFull();
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window.parent) return;
    const message = event.data;
    if (message?.jsonrpc !== "2.0") return;
    if (message.id && !message.method) {
      const pending = pendingRequests.get(message.id);
      if (!pending) return;
      pendingRequests.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message ?? "Host RPC failed"));
      else pending.resolve(message.result);
      return;
    }
    if (message.method !== "ui/notifications/tool-result") return;
    const meta = message.params?._meta ?? message.params?.result?._meta;
    const report = meta?.qualityReport;
    if (report) render(report, meta?.componentOnlyCanary ?? null);
  });

  const fixtures = window.__QUALITY_HARNESS_FIXTURES__;
  if (fixtures) {
    harness.hidden = false;
    harness.innerHTML = `<strong>Standalone harness：</strong> ` + Object.keys(fixtures).map((name) => `<button type="button" data-fixture="${esc(name)}">${esc(name)}</button>`).join("") + ` <span>（宿主 bridge 未模拟）</span>`;
    harness.querySelectorAll("[data-fixture]").forEach((button) => button.addEventListener("click", () => render(fixtures[button.dataset.fixture])));
    render(fixtures.PASS ?? Object.values(fixtures)[0]);
  } else {
    const resultMeta = window.openai?.toolResponseMetadata;
    const report = resultMeta?.qualityReport;
    if (report) render(report, resultMeta?.componentOnlyCanary ?? null);
    void rpc("ui/initialize", { clientInfo: { name: "quality-evidence-inspector", version: "1.0.0" } }).catch(() => {});
  }
})();
