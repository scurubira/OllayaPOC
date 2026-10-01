const state = { config: null, profile: "futebol", model: "local", lastResult: null, history: [] };

const samples = {
  triagem: [
    ["Cobrança duplicada", "Fui cobrado duas vezes pela assinatura deste mês e quero o estorno."],
    ["Sistema fora do ar", "O sistema retorna erro 500 para todos os usuários e a operação está parada."],
  ],
  telecom: [
    ["Queda regional", "Uma falha no backbone deixou 80 mil clientes sem internet. A recuperação deve levar quatro horas."],
    ["Expansão 5G", "A operadora avalia investir R$ 25 milhões em cobertura 5G, mas ainda não possui estudo de retorno."],
  ],
  futebol: [
    ["G4 do Brasileirão", "Quais resultados podem alterar o G4 do Campeonato Brasileiro nesta rodada?"],
    ["Mata-mata", "O time empatou a ida das oitavas da Libertadores. O que precisa fazer na volta para avançar?"],
    ["Calendário", "O clube joga pelo Brasileirão três dias antes da semifinal da Libertadores. Deve poupar titulares?"],
  ],
};

const $ = (selector) => document.querySelector(selector);
const formatName = (value) => String(value).replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase());
const percent = (value) => `${Math.round(Number(value) * 100)}%`;

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "Falha inesperada na requisição.");
  return body;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 2200);
}

function renderProfiles() {
  const nav = $("#profile-nav");
  nav.innerHTML = Object.entries(state.config.profiles).map(([key, profile]) => `
    <button class="profile-button ${key === state.profile ? "active" : ""}" data-profile="${key}" style="--profile-accent:${profile.accent}">
      <strong>${profile.name}</strong><small>${profile.description}</small>
    </button>`).join("");
  nav.querySelectorAll("button").forEach(button => button.addEventListener("click", () => selectProfile(button.dataset.profile)));
}

function renderModels() {
  const select = $("#model-select");
  select.innerHTML = state.config.models.map(model =>
    `<option value="${model.id}" ${model.available ? "" : "disabled"}>${model.name} · ${model.model}${model.available ? "" : " (sem chave)"}</option>`
  ).join("");
  select.value = state.model;
  updateModelBadge();
}

function updateModelBadge() {
  $("#privacy-badge").textContent = state.model === "local" ? "Processamento local" : "Via gateway seguro";
}

function selectProfile(key) {
  state.profile = key;
  const profile = state.config.profiles[key];
  document.documentElement.style.setProperty("--accent", profile.accent);
  document.documentElement.style.setProperty("--accent-soft", `${profile.accent}20`);
  $("#profile-eyebrow").textContent = key === "futebol" ? "BRASILEIRÃO + LIBERTADORES" : key.toUpperCase();
  $("#profile-title").textContent = profile.name;
  $("#profile-description").textContent = profile.description;
  $("#analysis-text").placeholder = key === "futebol" ? "Cole uma pergunta, notícia ou cenário sobre Brasileirão e Libertadores..." : "Cole uma situação para analisar...";
  renderProfiles();
  renderSamples();
}

function renderSamples() {
  $("#sample-prompts").innerHTML = samples[state.profile].map(([label, text]) =>
    `<button class="sample-chip" data-text="${text.replaceAll('"', '&quot;')}">${label}</button>`).join("");
  document.querySelectorAll(".sample-chip").forEach(button => button.addEventListener("click", () => {
    $("#analysis-text").value = button.dataset.text;
    updateCharCount();
    $("#analysis-text").focus();
  }));
}

function updateCharCount() {
  $("#char-count").textContent = `${$("#analysis-text").value.length.toLocaleString("pt-BR")} / 20.000`;
}

function questionFor(name) {
  return state.config.profiles[state.profile].questions[name] || {};
}

function answerCard(name, answer) {
  const question = questionFor(name);
  let value = "—";
  let meterValue = 0;
  let note = "";
  let confidence = "";

  if (answer.type === "choice") {
    value = formatName(answer.choice);
    meterValue = answer.probabilities?.[answer.choice] ?? answer.confidence ?? 0;
    confidence = `Confiança ${percent(answer.confidence ?? meterValue)}`;
    note = question.criteria?.[answer.choice] || "";
  } else if (answer.type === "score") {
    value = `${Number(answer.score).toFixed(2)} / ${(question.criteria?.length || 1) - 1}`;
    meterValue = answer.score / Math.max((question.criteria?.length || 1) - 1, 1);
    confidence = `Confiança ${percent(answer.confidence ?? 0)}`;
    const index = Math.max(0, Math.min(Math.round(answer.score), (question.criteria?.length || 1) - 1));
    note = question.criteria?.[index] || "";
  } else if (answer.type === "noul") {
    value = percent(answer.noul);
    meterValue = answer.noul;
    confidence = answer.noul >= .5 ? "Provável" : "Pouco provável";
    note = question.instructions || "";
  }

  return `<article class="insight-card">
    <div class="insight-top"><div><div class="insight-label">${formatName(name)}</div><div class="insight-value">${value}</div></div><span class="confidence">${confidence}</span></div>
    <div class="meter" aria-label="${Math.round(meterValue * 100)} por cento"><span style="--value:${Math.round(meterValue * 100)}%"></span></div>
    ${note ? `<p class="card-note">${note}</p>` : ""}
  </article>`;
}

function renderSingle(result) {
  $("#result-content").className = "";
  $("#result-content").innerHTML = `<div class="insight-grid">${Object.entries(result.answers).map(([name, answer]) => answerCard(name, answer)).join("")}</div>`;
  $("#elapsed-time").textContent = `${result.model?.name || "Modelo"} · ${Math.round(result.elapsed_ms)} ms`;
  $("#result-actions").classList.remove("hidden");
}

function renderBatch(results) {
  $("#result-content").className = "";
  $("#result-content").innerHTML = `<div class="batch-result-list">${results.map((result, index) => `
    <details class="batch-item" ${index === 0 ? "open" : ""}>
      <summary>${result.title}<span>${Math.round(result.elapsed_ms)} ms</span></summary>
      <div class="insight-grid">${Object.entries(result.answers).map(([name, answer]) => answerCard(name, answer)).join("")}</div>
    </details>`).join("")}</div>`;
  const total = results.reduce((sum, result) => sum + result.elapsed_ms, 0);
  $("#elapsed-time").textContent = `${results[0]?.model?.name || "Modelo"} · ${results.length} itens · ${Math.round(total)} ms`;
  $("#result-actions").classList.remove("hidden");
}

function setLoading(button, loading) {
  button.disabled = loading;
  button.dataset.label ||= button.textContent;
  button.textContent = loading ? "Processando..." : button.dataset.label;
  if (loading) {
    $("#result-content").className = "loading-state";
    $("#result-content").innerHTML = `<div><div class="loading-bars"><span></span><span></span><span></span></div><p>Consultando o modelo local...</p></div>`;
  }
}

function showError(error) {
  $("#result-content").className = "";
  $("#result-content").innerHTML = `<div class="error-box"><strong>Não foi possível concluir.</strong><br>${error.message}</div>`;
}

function addHistory(text, result) {
  state.history.unshift({ profile: state.profile, text, time: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }), result });
  state.history = state.history.slice(0, 12);
  renderHistory();
}

function renderHistory() {
  $("#history-count").textContent = `${state.history.length} ${state.history.length === 1 ? "análise" : "análises"}`;
  $("#history-list").innerHTML = state.history.length ? state.history.map((item, index) => `
    <div class="history-item" data-index="${index}"><span class="history-profile">${item.profile}</span><span class="history-text">${item.text}</span><span class="history-time">${item.time}</span></div>`).join("") : `<p class="muted">Nenhuma análise nesta sessão.</p>`;
  document.querySelectorAll(".history-item").forEach(item => item.addEventListener("click", () => {
    const historyItem = state.history[Number(item.dataset.index)];
    selectProfile(historyItem.profile);
    state.lastResult = historyItem.result;
    renderSingle(historyItem.result.result);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }));
}

async function analyzeSingle() {
  const text = $("#analysis-text").value.trim();
  if (!text) return toast("Digite um cenário para analisar.");
  const button = $("#analyze-button");
  setLoading(button, true);
  try {
    const data = await request("/api/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile: state.profile, model: state.model, text }) });
    state.lastResult = data;
    renderSingle(data.result);
    addHistory(text, data);
  } catch (error) { showError(error); }
  finally { setLoading(button, false); }
}

async function analyzeBatch() {
  const button = $("#batch-button");
  let items;
  try { items = JSON.parse($("#batch-text").value); }
  catch { return toast("O conteúdo não é um JSON válido."); }
  setLoading(button, true);
  try {
    const data = await request("/api/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile: state.profile, model: state.model, items }) });
    state.lastResult = data;
    renderBatch(data.results);
    data.results.forEach(result => addHistory(result.title || result.text, { profile: state.profile, result }));
  } catch (error) { showError(error); }
  finally { setLoading(button, false); }
}

function bindEvents() {
  $("#model-select").addEventListener("change", event => {
    state.model = event.target.value;
    updateModelBadge();
  });
  $("#analysis-text").addEventListener("input", updateCharCount);
  $("#analysis-text").addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") analyzeSingle();
  });
  $("#analyze-button").addEventListener("click", analyzeSingle);
  $("#batch-button").addEventListener("click", analyzeBatch);
  $("#batch-file").addEventListener("change", async event => {
    const [file] = event.target.files;
    if (file) $("#batch-text").value = await file.text();
  });
  document.querySelectorAll(".mode-tab").forEach(tab => tab.addEventListener("click", () => {
    document.querySelectorAll(".mode-tab").forEach(item => item.classList.toggle("active", item === tab));
    $("#single-panel").classList.toggle("hidden", tab.dataset.mode !== "single");
    $("#batch-panel").classList.toggle("hidden", tab.dataset.mode !== "batch");
  }));
  $("#download-button").addEventListener("click", () => {
    if (!state.lastResult) return;
    const blob = new Blob([JSON.stringify(state.lastResult, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `ollaya-${state.profile}-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  });
  $("#clear-history").addEventListener("click", () => { state.history = []; renderHistory(); toast("Histórico limpo."); });
}

async function checkHealth() {
  const status = $("#server-status");
  try {
    await request("/api/health");
    status.className = "server-status ready";
    status.querySelector("strong").textContent = "Ollaya disponível";
  } catch {
    status.className = "server-status error";
    status.querySelector("strong").textContent = "Ollaya indisponível";
  }
}

async function init() {
  bindEvents();
  try {
    state.config = await request("/api/config");
    renderModels();
    selectProfile(state.profile);
    checkHealth();
  } catch (error) { showError(error); }
}

init();
