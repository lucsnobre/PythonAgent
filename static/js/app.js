const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function setChipGroupSingle(containerId, defaultVal = null) {
  const box = document.getElementById(containerId);
  if (!box) return;
  const chips = Array.from(box.querySelectorAll('.chip'));
  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      chips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
    });
  });
  if (defaultVal) {
    const d = chips.find((c) => c.dataset.value == String(defaultVal));
    if (d) d.classList.add('active');
  }
}

function getActiveValue(containerId) {
  const box = document.getElementById(containerId);
  if (!box) return null;
  const active = box.querySelector('.chip.active');
  return active ? active.dataset.value : null;
}

function setupSteppers() {
  $$('.stepper .icon-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.stepTarget;
      const delta = parseInt(btn.dataset.step || '0', 10);
      const input = document.getElementById(id);
      const min = parseInt(input.min || '-9999', 10);
      const max = parseInt(input.max || '9999', 10);
      const step = parseInt(input.step || '1', 10);
      let val = parseInt(input.value || '0', 10);
      val = val + delta * step;
      if (val < min) val = min;
      if (val > max) val = max;
      input.value = String(val);
    });
  });
}

async function apiProfile() {
  const res = await fetch('/api/profile');
  return await res.json();
}

async function apiOnboarding(payload) {
  const res = await fetch('/api/onboarding', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  return await res.json();
}

async function apiChat(message) {
  const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }) });
  return await res.json();
}

function showOnboarding() {
  $('#onboarding').classList.remove('hidden');
  $('#chat').classList.add('hidden');
}

function showChat() {
  $('#onboarding').classList.add('hidden');
  $('#chat').classList.remove('hidden');
}

function addMessage(role, text) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'assistant' ? 'GB' : 'You';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  wrap.appendChild(avatar);
  wrap.appendChild(bubble);
  const list = $('#messages');
  list.appendChild(wrap);
  list.scrollTop = list.scrollHeight;
}

async function initialize() {
  setupSteppers();
  setChipGroupSingle('gender', 'male');
  setChipGroupSingle('main_goal', 'hypertrophy');
  setChipGroupSingle('experience', 'beginner');
  setChipGroupSingle('days_per_week', '4');
  setChipGroupSingle('minutes_per_workout', '60');
  setChipGroupSingle('injuries_yes_no', 'no');

  const p = await apiProfile();
  if (p.ok && p.profile) {
    showChat();
    addMessage('assistant', `Welcome back. Profile: ${p.profile_summary}`);
  } else {
    showOnboarding();
  }

  $('#startBtn').addEventListener('click', async () => {
    const payload = {
      weight_kg: parseInt($('#weight').value, 10),
      height_cm: parseInt($('#height').value, 10),
      age: parseInt($('#age').value, 10),
      gender: getActiveValue('gender'),
      main_goal: getActiveValue('main_goal'),
      experience: getActiveValue('experience'),
      days_per_week: parseInt(getActiveValue('days_per_week'), 10),
      minutes_per_workout: parseInt(getActiveValue('minutes_per_workout'), 10),
      injuries_yes_no: getActiveValue('injuries_yes_no') === 'yes',
      injuries_details: $('#injuries_details').value.trim(),
    };

    const res = await apiOnboarding(payload);
    if (!res.ok) {
      alert(res.error || 'Please complete the required fields.');
      return;
    }
    showChat();
    addMessage('assistant', `Your profile: ${res.profile_summary}`);
  });

  const send = async () => {
    const input = $('#chatInput');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage('user', text);
    $('#sendBtn').disabled = true;
    try {
      const res = await apiChat(text);
      if (res.ok) {
        addMessage('assistant', res.reply);
      } else {
        addMessage('assistant', res.error || 'Error generating reply.');
      }
    } catch (e) {
      addMessage('assistant', 'Network error.');
    } finally {
      $('#sendBtn').disabled = false;
    }
  };

  $('#sendBtn').addEventListener('click', send);
  $('#chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      send();
    }
  });
}

window.addEventListener('DOMContentLoaded', initialize);
