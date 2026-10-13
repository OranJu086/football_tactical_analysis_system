"use strict";

// ========== DOM 元素 ==========
const teamNameInput = document.getElementById("teamName");
const teamSuggestions = document.getElementById("teamSuggestions");
const competitionInput = document.getElementById("competition");
const matchSelect = document.getElementById("matchSelect");
const queryBtn = document.getElementById("queryBtn");
const promptInput = document.getElementById("prompt");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusHint = document.getElementById("statusHint");
const errorBox = document.getElementById("errorBox");
const resultArea = document.getElementById("resultArea");
const sourceBadge = document.getElementById("sourceBadge");
const elapsedEl = document.getElementById("elapsed");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const emptyState = document.getElementById("emptyState");
const scoreHome = document.getElementById("scoreHome");
const scoreDigits = document.getElementById("scoreDigits");
const scoreAway = document.getElementById("scoreAway");
const narrativeEl = document.getElementById("narrative");
const statTeamHead = document.getElementById("statTeamHead");
const statOpponentHead = document.getElementById("statOpponentHead");
const statTableBody = document.querySelector("#statTable tbody");
const playerTableBody = document.querySelector("#playerTable tbody");
const figPassNetwork = document.getElementById("figPassNetwork");
const figShotMap = document.getElementById("figShotMap");
const figHeatmap = document.getElementById("figHeatmap");

// ========== 常量 ==========
const ANALYZE_IDLE = "分析";
const ANALYZE_LOADING = "分析中…（约 10–40 秒）";

// 自动补全状态：候选列表、键盘高亮下标、输入防抖定时器、请求序号、是否正在用输入法组字
let suggestItems = [];
let activeIndex = -1;
let suggestTimer = null;
let suggestSeq = 0;
let composing = false;

// 团队统计对比指标（中文名与 REST 契约字段一一对应）
const STAT_ROWS = [
  { key: "goals", label: "进球" },
  { key: "shots", label: "射门" },
  { key: "shots_on_target", label: "射正" },
  { key: "passes", label: "传球" },
  { key: "pass_accuracy_pct", label: "传球成功率%" },
  { key: "possessions", label: "控球次数" },
  { key: "possession_share_pct", label: "控球份额%" },
  { key: "final_third_passes", label: "进攻三区传球" },
  { key: "box_entries", label: "禁区进入" },
  { key: "pass_edges", label: "传球网络边数" },
];

// ========== 工具函数 ==========
function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
}

function setStatus(text, isError) {
  statusHint.textContent = text;
  statusHint.classList.toggle("status-error", Boolean(isError));
}

function setAnalyzeLoading(loading) {
  analyzeBtn.disabled = loading;
  analyzeBtn.textContent = loading ? ANALYZE_LOADING : ANALYZE_IDLE;
}

function formatValue(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  const num = Number(value);
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
}

// 重置比赛下拉框：清空选项、写占位文案并置为不可选
function resetMatchSelect(text) {
  matchSelect.innerHTML = "";
  const option = document.createElement("option");
  option.value = "";
  option.textContent = text || "先输入球队名";
  matchSelect.appendChild(option);
  matchSelect.disabled = true;
}

// ========== 错误处理 ==========
async function friendlyError(response) {
  if (response.status === 400) {
    let detail = "";
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || "");
    } catch (e) {
      detail = "";
    }
    return "输入有误：" + (detail || "请检查参数");
  }
  if (response.status === 429) {
    return "请求太频繁，请稍后再试";
  }
  if (response.status === 502) {
    // 后端会针对「该场比赛未预置数据」等情况给出可操作的中文说明，优先展示它
    let detail = "";
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch (e) {
      detail = "";
    }
    return detail || "服务暂时不可用（数据或模型），请稍后再试";
  }
  return "服务返回错误（HTTP " + response.status + "），请稍后再试";
}

// ========== 球队名自动补全 ==========
function closeSuggestions() {
  // 已经点了「查询比赛」时，把还在防抖里的候选请求一并取消，
  // 否则它晚一步返回，会把刚刚画好的「是不是要找」候选冲掉
  if (suggestTimer) {
    clearTimeout(suggestTimer);
    suggestTimer = null;
  }

  teamSuggestions.classList.add("hidden");
  teamSuggestions.innerHTML = "";
  teamNameInput.setAttribute("aria-expanded", "false");
  teamNameInput.removeAttribute("aria-activedescendant");
  suggestItems = [];
  activeIndex = -1;
}

// 把候选画进下拉框；note 是列表顶部的说明文案（热门球队 / 是不是要找）
function renderSuggestions(items, note) {
  teamSuggestions.innerHTML = "";
  suggestItems = items;
  activeIndex = -1;

  if (note) {
    const noteItem = document.createElement("li");
    noteItem.className = "suggestion-note";
    noteItem.textContent = note;
    teamSuggestions.appendChild(noteItem);
  }

  if (items.length === 0) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "suggestion-empty";
    emptyItem.textContent = "没有匹配的球队，试试输入球队全名";
    teamSuggestions.appendChild(emptyItem);
  }

  items.forEach((item, index) => {
    const li = document.createElement("li");
    li.className = "suggestion-item";
    li.id = "teamSuggestion-" + index;
    li.setAttribute("role", "option");

    const nameSpan = document.createElement("span");
    nameSpan.textContent = item.name;

    const metaSpan = document.createElement("span");
    metaSpan.className = "suggestion-meta";
    metaSpan.textContent = item.matches + " 场";

    li.appendChild(nameSpan);
    li.appendChild(metaSpan);
    li.addEventListener("mousedown", function (event) {
      // 用 mousedown 并阻止默认行为，抢在输入框失焦前完成选中
      event.preventDefault();
      chooseSuggestion(index);
    });
    teamSuggestions.appendChild(li);
  });

  teamSuggestions.classList.remove("hidden");
  teamNameInput.setAttribute("aria-expanded", "true");
}

// 上下键移动高亮；越界时循环到另一端
function highlightSuggestion(index) {
  const items = teamSuggestions.querySelectorAll(".suggestion-item");
  if (items.length === 0) {
    return;
  }

  if (index < 0) {
    index = items.length - 1;
  }
  if (index >= items.length) {
    index = 0;
  }

  items.forEach((element) => element.classList.remove("active"));
  items[index].classList.add("active");
  items[index].scrollIntoView({ block: "nearest" });

  activeIndex = index;
  teamNameInput.setAttribute("aria-activedescendant", items[index].id);
}

// 选中某个候选：回填输入框后直接查询比赛
function chooseSuggestion(index) {
  const item = suggestItems[index];
  if (!item) {
    return;
  }

  teamNameInput.value = item.name;
  closeSuggestions();
  queryMatches();
}

// 向后端要候选队名；q 为空时后端返回热门球队
async function fetchSuggestions(query) {
  const seq = ++suggestSeq;
  const params = new URLSearchParams();
  params.set("q", query);
  params.set("limit", "8");

  try {
    const response = await fetch("/api/teams?" + params.toString());
    if (seq !== suggestSeq) {
      return;
    }
    if (!response.ok) {
      closeSuggestions();
      return;
    }

    const data = await response.json();
    // 网络慢时可能先发后到，只认最新一次请求的结果
    if (seq !== suggestSeq) {
      return;
    }

    const items = Array.isArray(data.teams) ? data.teams : [];
    renderSuggestions(items, query ? "" : "热门球队");
  } catch (error) {
    // 网络异常时静默收摊，具体错误交给查询与分析流程提示
    if (seq === suggestSeq) {
      closeSuggestions();
    }
  }
}

// 输入防抖：停止输入 200 毫秒后再请求候选，避免每敲一个字都发请求
function scheduleSuggestions() {
  if (suggestTimer) {
    clearTimeout(suggestTimer);
  }

  const query = teamNameInput.value.trim();
  suggestTimer = setTimeout(function () {
    suggestTimer = null;
    fetchSuggestions(query);
  }, 200);
}

// ========== 查询比赛 ==========
async function queryMatches() {
  const team = teamNameInput.value.trim();
  if (!team) {
    showError("请输入球队名称");
    return;
  }

  hideError();
  closeSuggestions();
  setStatus("查询比赛中…");
  queryBtn.disabled = true;
  resetMatchSelect("查询中…");

  const params = new URLSearchParams();
  params.set("team", team);
  params.set("limit", "50");
  const competition = competitionInput.value.trim();
  if (competition) {
    params.set("competition", competition);
  }

  try {
    const response = await fetch("/api/matches?" + params.toString());
    if (!response.ok) {
      throw new Error(await friendlyError(response));
    }
    const data = await response.json();

    const matches = Array.isArray(data.matches) ? data.matches : [];
    if (matches.length === 0) {
      resetMatchSelect("未找到匹配的比赛");

      // 后端给了候选队名就直接摆进下拉框，点一下换成正确的队名再查
      const suggestions = Array.isArray(data.suggestions) ? data.suggestions : [];
      if (suggestions.length > 0) {
        renderSuggestions(suggestions, "没找到这支球队的比赛，是不是要找：");
        setStatus("未找到匹配的比赛，请从候选里选一支球队", true);
      } else {
        setStatus("未找到匹配的比赛", true);
      }
      return;
    }

    // 输入简称或拼写有误差时，后端会解析出规范队名，回填输入框让人看到实际用的是哪支队
    const resolvedTeam = data.resolved_team;
    let matchedNote = "";
    if (resolvedTeam && resolvedTeam !== team) {
      teamNameInput.value = resolvedTeam;
      matchedNote = "已按“" + resolvedTeam + "”匹配（输入：" + team + "） · ";
    }

    matchSelect.innerHTML = "";
    matches.forEach((match) => {
      const option = document.createElement("option");
      option.value = String(match.match_id);
      option.textContent = match.label || match.date || option.value;
      matchSelect.appendChild(option);
    });
    matchSelect.disabled = false;
    setStatus(matchedNote + "共 " + matches.length + " 场比赛，请选择");
  } catch (error) {
    if (error instanceof TypeError) {
      showError("无法连接服务，请确认服务已启动");
      setStatus("查询失败", true);
    } else {
      showError(error.message || "查询比赛失败");
      setStatus("查询失败", true);
    }
    matchSelect.disabled = true;
  } finally {
    queryBtn.disabled = false;
  }
}

// ========== 分析 ==========
async function runAnalysis() {
  const matchId = matchSelect.value;
  const teamName = teamNameInput.value.trim();
  const prompt = promptInput.value.trim();

  if (!teamName) {
    showError("请输入球队名称");
    return;
  }
  if (!matchId) {
    showError("请先查询并选择一场比赛");
    return;
  }
  if (!prompt) {
    showError("请输入分析提示词");
    return;
  }

  hideError();
  resultArea.classList.add("hidden");
  emptyState.classList.add("hidden");
  setStatus("正在分析，请稍候…");
  setAnalyzeLoading(true);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        match_id: Number(matchId),
        team_name: teamName,
        prompt: prompt,
      }),
    });

    if (!response.ok) {
      throw new Error(await friendlyError(response));
    }

    const data = await response.json();
    renderResult(data);
    setStatus("分析完成");
  } catch (error) {
    if (error instanceof TypeError) {
      showError("无法连接服务，请确认服务已启动");
    } else {
      showError(error.message || "分析失败，请稍后再试");
    }
    setStatus("分析失败", true);
    resultArea.classList.add("hidden");
  } finally {
    setAnalyzeLoading(false);
  }
}

// ========== 渲染结果 ==========
function renderResult(data) {
  const summary = data.summary || {};
  const team = summary.team || {};
  const opponent = summary.opponent_team || {};

  // 来源徽标
  if (data.narrative_source === "live") {
    sourceBadge.textContent = "实时分析";
    sourceBadge.className = "badge badge-live";
  } else if (data.narrative_source === "cache") {
    sourceBadge.textContent = "离线缓存结果";
    sourceBadge.className = "badge badge-cache";
  } else {
    sourceBadge.textContent = "";
    sourceBadge.className = "badge";
  }

  // 耗时
  if (data.elapsed_ms !== null && data.elapsed_ms !== undefined) {
    elapsedEl.textContent = "耗时 " + (Number(data.elapsed_ms) / 1000).toFixed(1) + " 秒";
  } else {
    elapsedEl.textContent = "";
  }

    renderScoreline(summary, data);

  // 三张图
  const figures = data.figures || {};
  setFigure(figPassNetwork, figures.pass_network);
  setFigure(figShotMap, figures.shot_map);
  setFigure(figHeatmap, figures.heatmap);

  // 叙述文本
  narrativeEl.textContent = data.narrative || "（无分析文本）";

  // 团队统计对比
  statTeamHead.textContent = summary.focus_team || data.team_name || "球队";
  statOpponentHead.textContent = summary.opponent || "对手";
  renderStatTable(team, opponent);

  // 核心球员
  renderPlayerTable(Array.isArray(summary.core_players) ? summary.core_players : []);

  resultArea.classList.remove("hidden");
}

// 比分牌：把 summary.match 里的对阵、比分与赛事信息摆成记分牌样式
function renderScoreline(summary, data) {
  const match = summary.match || {};
  const focusName = summary.focus_team || data.team_name || teamNameInput.value.trim();
  const home = match.home_team || "";
  const away = match.away_team || "";

  // 上游没给对阵信息时退回一句纯文字标题，不留空壳
  if (!home || !away) {
    resultMeta.textContent = "";
    scoreHome.textContent = "";
    scoreDigits.textContent = "";
    scoreAway.textContent = "";
    resultTitle.textContent = focusName ? focusName + " 战术分析" : "战术分析";
    return;
  }

  const competition = [match.competition, match.season].filter(Boolean).join(" ");
  resultMeta.textContent = [match.date, competition].filter(Boolean).join(" / ");
  scoreHome.textContent = home;
  scoreDigits.textContent = match.home_score + " : " + match.away_score;
  scoreAway.textContent = away;

  // 正在分析哪支队，就在这里标出来，免得看图时分不清主客
  scoreHome.classList.toggle("is-focus", focusName === home);
  scoreAway.classList.toggle("is-focus", focusName === away);
  resultTitle.textContent = "分析视角：" + focusName;
}

function setFigure(imgEl, url) {
  if (url) {
    imgEl.src = url;
    imgEl.style.display = "";
  } else {
    imgEl.removeAttribute("src");
    imgEl.style.display = "none";
  }
}

function renderStatTable(team, opponent) {
  statTableBody.innerHTML = "";

  STAT_ROWS.forEach((row) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = row.label;
    const tdTeam = document.createElement("td");
    tdTeam.textContent = formatValue(team[row.key]);
    const tdOpponent = document.createElement("td");
    tdOpponent.textContent = formatValue(opponent[row.key]);
    tr.appendChild(th);
    tr.appendChild(tdTeam);
    tr.appendChild(tdOpponent);
    statTableBody.appendChild(tr);
  });
}

function renderPlayerTable(players) {
  playerTableBody.innerHTML = "";

  const topPlayers = players.slice(0, 5);
  if (topPlayers.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 8;
    td.textContent = "无核心球员数据";
    tr.appendChild(td);
    playerTableBody.appendChild(tr);
    return;
  }

  topPlayers.forEach((player) => {
    const tr = document.createElement("tr");
    const cells = [
      player.name,
      formatValue(player.score),
      formatValue(player.passes),
      formatValue(player.pass_accuracy_pct),
      formatValue(player.key_passes),
      formatValue(player.shots),
      formatValue(player.goals),
      formatValue(player.touches),
    ];
    cells.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value;
      tr.appendChild(td);
    });
    playerTableBody.appendChild(tr);
  });
}

// ========== 初始化 ==========
async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      setStatus("服务异常（HTTP " + response.status + "）", true);
      return;
    }
    const data = await response.json();
    if (data.status === "ok") {
      setStatus(data.llm_configured ? "服务正常，LLM 已配置" : "服务正常，LLM 未配置");
    } else {
      setStatus("服务状态异常", true);
    }
  } catch (error) {
    setStatus("无法连接服务，请确认服务已启动", true);
  }
}

queryBtn.addEventListener("click", queryMatches);
analyzeBtn.addEventListener("click", runAnalysis);
matchSelect.addEventListener("change", hideError);

teamNameInput.addEventListener("focus", function () {
  fetchSuggestions(teamNameInput.value.trim());
});

teamNameInput.addEventListener("input", function () {
  hideError();
  // 球队名变化后，旧比赛列表不再可信，重置下拉
  resetMatchSelect();

  // 输入法组字过程中不查询，等按下空格或回车确定后再查
  if (!composing) {
    scheduleSuggestions();
  }
});

teamNameInput.addEventListener("compositionstart", function () {
  composing = true;
});

teamNameInput.addEventListener("compositionend", function () {
  composing = false;
  scheduleSuggestions();
});

teamNameInput.addEventListener("keydown", function (event) {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    highlightSuggestion(activeIndex + 1);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    highlightSuggestion(activeIndex - 1);
    return;
  }
  if (event.key === "Escape") {
    closeSuggestions();
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    if (activeIndex >= 0) {
      chooseSuggestion(activeIndex);
    } else {
      closeSuggestions();
      queryMatches();
    }
  }
});

// 点击页面其他位置时收起候选列表
document.addEventListener("mousedown", function (event) {
  if (!event.target.closest(".field-suggest")) {
    closeSuggestions();
  }
});

checkHealth();
