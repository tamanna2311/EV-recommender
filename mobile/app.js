const DEFAULT_API_URL = "https://ev-recommender.onrender.com";
const isLocalHost = ["localhost", "127.0.0.1", ""].includes(window.location.hostname) || window.location.protocol === "file:";
const API_URL = window.EV_API_URL || (isLocalHost ? "http://127.0.0.1:8000" : DEFAULT_API_URL);
const BEHAVIOR_STORAGE_KEY = "evFinder.behavior.v2";

const form = document.querySelector("#preferenceForm");
const results = document.querySelector("#results");
const personalizedResults = document.querySelector("#personalizedResults");
const personalizedReason = document.querySelector("#personalizedReason");
const refreshPersonalized = document.querySelector("#refreshPersonalized");
const marketCount = document.querySelector("#marketCount");
const resultTemplate = document.querySelector("#resultTemplate");
const budget = document.querySelector("#budget");
const range = document.querySelector("#range");
const budgetValue = document.querySelector("#budgetValue");
const rangeValue = document.querySelector("#rangeValue");
const installButton = document.querySelector("#installButton");
const navButtons = document.querySelectorAll(".nav-button");
const views = document.querySelectorAll(".app-view");
const brandPreference = document.querySelector("#brandPreference");
const bodyPreference = document.querySelector("#bodyPreference");

const newsList = document.querySelector("#newsList");
const newsTemplate = document.querySelector("#newsTemplate");
const refreshNews = document.querySelector("#refreshNews");

const recordStatus = document.querySelector("#recordStatus");
const recordState = document.querySelector("#recordState");
const sampleCount = document.querySelector("#sampleCount");
const captureDuration = document.querySelector("#captureDuration");
const startCapture = document.querySelector("#startCapture");
const stopCapture = document.querySelector("#stopCapture");
const sendCapture = document.querySelector("#sendCapture");
const detectResults = document.querySelector("#detectResults");

const shareTitle = document.querySelector("#shareTitle");
const shareText = document.querySelector("#shareText");
const sharePost = document.querySelector("#sharePost");
const copyPost = document.querySelector("#copyPost");
const shareStatus = document.querySelector("#shareStatus");

let deferredInstallPrompt;
let captureRows = [];
let captureStartMs = 0;
let captureTimer;
let isRecording = false;

const activateView = (target) => {
  views.forEach((view) => view.classList.toggle("active", view.dataset.view === target));
  navButtons.forEach((button) => button.classList.toggle("active", button.dataset.target === target));
  window.scrollTo({ top: 0, behavior: "smooth" });
};

navButtons.forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.target));
});

const formatLakh = (value) => Number(value).toLocaleString("en-IN", { maximumFractionDigits: 1 });

const updateRangeLabels = () => {
  budgetValue.value = `${formatLakh(budget.value)} L`;
  rangeValue.value = `${Number(range.value).toLocaleString("en-IN")} km`;
};

const setNotice = (container, message) => {
  container.innerHTML = "";
  const notice = document.createElement("p");
  notice.className = "notice";
  notice.textContent = message;
  container.appendChild(notice);
};

const loadBehaviorEvents = () => {
  try {
    const events = JSON.parse(localStorage.getItem(BEHAVIOR_STORAGE_KEY) || "[]");
    return Array.isArray(events) ? events.slice(-60) : [];
  } catch {
    return [];
  }
};

const recordBehavior = (event) => {
  const events = loadBehaviorEvents();
  events.push({
    ...event,
    created_at: new Date().toISOString(),
  });
  localStorage.setItem(BEHAVIOR_STORAGE_KEY, JSON.stringify(events.slice(-80)));
};

const recordCarBehavior = (rec, type = "view_car") => {
  recordBehavior({
    type,
    car_id: rec.car_id,
    brand: rec.brand,
    body_type: rec.body_type,
    minimum_range_km: rec.real_world_range_km || rec.claimed_range_km,
    budget_lakh: rec.price_lakh,
    weight: type === "open_source" ? 1.6 : 1.2,
  });
};

const getPayload = () => {
  const data = new FormData(form);
  return {
    budget_lakh: Number(data.get("budget_lakh")),
    minimum_range_km: Number(data.get("minimum_range_km")),
    daily_travel_km: Number(data.get("daily_travel_km")),
    city: data.get("city"),
    state: data.get("state"),
    use_case: data.get("use_case"),
    preferred_body_type: data.get("preferred_body_type"),
    family_size: Number(data.get("family_size")),
    home_charging_available: data.get("home_charging_available") === "on",
    fast_charging_needed: data.get("fast_charging_needed") === "on",
    brand_preference: data.get("brand_preference"),
    priority: data.get("priority"),
  };
};

const displayPrice = (rec) => rec.price_text || `Rs ${formatLakh(rec.price_lakh)} Lakh`;
const displayRange = (rec) => rec.range_text || `${Number(rec.claimed_range_km).toLocaleString("en-IN")} km`;
const displayBattery = (rec) => rec.battery_text || `${formatLakh(rec.battery_capacity_kwh)} kWh`;

const renderRecommendations = (container, recommendations, options = {}) => {
  const emptyMessage = options.emptyMessage || "No cars matched this search. Try relaxing budget, range, or family size.";
  container.innerHTML = "";

  if (!recommendations.length) {
    setNotice(container, emptyMessage);
    return;
  }

  recommendations.forEach((rec) => {
    const card = resultTemplate.content.cloneNode(true);
    const article = card.querySelector(".result-card");
    const image = card.querySelector(".car-image");
    const status = card.querySelector(".status-pill");
    const link = card.querySelector(".details-link");
    const sales = card.querySelector(".sales");

    card.querySelector(".rank").textContent = `${options.rankLabel || "Pick"} #${rec.rank}`;
    card.querySelector("h2").textContent = `${rec.car_name}`;
    card.querySelector(".body-meta").textContent = [rec.brand, rec.body_type].filter(Boolean).join(" · ");
    card.querySelector(".match").textContent = `${rec.match_percentage}%`;
    card.querySelector(".price").textContent = displayPrice(rec);
    card.querySelector(".car-range").textContent = displayRange(rec);
    card.querySelector(".battery").textContent = displayBattery(rec);
    card.querySelector(".reason").textContent = rec.reason || "";
    card.querySelector(".drawbacks").textContent = rec.drawbacks || "";
    status.textContent = rec.status || "";

    if (rec.image_url) {
      image.src = rec.image_url;
      image.alt = `${rec.car_name} exterior`;
      image.addEventListener("error", () => image.remove());
    } else {
      image.remove();
    }

    if (rec.source_url) {
      link.href = rec.source_url;
      link.addEventListener("click", () => {
        recordCarBehavior(rec, "open_source");
        window.setTimeout(loadPersonalizedRecommendations, 250);
      });
    } else {
      link.remove();
    }

    if (rec.sales_latest_month) {
      sales.textContent = `${Number(rec.sales_latest_month).toLocaleString("en-IN")} recent sales`;
    }

    article.addEventListener("pointerdown", () => recordCarBehavior(rec));
    container.appendChild(card);
  });
};

const loadPersonalizedRecommendations = async () => {
  refreshPersonalized.disabled = true;
  const behaviorEvents = loadBehaviorEvents();
  setNotice(personalizedResults, "Loading recommendations...");

  try {
    const response = await fetch(`${API_URL}/recommend/personalized`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: behaviorEvents, limit: 6 }),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    personalizedReason.textContent = data.mode === "personalized"
      ? "Tuned from your recent searches and viewed cars."
      : "Popular Indian EVs with strong value signals.";
    renderRecommendations(personalizedResults, data.recommendations || [], {
      rankLabel: data.mode === "personalized" ? "For you" : "Popular",
      emptyMessage: "No market recommendations are available right now.",
    });
  } catch (error) {
    setNotice(personalizedResults, `Could not load recommendations. ${error.message}`);
  } finally {
    refreshPersonalized.disabled = false;
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector(".primary-button");
  submitButton.disabled = true;
  setNotice(results, "Finding the best EVs for you...");

  const preferencePayload = getPayload();
  recordBehavior({ type: "search", ...preferencePayload, weight: 1.25 });
  const payload = {
    ...preferencePayload,
    behavior_events: loadBehaviorEvents(),
  };

  try {
    const response = await fetch(`${API_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    renderRecommendations(results, data.recommendations || [], { rankLabel: "Match" });
    loadPersonalizedRecommendations();
  } catch (error) {
    setNotice(results, `Could not reach the recommendation API. ${error.message}`);
  } finally {
    submitButton.disabled = false;
  }
});

const formatArticleDate = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
};

const renderNews = (articles) => {
  newsList.innerHTML = "";

  if (!articles.length) {
    setNotice(newsList, "No EV news is available right now.");
    return;
  }

  articles.forEach((article) => {
    const card = newsTemplate.content.cloneNode(true);
    const link = card.querySelector("a");
    const meta = [article.source, formatArticleDate(article.published_at)].filter(Boolean).join(" - ");

    link.href = article.url;
    card.querySelector("h3").textContent = article.title;
    card.querySelector(".news-meta").textContent = meta;
    newsList.appendChild(card);
  });
};

const loadNews = async () => {
  refreshNews.disabled = true;
  setNotice(newsList, "Loading EV news...");

  try {
    const response = await fetch(`${API_URL}/news`);
    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    renderNews(data.articles || []);
  } catch (error) {
    setNotice(newsList, `Could not load EV news. ${error.message}`);
  } finally {
    refreshNews.disabled = false;
  }
};

const populateSelect = (select, values) => {
  const current = select.value;
  const options = ["Any", ...values.filter((value) => value && value !== "Any").sort((a, b) => a.localeCompare(b))];
  select.innerHTML = "";
  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  select.value = options.includes(current) ? current : "Any";
};

const loadCatalogFilters = async () => {
  try {
    const response = await fetch(`${API_URL}/cars`);
    if (!response.ok) return;
    const data = await response.json();
    const cars = data.cars || [];
    if (!cars.length) return;

    marketCount.textContent = `${cars.length.toLocaleString("en-IN")} models`;
    populateSelect(brandPreference, [...new Set(cars.map((car) => car.brand).filter(Boolean))]);
    populateSelect(bodyPreference, [...new Set(cars.map((car) => car.body_type).filter(Boolean))]);
  } catch {
    marketCount.textContent = "Market data";
  }
};

const updateCaptureStats = () => {
  sampleCount.textContent = captureRows.length.toLocaleString("en-IN");
  const duration = captureRows.length ? captureRows[captureRows.length - 1].time_sec : 0;
  captureDuration.textContent = duration.toFixed(1);
};

const setRecordingState = (state) => {
  recordState.textContent = state;
  recordStatus.classList.toggle("recording", state === "Recording");
};

const requestMotionAccess = async () => {
  if (!("DeviceMotionEvent" in window)) {
    throw new Error("Motion sensors are not available on this device.");
  }

  if (typeof DeviceMotionEvent.requestPermission === "function") {
    const permission = await DeviceMotionEvent.requestPermission();
    if (permission !== "granted") {
      throw new Error("Motion permission was not granted.");
    }
  }
};

const handleMotion = (event) => {
  const acceleration = event.accelerationIncludingGravity || event.acceleration;
  if (!acceleration) return;

  const x = Number(acceleration.x);
  const y = Number(acceleration.y);
  const z = Number(acceleration.z);
  if (![x, y, z].every(Number.isFinite)) return;

  const now = performance.now();
  if (!captureStartMs) {
    captureStartMs = now;
  }

  captureRows.push({
    time_sec: (now - captureStartMs) / 1000,
    timestamp_ms: Date.now(),
    x,
    y,
    z,
  });
};

const startRecording = async () => {
  try {
    await requestMotionAccess();
    captureRows = [];
    captureStartMs = 0;
    updateCaptureStats();
    setNotice(detectResults, "Recording accelerometer data...");
    setRecordingState("Recording");
    isRecording = true;
    startCapture.disabled = true;
    stopCapture.disabled = false;
    sendCapture.disabled = true;
    window.addEventListener("devicemotion", handleMotion);
    captureTimer = window.setInterval(updateCaptureStats, 250);
  } catch (error) {
    setNotice(detectResults, error.message);
  }
};

const stopRecording = () => {
  if (!isRecording) return;

  isRecording = false;
  window.removeEventListener("devicemotion", handleMotion);
  window.clearInterval(captureTimer);
  updateCaptureStats();
  setRecordingState("Stopped");
  startCapture.disabled = false;
  stopCapture.disabled = true;
  sendCapture.disabled = captureRows.length === 0;
  setNotice(detectResults, `${captureRows.length.toLocaleString("en-IN")} samples captured.`);
};

const captureToCsv = () => {
  const header = "time_sec,timestamp_ms,x,y,z";
  const lines = captureRows.map((row) => [
    row.time_sec.toFixed(6),
    row.timestamp_ms,
    row.x.toFixed(8),
    row.y.toFixed(8),
    row.z.toFixed(8),
  ].join(","));
  return [header, ...lines].join("\n");
};

const renderDetection = (data) => {
  detectResults.innerHTML = "";
  const card = document.createElement("article");
  card.className = "result-card";
  const body = document.createElement("div");
  body.className = "result-body";
  const windowsUsed = data.features?.windows_used ?? data.windows_used ?? 0;
  const durationSeconds = data.duration_seconds ?? 0;

  const title = document.createElement("h2");
  title.textContent = data.label || "Detection result";

  const meta = document.createElement("p");
  meta.className = "reason";
  const confidence = typeof data.confidence === "number" ? `${Math.round(data.confidence * 100)}% confidence` : "Confidence unavailable";
  const evProbability = typeof data.ev_probability === "number"
    ? ` EV probability: ${Math.round(data.ev_probability * 100)}%.`
    : "";
  meta.textContent = `${confidence}. ${windowsUsed} windows used from ${durationSeconds} seconds.${evProbability}`;

  const status = document.createElement("p");
  status.className = data.model_status === "trained_model" ? "reason" : "drawbacks";
  status.textContent = data.model_status === "trained_model"
    ? "Prediction used the trained detector model."
    : "Prediction used the fallback detector because no trained model file is deployed yet.";

  body.append(title, meta, status);
  card.appendChild(body);
  detectResults.appendChild(card);
};

const sendRecording = async () => {
  if (!captureRows.length) {
    setNotice(detectResults, "No accelerometer samples captured.");
    return;
  }

  sendCapture.disabled = true;
  setNotice(detectResults, "Sending CSV to detector...");

  try {
    const response = await fetch(`${API_URL}/detect`, {
      method: "POST",
      headers: { "Content-Type": "text/csv" },
      body: captureToCsv(),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Backend returned ${response.status}`);
    }

    renderDetection(data);
  } catch (error) {
    setNotice(detectResults, `Could not detect ride type. ${error.message}`);
  } finally {
    sendCapture.disabled = false;
  }
};

const getSharePayload = () => ({
  title: shareTitle.value.trim() || "EV Finder",
  text: shareText.value.trim(),
  url: window.location.origin,
});

const copyShareText = async () => {
  const payload = getSharePayload();
  const text = `${payload.title}\n\n${payload.text}\n\n${payload.url}`;
  await navigator.clipboard.writeText(text);
  setNotice(shareStatus, "Copied.");
};

sharePost.addEventListener("click", async () => {
  const payload = getSharePayload();
  try {
    if (navigator.share) {
      await navigator.share(payload);
      setNotice(shareStatus, "Shared.");
    } else {
      await copyShareText();
    }
  } catch (error) {
    setNotice(shareStatus, `Could not share. ${error.message}`);
  }
});

copyPost.addEventListener("click", async () => {
  try {
    await copyShareText();
  } catch (error) {
    setNotice(shareStatus, `Could not copy. ${error.message}`);
  }
});

[budget, range].forEach((input) => input.addEventListener("input", updateRangeLabels));
updateRangeLabels();

refreshPersonalized.addEventListener("click", loadPersonalizedRecommendations);
refreshNews.addEventListener("click", loadNews);
startCapture.addEventListener("click", startRecording);
stopCapture.addEventListener("click", stopRecording);
sendCapture.addEventListener("click", sendRecording);

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  installButton.hidden = false;
});

installButton.addEventListener("click", async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  installButton.hidden = true;
});

loadCatalogFilters();
loadPersonalizedRecommendations();
loadNews();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js");
  });
}
