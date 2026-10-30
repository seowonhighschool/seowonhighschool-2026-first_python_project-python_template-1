// static/js/auth.js
// 로그인 · 회원가입 화면. 앱 화면 전환은 main.js가 넘겨준 콜백으로 한다.
import { showToast, showLoading } from './utils.js';
import { signup, login, logout } from './api.js';

let callbacks = { onLogin: () => {}, onLogout: () => {} };

// =========================================
// 화면 전환
// =========================================
function setAppVisible(visible) {
  document.querySelector('#auth-screen').hidden = visible;
  document.querySelector('#app-main').hidden    = !visible;
  document.querySelector('#app-tab-nav').hidden = !visible;
  document.querySelector('#header-user').hidden = !visible;
}

function showAuthScreen() {
  setAppVisible(false);
  // 열려 있던 거래 상세가 로그인 화면 위에 남지 않게 닫는다
  const dialog = document.querySelector('#transaction-dialog');
  if (dialog.open) dialog.close();
}

function showApp(user) {
  document.querySelector('#header-username').textContent = user.username;
  setAppVisible(true);
}

function setMode(mode) {
  document.querySelectorAll('[data-auth-mode]').forEach(btn => {
    const isActive = btn.dataset.authMode === mode;
    btn.classList.toggle('auth__switch-btn--active', isActive);
    btn.setAttribute('aria-selected', String(isActive));
  });

  document.querySelector('#login-form').hidden  = mode !== 'login';
  document.querySelector('#signup-form').hidden = mode !== 'signup';
  document.querySelector(`#${mode}-username`).focus();
}

// =========================================
// 제출
// =========================================
async function submitForm(form, action) {
  const data = Object.fromEntries(new FormData(form));

  // 빈 칸은 서버까지 보내지 않고 바로 알려준다
  if (!data.username?.trim() || !data.password) {
    showToast('아이디와 비밀번호를 입력해주세요', 'error');
    return;
  }

  showLoading(true);
  try {
    const res = await action(data);
    if (!res.success) throw new Error(res.error);

    form.reset();
    callbacks.onLogin(res.data);
  } catch (err) {
    showToast(err.message || '잠시 후 다시 시도해주세요', 'error');
  } finally {
    showLoading(false);
  }
}

async function handleLogout() {
  showLoading(true);
  try {
    // 서버 로그아웃이 실패해도 이 화면에서는 로그인 화면으로 보낸다 (남의 기기에서 앱 화면이 남지 않게)
    await logout();
  } finally {
    showLoading(false);
    callbacks.onLogout();
    showAuthScreen();
    setMode('login');
    showToast('로그아웃했어요');
  }
}

// =========================================
// 초기화
// =========================================
// 가입 화면의 연령대·소득 선택지는 AI 분석 드롭다운에서 복사한다 (그룹 목록을 두 군데서 관리하지 않게)
function copyOptions(fromSelector, toSelector) {
  const from = document.querySelector(fromSelector);
  const to   = document.querySelector(toSelector);
  to.replaceChildren(...[...from.options].map(o => new Option(o.text, o.value, false, o.defaultSelected)));
}

function initAuth({ onLogin, onLogout }) {
  callbacks = { onLogin, onLogout };

  copyOptions('#analysis-age-group', '#signup-age-group');
  copyOptions('#analysis-income-group', '#signup-income-group');

  document.querySelectorAll('[data-auth-mode]').forEach(btn => {
    btn.addEventListener('click', () => setMode(btn.dataset.authMode));
  });

  const loginForm  = document.querySelector('#login-form');
  const signupForm = document.querySelector('#signup-form');
  loginForm.addEventListener('submit', e => {
    e.preventDefault();
    submitForm(loginForm, login);
  });
  signupForm.addEventListener('submit', e => {
    e.preventDefault();
    submitForm(signupForm, signup);
  });

  document.querySelector('#logout-btn').addEventListener('click', handleLogout);
}

export { initAuth, showAuthScreen, showApp };
