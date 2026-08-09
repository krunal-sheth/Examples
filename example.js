const appState = {
  date: new Date(2026, 7, 9),
  today: new Date(2026, 7, 9),
};

const dateLabel = document.querySelector('#dateLabel');
const dayLabel = document.querySelector('#dayLabel');
const nextDay = document.querySelector('#nextDay');
const toast = document.querySelector('#toast');

function sameDay(a, b) {
  return a.toDateString() === b.toDateString();
}

function updateDate() {
  const isToday = sameDay(appState.date, appState.today);
  dayLabel.textContent = isToday ? 'TODAY' : appState.date < appState.today ? 'PAST READING' : 'UPCOMING';
  dateLabel.textContent = appState.date.toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
  nextDay.disabled = isToday;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('visible');
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove('visible'), 2600);
}

document.querySelector('#previousDay').addEventListener('click', () => {
  appState.date.setDate(appState.date.getDate() - 1);
  updateDate();
});

nextDay.addEventListener('click', () => {
  if (appState.date < appState.today) appState.date.setDate(appState.date.getDate() + 1);
  updateDate();
});

const views = document.querySelectorAll('.view');
document.querySelectorAll('.nav-item').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    views.forEach((view) => view.classList.remove('active'));
    document.querySelector(`#${button.dataset.view}View`).classList.add('active');
    document.querySelector('.sidebar').classList.remove('open');
  });
});

document.querySelector('#menuButton').addEventListener('click', () => {
  document.querySelector('.sidebar').classList.toggle('open');
});

document.querySelectorAll('.feedback-options button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.feedback-options button').forEach((option) => option.classList.remove('selected'));
    button.classList.add('selected');
    localStorage.setItem('jyotish-yesterday-rating', button.dataset.rating);
    showToast('Thank you — your reflection has been saved.');
  });
});

const savedRating = localStorage.getItem('jyotish-yesterday-rating');
if (savedRating) document.querySelector(`[data-rating="${savedRating}"]`)?.classList.add('selected');

const dialog = document.querySelector('#journalDialog');
const journalText = document.querySelector('#journalText');
document.querySelector('#openJournal').addEventListener('click', () => {
  journalText.value = localStorage.getItem('jyotish-journal') || '';
  dialog.showModal();
});
document.querySelector('#closeJournal').addEventListener('click', () => dialog.close());
document.querySelector('#saveJournal').addEventListener('click', () => {
  localStorage.setItem('jyotish-journal', journalText.value);
  dialog.close();
  showToast('Your private reflection is saved.');
});

const readings = [
  ['8 August', 'Patience makes room for the answer', 'Somewhat'],
  ['7 August', 'Let curiosity guide the conversation', 'Very much'],
  ['6 August', 'Protect your attention with care', 'Not rated'],
  ['5 August', 'A practical choice brings relief', 'Very much'],
];
document.querySelector('#calendarList').innerHTML = readings.map(([date, title, rating]) => `
  <button class="history-row"><span><small>${date}</small><strong>${title}</strong></span><span>${rating} →</span></button>
`).join('');

document.querySelector('#profileButton').addEventListener('click', () => showToast('Profile settings are coming next.'));
updateDate();
