import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const state = {
  supabase: null,
  session: null,
  refreshTimer: null,
};

const configPanel = document.querySelector("#config-panel");
const loginPanel = document.querySelector("#login-panel");
const dashboard = document.querySelector("#dashboard");
const commandsPanel = document.querySelector("#commands-panel");
const message = document.querySelector("#message");
const campaignList = document.querySelector("#campaign-list");
const emptyState = document.querySelector("#empty-state");
const commandList = document.querySelector("#command-list");
const sessionLabel = document.querySelector("#session-label");
const logoutButton = document.querySelector("#logout-button");
const resetConfigButton = document.querySelector("#reset-config-button");
const statusFilter = document.querySelector("#status-filter");

const PUBLISHABLE_STATUSES = new Set([
  "APROVADA",
  "PRONTA_PARA_PUBLICAR",
  "ERRO_PUBLICACAO",
]);

function showMessage(text, kind = "") {
  message.textContent = text;
  message.className = `message${kind ? ` ${kind}` : ""}`;
  message.classList.toggle("hidden", !text);
}

function showPanelMessage(id, text, kind = "") {
  const target = document.querySelector(`#${id}`);
  if (!target) return;
  target.textContent = text;
  target.className = `message${kind ? ` ${kind}` : ""}`;
  target.classList.toggle("hidden", !text);
}

function errorText(error, fallback) {
  return error?.message || fallback;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString("pt-BR");
}

function displayValue(value) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function validateSupabaseUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || (url.protocol === "http:" && url.hostname === "localhost");
  } catch {
    return false;
  }
}

function validatePublishableKey(value) {
  const key = value.trim();
  if (!key) return "Informe a chave publicável do Supabase.";
  if (key.startsWith("sb_secret_") || key.includes("service_role")) {
    return "Esta é uma chave secreta. Use a Publishable key.";
  }
  if (!key.startsWith("sb_publishable_") && !key.startsWith("eyJ")) {
    return "Use a Publishable key ou a chave pública anon legada.";
  }
  return "";
}

function setAuthenticatedView(session) {
  state.session = session;
  const authenticated = Boolean(session);
  configPanel.classList.toggle("hidden", authenticated || Boolean(state.supabase));
  loginPanel.classList.toggle("hidden", !state.supabase || authenticated);
  dashboard.classList.toggle("hidden", !authenticated);
  commandsPanel.classList.toggle("hidden", !authenticated);
  logoutButton.classList.toggle("hidden", !authenticated);
  sessionLabel.textContent = authenticated
    ? session.user.email || "Autenticado"
    : state.supabase
      ? "Não autenticado"
      : "Desconectado";
}

async function connectSupabase(event) {
  event.preventDefault();
  const url = document.querySelector("#supabase-url").value.trim();
  const key = document.querySelector("#publishable-key").value.trim();
  if (!validateSupabaseUrl(url)) {
    showPanelMessage("config-message", "Informe uma URL HTTPS válida do Supabase.", "error");
    return;
  }
  const keyError = validatePublishableKey(key);
  if (keyError) {
    showPanelMessage("config-message", keyError, "error");
    return;
  }
  state.supabase = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: true, detectSessionInUrl: true },
  });
  state.supabase.auth.onAuthStateChange((eventName, session) => {
    if (eventName === "SIGNED_OUT") {
      stopRefresh();
    }
    setAuthenticatedView(session);
    if (session) void refreshData();
  });
  setAuthenticatedView(null);
  showPanelMessage("config-message", "Supabase conectado. Faça login para continuar.", "success");
}

async function signIn(event) {
  event.preventDefault();
  if (!state.supabase) return;
  const submitButton = event.currentTarget.querySelector("button[type=submit]");
  const email = document.querySelector("#email").value.trim();
  const password = document.querySelector("#password").value;
  submitButton.disabled = true;
  submitButton.textContent = "Entrando...";
  showPanelMessage("auth-message", "Validando acesso...", "");
  try {
    const { error } = await state.supabase.auth.signInWithPassword({ email, password });
    if (error) {
      showPanelMessage(
        "auth-message",
        `Não foi possível entrar: ${errorText(error, "credenciais inválidas")}`,
        "error",
      );
      return;
    }
    document.querySelector("#password").value = "";
    showMessage("Login realizado. Carregando campanhas...", "success");
  } catch (error) {
    const detail = errorText(error, "verifique a rede");
    const messageText = /invalid api key/i.test(detail)
      ? "Chave inválida para esta URL. Copie a Publishable key do mesmo projeto Supabase."
      : `Não foi possível conectar: ${detail}`;
    showPanelMessage(
      "auth-message",
      messageText,
      "error",
    );
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Entrar";
  }
}

async function signOut() {
  if (!state.supabase) return;
  const { error } = await state.supabase.auth.signOut();
  if (error) showMessage(`Não foi possível sair: ${errorText(error, "erro de sessão")}`, "error");
}

function resetConfiguration() {
  stopRefresh();
  state.supabase = null;
  state.session = null;
  document.querySelector("#publishable-key").value = "";
  document.querySelector("#password").value = "";
  setAuthenticatedView(null);
  showPanelMessage(
    "config-message",
    "Informe novamente a URL e a chave do projeto.",
    "success",
  );
}

async function loadCampaigns() {
  const status = statusFilter.value;
  let query = state.supabase
    .from("mkt_campaigns")
    .select(
      "campaign_id,version,status,publico,golpe,canal,midia,basename," +
      "storage_bucket,storage_path,legenda,roteiro,preset,metadata,plataforma," +
      "id_retornado,mensagem_erro,data_criacao,data_aprovacao,data_publicacao,atualizado_em",
    )
    .order("atualizado_em", { ascending: false })
    .limit(50);
  if (status) query = query.eq("status", status);
  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

async function loadCommands() {
  const { data, error } = await state.supabase
    .from("mkt_campaign_commands")
    .select("id,campaign_id,action,status,requested_by,result,created_at,completed_at")
    .order("created_at", { ascending: false })
    .limit(20);
  if (error) throw error;
  return data || [];
}

async function createPreview(assetFrame, campaign) {
  const storagePath = campaign.storage_path;
  if (!storagePath) {
    const placeholder = document.createElement("p");
    placeholder.className = "asset-placeholder";
    placeholder.textContent = "Asset ainda não disponível.";
    assetFrame.append(placeholder);
    return;
  }
  const { data, error } = await state.supabase.storage
    .from(campaign.storage_bucket || "mkt-campaign-assets")
    .createSignedUrl(storagePath, 300);
  if (error || !data?.signedUrl) {
    const placeholder = document.createElement("p");
    placeholder.className = "asset-placeholder";
    placeholder.textContent = "Não foi possível carregar a prévia.";
    assetFrame.append(placeholder);
    return;
  }
  const url = new URL(data.signedUrl);
  if (url.protocol !== "https:") {
    throw new Error("URL de prévia insegura.");
  }
  const isVideo = storagePath.toLowerCase().endsWith(".mp4");
  const media = document.createElement(isVideo ? "video" : "img");
  media.src = url.href;
  media.alt = `Prévia da campanha ${campaign.campaign_id}`;
  if (isVideo) {
    media.controls = true;
    media.preload = "metadata";
  }
  assetFrame.append(media);
}

function addMetaItem(container, label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = displayValue(value);
  container.append(term, description);
}

function canRequestPublication(campaign) {
  return (
    PUBLISHABLE_STATUSES.has(campaign.status) &&
    !String(campaign.canal || "").toLowerCase().includes("tiktok")
  );
}

async function requestPublication(campaign, button) {
  if (!canRequestPublication(campaign)) {
    showMessage("Esta campanha não pode ser publicada automaticamente.", "error");
    return;
  }
  const confirmed = window.confirm(
    `Confirma a publicação da campanha ${campaign.campaign_id} no Instagram?`,
  );
  if (!confirmed) return;
  button.disabled = true;
  try {
    const { data: userData, error: userError } = await state.supabase.auth.getUser();
    if (userError || !userData?.user?.id) {
      throw userError || new Error("Sessão autenticada não encontrada.");
    }
    const { error } = await state.supabase.from("mkt_campaign_commands").insert({
      campaign_id: campaign.campaign_id,
      action: "PUBLISH",
      requested_by: userData.user.id,
      payload: { confirmed: true, confirmed_at: new Date().toISOString() },
    });
    if (error) {
      throw new Error("Já existe um comando pendente ou a campanha não está acessível.");
    }
    showMessage("Comando criado. O Linux processará a publicação.", "success");
    await refreshData();
  } catch (error) {
    showMessage(errorText(error, "Não foi possível criar o comando."), "error");
  } finally {
    button.disabled = false;
  }
}

async function renderCampaigns(campaigns) {
  campaignList.replaceChildren();
  emptyState.classList.toggle("hidden", campaigns.length > 0);
  for (const campaign of campaigns) {
    const card = document.querySelector("#campaign-template").content.cloneNode(true);
    card.querySelector(".campaign-id").textContent = campaign.campaign_id;
    card.querySelector(".campaign-title").textContent =
      campaign.metadata?.headline || campaign.golpe || "Campanha Guardian AI";
    card.querySelector(".campaign-copy").textContent =
      campaign.legenda || campaign.roteiro || "Sem legenda registrada.";
    const status = card.querySelector(".status-pill");
    status.textContent = campaign.status;
    status.classList.add(`status-${String(campaign.status).toLowerCase()}`);
    const meta = card.querySelector(".campaign-meta");
    addMetaItem(meta, "Público", campaign.publico);
    addMetaItem(meta, "Canal", campaign.canal);
    addMetaItem(meta, "Mídia", campaign.midia);
    addMetaItem(meta, "Atualizada", formatDate(campaign.atualizado_em));
    const button = card.querySelector(".publish-button");
    button.addEventListener("click", () => void requestPublication(campaign, button));
    button.disabled = !canRequestPublication(campaign);
    if (campaign.status === "PUBLICADA") button.textContent = "Já publicada";
    if (String(campaign.canal || "").toLowerCase().includes("tiktok")) {
      button.textContent = "Upload manual TikTok";
    }
    await createPreview(card.querySelector(".asset-frame"), campaign);
    campaignList.append(card);
  }
}

function renderCommands(commands) {
  commandList.replaceChildren();
  if (!commands.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Nenhum comando registrado.";
    commandList.append(empty);
    return;
  }
  for (const command of commands) {
    const row = document.createElement("div");
    row.className = "command-row";
    const id = document.createElement("span");
    id.className = "command-id";
    id.textContent = `${command.campaign_id} · ${command.action}`;
    const status = document.createElement("span");
    status.className = "status-pill";
    status.textContent = command.status;
    const date = document.createElement("time");
    date.className = "command-id";
    date.textContent = formatDate(command.completed_at || command.created_at);
    row.append(id, status, date);
    commandList.append(row);
  }
}

async function refreshData() {
  if (!state.supabase || !state.session) return;
  try {
    const [campaigns, commands] = await Promise.all([loadCampaigns(), loadCommands()]);
    await renderCampaigns(campaigns);
    renderCommands(commands);
    showMessage("");
  } catch (error) {
    showMessage(errorText(error, "Não foi possível carregar os dados."), "error");
  }
}

function startRefresh() {
  stopRefresh();
  state.refreshTimer = window.setInterval(() => void refreshData(), 15000);
}

function stopRefresh() {
  if (state.refreshTimer) window.clearInterval(state.refreshTimer);
  state.refreshTimer = null;
}

document.querySelector("#config-form").addEventListener("submit", (event) => {
  void connectSupabase(event);
});
document.querySelector("#login-form").addEventListener("submit", (event) => {
  void signIn(event);
});
logoutButton.addEventListener("click", () => void signOut());
resetConfigButton.addEventListener("click", resetConfiguration);
document.querySelector("#refresh-button").addEventListener("click", () => void refreshData());
statusFilter.addEventListener("change", () => void refreshData());

setAuthenticatedView(null);
