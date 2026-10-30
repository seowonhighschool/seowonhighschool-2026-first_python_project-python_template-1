import {
  CATEGORY_MAP,
  showToast,
  showLoading,
  formatCurrency,
  formatDate,
  formatShortDate,
  formatMonth,
  getCategoryLabel,
  getCurrentMonth,
  getRecentMonths,
  createEmptyState,
  debounce,
} from './utils.js';

import {
  getMe,
  parseSMS,
  saveTransaction,
  deleteTransaction,
  getTransactions,
  getDashboardStats,
  getAIAnalysis,
} from './api.js';

import { initAuth, showAuthScreen, showApp } from './auth.js';

import {
  renderCategoryChart,
  renderDailyChart,
  renderMonthlyChart,
  renderComparisonChart,
} from './dashboard.js';

// 대시보드 월별 추이에 보여줄 개월 수 (선택한 달 포함)
const MONTHLY_TREND_COUNT = 6;

// =========================================
// 탭 전환
// =========================================
function initTabs() {
  document.querySelectorAll('.tab-nav__item').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // 빈 상태 안내의 "문자 입력하러 가기" 버튼은 렌더링 때마다 새로 생기므로 document에 위임한다
  document.addEventListener('click', e => {
    const goBtn = e.target.closest('[data-go-tab]');
    if (goBtn) switchTab(goBtn.dataset.goTab);
  });
}

function switchTab(target) {
  document.querySelectorAll('.tab-nav__item').forEach(b => {
    const isActive = b.dataset.tab === target;
    b.classList.toggle('tab-nav__item--active', isActive);
    b.setAttribute('aria-selected', String(isActive));
  });

  document.querySelectorAll('.tab-content').forEach(c => {
    c.classList.toggle('tab-content--active', c.dataset.tabContent === target);
  });

  if (target === 'dashboard') loadDashboard();
  if (target === 'history')   loadHistory();
  if (target === 'analysis')  loadAnalysis();
}

// =========================================
// Tab 1: 문자 입력
// =========================================
let parsedData = null;

function initInputTab() {
  document.querySelector('#parse-btn').addEventListener('click', handleParse);
  document.querySelector('#reparse-btn').addEventListener('click', resetInput);
  document.querySelector('#save-btn').addEventListener('click', handleSave);

  // Gemini가 카테고리를 잘못 고를 수 있어 저장 전에 고칠 수 있게 한다.
  // 바꾼 값은 parsedData에 반영되고, 저장 API가 7개 key인지 다시 검증한다.
  const categorySelect = document.querySelector('#result-category');
  Object.keys(CATEGORY_MAP).forEach(key => {
    categorySelect.append(new Option(getCategoryLabel(key), key));
  });
  categorySelect.addEventListener('change', () => {
    if (parsedData) parsedData.category = categorySelect.value;
  });
}

async function handleParse() {
  const smsText = document.querySelector('#sms-input').value.trim();

  if (!smsText) {
    showToast('결제 문자를 입력해주세요', 'error');
    return;
  }

  showLoading(true);
  try {
    const res = await parseSMS(smsText);
    if (!res.success) throw new Error(res.error);
    parsedData = res.data;
    renderParseResult(parsedData);
  } catch (err) {
    showToast(err.message || '분석에 실패했습니다. 다시 시도해주세요', 'error');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

function renderParseResult(data) {
  document.querySelector('#result-store').textContent    = data.store;
  document.querySelector('#result-amount').textContent   = formatCurrency(data.amount);
  document.querySelector('#result-category').value       = data.category;
  document.querySelector('#result-date').textContent     = `${formatDate(data.date)} ${data.time}`;
  document.querySelector('#result-card').textContent     = data.card || '—';
  document.querySelector('#parse-result').hidden         = false;
}

function resetInput() {
  parsedData = null;
  document.querySelector('#sms-input').value    = '';
  document.querySelector('#parse-result').hidden = true;
}

async function handleSave() {
  if (!parsedData) return;

  showLoading(true);
  try {
    const res = await saveTransaction(parsedData);
    if (!res.success) throw new Error(res.error);
    showToast('저장됐어요! ✅', 'success');
    resetInput();
  } catch (err) {
    showToast(err.message || '저장에 실패했습니다', 'error');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

// =========================================
// Tab 2: 대시보드
// =========================================
async function loadDashboard() {
  const month = document.querySelector('#dashboard-month').value || getCurrentMonth();

  showLoading(true);
  try {
    // 월별 추이용으로 최근 6개월을 한꺼번에 받는다. 마지막이 선택한 달이라 아래 차트도 그 응답을 쓴다.
    // API는 월 단위 그대로 두고(스키마 변경 없음) 프론트에서 여러 번 부른다.
    const months    = getRecentMonths(month, MONTHLY_TREND_COUNT);
    const responses = await Promise.all(months.map(m => getDashboardStats(m)));
    const failed    = responses.find(r => !r.success);
    if (failed) throw new Error(failed.error);

    const { total_amount, by_category, by_date } = responses.at(-1).data;

    document.querySelector('#total-amount').textContent = formatCurrency(total_amount);

    // 지출이 없는 달은 차트 대신 안내를 보여준다.
    // 전부 0인 도넛은 아무것도 그리지 않아서 빈 카드만 남고 고장처럼 보인다.
    const isEmpty  = by_date.length === 0;
    const emptyBox = document.querySelector('#dashboard-empty');
    emptyBox.hidden = !isEmpty;
    document.querySelector('#dashboard-charts').hidden = isEmpty;

    if (isEmpty) {
      emptyBox.replaceChildren(createEmptyState({
        title:  `${formatMonth(month)}에는 아직 지출 내역이 없어요`,
        desc:   '결제 문자를 입력하면 카테고리별·일별 차트가 여기에 그려져요',
        action: { label: '문자 입력하러 가기', tab: 'input' },
      }));
    } else {
      // 숨김을 먼저 풀고 그린다. 숨겨진 상태에서 만들면 Chart.js가 크기를 0으로 잡는다.
      renderCategoryChart(by_category);
      renderDailyChart(by_date, month);
    }

    const monthlyTotals = months.map((m, i) => ({ month: m, total: responses[i].data.total_amount }));
    const hasTrend = monthlyTotals.some(m => m.total > 0);
    document.querySelector('#monthly-card').hidden = !hasTrend;
    if (hasTrend) renderMonthlyChart(monthlyTotals);
  } catch (err) {
    showToast(err.message || '데이터를 불러오지 못했습니다', 'error');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

// =========================================
// Tab 3: 내역 조회
// =========================================
// 마지막으로 그린 거래들 (id → 거래). 행을 눌렀을 때 상세 다이얼로그에 쓴다.
let historyRows = new Map();
let selectedTransactionId = null;

async function loadHistory() {
  const month    = document.querySelector('#history-month').value    || getCurrentMonth();
  const category = document.querySelector('#history-category').value || '';
  const search   = document.querySelector('#history-search').value   || '';

  showLoading(true);
  try {
    const res = await getTransactions({ month, category, search });
    if (!res.success) throw new Error(res.error);
    renderTransactionTable(res.data, { month, category, search });
    renderHistorySummary(res.total, month);
  } catch (err) {
    showToast(err.message || '내역을 불러오지 못했습니다', 'error');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

function renderTransactionTable(transactions, filters = {}) {
  const tbody = document.querySelector('#transaction-tbody');
  tbody.textContent = '';
  historyRows = new Map((transactions || []).map(t => [t.id, t]));

  if (!transactions || transactions.length === 0) {
    const row  = document.createElement('tr');
    const cell = document.createElement('td');
    row.className = 'table__empty-row';
    cell.colSpan = 4;
    cell.append(createHistoryEmptyState(filters));
    row.append(cell);
    tbody.append(row);
    return;
  }

  // 상점명은 사용자가 붙여넣은 문자에서 나온 값이라 innerHTML로 넣으면 안 된다.
  // textContent로 채우면 어떤 문자열이 와도 스크립트로 실행되지 않는다.
  const fragment = document.createDocumentFragment();

  const textCell = value => {
    const cell = document.createElement('td');
    cell.textContent = value;
    return cell;
  };

  transactions.forEach(t => {
    const row = document.createElement('tr');
    row.className = 'table__row--clickable';
    row.dataset.transactionId = t.id;

    // 행 어디를 눌러도 상세가 열리지만, 키보드·스크린리더 사용자는 상점명 버튼으로 연다
    const storeCell = document.createElement('td');
    const storeBtn  = document.createElement('button');
    storeBtn.type = 'button';
    storeBtn.className = 'table__store-btn';
    storeBtn.textContent = t.store;
    storeBtn.setAttribute('aria-haspopup', 'dialog');
    storeCell.append(storeBtn);

    row.append(
      textCell(formatShortDate(t.date)),
      storeCell,
      textCell(getCategoryLabel(t.category)),
      textCell(formatCurrency(t.amount)),
    );
    fragment.append(row);
  });

  tbody.append(fragment);
}

// 상세에서 시간·카드사까지 보여준다. 375px 표에는 열을 더 넣을 자리가 없다.
function openTransactionDialog(id) {
  const t = historyRows.get(id);
  if (!t) return;

  selectedTransactionId = id;
  document.querySelector('#transaction-dialog-title').textContent    = t.store;
  document.querySelector('#transaction-dialog-amount').textContent   = formatCurrency(t.amount);
  document.querySelector('#transaction-dialog-datetime').textContent = `${formatDate(t.date)} ${t.time}`;
  document.querySelector('#transaction-dialog-category').textContent = getCategoryLabel(t.category);
  document.querySelector('#transaction-dialog-card').textContent     = t.card || '—';
  document.querySelector('#transaction-dialog').showModal();
}

async function handleDeleteTransaction() {
  const id = selectedTransactionId;
  if (id === null) return;

  // 다이얼로그는 화면 최상단(top layer)이라 열린 채로는 로딩·토스트가 그 뒤에 가려진다. 먼저 닫는다.
  document.querySelector('#transaction-dialog').close();

  showLoading(true);
  try {
    const res = await deleteTransaction(id);
    if (!res.success) throw new Error(res.error);
    showToast('삭제했어요', 'success');
    await loadHistory();
  } catch (err) {
    showToast(err.message || '거래를 삭제하지 못했어요', 'error');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

function initTransactionDialog() {
  const dialog = document.querySelector('#transaction-dialog');

  document.querySelector('#transaction-tbody').addEventListener('click', e => {
    const row = e.target.closest('tr[data-transaction-id]');
    if (row) openTransactionDialog(Number(row.dataset.transactionId));
  });

  document.querySelector('#dialog-close-btn').addEventListener('click', () => dialog.close());
  document.querySelector('#dialog-delete-btn').addEventListener('click', handleDeleteTransaction);

  // 바깥(배경)을 누르면 닫는다. 내용은 .dialog__body 안에 있어서 배경을 누를 때만 target이 dialog다.
  dialog.addEventListener('click', e => {
    if (e.target === dialog) dialog.close();
  });
  dialog.addEventListener('close', () => {
    selectedTransactionId = null;
  });
}

function renderHistorySummary(total, month) {
  const summary = document.querySelector('#history-summary');
  summary.hidden = !total;
  summary.textContent = `${formatMonth(month)} · ${total}건`;
}

// 필터 때문에 비었는지, 그 달에 정말 내역이 없는지에 따라 사용자가 할 일이 다르다
function createHistoryEmptyState({ month, category, search }) {
  if (category || search) {
    return createEmptyState({
      title: '조건에 맞는 내역이 없어요',
      desc:  '카테고리나 검색어를 바꿔보세요',
    });
  }

  return createEmptyState({
    title:  `${formatMonth(month)}에는 아직 내역이 없어요`,
    desc:   '결제 문자를 입력하면 여기에 쌓여요',
    action: { label: '문자 입력하러 가기', tab: 'input' },
  });
}

// =========================================
// Tab 4: AI 분석
// =========================================
async function loadAnalysis() {
  const ageGroup    = document.querySelector('#analysis-age-group').value;
  const incomeGroup = document.querySelector('#analysis-income-group').value;
  const month       = document.querySelector('#dashboard-month').value || getCurrentMonth();

  showLoading(true);
  try {
    const res = await getAIAnalysis(ageGroup, incomeGroup, month);
    if (!res.success) throw new Error(res.error);

    const { user_total, peer_average, peer_group, has_peer_data, by_category, advice } = res.data;

    document.querySelector('#user-total').textContent = formatCurrency(user_total);

    // 어느 그룹과 비교했는지 화면에 표시한다 (드롭다운이 실제로 반영되는지 눈으로 확인 가능)
    document.querySelector('#peer-label').textContent = `또래 평균 (${peer_group})`;

    // 또래 데이터가 없으면 0원 대신 '데이터 없음'으로 구분해서 보여준다
    document.querySelector('#peer-total').textContent =
      has_peer_data ? formatCurrency(peer_average) : '데이터 없음';

    // 지출이 없는 달은 비교 차트·조언 대신 안내를 보여준다 (백엔드도 이때는 Gemini를 부르지 않는다).
    // 위의 내 지출 / 또래 평균 카드는 그대로 둬서 어느 그룹과 비교 중인지는 계속 보이게 한다.
    const isEmpty  = user_total === 0;
    const emptyBox = document.querySelector('#analysis-empty');
    emptyBox.hidden = !isEmpty;
    document.querySelector('#analysis-result').hidden = isEmpty;

    if (isEmpty) {
      emptyBox.replaceChildren(createEmptyState({
        title:  `${formatMonth(month)}에는 아직 지출 내역이 없어요`,
        desc:   '결제 문자를 입력하면 또래 평균과 비교해 맞춤 조언을 드려요',
        action: { label: '문자 입력하러 가기', tab: 'input' },
      }));
    } else {
      document.querySelector('#advice-text').textContent = advice;

      // 또래 데이터가 없으면 또래 막대가 전부 0으로 그려져 "또래는 한 푼도 안 쓴다"로 읽힌다.
      // 이때는 차트 대신 안내를 보여준다 (내 지출 금액과 조언은 그대로 둔다).
      const peerEmpty = document.querySelector('#comparison-empty');
      peerEmpty.hidden = has_peer_data;
      document.querySelector('#comparison-card').hidden = !has_peer_data;

      if (has_peer_data) {
        // 숨김을 먼저 풀고 그린다. 숨겨진 상태에서 만들면 Chart.js가 크기를 0으로 잡는다.
        renderComparisonChart(by_category);
      } else {
        peerEmpty.replaceChildren(createEmptyState({
          title: `'${peer_group}' 그룹의 또래 데이터가 없어요`,
          desc:  '다른 연령대나 소득 구간을 골라보세요',
        }));
      }
    }
  } catch (err) {
    showToast(err.message || '분석 데이터를 불러오지 못했습니다', 'error');
    console.error(err);
  } finally {
    showLoading(false);
  }
}

// =========================================
// 로그인 상태 전환
// =========================================
function enterApp(user) {
  // AI 분석은 가입 때 고른 내 그룹과 비교하는 것으로 시작한다 (드롭다운으로 바꿀 수 있다)
  document.querySelector('#analysis-age-group').value    = user.age_group;
  document.querySelector('#analysis-income-group').value = user.income_group;

  showApp(user);
  switchTab('input');
}

// 다른 사람이 같은 기기로 로그인했을 때 앞 사람의 미리보기·검색어가 남아 있지 않게 비운다
function resetAppState() {
  resetInput();
  historyRows = new Map();
  selectedTransactionId = null;
  document.querySelector('#history-search').value   = '';
  document.querySelector('#history-category').value = '';
}

// =========================================
// 초기화
// =========================================
async function init() {
  initAuth({ onLogin: enterApp, onLogout: resetAppState });

  // 세션이 만료된 채로 API를 부르면 api.js가 이 이벤트를 보낸다 (원인 토스트는 각 화면이 이미 띄운다)
  window.addEventListener('auth:required', () => {
    resetAppState();
    showAuthScreen();
  });

  // 탭 전환 초기화
  initTabs();

  // 문자 입력 탭 초기화
  initInputTab();

  // 대시보드 월 선택
  const dashboardMonth = document.querySelector('#dashboard-month');
  dashboardMonth.value = getCurrentMonth();
  dashboardMonth.addEventListener('change', loadDashboard);

  // 내역 조회 필터
  const historyMonth = document.querySelector('#history-month');
  historyMonth.value = getCurrentMonth();

  document.querySelector('#history-month').addEventListener('change', loadHistory);
  document.querySelector('#history-category').addEventListener('change', loadHistory);
  // 타이핑 중에는 마지막 입력 후 300ms 뒤에 한 번만 요청한다
  document.querySelector('#history-search').addEventListener('input', debounce(loadHistory, 300));

  // 내역 행을 누르면 상세·삭제 다이얼로그
  initTransactionDialog();

  // AI 분석 새로고침 버튼
  document.querySelector('#refresh-analysis-btn').addEventListener('click', loadAnalysis);
  document.querySelector('#analysis-age-group').addEventListener('change', loadAnalysis);
  document.querySelector('#analysis-income-group').addEventListener('change', loadAnalysis);

  // 새로고침해도 세션 쿠키가 남아 있으면 바로 앱으로 들어간다
  const me = await getMe();
  if (me.success) {
    enterApp(me.data);
  } else {
    showAuthScreen();
  }
}

document.addEventListener('DOMContentLoaded', init);
