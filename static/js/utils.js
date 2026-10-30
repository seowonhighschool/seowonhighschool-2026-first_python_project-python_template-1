// =========================================
// 카테고리 정의
// =========================================
const CATEGORY_MAP = {
  food:      { label: '식비',    icon: '🍽️', color: '#FF6B6B' },
  cafe:      { label: '카페',    icon: '☕',  color: '#C49A6C' },
  transport: { label: '교통',    icon: '🚌',  color: '#4ECDC4' },
  shopping:  { label: '쇼핑',   icon: '🛍️', color: '#9B59B6' },
  medical:   { label: '의료',    icon: '💊',  color: '#2ECC71' },
  leisure:   { label: '문화/여가', icon: '🎬', color: '#F39C12' },
  etc:       { label: '기타',    icon: '📌',  color: '#95A5A6' },
};

const CATEGORY_COLORS = Object.values(CATEGORY_MAP).map(c => c.color);
const CATEGORY_LABELS = Object.values(CATEGORY_MAP).map(c => `${c.icon} ${c.label}`);

// =========================================
// 포매팅 유틸
// =========================================
function formatCurrency(amount) {
  return `${Number(amount).toLocaleString('ko-KR')}원`;
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [year, month, day] = dateStr.split('-');
  return `${year}.${month}.${day}`;
}

// '2026-10-14' → '10.14'
// 내역 표처럼 이미 월로 걸러진 목록에서 쓴다. 연·월이 매 행 반복되면 좁은 화면에서 상점명 칸이 밀린다.
function formatShortDate(dateStr) {
  if (!dateStr) return '—';
  const [, month, day] = dateStr.split('-');
  return `${month}.${day}`;
}

// '2026-10' → '2026년 10월'
function formatMonth(monthStr) {
  if (!monthStr) return '—';
  const [year, month] = monthStr.split('-');
  return `${year}년 ${Number(month)}월`;
}

function getCategoryLabel(key) {
  const cat = CATEGORY_MAP[key];
  if (!cat) return key;
  return `${cat.icon} ${cat.label}`;
}

function getCurrentMonth() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
}

// ('2026-03', 3) → ['2026-01', '2026-02', '2026-03']  (기준 달을 마지막으로, 오래된 달부터)
function getRecentMonths(monthStr, count) {
  const [year, month] = monthStr.split('-').map(Number);

  return Array.from({ length: count }, (_, i) => {
    // Date가 0월·음수 월을 알아서 이전 해로 넘겨준다
    const d = new Date(year, month - 1 - (count - 1 - i), 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });
}

// =========================================
// Toast 알림
// =========================================
let toastTimer = null;

function showToast(message, type = 'default') {
  const toast = document.querySelector('#toast');
  const toastMessage = document.querySelector('#toast-message');

  toastMessage.textContent = message;
  toast.className = `toast toast--${type}`;
  toast.hidden = false;

  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 2500);
}

// =========================================
// 로딩 오버레이
// =========================================
// 요청 2개가 겹칠 때 먼저 끝난 쪽이 오버레이를 꺼버리지 않도록 호출 수를 센다.
let loadingCount = 0;

function showLoading(visible) {
  loadingCount = visible ? loadingCount + 1 : Math.max(0, loadingCount - 1);
  document.querySelector('#loading-overlay').hidden = loadingCount === 0;
}

// =========================================
// 빈 상태 안내
// =========================================
// 데이터가 없을 때 빈 표·빈 캔버스 대신 보여준다. 아무것도 없으면 고장 난 것처럼 보인다.
// action을 주면 해당 탭으로 가는 버튼을 붙인다 (클릭은 main.js가 data-go-tab으로 처리한다).
function createEmptyState({ title, desc, action } = {}) {
  const wrapper = document.createElement('div');
  wrapper.className = 'empty-state';

  const titleEl = document.createElement('p');
  titleEl.className = 'empty-state__title';
  titleEl.textContent = title;
  wrapper.append(titleEl);

  if (desc) {
    const descEl = document.createElement('p');
    descEl.className = 'empty-state__desc';
    descEl.textContent = desc;
    wrapper.append(descEl);
  }

  if (action) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn--primary empty-state__action';
    btn.dataset.goTab = action.tab;
    btn.textContent = action.label;
    wrapper.append(btn);
  }

  return wrapper;
}

// =========================================
// Debounce
// =========================================
// 검색창처럼 입력할 때마다 호출되는 이벤트에 쓴다.
// 없으면 '스타벅스' 입력에 요청이 4번 나가고 오버레이가 4번 깜빡인다.
function debounce(fn, delay = 300) {
  let timer = null;

  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// =========================================
// Exports
// =========================================
export {
  CATEGORY_MAP,
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  formatCurrency,
  formatDate,
  formatShortDate,
  formatMonth,
  getCategoryLabel,
  getCurrentMonth,
  getRecentMonths,
  showToast,
  showLoading,
  createEmptyState,
  debounce,
};
