const form = document.querySelector("#scoreForm");
const resumeInput = document.querySelector("#resume");
const jobsInput = document.querySelector("#jobs");
const resumeCount = document.querySelector("#resumeCount");
const jobsCount = document.querySelector("#jobsCount");
const resumeFile = document.querySelector("#resumeFile");
const fileStatus = document.querySelector("#fileStatus");
const resumeCard = document.querySelector("#resumeCard");
const statusLine = document.querySelector("#status");
const submitButton = document.querySelector("#submitButton");
const sampleButton = document.querySelector("#sampleButton");
const heroSample = document.querySelector("#heroSample");
const resultsSection = document.querySelector("#results");
const resultMeta = document.querySelector("#resultMeta");
const jobList = document.querySelector("#jobList");
const copyButton = document.querySelector("#copyButton");
const downloadButton = document.querySelector("#downloadButton");

let latestResult = null;
let latestSamplePromise = null;

function updateCounts() {
  resumeCount.textContent = `${resumeInput.value.length.toLocaleString()} chars`;
  jobsCount.textContent = `${jobsInput.value.length.toLocaleString()} chars`;
}

function setStatus(message, isError = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle("error", isError);
}

function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function loadSample() {
  if (!latestSamplePromise) {
    latestSamplePromise = fetch("/api/sample").then((response) => {
      if (!response.ok) throw new Error("The sample could not be loaded.");
      return response.json();
    });
  }
  setStatus("Loading the fictional sample…");
  return latestSamplePromise
    .then((sample) => {
      resumeInput.value = sample.resume;
      jobsInput.value = sample.jobs;
      updateCounts();
      setStatus("Sample loaded. Press “Rank my roles” to see the shortlist.");
      document.querySelector("#workbench").scrollIntoView({ behavior: "smooth", block: "start" });
    })
    .catch((error) => setStatus(error.message, true));
}

async function importResume(file) {
  if (!file) return;
  if (file.size > 8_000_000) {
    fileStatus.textContent = "File is larger than 8 MB.";
    fileStatus.classList.add("error");
    return;
  }
  fileStatus.textContent = `Reading ${file.name} locally…`;
  fileStatus.classList.remove("error");
  try {
    const response = await fetch(`/api/extract?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "This file could not be read.");
    resumeInput.value = payload.text;
    updateCounts();
    fileStatus.textContent = `${file.name} · ${payload.characters.toLocaleString()} characters`;
    setStatus("Resume imported locally. Review the extracted text before ranking jobs.");
  } catch (error) {
    fileStatus.textContent = error.message;
    fileStatus.classList.add("error");
    setStatus(error.message, true);
  } finally {
    resumeFile.value = "";
  }
}

async function score() {
  const resume = resumeInput.value.trim();
  const jobs = jobsInput.value.trim();
  if (resume.length < 20) {
    setStatus("Add a little more resume text so evidence can be compared.", true);
    resumeInput.focus();
    return;
  }
  if (!jobs) {
    setStatus("Add at least one job description.", true);
    jobsInput.focus();
    return;
  }

  submitButton.disabled = true;
  setStatus("Matching requirements against your resume…");
  try {
    const response = await fetch("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume, jobs }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "The analysis could not be completed.");
    latestResult = payload;
    renderResults(payload);
    setStatus(`Ranked ${payload.jobs.length} role${payload.jobs.length === 1 ? "" : "s"} locally.`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    submitButton.disabled = false;
  }
}

function fitClass(label) {
  if (label === "Strong fit") return "";
  if (label === "Worth tailoring") return "tailoring";
  if (label === "Stretch") return "stretch";
  return "low";
}

function addDetailBlock(parent, title, content) {
  if (!content) return;
  const block = createElement("div", "detail-block");
  block.append(createElement("h4", "", title), content);
  parent.append(block);
}

function makeChips(items, className = "") {
  const wrapper = createElement("div", "chip-list");
  for (const item of items) {
    wrapper.append(createElement("span", `chip ${className}`.trim(), item));
  }
  return wrapper;
}

function makeEvidence(matched) {
  const wrapper = createElement("div", "evidence-list");
  for (const item of matched.slice(0, 8)) {
    const details = createElement("details", "evidence-item");
    const summary = createElement("summary");
    summary.append(createElement("span", "", item.skill));
    summary.append(createElement("small", "", item.priority === "must" ? "MUST-HAVE" : "PREFERRED"));
    details.append(summary);
    for (const evidence of item.evidence) {
      details.append(createElement("p", "evidence-copy", evidence));
    }
    wrapper.append(details);
  }
  return wrapper;
}

function makeFlags(flags) {
  const wrapper = createElement("div", "flag-list");
  for (const flag of flags) {
    const row = createElement("div", "flag");
    row.append(createElement("strong", "", flag.label));
    row.append(createElement("p", "", flag.detail));
    wrapper.append(row);
  }
  return wrapper;
}

function makeActions(actions) {
  const list = createElement("ul", "action-list");
  for (const action of actions) {
    list.append(createElement("li", "", action));
  }
  return list;
}

function jobCard(job) {
  const card = createElement("article", "job-card");
  const scoreColumn = createElement("div", "score-column");
  const ring = createElement("div", "score-ring");
  ring.style.setProperty("--score", job.score);
  const ringValue = createElement("div", "score-ring-value", job.score);
  ringValue.append(createElement("small", "", "FIT SCORE"));
  ring.append(ringValue);
  scoreColumn.append(ring, createElement("div", "rank-label", `RANK #${job.rank}`));

  const main = createElement("div", "job-main");
  const kicker = createElement("div", "job-kicker");
  kicker.append(
    createElement("span", `fit-pill ${fitClass(job.label)}`.trim(), job.label),
    createElement("span", "confidence", `${job.confidence} confidence`),
  );
  main.append(kicker);
  main.append(createElement("h3", "job-title", job.title));

  const companyLine = createElement("p", "company-line");
  for (const value of [job.company, job.location, job.salary].filter(Boolean)) {
    companyLine.append(createElement("span", "", value));
  }
  main.append(companyLine, createElement("p", "job-summary", job.summary));

  const metrics = createElement("div", "metric-row");
  const metricValues = [
    [`${job.must_coverage}%`, "must-have coverage"],
    [`${job.requirement_count}`, "recognized requirements"],
    [`${job.matched.length}`, "evidence matches"],
  ];
  for (const [value, label] of metricValues) {
    const metric = createElement("div", "metric");
    metric.append(createElement("strong", "", value), createElement("span", "", label));
    metrics.append(metric);
  }
  main.append(metrics);

  if (job.matched.length) addDetailBlock(main, "Why it matched · click to inspect evidence", makeEvidence(job.matched));
  if (job.missing_must.length) addDetailBlock(main, "Must-have gaps", makeChips(job.missing_must, "must-gap"));
  if (job.missing_preferred.length) {
    addDetailBlock(main, "Nice to have, not a blocker", makeChips(job.missing_preferred, "preferred-gap"));
  }
  if (job.red_flags.length) addDetailBlock(main, "Check before applying", makeFlags(job.red_flags));
  addDetailBlock(main, "Your next best action", makeActions(job.next_actions));

  card.append(scoreColumn, main);
  return card;
}

function renderResults(result) {
  jobList.replaceChildren();
  for (const job of result.jobs) jobList.append(jobCard(job));
  const top = result.jobs[0];
  resultMeta.textContent = `${result.jobs.length} roles ranked · top match: ${top.title} at ${top.company} · processed locally`;
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function copyTopSummary() {
  if (!latestResult?.jobs?.length) return;
  const job = latestResult.jobs[0];
  const gaps = job.missing_must.length ? `Must-have gaps: ${job.missing_must.join(", ")}.` : "No recognized must-have gaps.";
  const text = `${job.title} @ ${job.company}\nFit ${job.score}/100 (${job.label})\n${job.summary}\n${gaps}\nNext: ${job.next_actions[0]}`;
  try {
    await navigator.clipboard.writeText(text);
    setStatus("Top shortlist summary copied.");
  } catch {
    setStatus("Clipboard access was blocked. Use Download JSON instead.", true);
  }
}

function downloadJson() {
  if (!latestResult) return;
  const blob = new Blob([JSON.stringify(latestResult, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "applyless-shortlist.json";
  link.click();
  URL.revokeObjectURL(link.href);
}

resumeInput.addEventListener("input", updateCounts);
jobsInput.addEventListener("input", updateCounts);
resumeFile.addEventListener("change", () => importResume(resumeFile.files[0]));
sampleButton.addEventListener("click", loadSample);
heroSample.addEventListener("click", loadSample);
copyButton.addEventListener("click", copyTopSummary);
downloadButton.addEventListener("click", downloadJson);
form.addEventListener("submit", (event) => {
  event.preventDefault();
  score();
});
resumeCard.addEventListener("dragover", (event) => {
  event.preventDefault();
  resumeCard.classList.add("dragging");
});
resumeCard.addEventListener("dragleave", () => resumeCard.classList.remove("dragging"));
resumeCard.addEventListener("drop", (event) => {
  event.preventDefault();
  resumeCard.classList.remove("dragging");
  importResume(event.dataTransfer.files[0]);
});

updateCounts();

