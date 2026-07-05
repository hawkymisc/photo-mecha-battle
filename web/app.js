"use strict";

/**
 * Photo Mecha Battle — 簡易Webクライアント（デモ用プロトタイプ）。
 *
 * 既存のバックエンドAPI（src/photo_mecha_battle/api/app.py）をそのまま呼び出すだけの
 * 薄いフロントエンドで、以下のコアループを一気通貫で体験できるようにする。
 *   撮影アップロード → 検出/抽出 → メカ生成 → チーム編成 → CPU戦バトル → ログ確認 → ランキング
 *
 * バトル自体はサーバー側で決定的に解決される（docs/09 信頼モデル）。このクライアントは
 * 演出・入力補助のみを担い、勝敗やダメージを自前で計算しない。
 */

const FORM_LABELS = { bird: "鳥形", human: "人型", beast: "獣形" };
const STAT_MAX = 200;
const STAT_ORDER = ["hp", "atk", "defense", "spd", "tec", "en"];
const STAT_SHORT = { hp: "HP", atk: "ATK", defense: "DEF", spd: "SPD", tec: "TEC", en: "EN" };
const POSITIONS = [
  { key: "front", label: "前衛" },
  { key: "middle", label: "中衛" },
  { key: "back", label: "後衛" },
];

const state = {
  token: localStorage.getItem("pmb_token") || null,
  userId: localStorage.getItem("pmb_user_id") || null,
  userName: localStorage.getItem("pmb_user_name") || null,
  rating: null,
  mechs: [],
  presets: [],
  pendingCapture: null, // { file }
  lastSegment: null, // { objectId }
};

// ---------- low-level API helper ----------

async function api(path, { method = "GET", json, form, auth = true } = {}) {
  const headers = {};
  if (auth && state.token) headers["X-User-Token"] = state.token;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form !== undefined) {
    body = form; // FormData: let the browser set Content-Type with boundary
  }

  const response = await fetch(path, { method, headers, body });
  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const message = extractErrorMessage(payload, response.status);
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

// バックエンドが返す英語の detail 文字列を、プレイヤー向けの日本語メッセージに変換する。
// 完全一致しないメッセージは末尾の fallback で素通しする（新規エラー種別の追加を妨げないため）。
const KNOWN_ERROR_MESSAGES = [
  { test: (d) => d === "duplicate capture", message: "この写真は既にアップロード済みの写真と酷似しています。別の被写体を撮影してください。" },
  { test: (d) => /quota exceeded$/.test(d) && d.startsWith("captures"), message: "本日の撮影回数の上限に達しました。日付が変わるまでお待ちください。" },
  { test: (d) => /quota exceeded$/.test(d) && d.startsWith("mechs"), message: "本日のメカ生成回数の上限に達しました。日付が変わるまでお待ちください。" },
  { test: (d) => d === "empty file", message: "空のファイルはアップロードできません。写真を選び直してください。" },
  { test: (d) => d === "missing token" || d === "invalid token", message: "ログインが必要です。パイロット登録をやり直してください。" },
];

function extractErrorMessage(payload, status) {
  const detail = payload && typeof payload === "object" ? payload.detail : payload;
  if (detail && typeof detail === "object") {
    if (detail.reason || detail.error === "unsafe_capture") {
      return `安全性チェックにより撮影を受け付けられませんでした（理由: ${detail.reason || "unknown"}）。撮り直してください。`;
    }
    return JSON.stringify(detail);
  }
  if (typeof detail === "string" && detail) {
    const known = KNOWN_ERROR_MESSAGES.find((entry) => entry.test(detail));
    return known ? known.message : detail;
  }
  return `通信エラーが発生しました（HTTP ${status}）`;
}

// ---------- toast ----------

function toast(message, kind = "info") {
  const stack = document.getElementById("toast-stack");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 5200);
}

// ---------- panel visibility ----------

function showPanel(id, visible = true) {
  document.getElementById(id).hidden = !visible;
}

function revealGameplayPanels() {
  showPanel("panel-auth", false);
  document.getElementById("user-box").hidden = false;
  showPanel("panel-capture", true);
  showPanel("panel-mechs", true);
  showPanel("panel-deploy", true);
  showPanel("panel-ranking", true);
}

function renderUserBox() {
  document.getElementById("user-name").textContent = state.userName || "-";
  document.getElementById("user-rating").textContent = state.rating ?? "-";
}

async function refreshQuota() {
  try {
    const quota = await api("/users/quotas");
    document.getElementById("user-quota").textContent =
      `撮影 ${quota.captures.used}/${quota.captures.limit} ・ メカ ${quota.mechs.used}/${quota.mechs.limit}`;
  } catch {
    // クォータ表示はベストエフォート。失敗しても操作は継続できる。
  }
}

// ---------- auth ----------

async function handleRegister() {
  const nameInput = document.getElementById("register-name");
  const name = nameInput.value.trim();
  if (!name) {
    toast("パイロット名を入力してください", "error");
    return;
  }
  try {
    const user = await api("/auth/register", { method: "POST", json: { name }, auth: false });
    state.token = user.token;
    state.userId = user.user_id;
    state.userName = user.name;
    state.rating = user.rating;
    localStorage.setItem("pmb_token", user.token);
    localStorage.setItem("pmb_user_id", user.user_id);
    localStorage.setItem("pmb_user_name", user.name);
    onLoggedIn();
    toast(`ようこそ、${user.name}パイロット`, "success");
  } catch (err) {
    toast(err.message, "error");
  }
}

async function tryRestoreSession() {
  if (!state.token) return;
  try {
    const me = await api("/auth/me");
    state.userId = me.user_id;
    state.userName = me.name;
    state.rating = me.rating;
    onLoggedIn();
  } catch {
    // トークンが無効化されている場合は再登録させる。
    localStorage.removeItem("pmb_token");
    localStorage.removeItem("pmb_user_id");
    localStorage.removeItem("pmb_user_name");
    state.token = null;
  }
}

function onLoggedIn() {
  revealGameplayPanels();
  renderUserBox();
  refreshQuota();
  refreshMechs();
  refreshPresets().then(renderDeployGrid);
  refreshRanking();
}

function handleLogout() {
  localStorage.removeItem("pmb_token");
  localStorage.removeItem("pmb_user_id");
  localStorage.removeItem("pmb_user_name");
  Object.assign(state, { token: null, userId: null, userName: null, rating: null, mechs: [] });
  location.reload();
}

// ---------- capture -> mech pipeline ----------

function bindCaptureForm() {
  const fileInput = document.getElementById("capture-file");
  const dropzone = document.getElementById("dropzone");
  const hint = document.getElementById("dropzone-hint");
  const buildBtn = document.getElementById("build-mech-btn");

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (!file) return;
    state.pendingCapture = { file };
    dropzone.classList.add("has-image");
    const reader = new FileReader();
    reader.onload = () => {
      hint.innerHTML = "";
      const img = document.createElement("img");
      img.src = reader.result;
      hint.appendChild(img);
      const caption = document.createElement("div");
      caption.textContent = file.name;
      hint.appendChild(caption);
    };
    reader.readAsDataURL(file);
    buildBtn.disabled = false;
  });

  buildBtn.addEventListener("click", handleBuildMech);
}

async function handleBuildMech() {
  const buildBtn = document.getElementById("build-mech-btn");
  const file = state.pendingCapture && state.pendingCapture.file;
  const name = document.getElementById("mech-name").value.trim();

  if (!file) {
    toast("先に写真を選択してください", "error");
    return;
  }
  if (!name) {
    toast("メカ名を入力してください", "error");
    return;
  }

  buildBtn.disabled = true;
  const originalLabel = buildBtn.textContent;
  try {
    buildBtn.innerHTML = '<span class="spinner"></span>アップロード中…';
    const formData = new FormData();
    formData.append("file", file);
    const capture = await api("/captures/upload", { method: "POST", form: formData });

    buildBtn.innerHTML = '<span class="spinner"></span>被写体を検出中…';
    const detection = await api(`/captures/${capture.id}/detect`, { method: "POST" });
    const candidate = detection.candidates[0];
    if (!candidate) throw new Error("被写体を検出できませんでした。別の写真を試してください。");

    buildBtn.innerHTML = '<span class="spinner"></span>特徴量を抽出中…';
    const segment = await api(`/captures/${capture.id}/segment`, {
      method: "POST",
      json: { label: candidate.label, bbox: candidate.bbox },
    });

    buildBtn.innerHTML = '<span class="spinner"></span>メカを生成中…';
    // PLAN D-013: form は送らない。型はサーバーが特徴量から自動推定する（docs/03）。
    const mech = await api("/mechs", {
      method: "POST",
      json: { object_id: segment.id, name },
    });

    toast(
      `「${mech.name}」が完成しました — 判明した型: ${FORM_LABELS[mech.form] || mech.form}（情報量スコア ${segment.info_score.toFixed(2)}）`,
      "success"
    );
    resetCaptureForm();
    await refreshMechs();
    refreshQuota();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    buildBtn.disabled = false;
    buildBtn.textContent = originalLabel;
  }
}

function resetCaptureForm() {
  state.pendingCapture = null;
  document.getElementById("capture-file").value = "";
  document.getElementById("mech-name").value = "";
  document.getElementById("dropzone").classList.remove("has-image");
  document.getElementById("dropzone-hint").textContent = "クリックして写真を選択";
  document.getElementById("build-mech-btn").disabled = true;
}

// ---------- mech list ----------

async function refreshMechs() {
  try {
    const data = await api("/mechs");
    state.mechs = data.mechs;
    renderMechGrid();
    renderDeployGrid();
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderMechGrid() {
  const grid = document.getElementById("mech-grid");
  grid.innerHTML = "";
  if (state.mechs.length === 0) {
    grid.innerHTML = '<div class="empty-hint">まだメカがありません。STEP 01 でメカを作りましょう。</div>';
    return;
  }
  for (const mech of state.mechs) {
    grid.appendChild(renderMechCard(mech));
  }
}

function renderMechCard(mech) {
  const card = document.createElement("div");
  card.className = "mech-card";

  const artFrame = document.createElement("div");
  artFrame.className = "art-frame";
  if (mech.art_url) {
    const img = document.createElement("img");
    img.src = mech.art_url;
    img.alt = mech.name;
    artFrame.appendChild(img);
  } else {
    artFrame.textContent = "NO IMAGE";
  }
  card.appendChild(artFrame);

  const badge = document.createElement("span");
  badge.className = `form-badge form-${mech.form}`;
  badge.textContent = FORM_LABELS[mech.form] || mech.form;
  card.appendChild(badge);

  const title = document.createElement("h3");
  title.textContent = mech.name;
  card.appendChild(title);

  const bars = document.createElement("div");
  bars.className = "stat-bars";
  for (const key of STAT_ORDER) {
    const value = mech.stats[key] ?? 0;
    const row = document.createElement("div");
    row.className = "stat-bar";
    row.innerHTML = `
      <span>${STAT_SHORT[key]}</span>
      <span class="track"><span class="fill" style="width:${Math.min(100, (value / STAT_MAX) * 100)}%"></span></span>
      <span>${value}</span>
    `;
    bars.appendChild(row);
  }
  card.appendChild(bars);
  return card;
}

// ---------- tactic presets + deploy grid ----------

async function refreshPresets() {
  try {
    const data = await api("/tactic-presets", { auth: false });
    state.presets = data.presets;
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderDeployGrid() {
  const grid = document.getElementById("deploy-grid");
  grid.innerHTML = "";
  for (const position of POSITIONS) {
    const slot = document.createElement("div");
    slot.className = "deploy-slot";
    slot.dataset.position = position.key;

    const label = document.createElement("div");
    label.className = "slot-label";
    label.textContent = position.label;
    slot.appendChild(label);

    const mechSelect = document.createElement("select");
    mechSelect.className = "form-select mech-select";
    mechSelect.innerHTML = buildMechOptions();
    slot.appendChild(mechSelect);

    const presetSelect = document.createElement("select");
    presetSelect.className = "form-select preset-select";
    presetSelect.style.marginTop = "8px";
    presetSelect.innerHTML = state.presets
      .map((preset) => `<option value="${preset.id}">${preset.label}</option>`)
      .join("");
    slot.appendChild(presetSelect);

    mechSelect.addEventListener("change", updateBattleButtonState);
    grid.appendChild(slot);
  }
  updateBattleButtonState();
}

function buildMechOptions() {
  if (state.mechs.length === 0) {
    return '<option value="">-- メカがありません --</option>';
  }
  const options = ['<option value="">-- 選択してください --</option>'];
  for (const mech of state.mechs) {
    options.push(`<option value="${mech.id}">${mech.name}（${FORM_LABELS[mech.form] || mech.form}）</option>`);
  }
  return options.join("");
}

function updateBattleButtonState() {
  const selects = document.querySelectorAll(".mech-select");
  const allSelected = selects.length === 3 && Array.from(selects).every((s) => s.value);
  document.getElementById("battle-btn").disabled = !allSelected;
}

// ---------- battle ----------

async function handleBattle() {
  const battleBtn = document.getElementById("battle-btn");
  const slots = Array.from(document.querySelectorAll(".deploy-slot")).map((slotEl) => ({
    mech_id: slotEl.querySelector(".mech-select").value,
    position: slotEl.dataset.position,
    preset: slotEl.querySelector(".preset-select").value,
  }));

  battleBtn.disabled = true;
  const originalLabel = battleBtn.textContent;
  try {
    battleBtn.innerHTML = '<span class="spinner"></span>交戦中…';
    const seed = Math.floor(Math.random() * 1_000_000);
    const created = await api("/battles", {
      method: "POST",
      auth: false,
      json: { team_name: `${state.userName || "Player"}隊`, slots, seed },
    });
    const detail = await api(`/battles/${created.id}`);
    renderBattleResult(detail);
    showPanel("panel-battle", true);
    document.getElementById("panel-battle").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    toast(err.message, "error");
  } finally {
    battleBtn.disabled = false;
    battleBtn.textContent = originalLabel;
  }
}

function renderBattleResult(detail) {
  const container = document.getElementById("battle-result");
  container.innerHTML = "";

  const banner = document.createElement("div");
  let bannerClass = "draw";
  let bannerText = `${detail.turns}ターンで決着つかず、引き分け`;
  if (detail.winner_team_id === "player") {
    bannerClass = "win";
    bannerText = `勝利！（${detail.turns}ターン / seed ${detail.seed}）`;
  } else if (detail.winner_team_id) {
    bannerClass = "lose";
    bannerText = `敗北…（${detail.turns}ターン / seed ${detail.seed}）`;
  }
  banner.className = `battle-banner ${bannerClass}`;
  banner.textContent = bannerText;
  container.appendChild(banner);

  const entries = detail.log_entries || [];
  if (entries.length === 0) {
    const fallback = document.createElement("pre");
    fallback.textContent = detail.log || "ログがありません";
    container.appendChild(fallback);
    return;
  }

  for (const entry of entries) {
    const turnEl = document.createElement("div");
    turnEl.className = "log-turn";

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `TURN ${entry.turn} — ${entry.actor_team === "player" ? "自軍" : "敵軍"} / ${positionLabel(entry.actor_position)}`;
    turnEl.appendChild(meta);

    const actionLine = document.createElement("div");
    actionLine.className = "action-line";
    actionLine.innerHTML = `<strong>${entry.actor_name}</strong> — 条件「${entry.condition_label}」→ ${actionLabelOf(entry.action)}`;
    turnEl.appendChild(actionLine);

    for (const dmg of entry.damage_events || []) {
      const dmgLine = document.createElement("div");
      dmgLine.className = `damage-line${dmg.defeated ? " defeated" : ""}`;
      dmgLine.textContent = `→ ${dmg.target_name} に ${dmg.damage} ダメージ${dmg.defeated ? "（撃破）" : ""}`;
      turnEl.appendChild(dmgLine);
    }
    if (entry.note) {
      const noteLine = document.createElement("div");
      noteLine.className = "damage-line";
      noteLine.textContent = `→ ${entry.note}`;
      turnEl.appendChild(noteLine);
    }
    container.appendChild(turnEl);
  }
}

function positionLabel(position) {
  const found = POSITIONS.find((p) => p.key === position);
  return found ? found.label : position;
}

function actionLabelOf(actionId) {
  // サーバーはaction IDのみを構造化ログに載せる（docs/05）。表示用ラベルは簡易マップで補う。
  const map = {
    normal_attack: "通常攻撃",
    high_power_attack: "高出力攻撃",
    accuracy_attack: "精密射撃",
    pierce_attack: "貫通攻撃",
    area_attack: "範囲攻撃",
    defend: "防御",
    evade: "回避",
    charge: "チャージ",
    disrupt: "妨害",
    finisher: "フィニッシャー",
    close_attack: "近接攻撃",
    intercept: "迎撃",
    backline_attack: "後衛狙い",
    sniper_shot: "狙撃",
    heavy_artillery: "重砲撃",
    normal_shot: "通常射撃",
    normal_shell: "通常砲撃",
  };
  return map[actionId] || actionId;
}

// ---------- ranking ----------

async function refreshRanking() {
  try {
    const data = await api("/ranking", { auth: false });
    const body = document.getElementById("ranking-body");
    body.innerHTML = "";
    data.entries.forEach((entry, idx) => {
      const row = document.createElement("tr");
      row.innerHTML = `<td>${idx + 1}</td><td>${entry.team_name}</td><td>${entry.rating}</td>`;
      body.appendChild(row);
    });
  } catch (err) {
    toast(err.message, "error");
  }
}

// ---------- boot ----------

function init() {
  document.getElementById("register-btn").addEventListener("click", handleRegister);
  document.getElementById("logout-btn").addEventListener("click", handleLogout);
  document.getElementById("battle-btn").addEventListener("click", handleBattle);
  document.getElementById("refresh-ranking-btn").addEventListener("click", refreshRanking);
  bindCaptureForm();
  tryRestoreSession();
}

document.addEventListener("DOMContentLoaded", init);
