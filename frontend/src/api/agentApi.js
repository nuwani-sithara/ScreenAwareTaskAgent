const BASE_URL = "http://localhost:8000"; // FastAPI backend


export async function startAgent(task) {
const res = await fetch(`${BASE_URL}/agent/start`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ task })
});
return res.json();
}


export async function getPerception() {
const res = await fetch(`${BASE_URL}/agent/perception`);
return res.json();
}


export async function getPlan() {
const res = await fetch(`${BASE_URL}/agent/plan`);
return res.json();
}


export async function getStatus() {
const res = await fetch(`${BASE_URL}/agent/status`);
return res.json();
}


export async function getLogs() {
const res = await fetch(`${BASE_URL}/agent/logs`);
return res.json();
}