const $ = (selector) => document.querySelector(selector);
const appState = { date: new Date(), today: new Date(), user: null, profile: null, predictionId: null, authMode: 'register' };

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Something went wrong');
  return data;
}

function formatISO(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function sameDay(a, b) { return formatISO(a) === formatISO(b); }

function showToast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(showToast.timeout);
  showToast.timeout = setTimeout(() => $('#toast').classList.remove('visible'), 2600);
}

function showOnly(id) {
  ['authScreen', 'onboardingScreen', 'appShell', 'loadingScreen'].forEach((name) => {
    const element = $(`#${name}`);
    element.hidden = name !== id;
  });
}

async function bootstrap() {
  showOnly('loadingScreen');
  try {
    const data = await api('/api/me');
    appState.user = data.user; appState.profile = data.profile;
    if (!data.profile) return showOnly('onboardingScreen');
    hydrateUser(); showOnly('appShell'); await loadPrediction();
  } catch (error) {
    showOnly('authScreen');
  }
}

function hydrateUser() {
  const firstName = appState.user.name.split(' ')[0];
  $('#sidebarName').textContent = appState.user.name;
  $('#greetingName').textContent = `${firstName}.`;
  $('.avatar').textContent = appState.user.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase();
  const { kundli } = appState.profile;
  $('#birthDateTime').textContent = `${appState.profile.birthDate} · ${appState.profile.birthTime}`;
  $('#birthplaceValue').textContent = appState.profile.birthplace;
  $('#lagnaValue').textContent = `${kundli.ascendant.sign} ${kundli.ascendant.degree}°`;
  $('#rashiValue').textContent = kundli.moon_sign;
  $('#nakshatraValue').textContent = `${kundli.nakshatra}, Pada ${kundli.pada}`;
  $('#dashaValue').textContent = kundli.current_dasha;
  $('.chart-center b').textContent = kundli.ascendant.sign;
}

function updateDate() {
  const isToday = sameDay(appState.date, appState.today);
  $('#dayLabel').textContent = isToday ? 'TODAY' : 'PAST READING';
  $('#dateLabel').textContent = appState.date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
  $('#nextDay').disabled = isToday;
}

async function loadPrediction() {
  updateDate();
  try {
    const { id, content, rating } = await api(`/api/prediction/${formatISO(appState.date)}`);
    appState.predictionId = id;
    $('#scoreValue').textContent = content.score;
    $('#scoreRing').style.background = `conic-gradient(var(--saffron) 0 ${content.score}%, #ded8cc ${content.score}%)`;
    $('#energyValue').textContent = content.energy;
    $('#transitTitle').textContent = content.transit;
    $('#predictionSummary').textContent = content.summary;
    $('#predictionDetail').textContent = content.title;
    $('#relationshipsText').textContent = content.categories.Relationships;
    $('#workText').textContent = content.categories['Work & purpose'];
    $('#wellbeingText').textContent = content.categories.Wellbeing;
    $('#reflectionText').textContent = content.reflection;
    document.querySelectorAll('.feedback-options button').forEach((button) => button.classList.toggle('selected', Number(button.dataset.rating) === rating));
  } catch (error) { showToast(error.message); }
}

$('#authForm').addEventListener('submit', async (event) => {
  event.preventDefault(); $('#authError').textContent = '';
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    await api(`/api/${appState.authMode}`, { method: 'POST', body: JSON.stringify(values) });
    await bootstrap();
  } catch (error) { $('#authError').textContent = error.message; }
});

$('#switchAuth').addEventListener('click', () => {
  appState.authMode = appState.authMode === 'register' ? 'login' : 'register';
  const login = appState.authMode === 'login';
  $('#authTitle').textContent = login ? 'Welcome back' : 'Begin your journey';
  $('#authIntro').textContent = login ? 'Sign in to return to your daily reading.' : 'Create an account to discover the patterns written in your birth chart.';
  $('#nameField').hidden = login; $('#nameField input').required = !login;
  $('#authForm button[type="submit"]').firstChild.textContent = login ? 'Sign in ' : 'Create my account ';
  $('#switchPrompt').textContent = login ? 'New to Jyotish?' : 'Already have an account?';
  $('#switchAuth').textContent = login ? 'Create an account' : 'Sign in';
});

$('#birthForm').addEventListener('submit', async (event) => {
  event.preventDefault(); $('#birthError').textContent = '';
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const data = await api('/api/profile', { method: 'POST', body: JSON.stringify(values) });
    appState.profile = data.profile; hydrateUser(); showOnly('appShell'); await loadPrediction();
  } catch (error) { $('#birthError').textContent = error.message; }
});

$('#previousDay').addEventListener('click', () => { appState.date.setDate(appState.date.getDate() - 1); loadPrediction(); });
$('#nextDay').addEventListener('click', () => { if (!sameDay(appState.date, appState.today)) appState.date.setDate(appState.date.getDate() + 1); loadPrediction(); });

document.querySelectorAll('.nav-item').forEach((button) => button.addEventListener('click', async () => {
  document.querySelectorAll('.nav-item').forEach((item) => item.classList.remove('active')); button.classList.add('active');
  document.querySelectorAll('.view').forEach((view) => view.classList.remove('active')); $(`#${button.dataset.view}View`).classList.add('active');
  $('.sidebar').classList.remove('open');
  if (button.dataset.view === 'calendar') {
    const { readings } = await api('/api/history');
    $('#calendarList').innerHTML = readings.length ? readings.map((reading) => `<button class="history-row" data-date="${reading.date}"><span><small>${new Date(`${reading.date}T12:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })}</small><strong>${reading.content.title}</strong></span><span>${reading.rating === 1 ? 'Very much' : reading.rating === 0 ? 'Somewhat' : reading.rating === -1 ? 'Not really' : 'Not rated'} →</span></button>`).join('') : '<p class="empty-message">Your readings will appear here.</p>';
    document.querySelectorAll('.history-row').forEach((row) => row.addEventListener('click', () => { appState.date = new Date(`${row.dataset.date}T12:00`); document.querySelector('[data-view="today"]').click(); loadPrediction(); }));
  }
}));

$('#menuButton').addEventListener('click', () => $('.sidebar').classList.toggle('open'));
document.querySelectorAll('.feedback-options button').forEach((button) => button.addEventListener('click', async () => {
  await api(`/api/feedback/${appState.predictionId}`, { method: 'POST', body: JSON.stringify({ rating: Number(button.dataset.rating) }) });
  document.querySelectorAll('.feedback-options button').forEach((option) => option.classList.toggle('selected', option === button)); showToast('Thank you — your reflection has been saved.');
}));

const dialog = $('#journalDialog');
$('#openJournal').addEventListener('click', () => { $('#journalText').value = localStorage.getItem(`jyotish-journal-${formatISO(appState.date)}`) || ''; dialog.showModal(); });
$('#closeJournal').addEventListener('click', () => dialog.close());
$('#saveJournal').addEventListener('click', () => { localStorage.setItem(`jyotish-journal-${formatISO(appState.date)}`, $('#journalText').value); dialog.close(); showToast('Your private reflection is saved on this device.'); });
$('#profileButton').addEventListener('click', () => document.querySelector('[data-view="kundli"]').click());
$('#logoutButton').addEventListener('click', async () => { await api('/api/logout', { method: 'POST', body: '{}' }); location.reload(); });

bootstrap();
