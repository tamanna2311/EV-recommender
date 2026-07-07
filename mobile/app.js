const API_URL = "https://ev-recommender.onrender.com";

const form = document.querySelector("#preferenceForm");
const results = document.querySelector("#results");
const template = document.querySelector("#resultTemplate");
const budget = document.querySelector("#budget");
const range = document.querySelector("#range");
const budgetValue = document.querySelector("#budgetValue");
const rangeValue = document.querySelector("#rangeValue");
const installButton = document.querySelector("#installButton");
const navButtons = document.querySelectorAll(".nav-button");
const views = document.querySelectorAll(".app-view");

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

const updateRangeLabels = () => {
  budgetValue.value = `${Number(budget.value).toLocaleString("en-IN")} L`;
  rangeValue.value = `${Number(range.value).toLocaleString("en-IN")} km`;
};

const setNotice = (container, message) => {
  container.innerHTML = "";
  const notice = document.createElement("p");
  notice.className = "notice";
  notice.textContent = message;
  container.appendChild(notice);
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

const renderRecommendations = (recommendations) => {
  results.innerHTML = "";

  if (!recommendations.length) {
    setNotice(results, "No cars matched this search. Try relaxing budget, range, or family size.");
    return;
  }

  recommendations.forEach((rec) => {
    const card = template.content.cloneNode(true);
    card.querySelector(".rank").textContent = `Recommendation #${rec.rank}`;
    card.querySelector("h2").textContent = `${rec.car_name} - ${rec.brand}`;
    card.querySelector(".match").textContent = `${rec.match_percentage}%`;
    card.querySelector(".price").textContent = `Price: Rs ${rec.price_lakh} L`;
    card.querySelector(".car-range").textContent = `Range: ${rec.claimed_range_km} km`;
    card.querySelector(".battery").textContent = `Battery: ${rec.battery_capacity_kwh} kWh`;
    card.querySelector(".reason").textContent = rec.reason;
    card.querySelector(".drawbacks").textContent = rec.drawbacks;
    results.appendChild(card);
  });
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector(".primary-button");
  submitButton.disabled = true;
  setNotice(results, "Finding the best EVs for you...");

  try {
    const response = await fetch(`${API_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(getPayload()),
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    renderRecommendations(data.recommendations || []);
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

  const title = document.createElement("h2");
  title.textContent = data.label || "Detection result";

  const meta = document.createElement("p");
  meta.className = "reason";
  const confidence = typeof data.confidence === "number" ? `${Math.round(data.confidence * 100)}% confidence` : "Confidence unavailable";
  meta.textContent = `${confidence}. ${data.windows_used || 0} windows used from ${data.duration_seconds || 0} seconds.`;

  const status = document.createElement("p");
  status.className = "drawbacks";
  status.textContent = data.model_status === "trained_model"
    ? "Prediction used the trained detector model."
    : "Prediction used the fallback detector because no trained model file is deployed yet.";

  card.append(title, meta, status);
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

loadNews();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js");
  });
}
